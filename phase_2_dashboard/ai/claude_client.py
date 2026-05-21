"""
Anthropic API — Haiku + Prompt Caching + streaming (Phase 3–4).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ai.prompts import cached_system_blocks
from ai.usage_logger import log_ai_usage
from core.config import get_settings

HAIKU_MODEL = "claude-3-5-haiku-20241022"
DEFAULT_MAX_TOKENS = 1024


def _client():
    import anthropic

    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()


def build_messages(
    chat_history: list[dict[str, str]],
    user_prompt: str,
    session_context: str,
) -> list[dict[str, Any]]:
    """History + new turn; context prepended to latest user message (not cached)."""
    prior = [{"role": m["role"], "content": m["content"]} for m in chat_history[:-1]]
    wrapped_user = f"{session_context}\n\n---\n\nმომხმარებელი: {user_prompt}"
    return prior + [{"role": "user", "content": wrapped_user}]


def stream_assistant_reply(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    user_id: int | None = None,
    session_id: str | None = None,
) -> Iterator[str]:
    """
    Yield text deltas for ``st.write_stream``; log usage to ``logs/ai_usage.log``.
    """
    settings = get_settings()
    model = settings.anthropic_model or HAIKU_MODEL
    client = _client()

    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=cached_system_blocks(),
        messages=messages,
    ) as stream:
        yield from stream.text_stream
        final = stream.get_final_message()
        log_ai_usage(
            user_id=user_id,
            session_id=session_id,
            model=model,
            usage=getattr(final, "usage", None),
        )
