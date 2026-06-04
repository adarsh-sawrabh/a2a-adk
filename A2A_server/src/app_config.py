"""
Application bootstrap configuration.

Central place for all one-time setup that must happen before the FastAPI app starts
serving requests. Each function here is called in the `main.py` file during module initialization.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import json
import logging

logger = logging.getLogger(__name__)

SRC_DIR = Path(__file__).resolve().parent

def update_dotenv_path() -> None:
    """
    Load environment variables from a .env file located in the root folder of the project.
    This must be called before any other configuration or setup.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

def update_sys_path() -> None:
    """
    Add the project root to sys.path so the `src` package imports resolve correctly.
    This is called from app_run.py before importing any application modules.
    """
    if str(SRC_DIR) not in sys.path:
        sys.path.append(str(SRC_DIR))

def load_agent_card(agent_dir: str) -> dict:
    """
    Load the agent card JSON file (agent.json) & patch the URL in memory.
    Reads the agent card & replaces the ``url`` field with the environment-specific value from the .env file.
    This card is never written back to disk, the patched dict is served directly via a FastAPI endpoint, keeping the file read-only.  
    """
    a2a_url = os.environ.get("A2A_AGENT_URL","")
    if not a2a_url:
        raise ValueError("A2A_AGENT_URL is not set.")
    agent_card_path = Path(agent_dir) / "a2a_agent" / "agent.json"
    if not agent_card_path.is_file():
        raise FileNotFoundError(f"Agent card not found at {agent_card_path}")
    agent_card = json.loads(agent_card_path.read_text(encoding="utf-8"))
    agent_card["url"] = a2a_url
    logger.info(f"Loaded agent card from {agent_card_path} with patched URL: {a2a_url}")
    return agent_card