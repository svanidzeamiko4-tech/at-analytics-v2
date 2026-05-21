# AT Analytics — Streamlit app + RS.GE worker (same image, different CMD)
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs deploy/certs \
    && chmod +x scripts/docker-entrypoint-app.sh

ENV PYTHONPATH=/app/phase_2_dashboard \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

EXPOSE 8501

CMD ["/app/scripts/docker-entrypoint-app.sh"]
