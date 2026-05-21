# Phase 1b — Dry-run validation (SQLite vs PostgreSQL)

**Goal:** Prove that dashboard numbers from Postgres match SQLite **before** setting `USE_POSTGRES=true` in production.

**Constraint:** No UI changes; only `data_loader` ↔ `database/adapter.py`.

---

## Prerequisites

| Step | Action |
|------|--------|
| 1 | PostgreSQL instance running |
| 2 | `.env`: `DATABASE_URL` correct |
| 3 | `alembic -c alembic.ini upgrade head` (schemas + tables) |
| 4 | `python scripts/migrate_sqlite_to_pg.py` (data copied) |
| 5 | `pip install -r requirements.txt` |

---

## Automated comparison

From repo root:

```bash
set PYTHONPATH=phase_2_dashboard
python scripts/validate_pg_vs_sqlite.py
```

Optional flags:

- `--preset "1 თვე"` — date window (default: last 30 days)
- `--tolerance 0.01` — max abs diff for float KPIs (GEL)
- `--skip-row-compare` — KPI only (faster)

**Pass criteria:**

1. Invoice and line-item **row counts** match.
2. **Column sets** match (order may differ; validator normalizes).
3. **KPI bundle** (`total_revenue_gel`, `total_returns_gel`, `returns_pct`, `n_stores`) within tolerance.
4. **Aggregates:** `revenue_by_store` sum, `returns_vs_sales_by_store` totals (if non-empty).

Exit code `0` = safe to trial `USE_POSTGRES=true` on a staging host.

---

## Manual checklist (staging)

Run dashboard twice (same machine, same period):

| # | Check | SQLite (`USE_POSTGRES=false`) | Postgres (`USE_POSTGRES=true`) |
|---|--------|-------------------------------|--------------------------------|
| 1 | App starts | `streamlit run phase_2_dashboard/app.py` | Same |
| 2 | Overview revenue KPI | note value | must match |
| 3 | Returns % | note | must match |
| 4 | Store count | note | must match |
| 5 | Top products chart | top 3 labels + values | must match |
| 6 | მარაგები restock table | first row `recommended_restock_gel` | must match |
| 7 | Distributor login | scoped stores only | unchanged (auth still SQLite until Phase 2) |

---

## Rollback

Set `USE_POSTGRES=false` in `.env` and restart Streamlit — instant return to SQLite with zero code deploy.

---

## Known differences (acceptable)

- `created_at` / `effective_date` timezone display in raw DB dumps (comparison script normalizes to dates).
- Floating-point rounding beyond `--tolerance` (default 0.01 GEL) — investigate if larger.

---

## After validation

1. Staging: `USE_POSTGRES=true` for 24–48h smoke test.
2. Production cutover only after automated script + manual checklist pass.
3. Phase 2: auth + waybills on Postgres (separate migration).
