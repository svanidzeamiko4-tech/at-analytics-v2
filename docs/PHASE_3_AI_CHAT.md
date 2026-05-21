# Phase 3 — AI Chat (Haiku + Prompt Caching + Streaming)

## Model

- **Production:** `claude-3-5-haiku-20241022` (`ANTHROPIC_MODEL` in `.env`)
- **Removed:** `claude-sonnet-4-20250514` (Phase 2 chat)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Streamlit ai_chat.py                                        │
│    build_session_context()  ← data_loader + auth filter      │
│    stream_assistant_reply() ← Anthropic Haiku + cache        │
└─────────────────────────────────────────────────────────────┘

Cached (same for all 200 users)          Per request (NOT cached)
────────────────────────────────         ────────────────────────
ai/prompts.py STATIC_SYSTEM_PROMPT       <session_context>
ai/prompts.py STATIC_DB_SCHEMA_PROMPT       user question
         │ cache_control on schema block
         ▼
   Anthropic cache read ~90% cheaper
```

## Prompt Caching — how it is embedded

### 1. Static system blocks (`ai/prompts.py`)

```python
def cached_system_blocks() -> list[dict]:
    return [
        {"type": "text", "text": STATIC_SYSTEM_PROMPT},
        {
            "type": "text",
            "text": STATIC_DB_SCHEMA_PROMPT,
            "cache_control": {"type": "ephemeral"},  # breakpoint
        },
    ]
```

- **Block 1:** Role, rules, Georgian format, no-SQL policy.
- **Block 2:** DB schema + `data_loader` function contract (no live numbers).
- **`cache_control` on block 2** caches the **prefix** (block 1 + block 2) for all users.

### 2. Dynamic context (NOT in cached blocks)

Built in `ai/context_builder.py` from:

- `load_dashboard_frames()` → filter by `get_allowed_store_ids()`
- `kpi_bundle`, `revenue_by_store`, `restock_recommendations_by_store`, `top_products_by_quantity`
- Optional store focus from keywords / `#branch` in the user question

Wrapped in the **user message**:

```
<session_context>...</session_context>

---

მომხმარებელი: {prompt}
```

This follows Anthropic guidance: *cache only content identical across requests*; per-user numbers must sit **after** the cache breakpoint (in `messages`, not in cached `system`).

### 3. API call (`ai/claude_client.py`)

```python
client.messages.stream(
    model="claude-3-5-haiku-20241022",
    system=cached_system_blocks(),
    messages=messages,  # history + wrapped user turn
)
```

Streamlit: `st.write_stream(stream_assistant_reply(...))` — word-by-word UI.

### 4. Verify cache hits

Check response `usage` (log in future):

- `cache_creation_input_tokens` — first write in 5 min window
- `cache_read_input_tokens` — subsequent reads (cost savings)

**Haiku 3.5 note:** Minimum cacheable prefix is **~2048 tokens**. If `STATIC_DB_SCHEMA_PROMPT` is shorter, caching is skipped silently. Expand `prompts.py` if `cache_read_input_tokens` stays 0.

## Context isolation

| Role | `get_allowed_store_ids()` | AI sees |
|------|---------------------------|---------|
| `manager` | `None` | All stores (same as dashboard) |
| `distributor` | `frozenset(store_ids)` | Only assigned stores |
| unauthenticated | — | Chat blocked in UI |

**No direct SQL** in AI layer — removed from legacy `ai_chat.py`.

## Files

| File | Purpose |
|------|---------|
| `ai/prompts.py` | Static cached prompts |
| `ai/context_builder.py` | `data_loader` → `<session_context>` |
| `ai/claude_client.py` | Haiku + stream + cache |
| `ai_chat.py` | Streamlit UI only |

## Env

```env
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
```

## Test checklist

1. Login as distributor A — ask about store in scope → numbers appear.
2. Login as distributor B — must not see A's store names/revenue in context.
3. Manager — broader KPI in context.
4. Network tab / logs: `cache_read_input_tokens > 0` on 2nd message within 5 min.
5. UI: response streams without long spinner (only brief latency before first token).
