# music-streaming-service-21915-22059

This workspace contains the Monitoring & Logging container for the music streaming service.

- Container path: `music-streaming-service-21915-22059/MonitoringLogging`
- Env sample: `MonitoringLogging/.env.example`
- OpenAPI: `MonitoringLogging/interfaces/openapi.json`
- Regenerate OpenAPI: from `MonitoringLogging/` run `python -m src.api.generate_openapi`
- Start (example): `uvicorn src.api.main:app --host ${OBS_HOST:-0.0.0.0} --port ${OBS_PORT:-8083}`

Environment variables (see .env.example):
- OBS_HOST: bind host (default 0.0.0.0)
- OBS_PORT: bind port (default 8083)
- OBS_API_KEYS: comma-separated "name:key" pairs for API key auth (Authorization: Bearer <key>)
- OBS_DATA_DIR: directory for JSON persistence (default ./data)
- OBS_ENABLE_PERSISTENCE: "true"/"false" to enable JSON snapshotting
