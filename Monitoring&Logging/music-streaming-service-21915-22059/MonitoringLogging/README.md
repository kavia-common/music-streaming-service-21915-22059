# Monitoring & Logging Container

- Start (example):
  uvicorn src.api.main:app --host ${OBS_HOST:-0.0.0.0} --port ${OBS_PORT:-8083}

- Environment variables (see `.env.example` for a template):
  - OBS_HOST: bind host (default 0.0.0.0)
  - OBS_PORT: bind port (default 8083)
  - OBS_API_KEYS: comma-separated list of name:key pairs for API key auth (Authorization: Bearer <key>)
  - OBS_DATA_DIR: path for JSON persistence (default ./data)
  - OBS_ENABLE_PERSISTENCE: true/false to enable JSON snapshotting

- Interfaces:
  - OpenAPI JSON: `interfaces/openapi.json`
  - To regenerate OpenAPI: `python -m src.api.generate_openapi` from this directory

See `USAGE.md` for API examples.
