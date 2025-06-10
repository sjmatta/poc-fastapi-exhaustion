import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Generator

import requests
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

# Create a deliberately small thread pool to demonstrate the problem
# In real scenarios, this would be the default FastAPI thread pool getting exhausted
MAX_WORKERS = 4
LIMITED_THREAD_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS)

router = APIRouter(prefix="/api/v1", tags=["broken"])

def blocking_stream_from_llm() -> Generator[bytes, None, None]:
    """
    This function simulates the problematic pattern:
    - Uses blocking requests library
    - Holds a thread for the entire duration of the stream
    - Each concurrent request consumes one thread from the limited pool
    """
    print("🔥 Starting blocking stream request (will hold thread for ~45 seconds)")
    
    try:
        # This is the core problem: blocking HTTP request that streams data
        with requests.get(
            "http://localhost:8001/slow_stream?chunks=30&delay=1.5", 
            stream=True,
            timeout=60
        ) as response:
            response.raise_for_status()
            
            # Iterate through the response chunks - this blocks the thread
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    # Simulate some processing time
                    time.sleep(0.01)
                    yield chunk
                    
    except Exception as e:
        print(f"🔥 Error in blocking stream: {e}")
        yield f"Error: {str(e)}".encode()
    
    print("🔥 Finished blocking stream request (thread now freed)")

@router.get("/chat/stream")
async def chat_stream_broken():
    """
    This endpoint demonstrates the thread exhaustion problem.
    
    The issue:
    1. Each request runs blocking_stream_from_llm() in a thread from LIMITED_THREAD_POOL
    2. The thread is held for the entire duration of the stream (~20 seconds)
    3. With only 4 threads available, the 5th concurrent request will hang
    4. The /health endpoint will also become unresponsive as threads are exhausted
    """
    loop = asyncio.get_running_loop()
    
    # This is where the magic happens - we explicitly use our limited thread pool
    # In a real FastAPI app, this would be the default thread pool getting exhausted
    stream_generator = await loop.run_in_executor(
        LIMITED_THREAD_POOL, 
        blocking_stream_from_llm
    )
    
    return StreamingResponse(
        stream_generator, 
        media_type="text/plain",
        headers={"X-Stream-Type": "broken-blocking"}
    )

@router.get("/info")
async def info():
    """Information about the broken implementation"""
    return {
        "implementation": "broken",
        "thread_pool_size": MAX_WORKERS,
        "problem": "Uses blocking requests library with limited thread pool",
        "symptoms": [
            "Thread exhaustion under concurrent load",
            "/health endpoint becomes unresponsive",
            "Requests hang when thread pool is full"
        ]
    }