# AT Analitc Proect 🚀

AI-Driven Enterprise Dashboard for Automated Financial Intelligence & RS.GE Integration.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Streamlit-1.57+-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/SQLite-Local-003B57?logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/Deploy-Local_Streamlit-FF4B4B" alt="Local" />
  <img src="https://img.shields.io/badge/Nginx-SSL-009639?logo=nginx&logoColor=white" alt="Nginx" />
  <img src="https://img.shields.io/badge/Claude-Haiku-191919?logo=anthropic&logoColor=white" alt="Anthropic Haiku" />
  <img src="https://img.shields.io/badge/RS.GE-Integration-2E7D32" alt="RS.GE" />
</p>

AT Analytics is a multi-tenant Streamlit dashboard that turns invoice and waybill data into actionable KPIs, store-level insights, and an AI assistant for field distributors. The platform integrates with **RS.GE** (Georgian Revenue Service) for waybill sync and applies **Anthropic Claude Haiku** with prompt caching for cost-efficient AI.

> **Current deployment (active):** **Local SQLite only** — `amiko_v3.db` (analytics) and `phase_2_dashboard/auth/at_auth.db` (users).  
> **Deferred this phase:** PostgreSQL, Docker Compose, and nginx (disk/ops). Set `USE_POSTGRES=false`.  
> **Developer guide:** [docs/LOCAL_SQLITE_ARCHITECTURE.md](docs/LOCAL_SQLITE_ARCHITECTURE.md)

---

## Table of Contents

