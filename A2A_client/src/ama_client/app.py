"""
    Streamlit chat UI for A2A client.

    This UI is wrapped in `main` so it can be invoked from `streamlit_app.py` without 
    re-importing Streamlit on every user interaction. 
"""

from __future__ import annotations
import httpx
import streamlit as st

from . import config, client

CONTEXT_FIELDS: list[tuple[str, str]] = [
    ("User ID", "user_id"),
    ("Conversation ID", "conversation_id"),
]

_CUSTOM_ENDPOINT_LABEL = "Custom URL..."

def _active_url() -> str:
    """Resolves the currently selected endpoint to a URL."""
    name = st.session_state.get("endpoint_name", config.DEFAULT_ENDPOINT_NAME)
    if name == _CUSTOM_ENDPOINT_LABEL:
        return st.session_state.get("custom_endpoint_url", config.A2A_URL).strip() or config.A2A_URL
    return config.ENDPOINTS.get(name, config.A2A_URL)

def _on_endpoint_change() -> None:
    """
    Reset convsation state when endpoint changes.
    ``task_id`` / ``context_id`` are bound to a specific endpoint's session, so reusing them against a different endpoint will cause 404 or hijack an unrelated session errors.
    """
    st.session_state.pop("messages", None)
    st.session_state.pop("task_id", None)
    st.session_state.pop("context_id", None)

def _render_sidebar() -> dict[str, str]:
    with st.sidebar:
        st.header("Server")

        endpoint_options = list(config.ENDPOINTS.keys()) + [_CUSTOM_ENDPOINT_LABEL]
        if "endpoint_name" not in st.session_state:
            initial = config.DEFAULT_ENDPOINT_NAME
            st.session_state["endpoint_name"] = (initial if initial in endpoint_options else endpoint_options[0]
            )

        st.selectbox(
            "Endpoint",
            options=endpoint_options,
            key="endpoint_name",
            on_change=_on_endpoint_change,
            help=(
                "Select which A2 server to connect to."
                "Conversations resets when switching endpoints."
                "Default endpoint is configured in $A2A_DEFAULT_ENDPOINT at launch."
            ),
        )

        if st.session_state["endpoint_name"] == _CUSTOM_ENDPOINT_LABEL:
            st.text_input(
                "Custom URL",
                key="endpoint_custom_url",
                value=st.session_state.get("endpoint_custom_url", config.A2A_URL),
                placeholder="https://host/a2a/agent_name",
            )
        else:
            st.caption(f"`{config.ENDPOINTS[st.session_state['endpoint_name']]}`")
            if st.session_state["endpoint_name"] == config.DEFAULT_ENDPOINT_NAME:
                st.caption(f"_(launch default: `{config.DEFAULT_ENDPOINT_NAME}`)_")

        st.divider()
        st.header("Context")

        values: dict[str, str] = {}
        for display_name, field_name in CONTEXT_FIELDS:
            default = st.session_state.get(f"ctx_{field_name}", config.CONTEXT_DATA[field_name])
            values[field_name] = st.text_input(display_name, value=default, key=f"ctx_{field_name}")

        interaction_id = st.session_state.get("interaction_id")
        if interaction_id:
            st.code(interaction_id, language=None)

        st.divider()
        if st.button("Reset conversation", use_container_width=True, help="Clear conversation history and context."):
            st.session_state.pop("messages", None)
            st.session_state.pop("task_id", None)
            st.session_state.pop("context_id", None)
            st.session_state.pop("interaction_id", None)
            st.rerun()

        if st.button("Check connection", use_container_width=True, help="Check if the server is reachable and responding."):
            with st.spinner("Checking connection..."):
                try:
                    r = client.probe_agent_card(url=_active_url())
                    if r.status_code == 200:
                        st.success(f"{r.status_code}-- Connection successful!")
                        try:
                            st.json(r.json())
                        except Exception:
                            st.code(r.text[:1000])
                    else:
                        st.warning(f"{r.status_code}-- Connection may be unhealthy.")
                        st.code(r.text[:1000] or "(empty_body)")
                except httpx.ConnectTimeout as e:
                    st.error(f"Connection timed out: {e}")
                except httpx.ConnectError as e:
                    st.error(f"Connection error: {e}")
                except Exception as e:
                    st.error(f"Unexpected error occurred: {e}")
        
        with st.expander("Metadata (read_only)"):
            st.json(config.CONTEXT_METADATA)

    return values

def _handle_user_message(user_input: str, context_values: dict[str, str]) -> None:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    config.CONTEXT_DATA.update(context_values)

    payload = client.build_payload(
        user_input,
        context_id=st.session_state.get("context_id"),
        interaction_id=st.session_state.get("interaction_id"),
    )
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.send(payload, url=_active_url())
                reply, task_id, context_id = client.extract_reply(response)
                # get interaction_id from response payload & save to session state for context continuity across messages
                interaction_id = payload.get("params", {}).get("metadata", {}).get("interaction_id")
                if interaction_id and not st.session_state.get("interaction_id"):
                    st.session_state["interaction_id"] = interaction_id
                st.session_state["task_id"] = task_id
                if context_id:
                    st.session_state["context_id"] = context_id
                st.session_state["messages"].append({"role": "assistant", "content": reply})
                # Rerun to immediately reflect updated interaction_id in sidebar
                if interaction_id and len(st.session_state["messages"]) == 2:
                    st.rerun()
                st.markdown(reply)
            except httpx.HTTPStatusError as e:
                err = f"HTTP error {e.response.status_code}: {e.response.text[:1000]}"
                st.error(err)
                st.session_state["messages"].append({"role": "assistant", "content": err})
            except Exception as e:
                st.error(f"Unexpected error occurred: {e}")
                st.session_state["messages"].append({"role": "assistant", "content": f"Unexpected error occurred: {e}"})

def main() -> None:
    st.set_page_config(page_title="A2A Client", page_icon="🤖", layout="centered")
    st.title("AMA Client")
    
    if "endpoint_name" not in st.session_state:
        st.session_state["endpoint_name"] = config.DEFAULT_ENDPOINT_NAME
    context_values = _render_sidebar()
    st.caption(f"Endpont: `{_active_url()}`")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "task_id" not in st.session_state:
        st.session_state["task_id"] = None
    if "context_id" not in st.session_state:
        st.session_state["context_id"] = None
    
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_input = st.chat_input("Type your message here...")
    if user_input:
        _handle_user_message(user_input, context_values)