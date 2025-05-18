from fastapi import FastAPI

from app.routers import generation, models # Import the new routers using absolute path

app = FastAPI()

app.include_router(generation.router, prefix="/generate", tags=["generate"])
app.include_router(models.router, prefix="", tags=["tasks"]) # Tasks at root or /tasks

@app.get("/")
def read_root():
    return {"Hello": "World"} 