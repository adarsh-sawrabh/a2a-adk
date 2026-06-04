from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from .request_context import interaction_id_ctx, user_id_ctx

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method != 'POST' or request.url.path != "/a2a/a2a_server_agent":
            return await call_next(request)
        try:
            body = await request.json()
            interaction_id = body.get("params",{}).get("metadata",{}).get("interractionId")
            interaction_id_ctx.set(interaction_id)
            parts = body.get("params",{}).get("message", {}).get("parts", [])
            data_part = next((p for p in parts if p.get("kind") == "data"), {})
            user_id = (data_part.get("data") or {}).get("user_id")
            user_id_ctx.set(user_id)
            return await call_next(request)
        finally:
            interaction_id_ctx.set(None)
            user_id_ctx.set(None)
