"""
Runtime configs: endpoints, request context, network/TLS settings, etc.

This module must be imported before `httpx` to ensure that ``no_proxy`` is set in time for any network requests.
"""

from __future__ import annotations
import os

_NO_PROXY_="localhost,127.0.0.1"
os.environ["NO_PROXY"] = _NO_PROXY_
os.environ["no_proxy"] = _NO_PROXY_

CA_BUNDLE: str | None = (
    os.environ.get("REQUESTS_CA_BUNDLE")
    or os.environ.get("SSL_CERT_FILE")
    or os.environ.get("NODE_EXTRA_CA_CERTS")
)

if CA_BUNDLE:
    os.environ.setdefault("SSL_CERT_FILE", CA_BUNDLE)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", CA_BUNDLE)

_DEFAULT_ENDPOINTS: dict[str, str] = {
    "local": "http://localhost:8000/a2a/my_agent_server",
}

def _load_endpoints() -> dict[str, str]:
    endpoints: dict[str, str] = {}
    for name, default in _DEFAULT_ENDPOINTS.items():
        env_key = f"A2A_URL_{name.replace('-', '_').upper()}"
        endpoints[name] = os.getenv(env_key, default)
    
    extra = os.getenv("A2A_EXTRA_ENDPOINTS", "").strip()
    if extra:
        for entry in extra.split(","):
            entry = entry.strip()
            if not entry or "=" not in entry:
                continue
            name, url = entry.split("=", 1)
            name, url = name.strip(), url.strip()
            if name and url:
                endpoints[name] = url
    return endpoints

ENDPOINTS: dict[str, str] = _load_endpoints()

DEFAULT_ENDPOINT_NAME: str = os.getenv("A2A_DEFAULT_ENDPOINT", "local" if "local" in ENDPOINTS else next(iter(ENDPOINTS)),)

A2A_URL: str = os.getenv("A2A_URL", ENDPOINTS.get(DEFAULT_ENDPOINT_NAME))

AGENT_CARD_PATH = "/.well-known/agent-card.json"

def _resolve_url(name_or_url: str | None) -> str:
    """Resolves an endpoint name or URL to a URL (eg. `local`)"""
    if not name_or_url:
        return A2A_URL
    if name_or_url in ENDPOINTS:
        return ENDPOINTS[name_or_url]
    return name_or_url.strip()

CONTEXT_DATA: dict[str, str] = {
    "user_id": "addy123",
    "conversation_id": "conv456",
    "task_id": "task789",
    "context_id": "ctx012",
}

CONTEXT_DATA_METADATA: dict[str, str] = {
    "user_id": "A unique identifier for the user (eg. username, email, or UUID).",
    "conversation_id": "A unique identifier for the conversation/session. Should be consistent across messages in the same conversation.",
    "task_id": "A unique identifier for the current task or goal. Can be used to group related conversations together.",
    "context_id": "A unique identifier for the current context or state. Can be used to track changes in context over time.",
}

CONTEXT_METADATA: dict[str, str] = {
    "channel": "chat",
    "locale": "en-US",
}

def tls_configured() -> str | bool:
    """Returns ``verify`` argument to pass to ``httpx`` clients"""
    return CA_BUNDLE if CA_BUNDLE else True