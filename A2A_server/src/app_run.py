"""
Bootstraps the A2AServerAgent: runs the FastAPI app under Uvicorn.

This is the main entry point for local runs.
"""

from app_config import update_sys_path

update_sys_path()

import uvicorn
import logging
import sys
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if __name__ == "__main__":
    try:
        logger.info("Starting the A2AServerAgent application")
        uvicorn.run(
            "main:app",
            host=os.environ.get("HOST", "0.0.0.0"),
            port=int(os.environ.get("PORT", 8001)),
            reload=False,
            log_level="debug",
            workers=1,
        )
    except Exception as e:
        logger.exception(f"Error starting the A2AServerAgent application: {e}")
        logger.error("Application cannot start. Exiting with error code 1.")
        sys.exit(1)