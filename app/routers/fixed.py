from typing import AsyncGenerator

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1", tags=["fixed"])

async def async_stream_from_llm(request: Request) -> AsyncGenerator[bytes, None]:
    """
    This function demonstrates the correct async pattern:
    - Uses async httpx client instead of blocking requests
    - Uses async for to iterate over response chunks
    - Yields control to the event loop while waiting for data
    - Properly handles client disconnections
    """
    print("✅ Starting async stream request (non-blocking)")
    
    try:
        # ✅ Set reasonable timeout to prevent hung connections
        timeout_config = httpx.Timeout(300.0, connect=60.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            async with client.stream(
                "GET", 
                "http://localhost:8001/slow_stream?chunks=20&delay=1.0"
            ) as response:
                response.raise_for_status()
                
                # The key difference: async for yields control to event loop
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    # Check for client disconnect to prevent zombie streams
                    if await request.is_disconnected():
                        print("✅ Client disconnected, closing stream")
                        break
                    
                    yield chunk
                    
    except Exception as e:
        print(f"✅ Error in async stream: {e}")
        yield f"Error: {str(e)}".encode()
    
    print("✅ Finished async stream request (no threads consumed)")

@router.get("/chat/stream")
async def chat_stream_fixed(request: Request):
    """
    This endpoint demonstrates the proper solution to thread exhaustion.
    
    The solution:
    1. Uses async httpx client instead of blocking requests
    2. No threads are consumed for I/O operations
    3. Event loop handles many concurrent connections efficiently
    4. Proper client disconnect handling prevents zombie streams
    5. /health endpoint remains responsive under any load
    """
    return StreamingResponse(
        async_stream_from_llm(request),
        media_type="text/plain",
        headers={"X-Stream-Type": "fixed-async"}
    )

@router.get("/info")
async def info():
    """Information about the fixed implementation"""
    return {
        "implementation": "fixed",
        "thread_pool_usage": "none (fully async)",
        "solution": "Uses async httpx client with proper disconnect handling",
        "benefits": [
            "No thread exhaustion under concurrent load",
            "/health endpoint always responsive",
            "Proper resource cleanup on client disconnect",
            "Scales to thousands of concurrent streams"
        ]
    }