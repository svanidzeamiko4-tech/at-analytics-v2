# AT Analytics — Enterprise Migration (Phase 0–4)

**Status (current phase):** **Local SQLite only** — `USE_POSTGRES=false`. PostgreSQL, Docker, and migration scripts are **deferred**.  
**Active guide:** [LOCAL_SQLITE_ARCHITECTURE.md](LOCAL_SQLITE_ARCHITECTURE.md)

**Approved:** 2026-05 — incremental migration; **preserve** existing UI/logic unless PostgreSQL requires it.

## Constraints (from product owner)

1. Do not rewrite working UI, design, or analytics logic.
2. AI must use `data_loader` / existing algorithms — not raw re-aggregation in the LLM.
3. PostgreSQL schema must allow future **admin panel** and **Telegram bot** (extensible `auth`, `integrations`, `audit` schemas).
4. `USE_POSTGRES=false` keeps current SQLite behavior unchanged.

## Current state (baseline)

| Asset | Path | Role |
|-------|------|------|
| Analytics SQLite | `amiko_v3.db` | stores, products, invoices, invoice_items, product_merge_rules, waybills |
| Auth SQLite | `phase_2_dashboard/auth/at_auth.db` | users, user_stores |
| Data access | `data_loader.py` | All dashboard KPIs, charts, restock heuristics |
| RS.GE | `integrations/rs_ge/sync.py` | SOAP/mock → waybills |
| AI | `ai_chat.py` | Anthropic (to be refactored in Phase 3 only) |
| UI | Streamlit `app.py`, `pages/*` | Unchanged in Phase 0–1 |

## Schema inventory (analytics — from `database_init.py` + `data_loader`)

### Core tables

- **stores** — id, code, name, address, city, phone, notes, created_at
- **products** — id, sku, name, category, unit, default_unit_price, notes, created_at
- **invoices** — id, invoice_number, store_id, invoice_date, subtotal, tax_total, total, currency, source_file, raw_text, notes, created_at
- **invoice_items** — id, invoice_id, product_id, line_no, description, quantity, unit_price, discount, line_total, vat_rate, created_at
- **product_merge_rules** — id, priority, canonical_name, m1, m2, m3, notes

### RS.GE (from `integrations/rs_ge/sync.py`)

- **waybills** — invoice_id, date, seller/buyer fields, product_name, quantity, price, line_total, synced_at

### Auth (from `auth/users.py`)

- **users** — id, username, password_hash, role (manager|distributor), display_name, active, created_at
- **user_stores** — user_id, store_id (distributor scope)

### `data_loader` logical columns (not always DB columns)

Enriched in Python: `store_display_name`, `revenue_gel`, `returns_gel`, `effective_date`, `is_return`, etc.  
Phase 1 Postgres: keep base tables; **views or repository layer** reproduces enrichment (same code path long-term).

## Target PostgreSQL layout

```
schemas:
  auth          — users, user_stores, (+ future: api_tokens, telegram_subscriptions)
  analytics     — stores, products, invoices, invoice_items, product_merge_rules
  integrations  — waybills, sync_runs
  audit         — audit_log (future)
```

## Phase 0 deliverables

- [x] `.env.example`
- [x] `phase_2_dashboard/core/config.py`
- [x] This document

## Phase 1 deliverables

- [x] `phase_2_dashboard/database/engine.py` — SQLAlchemy pool
- [x] `phase_2_dashboard/database/models/` — ORM mirrors SQLite
- [x] Alembic migrations `001_initial` (schemas + tables via metadata)
- [x] `scripts/migrate_sqlite_to_pg.py` — one-shot data copy
- [x] `database/adapter.py` — read-only backend for `data_loader` (Phase 1b)
- [ ] Production cutover: `USE_POSTGRES=true` only after `scripts/validate_pg_vs_sqlite.py` passes (see `docs/PHASE_1B_VALIDATION.md`)

### Phase 1 — runbook (when Postgres is ready)

```bash
# From repo root
pip install -r requirements.txt
copy .env.example .env
# Edit .env: USE_POSTGRES=true, DATABASE_URL=postgresql+psycopg://...

set PYTHONPATH=phase_2_dashboard
alembic -c alembic.ini upgrade head
python scripts/migrate_sqlite_to_pg.py --dry-run
python scripts/migrate_sqlite_to_pg.py
```

Phase 1b wires `data_loader` through `database/adapter.py` (default remains SQLite).

### Phase 1b — validation before cutover

```bash
set PYTHONPATH=phase_2_dashboard
python scripts/validate_pg_vs_sqlite.py
```

See `docs/PHASE_1B_VALIDATION.md` for the full checklist.

## Phase 2 — RS.GE worker (implemented)

- [x] `services/rs_sync.py` — fetch/parse (existing modules) + `sync_runs` audit
- [x] `services/rs_waybill_repository.py` — `integrations.waybills` upsert
- [x] `workers/rs_ge_worker.py` — APScheduler, **separate process**
- [x] `docs/PHASE_2_RS_GE_WORKER.md` — deployment plan (NSSM / systemd / Docker)
- [ ] Ops: register always-on service on server

```bash
set PYTHONPATH=phase_2_dashboard
python -m workers.rs_ge_worker --once   # smoke test
python -m workers.rs_ge_worker          # loop every RS_SYNC_INTERVAL_MINUTES
```

## Phase 4 — Security & deployment (implemented)

- [x] bcrypt passwords (`auth/passwords.py`)
- [x] Server-side `session_id` validation (`auth/sessions.py`)
- [x] `core/production_check.py`
- [x] `docker-compose.yml` + `deploy/nginx.conf` + `Dockerfile`
- [x] `logs/ai_usage.log` monitoring
- See `docs/PHASE_4_DEPLOYMENT.md`

```bash
docker compose up -d --build
```

## Phase 3 — AI Chat (implemented)

- [x] `claude-3-5-haiku-20241022` + streaming (`st.write_stream`)
- [x] Prompt caching — `ai/prompts.py` static system + schema
- [x] Context isolation — `get_allowed_store_ids()` + `data_loader` only
- [x] No direct SQL in AI layer
- See `docs/PHASE_3_AI_CHAT.md`

## Environment variables

See `/.env.example`.
