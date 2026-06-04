"""
A2A JSON-RPC Client - builds payloads, send, extract replies.
"""

from __future__ import annotations
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone

from . import config
import httpx

def build_payload(
        text: str,
        context_id: str | None = None,
        interaction_id: str | None = None,
        task_id: str | None = None,
) -> dict:
    """Builds a JSON-RPC payload for the given user input and context.
    To continue an existing conversation, pass the context_id and interaction_id from the previous response.
    The A2A spec puts these on the ``message`` object, not on ``params``.
    """

    message: dict= {
        "message_id": str(uuid.uuid4()),
        "role": "user",
        "parts":[
            {"kind": "text", "text": text},
            {
                "kind": "data",
                "data": config.CONTEXT_DATA,
                "metadata": config.CONTEXT_DATA_METADATA,
                },
            ],
        }
    if context_id:
        message["context_id"] = context_id
    if interaction_id:
        message["interaction_id"] = interaction_id
    if task_id:
        message["task_id"] = task_id

    return {
        "id": f"jsonrpc - {uuid.uuid4().hex[:8]}",
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {
            "message": message,
            "metadata": {
                **config.CONTEXT_METADATA,
                "interactionId": interaction_id or str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    }

def extract_reply(response: dict) -> tuple[str, str | None, str | None]:
    """Returns ``(reply_text, task_id, context_id)`` from a JSON-RPC response dict.
    
    Handles both A2A result shapes:
    - ``kind == "task"`` - text lives in ``status.message.parts`` or in
      ``artifacts[*].parts``; ``context_id`` & ``id`` are top-level.
    - ``kind == "message"`` - the result *is* a Message; text lives in ``parts``directly and ``context_id`` is on the message itself.

    ``context_id`` is what binds turns into one conversation, the server keeps it the same across session. ``task_id`` is per-task & may change across conversation turns if the agent decides to create a new task to handle the user input.
    """
    
    if "error" in response:
        err = response["error"] or {}
        msg = err.get("message", "Unknown error")
        code = err.get("code", "No code")
        return f"JSON-RPC Error {code}: {msg}", None, None
    
    result = response.get("result", {}) or {}
    kind = result.get("kind")

    task_id: str | None = None
    context_id: str | None = result.get("context_id")
    parts: list[dict] = []

    if kind == "message" or (kind is None and "parts" in result):
        # A2A Message result shape
        parts = result.get("parts", []) or []
    else:
        task_id = result.get("id") or result.get("task_id")
        status_msg = (result.get("status", {}) or {}).get("message", "") or {}
        if status_msg.get("parts"):
            parts = status_msg.get("parts", [])
            context_id = context_id or status_msg.get("context_id")
        for artifact in result.get("artifacts", []) or []:
            parts.extend(artifact.get("parts", []) or [])

    texts = [p.get("text", "") for p in parts if p.get("kind") == "text"]
    if texts:
        reply = "\n".join(t for t in texts if t)
    else:
        reply = json.dumps(result, indent=2) if response else "(empty response)"
    return reply, task_id, context_id

def send(payload: dict, url: str | None = None) -> dict:
    """
    POST a JSON-RPC payload to the given A2A URL and return the parsed response.
    """
    target = config._resolve_url(url)
    with httpx.Client(timeout=config.HTTP_TIMEOUT(600, connect=10),
                      verify=config.tls_configured()) as client:
        resp = client.post(target, json=payload)
        resp.raise_for_status()
        return resp.json()
    
def probe_agent_card(url: str | None = None) -> httpx.Response:

    """GET the agent card for the given (or default) A2A endpoint.The well-known card is served
        relative to the agent path(e.g. ``/a2a/agent/.well-known/agent.json``), not the host root.
    """

    target = config._resolve_url(url).rstrip("/") + config.AGENT_CARD_PATH
    with httpx.Client(
        timeout=httpx.Timeout(15, connect=10),
        verify=config.tls_configured(),
    ) as client:
        return client.get(target)

 

def run_cli(url: str | None = None) -> None:
    """Simple terminal REPL — handy for debugging without Streamlit."""
    target = config._resolve_url(url)
    print("A2A Client — context loaded. Type your messages below.")
    print(f"  URL:      {target}")
    print(f"  Data:     {json.dumps(config.CONTEXT_DATA)}")
    print('  Type "quit" to exit.\n')

    task_id: str | None = None
    context_id: str | None = None
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Bye.")
            return

        payload = build_payload(user_input, context_id=context_id)
        try:
            response = send(payload, url=target)
            reply, task_id, new_context_id = extract_reply(response)
            if new_context_id:
                context_id = new_context_id
            print(f"Agent: {reply}\n")
        except httpx.HTTPStatusError as e:
            print(f"Error: {e.response.status_code} — {e.response.text}\n")
        except Exception as e:  # noqa: BLE001
            print(f"Error: {e}\n")

 
def _parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="a2a_client",
        description="A2A JSON-RPC REPL — choose an endpoint by name or URL.",
    )
    parser.add_argument(
        "--url",
        "-u",
        default=None,
        help=(
            "Endpoint name (one of: "
            + ", ".join(config.ENDPOINTS)
            + ") or a full URL. Default: "
            + config.A2A_URL
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured endpoints and exit.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = _parse_cli_args()
    if args.list:
        width = max(len(n) for n in config.ENDPOINTS)
        for name, url in config.ENDPOINTS.items():
            marker = " (default)" if url == config.A2A_URL else ""
            print(f"  {name.ljust(width)}  {url}{marker}")
        sys.exit(0)
    run_cli(url=args.url)