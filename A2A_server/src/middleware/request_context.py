from contextvars import ContextVar
from typing import Optional

interaction_id_ctx: ContextVar[Optional[str]] = ContextVar("interaction_id", default=None)

user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

def get_interaction_id_from_context() -> Optional[str]:
    return interaction_id_ctx.get()

def get_user_id_from_context() -> Optional[str]:
    return user_id_ctx.get()