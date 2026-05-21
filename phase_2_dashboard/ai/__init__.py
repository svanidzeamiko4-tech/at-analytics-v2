"""AI chat layer (Haiku + caching + data_loader context)."""

from ai.context_builder import build_session_context
from ai.prompts import STATIC_DB_SCHEMA_PROMPT, STATIC_SYSTEM_PROMPT, cached_system_blocks

__all__ = [
    "STATIC_SYSTEM_PROMPT",
    "STATIC_DB_SCHEMA_PROMPT",
    "cached_system_blocks",
    "build_session_context",
]
