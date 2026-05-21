# Phase 2 — RS.GE Background Sync (APScheduler Worker)

**Goal:** Pull waybills from RS.GE on a fixed interval and persist to `integrations.waybills` in PostgreSQL, with audit rows in `integrations.sync_runs`.

**Hard rule:** Sync never runs inside the Streamlit process.

---

## Architecture

```
┌─────────────────────┐     ┌──────────────────────────────┐
│  streamlit app.py   │     │  workers/rs_ge_worker.py      │
│  (dashboard only)   │     │  APScheduler BlockingScheduler │
│  NO rs_ge calls     │     │  separate OS process           │
└─────────────────────┘     └──────────────┬───────────────┘
                                           │ every N min
                                           ▼
                            ┌──────────────────────────────┐
                            │  services/rs_sync.py          │
                            │  1. sync_run START (PG)       │
                            │  2. sync.fetch_xml()          │
                            │  3. parser.parse_invoices()   │
                            │  4. upsert waybills (PG)      │
                            │  5. sync_run FINISH (PG)      │
                            └──────────────────────────────┘
```

| Component | Role |
|-----------|------|
| `integrations/rs_ge/sync.py` | **Unchanged** fetch + SQLite `save_to_db` (legacy CLI) |
| `integrations/rs_ge/parser.py` | **Unchanged** XML → DataFrame |
| `services/rs_sync.py` | Orchestration + `sync_runs` logging |
| `services/rs_waybill_repository.py` | Postgres upsert (`integrations.waybills`) |
| `workers/rs_ge_worker.py` | APScheduler loop (`max_instances=1`) |

---

## Why a separate process (not Streamlit)

- Streamlit reruns the script on interaction; background threads are killed or duplicated across replicas.
- SOAP fetch (up to 120s timeout) would block UI and exhaust server workers.
- A dedicated worker scales independently and survives dashboard restarts.

---

## Deployment options (always-on)

### A — Development (Windows / manual)

```powershell
cd "F:\AT Analitc Proect\phase_2_dashboard"
$env:PYTHONPATH = "."
$env:USE_POSTGRES = "true"
python -m workers.rs_ge_worker
```

Leave the terminal open, or use **Option B** for production.

### B — Windows Service (recommended on-prem)

1. Install [NSSM](https://nssm.cc/) (Non-Sucking Service Manager).
2. Register service:

```powershell
nssm install ATRsGeWorker "C:\Path\To\python.exe" "-m" "workers.rs_ge_worker"
nssm set ATRsGeWorker AppDirectory "F:\AT Analitc Proect\phase_2_dashboard"
nssm set ATRsGeWorker AppEnvironmentExtra "PYTHONPATH=F:\AT Analitc Proect\phase_2_dashboard" "USE_POSTGRES=true"
nssm set ATRsGeWorker AppStdout "F:\AT Analitc Proect\logs\rs_ge_worker.out.log"
nssm set ATRsGeWorker AppStderr "F:\AT Analitc Proect\logs\rs_ge_worker.err.log"
nssm start ATRsGeWorker
```

3. Service auto-starts on boot; restart policy via NSSM.

### C — Linux systemd

```ini
# /etc/systemd/system/at-rs-ge-worker.service
[Unit]
Description=AT Analytics RS.GE sync worker
After=network.target postgresql.service

[Service]
Type=simple
User=at
WorkingDirectory=/opt/at-analytics/phase_2_dashboard
Environment=PYTHONPATH=/opt/at-analytics/phase_2_dashboard
EnvironmentFile=/opt/at-analytics/.env
ExecStart=/opt/at-analytics/.venv/bin/python -m workers.rs_ge_worker
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now at-rs-ge-worker
```

### D — Docker sidecar (cloud)

Second container in the same compose stack as Postgres:

```yaml
  rs_ge_worker:
    build: .
    command: python -m workers.rs_ge_worker
    env_file: .env
    depends_on: [postgres]
    restart: unless-stopped
```

Streamlit container has **no** RS.GE env vars required for sync.

---

## Configuration (`.env`)

| Variable | Default | Meaning |
|----------|---------|---------|
| `USE_POSTGRES` | `false` | Worker **requires** `true` for PG writes |
| `DATABASE_URL` | — | PostgreSQL connection |
| `RS_SYNC_INTERVAL_MINUTES` | `30` | APScheduler interval |
| `RS_GE_USE_MOCK` | `true` | Mock XML (dev); `false` = live SOAP |
| `RS_GE_USERNAME` / `RS_GE_PASSWORD` / `RS_GE_SOAP_URL` | — | Live RS.GE credentials |

Legacy `integrations/rs_ge/config.py` still applies to `sync.fetch_xml()` when env is not bridged; worker logs settings from `core.config`.

---

## Observability

- **DB:** `SELECT * FROM integrations.sync_runs ORDER BY started_at DESC LIMIT 20;`
- **Files:** `logs/rs_ge_worker.log` (loguru)
- **Metrics:** `status` = `success` | `failed`; `waybills_count` = distinct invoices; `rows_written` = line rows upserted

---

## Safety

- `max_instances=1` — skip overlapping runs if previous sync still running.
- `coalesce=True` — one catch-up run after downtime, not a backlog storm.
- Streamlit codebase has **zero** imports of `workers` or `services.rs_sync`.

---

## Rollout checklist

1. [ ] Postgres migrated (`integrations.waybills`, `sync_runs`)
2. [ ] `alembic upgrade head` (includes `002` if `waybills_count` column added)
3. [ ] `.env` with `USE_POSTGRES=true`, RS credentials
4. [ ] Manual once: `python -m services.rs_sync` (or worker `--once`)
5. [ ] Verify `sync_runs` row + waybill counts
6. [ ] Start worker service (B/C/D)
7. [ ] Confirm Streamlit dashboard still loads with no RS.GE delay

---

## Deprecated

- `integrations/rs_ge/scheduler.py` (`schedule` lib, daily 02:00) — replaced by APScheduler worker; kept for reference, not used in production path.
