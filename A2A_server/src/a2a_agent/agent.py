from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.readonly_context import ReadonlyContext
from typing import Any, Optional
from google.genai import types
from datetime import datetime

import logging
import os

from subagents.search_agent import search_agent
from middleware.request_context import user_id_ctx
from middleware.request_context import interaction_id_ctx
from services.in_memory_session_service import get_session_service

logger = logging.getLogger(__file__)

def _root_agent_instruction_provider(ctx: ReadonlyContext) -> str:
    
    current_datetime = datetime.now().strftime("%Y/%m/%d-%H:%M:%S")
    return f"""
    Current system date-time: {current_datetime}

    You are a helpful triaging agent who orchestrates various sub-agents based on tasks. You are the single
    entry point that customer interact with. Your job is to understand the customer's intent and delegate to
    the correct specialist sub-agents.

    ## Availabe specialist sub-agents
    | Agent             | When to delegate                                                      |
    |-------------------|-----------------------------------------------------------------------|
    | Search Agent      | Only delegate when user asks for current affairs,latest news,recent   |
    |                   | updates, breaking news, live events, or any information that depends  |
    |                   | on fresh web results.                                                 |
    |                   | Use this also for requests containing phrases such as:                |
    |                   |- latest                                                               |
    |                   |- recent                                                               |
    |                   |- today                                                                |
    |                   |- now                                                                  |
    |                   |- this week                                                            |
    |                   |- what happened                                                        |
    |                   |- check online                                                         |
    |                   |- look up on the internet                                              |
    |                   |- verify from the web                                                  |
    |-------------------|-----------------------------------------------------------------------|

    # Rules to be strictly followed at all times:
    1. Whenever customer greets (example: 'Hi', 'hello') as an initial `user` message, always reply politely
       along with your name as `Kritiyam AI`.
    2. Once the customer's request clearly matches with any one of the specialist sub-agents, delegate
        immediately - DO NOT ask unnecessary follow-up question
    3. If no specialist sub-agents can handle customer's request, please let the customer know what you *can
        help with politely.
    4. Never fabricate capabilities - only offer what the specialist sub-agents provide.
    5. Always be emphathetic, concise and professional.
    """

async def save_a2a_request_metadata_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """Extract A2A request metadata and persist it into the in-memory session store."""
    logger.info(f"save a2a request metadata started - session_id={callback_context.session.id}")

    callback_context.state.setdefault("ROOT_AGENT_NAME", "Kritiyam_AI_Agent")
    callback_context.state.setdefault("session_id", callback_context.session.id)

    user_id = callback_context.state.get("user_id") or user_id_ctx.get()
    if user_id is not None:
        callback_context.state["user_id"] = user_id
        logger.info(f"UserId {user_id} persisted in context state")

    interaction_id = callback_context.state.get("interaction_id") or interaction_id_ctx.get()
    if interaction_id is not None:
        callback_context.state["interaction_id"] = interaction_id
        logger.info(f"interactionId {interaction_id} persisted in context state")

    logger.info("save_a2a_request_metadata completed")

    # Session state persisted in InMemorySessionService
    session_service = get_session_service()
    await session_service.persist_session_state(callback_context.session, callback_context.state)
    logger.info("Session state persisted in InMemorySessionService")
    
    return None


root_agent = LlmAgent(
    name="kritiyam_ai_agent",
    model=os.environ['ROOT_AGENT_MODEL'],
    description="An agent that serves as the a2a root agent server, handling requests from a2a client and user interactions & delegating any tasks to sub-agents.",
    instruction=_root_agent_instruction_provider,
    before_agent_callback=save_a2a_request_metadata_callback,
    sub_agents=[search_agent]
)