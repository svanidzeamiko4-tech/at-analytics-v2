# Phase 4 — Security & Deployment

## Security

| Item | Implementation |
|------|----------------|
| Password hashing | `auth/passwords.py` — bcrypt (passlib); legacy pbkdf2 auto-upgrade on login |
| Session hijack | `auth/sessions.py` — `session_id` in DB + token `sid`; revoked on logout |
| Production gate | `core/production_check.py` — DEBUG off, secrets, API keys, DB ping |
| AI audit | `logs/ai_usage.log` — JSON per chat (tokens, cache cost est., cache_read) |

## One-command deploy

```bash
cp .env.example .env
# Edit: POSTGRES_PASSWORD, AT_AUTH_SECRET, ANTHROPIC_API_KEY, deploy/certs/

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deploy/certs/privkey.pem -out deploy/certs/fullchain.pem \
  -subj "/CN=localhost"

docker compose up -d --build
```

Open: `https://localhost` (self-signed warning in browser).

## Services

| Service | Role |
|---------|------|
| `postgres` | Primary DB |
| `app` | Streamlit dashboard |
| `worker` | RS.GE APScheduler sync |
| `nginx` | SSL termination → app:8501 |

## Post-deploy

1. Migrate SQLite data (once): `docker compose exec app python scripts/migrate_sqlite_to_pg.py`
2. Production check: `docker compose exec app python -m core.production_check`
3. AI logs: `tail -f logs/ai_usage.log`

## Local dev (no Docker)

```bash
AT_ENV=development
streamlit run phase_2_dashboard/app.py
```

Production checks are skipped unless `AT_ENV=production`.
