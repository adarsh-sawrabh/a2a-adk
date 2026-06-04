"""
A2A_Server_Agent - FastAPI Application Entrypoint

This module bootstraps the A2A_Server_Agent, a Google ADK-based agentic application that
orchestrates the task using sub-agents.

Startup sequence:
    1. Load environment variables.
    2. Register a deferred MongoSessionService factory with ADK service registry so ADK can resolve
        "mongodb://" session URIs.
    3. Create a FastAPI app via Google ADK's helper, enabling Web UI, A2A protocol & MongoDB backed
        session persistence.
    4. Applt CORS middleware & expose a /healthcheck endpoint for liveness probe.
"""

import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.adk.cli.fast_api import get_fast_api_app
from app_config import update_dotenv_path, load_agent_card
from utils.http_client import HTTPClient
from middleware.request_context_middleware import RequestContextMiddleware

logger = logging.getLogger(__name__)

# Early config which runs at import time
update_dotenv_path()

AGENT_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Manages application-wide resources across the server's lifetime.

    On Startup: opens general MongoDB connection -> opens the ADK session store MongoDB connection -> starts HTTP pool
    On Shutdown: closes resouces in reverse order.
    """

    HTTPClient.start()
    try:
        yield
    finally:
        await HTTPClient.stop()
        logger.info("Application shutdown completed")

_agent_card = load_agent_card(str(AGENT_DIR))

# Builds the FastAPI app via Google ADK, wiring up:
# -agent_dir: where ADK discovers agent definitions (agent.json + code) under a2a_agent/
# -lifespan: startup/shutdown hook
# -web/a2a: enables both browser UI & A2A protocol
# -session_service_uri: resolved by factory registered above

app = get_fast_api_app(agents_dir=str(AGENT_DIR), lifespan=lifespan, web=True, a2a=True, session_service_uri="")

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

_AGENT_CARD_PATHS = {
    "/a2a/a2a_agent/.well-known/agent-card.json",
    "/.well-known/agent.json"
}

app.routes[:] = [
    r for r in app.routes
    if not (hasattr(r, "path") and r.path in _AGENT_CARD_PATHS)
]

@app.get("/healthcheck")
def healthcheck():
    """ Liveness probe """
    return {"status": "ok"}

@app.get("/a2a/a2a_agent/.well-known/agent-card.json")
@app.get("/.well-known/agent.json")
def agent_card():
    """ Serves the agent card with env specific URL."""
    return _agent_card

logger.info("Application started")