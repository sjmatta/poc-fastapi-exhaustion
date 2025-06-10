# FastAPI Thread Exhaustion with LiteLLM Streaming

Demonstrates the critical thread exhaustion issue in FastAPI applications using blocking patterns with LiteLLM streaming, and provides the solution.

**Key insight:** The problem occurs at **~30-40 concurrent streams** and is usually caused by using `def` instead of `async def` or `litellm.completion()` instead of `litellm.acompletion()`.

## 🔥 The Problem

FastAPI apps using blocking patterns for streaming from external services experience **thread pool exhaustion**:

- Health endpoints become slow/unresponsive at **~30+ concurrent streams**
- Thread pool (default 40 threads) gets saturated by long-running requests  
- Entire application becomes unavailable at **~40-50 concurrent streams**

## ✅ The Solution

Use **async HTTP clients** (`httpx`) with proper async/await patterns.

## 🚀 Quick Demo

```bash
# Install dependencies
make install

# Demonstrate the problem (slow health checks)
make demo-broken

# Demonstrate the solution (fast health checks)  
make demo-fixed

# Clean up
make stop
```

## 🎯 Key Evidence

| Metric | Broken Mode | Fixed Mode |
|--------|-------------|------------|
| **Health Response Time** | **0.12s (slow!)** | **0.01s (fast)** |
| **Thread Pool Usage** | **100% saturated** | **0% (async)** |
| **Concurrent Streams** | **~40 max (real apps)** | **Unlimited** |

## 🔍 Technical Details

### The Real Problem Patterns

**Pattern 1: Using `def` instead of `async def`**
```python
# ❌ WRONG - Forces FastAPI to use thread pool
@app.post("/chat/stream")
def chat_stream():  # def = blocking = uses thread
    response = litellm.completion(
        model="gpt-4",
        messages=messages,
        stream=True
    )
    return StreamingResponse(response)  # Holds thread for 30-60s
```

**Pattern 2: Not using async LiteLLM methods**
```python
# ❌ WRONG - Blocking call in async function
@app.post("/chat/stream") 
async def chat_stream():
    response = litellm.completion(  # This is blocking!
        model="gpt-4",
        messages=messages, 
        stream=True
    )
    return StreamingResponse(response)
```

**Pattern 3: Using requests with LiteLLM REST API**
```python
# ❌ WRONG - Direct REST API calls with requests
@app.post("/chat/stream")
async def chat_stream():
    response = requests.post(  # Blocking requests
        "https://api.litellm.com/chat/completions",
        json=payload,
        stream=True
    )
    return StreamingResponse(response.iter_content())
```

### The Correct Solutions

**Solution 1: Use `async def` with LiteLLM**
```python
# ✅ CORRECT - Async endpoint
@app.post("/chat/stream")
async def chat_stream(request: Request):
    response = await litellm.acompletion(  # ✅ Use acompletion
        model="gpt-4",
        messages=messages,
        stream=True
    )
    
    async def generate():
        async for chunk in response:  # ✅ async for
            if await request.is_disconnected():
                break
            
            # ✅ Correctly extract content from the chunk
            content = chunk.choices[0].delta.content
            if content:
                yield f"data: {content}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**Solution 2: Proper async streaming wrapper**
```python
# ✅ CORRECT - Handle streaming properly
import litellm

async def stream_litellm_response(request: Request, **kwargs):
    """Async wrapper for LiteLLM streaming"""
    try:
        response = await litellm.acompletion(stream=True, **kwargs)
        
        async for chunk in response:
            if await request.is_disconnected():
                logger.info("Client disconnected")
                break
            
            content = chunk.choices[0].delta.content
            if content:
                # ✅ Format as SSE
                import json
                yield f"data: {json.dumps({'content': content})}\n\n"
            
    except Exception as e:
        logger.error(f"LiteLLM error: {e}")
        # ✅ Format error as SSE
        import json
        error_payload = json.dumps({"error": str(e)})
        yield f"data: {error_payload}\n\n"

@app.post("/chat/stream")
async def chat_stream(request: Request):
    return StreamingResponse(
        stream_litellm_response(
            request,
            model="gpt-4", 
            messages=messages
        ),
        media_type="text/event-stream"
    )
