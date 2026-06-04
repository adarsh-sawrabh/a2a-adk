"""
Entry point: `streamlit run streamlit_app.py`.

This file is re-executed by Streamlit on every user interaction, so the UI body lives in `ama_client.app.main()`.
"""

from __future__ import annotations
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ama_client.app import main

main()