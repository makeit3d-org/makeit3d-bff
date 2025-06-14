import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from api import app # Import the FastAPI app instance from api

# Remove redundant router inclusion and root endpoint from here
# app.include_router(...)
# @app.get('/')
# def read_root():
#     logger.info("Root endpoint accessed")
#     return {"Hello": "World"} 