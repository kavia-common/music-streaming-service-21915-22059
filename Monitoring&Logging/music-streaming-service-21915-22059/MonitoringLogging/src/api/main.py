import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# App initialization with metadata and tags for OpenAPI/Swagger
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Observability API",
    version="1.0.0",
    description="API for log and metric ingestion, querying, alert management, and compliance reporting.",
    openapi_tags=[
        {"name": "Health", "description": "Service health and readiness."},
        {"name": "Logs", "description": "Log ingestion and querying."},
        {"name": "Metrics", "description": "Metrics ingestion and querying."},
        {"name": "Alerts", "description": "Alert rule and status management."},
        {"name": "Compliance", "description": "Compliance and audit reporting."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Configuration flags
# -----------------------------------------------------------------------------
# Enable/disable JSON-file persistence of in-memory stores.
OBS_ENABLE_PERSISTENCE = os.getenv("OBS_ENABLE_PERSISTENCE", "true").lower() in {"1", "true", "yes"}

# -----------------------------------------------------------------------------
# Simple API key auth via Authorization: Bearer <key>
# Keys provided via OBS_API_KEYS env in format "name1:key1,name2:key2"
# -----------------------------------------------------------------------------
def _load_api_keys_from_env() -> Dict[str, str]:
    env_val = os.getenv("OBS_API_KEYS", "").strip()
    keys: Dict[str, str] = {}
    if not env_val:
        return keys
    parts = [p for p in env_val.split(",") if p]
    for p in parts:
        if ":" in p:
            name, key = p.split(":", 1)
            name = name.strip()
            key = key.strip()
            if name and key:
                keys[name] = key
    return keys


OBS_KEYS = _load_api_keys_from_env()
OBS_KEYS_SET = set(OBS_KEYS.values())

# PUBLIC_INTERFACE
async def auth_bearer_dependency(authorization: Optional[str] = Header(default=None)) -> str:
    """Authenticate request using Authorization: Bearer <token> header.

    Returns:
        str: The validated API key (token) string.

    Raises:
        HTTPException 401 if header missing or invalid.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization scheme")

    token = authorization.split(" ", 1)[1].strip()
    if token not in OBS_KEYS_SET and len(OBS_KEYS_SET) > 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")

    # If no keys configured (OBS_API_KEYS empty), allow for local/dev use.
    return token


# -----------------------------------------------------------------------------
# Persistence layer (in-memory with optional JSON file snapshotting)
# -----------------------------------------------------------------------------
DATA_DIR = os.getenv("OBS_DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
LOGS_FILE = os.path.join(DATA_DIR, "logs.json")
METRICS_FILE = os.path.join(DATA_DIR, "metrics.json")
ALERTS_FILE = os.path.join(DATA_DIR, "alerts.json")

# In-memory stores
_LOGS: List[Dict[str, Any]] = []
_METRICS: List[Dict[str, Any]] = []
_ALERTS: Dict[str, Dict[str, Any]] = {}

_store_lock = threading.Lock()

def _load_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _save_json_file(path: str, data: Any) -> None:
    if not OBS_ENABLE_PERSISTENCE:
        return
    tmp = f"{path}.tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp, path)

def _bootstrap_store() -> None:
    with _store_lock:
        if OBS_ENABLE_PERSISTENCE:
            logs = _load_json_file(LOGS_FILE, [])
            metrics = _load_json_file(METRICS_FILE, [])
            alerts = _load_json_file(ALERTS_FILE, {})
            if isinstance(logs, list):
                _LOGS.extend(logs)
            if isinstance(metrics, list):
                _METRICS.extend(metrics)
            if isinstance(alerts, dict):
                _ALERTS.update(alerts)

_bootstrap_store()

def _persist_async() -> None:
    # Persist stores in a simple background thread to avoid blocking
    if not OBS_ENABLE_PERSISTENCE:
        return

    def _persist():
        with _store_lock:
            _save_json_file(LOGS_FILE, _LOGS)
            _save_json_file(METRICS_FILE, _METRICS)
            _save_json_file(ALERTS_FILE, _ALERTS)
    t = threading.Thread(target=_persist, daemon=True)
    t.start()


# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------
class LogIngest(BaseModel):
    source: str = Field(..., description="Source service or component emitting the log")
    timestamp: datetime = Field(..., description="UTC timestamp of the log event")
    level: str = Field(..., description="Log level (e.g. DEBUG, INFO, WARN, ERROR)")
    message: str = Field(..., description="Log message text")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured metadata")

class MetricIngest(BaseModel):
    source: str = Field(..., description="Source service or component emitting the metrics")
    timestamp: datetime = Field(..., description="UTC timestamp associated with the metrics payload")
    metrics: Dict[str, float] = Field(..., description="Key/value numeric metrics")

class AlertRule(BaseModel):
    name: str = Field(..., description="Unique alert rule name")
    expression: str = Field(..., description="Expression to evaluate metrics (placeholder)")
    severity: str = Field(..., description="Severity label (e.g., info, warning, critical)")
    notification_channels: Optional[List[str]] = Field(default=None, description="Notification channels (email, slack)")

class AlertOut(BaseModel):
    name: str = Field(..., description="Alert rule name")
    expression: str = Field(..., description="Expression")
    severity: str = Field(..., description="Severity")
    notification_channels: List[str] = Field(default_factory=list, description="Channels")
    last_triggered: Optional[datetime] = Field(default=None, description="Last triggered timestamp")
    active: bool = Field(default=False, description="Whether any condition is currently active for this alert")


# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------
def _paginate(items: List[Dict[str, Any]], page: int, limit: int) -> Tuple[List[Dict[str, Any]], int]:
    total = len(items)
    if limit <= 0:
        return items, total
    start = (page - 1) * limit
    end = start + limit
    return items[start:end], total

def _filter_logs(source: Optional[str], level: Optional[str], start: Optional[datetime], end: Optional[datetime]) -> List[Dict[str, Any]]:
    def in_range(ts: datetime) -> bool:
        if start and ts < start:
            return False
        if end and ts > end:
            return False
        return True

    results: List[Dict[str, Any]] = []
    with _store_lock:
        for entry in _LOGS:
            ts_val = entry.get("timestamp")
            ts = datetime.fromisoformat(ts_val) if isinstance(ts_val, str) else ts_val
            if source and entry.get("source") != source:
                continue
            if level and entry.get("level") != level:
                continue
            if not in_range(ts):
                continue
            results.append(entry)
    # Sort by timestamp descending (latest first)
    results.sort(key=lambda e: e["timestamp"], reverse=True)
    return results

def _filter_metrics(source: Optional[str], metric_name: Optional[str], start: Optional[datetime], end: Optional[datetime]) -> List[Dict[str, Any]]:
    def in_range(ts: datetime) -> bool:
        if start and ts < start:
            return False
        if end and ts > end:
            return False
        return True

    results: List[Dict[str, Any]] = []
    with _store_lock:
        for entry in _METRICS:
            ts_val = entry.get("timestamp")
            ts = datetime.fromisoformat(ts_val) if isinstance(ts_val, str) else ts_val
            if source and entry.get("source") != source:
                continue
            metrics_dict = entry.get("metrics", {})
            if metric_name and metric_name not in metrics_dict:
                continue
            if not in_range(ts):
                continue
            results.append(entry)
    # Sort by timestamp descending
    results.sort(key=lambda e: e["timestamp"], reverse=True)
    return results


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", tags=["Health"], summary="Health Check")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for liveness probes.

    Returns:
        JSON with message Healthy.
    """
    return {"message": "Healthy"}

# PUBLIC_INTERFACE
@app.post(
    "/logs/ingest",
    tags=["Logs"],
    summary="Ingest logs",
    description="Ingest log entries from containers or agents.",
    responses={
        200: {"description": "Log ingested successfully"},
        400: {"description": "Invalid log format"},
        401: {"description": "Unauthorized"},
    },
)
async def ingest_logs(payload: LogIngest, _: str = Depends(auth_bearer_dependency)) -> Dict[str, Any]:
    """Ingest a single log entry and persist it."""
    entry = payload.model_dump()
    # Ensure ISO timestamp string for storage
    entry["timestamp"] = payload.timestamp.isoformat()
    with _store_lock:
        _LOGS.append(entry)
    _persist_async()
    return {"status": "ok", "ingested": 1}

# PUBLIC_INTERFACE
@app.post(
    "/metrics/ingest",
    tags=["Metrics"],
    summary="Ingest metrics",
    description="Ingest metrics from Prometheus exporters.",
    responses={
        200: {"description": "Metrics ingested successfully"},
        400: {"description": "Invalid metrics format"},
        401: {"description": "Unauthorized"},
    },
)
async def ingest_metrics(payload: MetricIngest, _: str = Depends(auth_bearer_dependency)) -> Dict[str, Any]:
    """Ingest a metrics payload and persist it."""
    entry = payload.model_dump()
    entry["timestamp"] = payload.timestamp.isoformat()
    with _store_lock:
        _METRICS.append(entry)
    _persist_async()
    return {"status": "ok", "ingested": 1}

# PUBLIC_INTERFACE
@app.get(
    "/logs/query",
    tags=["Logs"],
    summary="Query logs",
    description="Query logs for dashboards and analytics.",
    responses={
        200: {"description": "Query results returned"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Unauthorized"},
    },
)
async def query_logs(
    source: Optional[str] = Query(default=None, description="Filter by log source"),
    level: Optional[str] = Query(default=None, description="Filter by log level"),
    from_: Optional[str] = Query(default=None, alias="from", description="ISO datetime start"),
    to: Optional[str] = Query(default=None, description="ISO datetime end"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=50, ge=1, le=500, description="Items per page"),
    _: str = Depends(auth_bearer_dependency),
) -> Dict[str, Any]:
    """Return filtered and paginated logs."""
    start_dt = None
    end_dt = None
    try:
        if from_:
            start_dt = datetime.fromisoformat(from_)
        if to:
            end_dt = datetime.fromisoformat(to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid 'from' or 'to' datetime format. Use ISO format.")

    results = _filter_logs(source, level, start_dt, end_dt)
    items, total = _paginate(results, page, limit)
    return {"items": items, "page": page, "limit": limit, "total": total}

# PUBLIC_INTERFACE
@app.get(
    "/metrics/query",
    tags=["Metrics"],
    summary="Query metrics",
    description="Query metrics for dashboards and analytics.",
    responses={
        200: {"description": "Query results returned"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Unauthorized"},
    },
)
async def query_metrics(
    source: Optional[str] = Query(default=None, description="Filter by metric source"),
    metric: Optional[str] = Query(default=None, description="Filter entries that include a specific metric key"),
    from_: Optional[str] = Query(default=None, alias="from", description="ISO datetime start"),
    to: Optional[str] = Query(default=None, description="ISO datetime end"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(default=50, ge=1, le=500, description="Items per page"),
    _: str = Depends(auth_bearer_dependency),
) -> Dict[str, Any]:
    """Return filtered and paginated metrics entries."""
    start_dt = None
    end_dt = None
    try:
        if from_:
            start_dt = datetime.fromisoformat(from_)
        if to:
            end_dt = datetime.fromisoformat(to)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid 'from' or 'to' datetime format. Use ISO format.")

    results = _filter_metrics(source, metric, start_dt, end_dt)
    items, total = _paginate(results, page, limit)
    return {"items": items, "page": page, "limit": limit, "total": total}

# PUBLIC_INTERFACE
@app.get(
    "/alerts",
    tags=["Alerts"],
    summary="Get alerts",
    description="Retrieve current alerts and their status.",
    responses={200: {"description": "Alerts returned"}, 401: {"description": "Unauthorized"}},
)
async def get_alerts(_: str = Depends(auth_bearer_dependency)) -> Dict[str, Any]:
    """Return all alert rules and last status."""
    with _store_lock:
        alerts = [dict(name=name, **data) for name, data in _ALERTS.items()]
    return {"alerts": alerts, "count": len(alerts)}

# PUBLIC_INTERFACE
@app.post(
    "/alerts",
    tags=["Alerts"],
    summary="Create or update alert rule",
    description="Create or update an alert rule for monitoring.",
    responses={
        200: {"description": "Alert rule created/updated"},
        400: {"description": "Invalid alert rule format"},
        401: {"description": "Unauthorized"},
    },
)
async def upsert_alert(rule: AlertRule, _: str = Depends(auth_bearer_dependency)) -> Dict[str, Any]:
    """Create or update an alert rule. This stores rule and keeps prior status."""
    with _store_lock:
        current = _ALERTS.get(rule.name, {})
        stored: Dict[str, Any] = {
            "expression": rule.expression,
            "severity": rule.severity,
            "notification_channels": rule.notification_channels or [],
            "last_triggered": current.get("last_triggered"),
            "active": current.get("active", False),
        }
        _ALERTS[rule.name] = stored
    _persist_async()
    return {"status": "ok", "name": rule.name, "rule": _ALERTS[rule.name]}

# PUBLIC_INTERFACE
@app.get(
    "/compliance/reports",
    tags=["Compliance"],
    summary="Get compliance reports",
    description="Retrieve compliance and audit reports.",
    responses={200: {"description": "Reports returned"}, 401: {"description": "Unauthorized"}},
)
async def get_compliance_reports(_: str = Depends(auth_bearer_dependency)) -> Dict[str, Any]:
    """Return a minimal set of compliance reports summary based on ingested data."""
    with _store_lock:
        total_logs = len(_LOGS)
        total_metrics = len(_METRICS)
        alerts_count = len(_ALERTS)
    report_generated_at = datetime.utcnow().isoformat()
    return {
        "generated_at": report_generated_at,
        "reports": [
            {"name": "data_retention_summary", "details": {"total_logs": total_logs, "total_metrics": total_metrics}},
            {"name": "alerts_overview", "details": {"alert_rules": alerts_count}},
        ],
    }
