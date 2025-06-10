import os
import time
from fastapi import FastAPI
from app.routers import broken, fixed

# Create FastAPI app
app = FastAPI(
    title="FastAPI Thread Exhaustion Reproduction",
    description="Demonstrates thread exhaustion problem with streaming responses and the solution",
    version="1.0.0"
)

# Get app version from environment variable
APP_VERSION = os.getenv("APP_VERSION", "fixed").lower()

# Include the appropriate router based on environment
if APP_VERSION == "broken":
    print("🔥 Running in BROKEN mode. Expect thread exhaustion! 🔥")
    print("🔥 Thread pool limited to 4 workers - 5th concurrent request will hang")
    app.include_router(broken.router)
    current_mode = "broken"
else:
    print("✅ Running in FIXED mode. Using async client. ✅")
    print("✅ No thread pool limits - scales to thousands of concurrent requests")
    app.include_router(fixed.router)
    current_mode = "fixed"

# Define health check based on mode - crucial for demonstrating the problem
if APP_VERSION == "broken":
    # Import the same limited thread pool used by the broken router
    import asyncio
    from app.routers.broken import LIMITED_THREAD_POOL
    
    @app.get("/health")
    async def health_check_broken():
        """
        BROKEN: This explicitly uses the same limited thread pool as streaming requests
        When all 4 threads are exhausted by streaming requests, this cannot execute!
        """
        loop = asyncio.get_running_loop()
        
        def blocking_health_check():
            # Simulate some blocking operation to ensure it uses a thread
            time.sleep(0.1)  
            return {
                "status": "ok",
                "timestamp": time.time(),
                "mode": "broken",
                "message": "Health check - but thread pool may be exhausted!"
            }
        
        # Force this to use the same limited thread pool as streaming requests
        return await loop.run_in_executor(LIMITED_THREAD_POOL, blocking_health_check)
else:
    @app.get("/health")
    async def health_check_fixed():
        """
        FIXED: This is async and doesn't need threads - always responsive
        """
        return {
            "status": "ok",
            "timestamp": time.time(),
            "mode": "fixed",
            "message": "Health check successful - async and always responsive!"
        }

@app.get("/")
async def root():
    """Root endpoint with usage instructions"""
    instructions = {
        "mode": current_mode,
        "endpoints": {
            "/api/v1/chat/stream": "Stream endpoint (demonstrates the problem/solution)",
            "/api/v1/info": "Information about current implementation",
            "/health": "Health check endpoint (canary for thread exhaustion)"
        },
        "testing": {
            "broken_mode": "Set APP_VERSION=broken and test with 5+ concurrent requests",
            "fixed_mode": "Default mode, handles unlimited concurrent requests",
            "load_test": "Use locust to demonstrate the difference"
        }
    }
    
    if current_mode == "broken":
        instructions["warning"] = "🔥 BROKEN MODE: Max 4 concurrent streams, /health will fail under load"
    else:
        instructions["info"] = "✅ FIXED MODE: Unlimited concurrent streams, /health always responsive"
    
    return instructions

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)