```

## 🛠️ Project Structure

```
├── app/
│   ├── main.py              # FastAPI app with mode switching
│   └── routers/
│       ├── broken.py        # Blocking requests (problem)
│       └── fixed.py         # Async httpx (solution)
├── mock_llm/
│   └── main.py              # Mock slow streaming service
├── Makefile                 # Easy demo commands
└── requirements.txt         # Dependencies
```

This reproduction proves the FastAPI + LiteLLM streaming issue and shows the fix!

## 🏢 Migrating Your Existing FastAPI Application

### Step 1: Add Thread Exhaustion Detection

**Drop this into your existing app immediately for monitoring:**

```python
# Add to your main FastAPI app
import time
import asyncio
import psutil

@app.get("/debug/health-sync")
def health_sync():
    """Sync health check - will be slow if threads exhausted"""
    return {"status": "ok", "timestamp": time.time(), "type": "sync"}

@app.get("/debug/health-async") 
async def health_async():
    """Async health check - always fast"""
    return {"status": "ok", "timestamp": time.time(), "type": "async"}

@app.get("/health")
async def health_check():
    """Enhanced health check that detects thread exhaustion"""
    checks = {}
    overall_status = "healthy"
    
    # Test thread pool responsiveness
    try:
        loop = asyncio.get_running_loop()
        thread_start = time.time()
        await loop.run_in_executor(None, time.sleep, 0.01)
        checks["thread_pool_response_time"] = time.time() - thread_start
        
        if checks["thread_pool_response_time"] > 0.1:
            overall_status = "degraded"
            checks["thread_exhaustion_warning"] = True
            
    except Exception as e:
        overall_status = "unhealthy"
        checks["thread_pool_error"] = str(e)
    
    return {
        "status": overall_status,
        "timestamp": time.time(),
        "checks": checks
    }
```

### Step 2: Test Current Performance

```bash
# Monitor health during load
while true; do
  echo -n "Sync: "
  curl -w "%{time_total}s " -s http://localhost:8000/debug/health-sync > /dev/null
  echo -n "| Async: "  
  curl -w "%{time_total}s" -s http://localhost:8000/debug/health-async > /dev/null
  echo ""
  sleep 1
done

# Start concurrent streams to your existing endpoint
for i in {1..8}; do
  curl -m 60 -s http://localhost:8000/your/streaming/endpoint > /tmp/test_$i.log &
done
```

**If you see sync health checks become slow (>0.1s), you have thread exhaustion.**

### Step 3: Use Proper LiteLLM Async Methods

**Key changes needed:**

1. **Use `litellm.acompletion()` instead of `litellm.completion()`**
2. **Use `async def` for all streaming endpoints**  
3. **Use `async for` to iterate over response chunks**
4. **Add client disconnect detection**

**Create `utils/async_streaming.py`:**

```python
import litellm
import logging
from typing import AsyncGenerator, Dict, Any
from fastapi import Request

logger = logging.getLogger(__name__)

async def stream_litellm_completion(
    request: Request, 
    model: str,
    messages: list,
    **kwargs
) -> AsyncGenerator[str, None]:
    """Async wrapper for LiteLLM streaming that handles disconnects"""
    try:
        # Use acompletion for async streaming
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in response:
            # Critical: Check for client disconnect
            if await request.is_disconnected():
                logger.info("Client disconnected, terminating LiteLLM stream")
                break
            
            # ✅ Process LiteLLM chunk to get actual content
            content = chunk.choices[0].delta.content
            if content:
                yield f"data: {content}\n\n"
            
    except Exception as e:
        logger.error(f"LiteLLM streaming error: {e}")
        # ✅ Use json.dumps to safely create the JSON payload
        import json
        error_payload = json.dumps({"error": str(e)})
        yield f"data: {error_payload}\n\n"
```

### Step 4: Gradual Migration

**Replace your existing streaming endpoints:**

```python
# BEFORE (blocking patterns)
@app.post("/chat/stream")
def chat_stream():  # ❌ def = uses thread pool
    response = litellm.completion(  # ❌ blocking call
        model="gpt-4",
        messages=messages,
        stream=True
    )
    return StreamingResponse(response)

# AFTER (async patterns)
from utils.async_streaming import stream_litellm_completion

@app.post("/chat/stream") 
async def chat_stream(request: Request):  # ✅ async def
    return StreamingResponse(
        stream_litellm_completion(  # ✅ async wrapper
            request, 
            model="gpt-4",
            messages=messages
        )
    )
```

### Step 5: Safe Production Rollout

**Feature flag approach:**

```python
import os
import random
import logging
from fastapi.responses import JSONResponse

