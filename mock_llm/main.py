import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI(title="Mock LiteLLM Service")

async def slow_text_stream(chunks: int = 10, delay: float = 0.5):
    """
    An async generator that yields data chunks slowly.
    This simulates a slow LLM response.
    """
    for i in range(chunks):
        chunk_data = f"data: This is chunk {i+1} of {chunks} from the mock LLM service. " \
                    f"This simulates realistic streaming response patterns from LiteLLM.\n\n"
        yield chunk_data.encode("utf-8")
        await asyncio.sleep(delay)

@app.get("/slow_stream")
async def get_slow_stream(chunks: int = 20, delay: float = 1.0):
    """
    Endpoint that returns a slow streaming response.
    It's async, so it can handle many concurrent requests efficiently.
    The slowness is deliberate to simulate the LLM.
    
    Query parameters:
    - chunks: Number of chunks to send (default: 20)
    - delay: Delay between chunks in seconds (default: 1.0)
    """
    return StreamingResponse(
        slow_text_stream(chunks, delay), 
        media_type="text/event-stream"
    )

@app.get("/health")
async def health_check():
    """Health check endpoint for the mock service"""
    return {"status": "ok", "service": "mock-litellm"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)