from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter, _rate_limit_exceeded_handler # Import from app.limiter

from app.routers import generation, task_status # Import only the correct routers

app = FastAPI()
app.state.limiter = limiter # Attach the limiter to the app state
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # Add the exception handler

app.include_router(generation.router, prefix="/generate", tags=["generate"])
app.include_router(task_status.router, prefix="", tags=["Task Status"]) # Task status at root level

@app.get("/")
def read_root():
    return {"Hello": "World"} 