- [Local SQLite (active)](#local-sqlite-active)
- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Security Implementation](#security-implementation)
- [AI & Caching](#ai--caching)
- [Installation & Deployment](#installation--deployment)
- [File Structure](#file-structure)
- [Environment Variables](#environment-variables)
- [Further Documentation](#further-documentation)

---

## Local SQLite (active)

| File | Role |
|------|------|
| `amiko_v3.db` | Analytics (invoices, stores, waybills, …) |
| `phase_2_dashboard/auth/at_auth.db` | Users, sessions, store assignments |

```bash
pip install -r requirements.txt
cp .env.example .env   # keep USE_POSTGRES=false
streamlit run phase_2_dashboard/app.py
```

**Rules for new work:** [docs/LOCAL_SQLITE_ARCHITECTURE.md](docs/LOCAL_SQLITE_ARCHITECTURE.md) — use `data_loader` + `auth/*`; do not add PostgreSQL/Docker dependencies to new features.

**RS.GE sync (optional):** `python -m integrations.rs_ge.sync` from `phase_2_dashboard/` (writes to `amiko_v3.db`).

---

## Project Overview

### Purpose

AT Analytics helps distribution companies:

- Monitor **revenue, returns, and store efficiency** across retail outlets
- Plan **restock quantities** from historical sales (deterministic algorithms, not guesswork)
- Answer operational questions via an **AI chat** grounded in real analytics
- Keep **RS.GE waybills** in sync without blocking the dashboard

### Core Capabilities

| Capability | Description |
|------------|-------------|
| **Multi-user dashboard** | Role-based UI: **manager** (all stores) and **distributor** (assigned stores only) |
| **Analytics engine** | Centralized `data_loader` — KPIs, charts, restock heuristics, date presets |
| **RS.GE background sync** | Separate APScheduler worker pulls waybills → `integrations.waybills` |
| **AI analytics chat** | Streaming Haiku assistant; context from `data_loader` only (no ad-hoc SQL) |
| **Data layer (active)** | SQLite: `amiko_v3.db` + `at_auth.db` |
| **Data layer (deferred)** | PostgreSQL schemas: `analytics`, `auth`, `integrations` |
| **Production-ready ops** | Docker Compose, nginx SSL, health checks, usage logging |

### Typical Users

- **Managers** — portfolio-wide performance, returns, store ranking
- **Distributors** — route planning, restock hints, store-specific AI Q&A for assigned outlets

---

## Architecture

The system deliberately **separates** the interactive UI from long-running sync work so Streamlit never blocks on SOAP calls or heavy ETL.

```
                    ┌─────────────────────────────────────────┐
                    │           nginx (TLS :443)              │
                    └───────────────────┬─────────────────────┘
                                        │ HTTPS
                    ┌───────────────────▼─────────────────────┐
                    │     Streamlit app (phase_2_dashboard)    │
                    │  • app.py, dashboard_core, pages       │
                    │  • auth (HMAC token + session_id)        │
                    │  • data_loader ← database/adapter      │
                    │  • ai_chat → Claude API (streaming)    │
                    └───────────────┬─────────────┬───────────┘
                                    │             │
              ┌─────────────────────▼──┐    ┌─────▼──────────────┐
              │   PostgreSQL 16         │    │  Anthropic API     │
              │   • analytics.*         │    │  claude-3-5-haiku  │
              │   • auth.* (SQLite dev) │    │  + prompt caching  │
              │   • integrations.*      │    └────────────────────┘
              └─────────────▲──────────┘
                            │
              ┌─────────────┴─────────────┐
              │  RS.GE worker (separate     │
              │  OS process / container)    │
              │  APScheduler every N min    │
              │  • fetch_xml + parser       │
              │  • services/rs_sync         │
              │  • sync_runs audit log      │
              └─────────────┬─────────────┘
                            │ SOAP / mock XML
                    ┌───────▼────────┐
                    │    RS.GE API   │
                    └────────────────┘
```

### Data flow (analytics)

1. **Invoices / line items** live in `analytics` tables (or legacy `amiko_v3.db` in dev).
2. **`data_loader`** enriches raw rows (dates, store display names, return flags, revenue).
3. **`database/adapter.py`** routes reads to SQLite or PostgreSQL based on `USE_POSTGRES`.
4. **Dashboard** filters frames by `get_allowed_store_ids()` before any chart or KPI.

### Data flow (RS.GE)

1. **Worker** runs `services/rs_sync.py` on an interval (`RS_SYNC_INTERVAL_MINUTES`, default 30).
2. Existing **`integrations/rs_ge/parser.py`** parses XML (unchanged).
3. Rows upsert into **`integrations.waybills`**; each run writes **`integrations.sync_runs`**.

### Why two processes?

| Concern | Solution |
|---------|----------|
| UI blocking | Sync never runs inside Streamlit |
| Scale (~200 users) | PostgreSQL + connection pooling |
| Cost control | Haiku + cached static system/schema prompts |
| Tenant isolation | Row-level filter on `store_id` before AI and charts |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Language** | Python 3.12+ |
| **UI** | Streamlit 1.57+, custom design system (`ui_theme.py`, CSS tokens) |
| **Charts** | Plotly |
| **Database** | PostgreSQL 16 (production), SQLite (local legacy / auth file) |
| **ORM / migrations** | SQLAlchemy 2, Alembic |
| **Background jobs** | APScheduler (RS.GE worker) |
| **AI** | Anthropic SDK — `claude-3-5-haiku-20241022` |
| **Auth** | bcrypt, HMAC-signed tokens, server-side sessions |
| **Config** | pydantic-settings, `.env` |
| **Logging** | loguru, `logs/ai_usage.log`, `logs/rs_ge_worker.log` |
| **Deployment** | Docker, Docker Compose, nginx (SSL termination) |

---

## Security Implementation

### Password hashing (bcrypt)

- Passwords are stored only as **bcrypt hashes** (`auth/passwords.py`).
- Legacy `pbkdf2_sha256` hashes from older installs still verify; successful login **re-hashes to bcrypt**.
- Plain-text passwords are never persisted.

### Session security (HMAC + server-side `session_id`)

| Mechanism | Behavior |
|-----------|----------|
| **Signed token** | Payload includes `sub` (user id), `sid` (session id), role, store_ids, `exp` — HMAC-SHA256 with `AT_AUTH_SECRET` |
| **Server registry** | `sessions` table in auth DB: create on login, revoke on logout |
| **Validation** | Every restore verifies signature **and** `validate_session(sid, user_id)` |
| **Hijack mitigation** | Stolen token after logout fails (session revoked); password change revokes all sessions |

### Row-level isolation (multi-tenant)

- **`get_allowed_store_ids()`** returns `None` for managers (all stores) or a `frozenset` of store IDs for distributors.
- **`dashboard_core`** and **`ai/context_builder`** filter invoice/line DataFrames **before** aggregation.
- The AI receives only a **pre-computed `<session_context>`** block — it cannot query other tenants’ data and does not write SQL.

### Production hardening

`core/production_check.py` runs when `AT_ENV=production`:

- Debug flags off (`AT_DEBUG`, `STREAMLIT_GLOBAL_DEBUG`)
- Strong `AT_AUTH_SECRET` (not default)
- Required API keys and database connectivity
- Fails fast at startup if misconfigured

---

## AI & Caching

### Design principles

1. **No direct SQL** — AI context is built exclusively via `data_loader` functions (`kpi_bundle`, `restock_recommendations_by_store`, etc.).
2. **Context isolation** — Same store filter as the dashboard; `user_id` and `store_ids` are declared in `<session_context>`.
3. **Streaming UX** — Responses stream token-by-token via `st.write_stream` (no long spinner).
4. **Cost control** — Static prompts cached across all users.

### Prompt caching (Anthropic)

Static content lives in `ai/prompts.py`:

| Block | Content | Cached? |
|-------|---------|---------|
| 1 | `STATIC_SYSTEM_PROMPT` — role, rules, Georgian output format | Part of prefix |
| 2 | `STATIC_DB_SCHEMA_PROMPT` — schema + `data_loader` contract | **`cache_control: ephemeral`** on block 2 |

Dynamic per-request data is appended to the **user message** (not cached):

```text
<session_context>
  user_id, role, store_ids, KPIs, top stores, restock, optional store focus
</session_context>

---

მომხმარებელი: {question}
```

This layout ensures **200 distributors** share one cached prefix (system + schema), while per-user numbers change only in the message tail.

### Usage monitoring

After each chat completion, `ai/usage_logger.py` appends JSON to **`logs/ai_usage.log`**:

- `tokens_used`, `cache_creation_cost_usd_est`, `cache_read_count`
- `user_id`, `session_id`, `model`

---

## Installation & Deployment

### Prerequisites (local SQLite)

- Python 3.12+
- `pip install -r requirements.txt`
- Existing databases: `amiko_v3.db`, `phase_2_dashboard/auth/at_auth.db`
- Optional: `ANTHROPIC_API_KEY` for AI chat

### Quick start (active path)

**1. Configure environment**

```bash
git clone <repository-url>
cd "AT Analitc Proect"
cp .env.example .env
```

Keep in `.env`:

```env
USE_POSTGRES=false
AT_ANALYTICS_DB=amiko_v3.db
AT_AUTH_DB=phase_2_dashboard/auth/at_auth.db
AT_ENV=development
```

**2. Run the dashboard**

```bash
streamlit run phase_2_dashboard/app.py
```

Open: **http://localhost:8501**

**3. Verify**

- Log in as `manager` / `distributor` (passwords from `.env` or seeded defaults)
- Confirm KPIs load from `amiko_v3.db`

### Default login

| User | Role | Password env var |
|------|------|------------------|
| `manager` | manager | `AT_MANAGER_PASSWORD` |
| `distributor` | distributor | `AT_DISTRIBUTOR_PASSWORD` |

### Deferred: Docker + PostgreSQL

Not used in the current phase. Files remain for future scale-up:

- `docker-compose.yml`, `Dockerfile`, `deploy/nginx.conf`
- `scripts/migrate_sqlite_to_pg.py`, `workers/rs_ge_worker.py` (Postgres worker)

See [docs/PHASE_4_DEPLOYMENT.md](docs/PHASE_4_DEPLOYMENT.md) when re-enabling.

---

## File Structure

```text
AT Analitc Proect/
├── README.md                 # This file — project overview for investors & developers
├── docker-compose.yml        # Full stack: postgres, app, worker, nginx
├── Dockerfile                # Shared image for app + worker
├── alembic.ini               # Database migrations (repo root)
├── requirements.txt          # Python dependencies
├── .env.example              # Environment template (copy to .env)
│
├── deploy/
│   ├── nginx.conf            # SSL reverse proxy → Streamlit
│   └── certs/                # TLS certificates (not committed)
│
├── docs/
│   ├── ENTERPRISE_MIGRATION.md
│   ├── PHASE_1B_VALIDATION.md
│   ├── PHASE_2_RS_GE_WORKER.md
│   ├── PHASE_3_AI_CHAT.md
│   └── PHASE_4_DEPLOYMENT.md
│
├── scripts/
│   ├── docker-entrypoint-app.sh
│   ├── migrate_sqlite_to_pg.py
│   ├── validate_pg_vs_sqlite.py
│   ├── generate-dev-certs.ps1
│   └── run_rs_ge_worker.ps1
│
├── logs/                     # ai_usage.log, worker logs (gitignored)
├── amiko_v3.db               # Legacy analytics SQLite (dev / migration source)
│
└── phase_2_dashboard/        # ★ Main application package
    ├── app.py                # Streamlit entry point
    ├── dashboard_core.py     # Shared dashboard layout & KPI sections
    ├── data_loader.py        # Single source of analytics truth (SQL/read layer)
    ├── ai_chat.py            # Floating AI chat UI (streaming)
    │
    ├── auth/
    │   ├── auth.py           # Login, HMAC token, session binding
    │   ├── users.py          # User CRUD, bcrypt verify
    │   ├── passwords.py      # bcrypt + legacy pbkdf2 upgrade
    │   ├── sessions.py       # Server-side session registry
    │   └── at_auth.db        # Auth SQLite (volume in Docker)
    │
    ├── ai/
    │   ├── prompts.py        # Cached static system + schema prompts
    │   ├── context_builder.py # data_loader → <session_context>
    │   ├── claude_client.py  # Haiku streaming + usage hook
    │   └── usage_logger.py   # logs/ai_usage.log
    │
    ├── core/
    │   ├── config.py         # pydantic-settings / .env
    │   ├── production_check.py
    │   └── logging_setup.py
    │
    ├── database/
    │   ├── adapter.py        # SQLite ↔ PostgreSQL read adapter
    │   ├── engine.py, session.py
    │   ├── models/           # ORM: analytics, auth, integrations
    │   └── migrations/     # Alembic versions
    │
    ├── services/
    │   ├── rs_sync.py        # RS.GE orchestration + sync_runs
    │   └── rs_waybill_repository.py
    │
    ├── workers/
    │   └── rs_ge_worker.py   # APScheduler (never import from Streamlit)
    │
    ├── integrations/rs_ge/
    │   ├── sync.py           # fetch_xml, legacy SQLite save
    │   ├── parser.py         # XML → DataFrame (stable)
    │   └── mock_data.xml
    │
    ├── pages/                # login, manager_view, distributor_view, admin, …
    ├── charts/               # Plotly chart builders
    ├── components/           # KPI cards, sidebar shell
    ├── ui_theme.py           # Dark/light theme, Plotly styling
    └── assets/               # Logos, static files
```

**Legacy / auxiliary** (outside the main deployment path):

- `at_analytics_v2/` — earlier prototype
- `database_init.py`, `split_pdf.py` — OCR / ingestion utilities
- Root `check_*.py` — ad-hoc validation scripts

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AT_ENV` | `development` or `production` (enables production checks) |
| `AT_DEBUG` | Must be `false` in production |
| `USE_POSTGRES` | `true` for PostgreSQL via adapter |
| `DATABASE_URL` | SQLAlchemy URL for PostgreSQL |
| `AT_AUTH_SECRET` | HMAC signing key (≥32 chars in prod) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `ANTHROPIC_MODEL` | Default: `claude-3-5-haiku-20241022` |
| `RS_GE_USE_MOCK` | `true` = local mock XML |
| `RS_SYNC_INTERVAL_MINUTES` | Worker interval (default 30) |
| `POSTGRES_*` | Docker Compose Postgres credentials |

See [`.env.example`](.env.example) for the full list.

---

## Further Documentation

| Document | Topic |
|----------|--------|
| [docs/LOCAL_SQLITE_ARCHITECTURE.md](docs/LOCAL_SQLITE_ARCHITECTURE.md) | **Active:** local SQLite rules for all new work |
| [docs/ENTERPRISE_MIGRATION.md](docs/ENTERPRISE_MIGRATION.md) | Phased migration plan (PostgreSQL deferred) |
| [docs/PHASE_1B_VALIDATION.md](docs/PHASE_1B_VALIDATION.md) | SQLite vs Postgres parity tests |
| [docs/PHASE_2_RS_GE_WORKER.md](docs/PHASE_2_RS_GE_WORKER.md) | RS.GE worker deployment (NSSM, systemd) |
| [docs/PHASE_3_AI_CHAT.md](docs/PHASE_3_AI_CHAT.md) | AI caching and isolation details |
| [docs/PHASE_4_DEPLOYMENT.md](docs/PHASE_4_DEPLOYMENT.md) | Security checklist and Docker ops |

---

## License & Contact

Proprietary — AT Analytics / Amiko distribution stack.  
For onboarding, deployment support, or investor technical due diligence, refer to this README and the `docs/` phase guides above.
