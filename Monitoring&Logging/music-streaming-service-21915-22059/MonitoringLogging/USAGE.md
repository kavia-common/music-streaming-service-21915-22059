# Monitoring & Logging API - Usage

- Start the API (example):
  uvicorn src.api.main:app --host ${OBS_HOST:-0.0.0.0} --port ${OBS_PORT:-8083}

- Auth:
  Set OBS_API_KEYS in .env as "frontend:key1,backend:key2". Clients must send:
  Authorization: Bearer key1

- Ingest examples (curl):
  curl -X POST "http://localhost:8083/logs/ingest" \
    -H "Authorization: Bearer key1" \
    -H "Content-Type: application/json" \
    -d '{"source":"BackendAPI","timestamp":"2025-01-01T00:00:00Z","level":"INFO","message":"started"}'

  curl -X POST "http://localhost:8083/metrics/ingest" \
    -H "Authorization: Bearer key1" \
    -H "Content-Type: application/json" \
    -d '{"source":"BackendAPI","timestamp":"2025-01-01T00:00:00Z","metrics":{"requests_per_minute":42}}'

- Query examples:
  curl -H "Authorization: Bearer key1" "http://localhost:8083/logs/query?source=BackendAPI&from=2025-01-01T00:00:00Z"

  curl -H "Authorization: Bearer key1" "http://localhost:8083/metrics/query?metric=requests_per_minute&limit=10"

- Alerts:
  curl -X POST "http://localhost:8083/alerts" \
    -H "Authorization: Bearer key1" \
    -H "Content-Type: application/json" \
    -d '{"name":"high_rpm","expression":"requests_per_minute>100","severity":"warning","notification_channels":["email"]}'

- Compliance:
  curl -H "Authorization: Bearer key1" "http://localhost:8083/compliance/reports"
