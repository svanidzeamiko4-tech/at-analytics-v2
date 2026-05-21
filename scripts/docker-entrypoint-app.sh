#!/bin/sh
set -e
cd /app

if [ "${USE_POSTGRES}" = "true" ]; then
  echo "[entrypoint] Running Alembic migrations..."
  alembic -c alembic.ini upgrade head || echo "[entrypoint] Alembic skipped (check DATABASE_URL)"
fi

exec streamlit run phase_2_dashboard/app.py \
  --server.port=8501 \
  --server.address=0.0.0.0 \
  --server.headless=true \
  --browser.gatherUsageStats=false