ASYNC_ROLLOUT_PERCENTAGE = int(os.getenv("ASYNC_ROLLOUT_PERCENTAGE", "0"))

@app.post("/chat/stream")
async def chat_stream(request: Request):
    use_async = random.randint(1, 100) <= ASYNC_ROLLOUT_PERCENTAGE
    
    if use_async:
        try:
            # Use async LiteLLM
            return StreamingResponse(
                stream_litellm_completion(request, model="gpt-4", messages=messages),
                headers={"X-Stream-Method": "async"}
            )
        except Exception as e:
            logging.error(f"Async LiteLLM failed, returning 503: {e}")
            # ❌ DO NOT FALL BACK TO BLOCKING CODE - this re-introduces thread exhaustion!
            # ✅ FAIL FAST: Return error and let monitoring handle the issue
            return JSONResponse(
                status_code=503,
                content={"detail": "Service temporarily unavailable. Please try again later."},
                headers={"X-Stream-Method": "async_failure"}
            )
    else:
        # Original blocking method - must use run_in_executor to avoid blocking event loop
        import functools
        import asyncio
        
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,  # Use default thread pool
            functools.partial(
                litellm.completion, 
                model="gpt-4", 
                messages=messages, 
                stream=True
            )
        )
        return StreamingResponse(response, headers={"X-Stream-Method": "blocking"})
```

**Deploy sequence:**
1. `ASYNC_ROLLOUT_PERCENTAGE=5` (test with 5% of traffic)
2. Monitor health checks for 24 hours
3. Increase to `20`, then `50`, then `100`
4. Remove feature flag after validation

### Step 6: Validation

**Load test script to verify the fix:**

```python
# test_migration.py
import asyncio
import httpx
import time

URL = "http://localhost:8000"
PAYLOAD = {"messages": [{"role": "user", "content": "test"}]}

async def consume_stream(client: httpx.AsyncClient):
    """Establishes and consumes a single stream."""
    try:
        async with client.stream("POST", f"{URL}/chat/stream", json=PAYLOAD, timeout=60) as response:
            response.raise_for_status()
            async for _ in response.aiter_bytes():
                pass  # Consume the data to keep the connection active
    except httpx.HTTPStatusError as e:
        print(f"Stream failed with status error: {e.response.status_code}")
    except Exception as e:
        print(f"An error occurred during streaming: {e}")

async def health_check(client: httpx.AsyncClient):
    """Performs a single sync health check."""
    start = time.time()
    await client.get(f"{URL}/debug/health-sync")
    return time.time() - start

async def load_test():
    async with httpx.AsyncClient() as client:
        # Start 40 concurrent streams to saturate the default thread pool
        print("Starting 40 concurrent streams...")
        stream_tasks = [
            asyncio.create_task(consume_stream(client)) for _ in range(40)
        ]

        # Monitor health for 15 seconds while streams are active
        health_times = []
        for i in range(15):
            if all(task.done() for task in stream_tasks):
                print("All streams finished early.")
                break
            
            health_times.append(await health_check(client))
            print(f"[{i+1}/15] Health check time: {health_times[-1]:.4f}s")
            await asyncio.sleep(1)
        
        # Clean up tasks
        await asyncio.gather(*stream_tasks, return_exceptions=True)

    if not health_times:
        print("❌ FAIL: No health checks were performed. Test may have ended too quickly.")
        return

    avg_health_time = sum(health_times) / len(health_times)
    print(f"\nAverage health check time under load: {avg_health_time:.3f}s")
    
    if avg_health_time < 0.1:
        print("✅ PASS: No significant thread exhaustion detected.")
    else:
        print("❌ FAIL: Thread exhaustion detected! Health checks are slow.")

asyncio.run(load_test())
```

### Critical Migration Checklist

- [ ] Add enhanced health check with thread pool monitoring
- [ ] **Change `def` endpoints to `async def`**
- [ ] **Replace `litellm.completion()` with `litellm.acompletion()`**
- [ ] **Use `async for` to iterate over LiteLLM response chunks**
- [ ] **Add `await request.is_disconnected()` checks**
- [ ] Create async streaming utility wrapper
- [ ] Test with feature flag at 5% traffic
- [ ] Monitor health check latency during rollout  
- [ ] Gradually increase rollout percentage
- [ ] Validate memory usage and connection handling
- [ ] Remove blocking patterns after 100% rollout

**Key insight: The problem is usually `def` vs `async def` and `completion()` vs `acompletion()`, not the HTTP client itself.**