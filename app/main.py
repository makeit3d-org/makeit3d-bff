import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from fastapi import FastAPI

from .routers import generation, models

app = FastAPI()

app.include_router(generation.router, prefix="/generate", tags=["generate"])
app.include_router(models.router, prefix="", tags=["tasks"])

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"Hello": "World"} 