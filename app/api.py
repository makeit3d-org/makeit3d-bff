from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter, _rate_limit_exceeded_handler # Import from app.limiter

from app.routers import generation, models # Import the new routers using absolute path

app = FastAPI()
app.state.limiter = limiter # Attach the limiter to the app state
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # Add the exception handler

app.include_router(generation.router, prefix="/generate", tags=["generate"])
app.include_router(models.router, prefix="", tags=["tasks"]) # Tasks at root or /tasks

@app.get("/")
def read_root():
    return {"Hello": "World"} 