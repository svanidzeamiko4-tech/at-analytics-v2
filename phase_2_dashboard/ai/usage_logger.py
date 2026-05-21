"""
AI usage monitoring — append-only ``logs/ai_usage.log`` (Phase 4).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.config import get_settings

# Haiku approximate USD per 1M tokens (input cache write / read / output) — estimates for ops
_COST_PER_M_INPUT = 0.80
_COST_PER_M_CACHE_WRITE = 1.00
_COST_PER_M_CACHE_READ = 0.08
_COST_PER_M_OUTPUT = 4.00


def _log_path() -> Path:
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings.log_dir / "ai_usage.log"


def _estimate_cache_creation_cost_usd(cache_creation_tokens: int) -> float:
    return round(cache_creation_tokens * _COST_PER_M_CACHE_WRITE / 1_000_000, 6)


def log_ai_usage(
    *,
    user_id: int | None,
    session_id: str | None,
    model: str,
    usage: Any,
) -> None:
    """
    Log one chat completion after streaming ends.

    Fields: tokens_used, cache_creation_cost (USD est.), cache_read_count.
    """
    if usage is None:
        return

    input_t = int(getattr(usage, "input_tokens", 0) or 0)
    output_t = int(getattr(usage, "output_tokens", 0) or 0)
    cache_create = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)

    tokens_used = input_t + output_t
    cache_creation_cost = _estimate_cache_creation_cost_usd(cache_create)

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "model": model,
        "tokens_used": tokens_used,
        "input_tokens": input_t,
        "output_tokens": output_t,
        "cache_creation_input_tokens": cache_create,
        "cache_creation_cost_usd_est": cache_creation_cost,
        "cache_read_count": cache_read,
    }

    line = json.dumps(record, ensure_ascii=False)
    path = _log_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
