# music-streaming-service-21915-22059

## Monitoring & Logging container

- Location: `music-streaming-service-21915-22059/MonitoringLogging`
- Start (example):
  uvicorn src.api.main:app --host ${OBS_HOST:-0.0.0.0} --port ${OBS_PORT:-8083}

- Environment variables:
  - OBS_HOST: bind host (default 0.0.0.0)
  - OBS_PORT: bind port (default 8083)
  - OBS_API_KEYS: comma-separated list of name:key pairs for API key auth (Authorization: Bearer <key>)
  - OBS_DATA_DIR: path for JSON persistence (default ./data)
  - OBS_ENABLE_PERSISTENCE: true/false to enable JSON snapshotting

See `.env.example` in the container for a template and `MonitoringLogging/USAGE.md` for API examples.
