from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit.components.v1 as components

_COMPONENT_PATH = Path(__file__).parent / "frontend"

_asana_component = components.declare_component(
    "asana_sense",
    path=str(_COMPONENT_PATH),
)


def render(props: Dict[str, Any], key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Render the AsanaSense custom component."""
    return _asana_component(props=props, key=key, default=None)
