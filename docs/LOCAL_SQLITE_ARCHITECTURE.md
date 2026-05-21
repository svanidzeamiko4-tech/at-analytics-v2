# Local SQLite Architecture (Active Deployment)

**Decision (current phase):** Run entirely on **local SQLite**. PostgreSQL and Docker are **deferred** (disk space / ops constraints).

All new features and modifications must align with this mode unless explicitly re-approved.

---

## Data stores

| Database | Path | Purpose |
|----------|------|---------|
| **Analytics** | `amiko_v3.db` (repo root) | stores, invoices, invoice_items, products, waybills |
| **Auth** | `phase_2_dashboard/auth/at_auth.db` | users, user_stores, sessions |

---

## Runtime rules

1. **`USE_POSTGRES=false`** in `.env` (default). Do not enable PostgreSQL in this phase.
2. **Analytics reads** go through `data_loader.py` → `database/adapter.py` → **SQLite** (`connect_readonly` / `SqliteAnalyticsBackend`).
3. **Auth** stays in `auth/users.py`, `auth/auth.py`, `auth/sessions.py` — SQLite only; no `auth.*` PostgreSQL schema required.
4. **Do not require** `docker compose`, Alembic, or `scripts/migrate_sqlite_to_pg.py` for daily development.
5. **RS.GE sync** (when needed): use existing `integrations/rs_ge/sync.py` → writes to **`amiko_v3.db`** (`waybills` table). Optional: `python -m integrations.rs_ge.sync` or legacy scheduler — **not** the Postgres-only worker unless `USE_POSTGRES=true`.

---

## What remains in the repo (inactive for now)

These are **future / optional** — do not wire them into new features by default:

- `docker-compose.yml`, `Dockerfile`, `deploy/nginx.conf`
- `database/engine.py`, Alembic migrations, `scripts/migrate_sqlite_to_pg.py`
- `workers/rs_ge_worker.py` (PostgreSQL + APScheduler sidecar)
- `USE_POSTGRES=true` code paths in `database/adapter.py`

Keep them for a later scale-up phase; do not delete without product approval.

---

## Checklist for new code

- [ ] Works with `USE_POSTGRES=false`
- [ ] Uses `data_loader` for analytics (no new raw SQL in UI/AI unless added to `data_loader`)
- [ ] Auth via `auth/auth.py` + `at_auth.db`
- [ ] No new hard dependency on Docker or PostgreSQL
- [ ] Document any new SQLite tables in `database_init.py` or `auth/users.py` schema

---

## Local run (canonical)

```bash
pip install -r requirements.txt
cd phase_2_dashboard
set PYTHONPATH=.
set USE_POSTGRES=false
streamlit run app.py
```

From repo root:

```bash
streamlit run phase_2_dashboard/app.py
```

---

## Environment (minimal)

```env
USE_POSTGRES=false
AT_ANALYTICS_DB=amiko_v3.db
AT_AUTH_DB=phase_2_dashboard/auth/at_auth.db
AT_ENV=development
```

`DATABASE_URL` is ignored while `USE_POSTGRES=false`.
