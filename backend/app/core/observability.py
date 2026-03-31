"""
RAIN Observability Module
=========================
Structured logging (structlog), Prometheus custom metrics, correlation ID
middleware, and health-check endpoints.

All critical code paths emit structured JSON logs containing session_id,
user_id, stage, duration_ms, and error_code per CLAUDE.md logging requirements.
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import APIRouter, FastAPI, Request, Response
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

# ---------------------------------------------------------------------------
# Correlation ID context var
# ---------------------------------------------------------------------------
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Return the current correlation ID from context."""
    return correlation_id_ctx.get()


# ---------------------------------------------------------------------------
# Prometheus custom metrics
# ---------------------------------------------------------------------------
rain_render_queue_depth = Gauge(
    "rain_render_queue_depth",
    "Number of render jobs waiting in the queue",
)

rain_render_duration_seconds = Histogram(
    "rain_render_duration_seconds",
    "Time spent rendering a mastering session",
    labelnames=["tier"],
    buckets=[10, 30, 60, 120, 180, 300],
)

rain_render_cost_dollars_total = Counter(
    "rain_render_cost_dollars_total",
    "Cumulative render cost in USD",
    labelnames=["tier", "path"],
)

rain_active_websocket_connections = Gauge(
    "rain_active_websocket_connections",
    "Number of active WebSocket connections",
)

rain_heuristic_fallback_total = Counter(
    "rain_heuristic_fallback_total",
    "Number of times the heuristic fallback was used instead of RainNet",
)

rain_error_total = Counter(
    "rain_error_total",
    "Total errors by RAIN error code",
    labelnames=["error_code"],
)


# ---------------------------------------------------------------------------
# structlog configuration
# ---------------------------------------------------------------------------
def _add_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject the current correlation ID into every log event."""
    cid = correlation_id_ctx.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def _add_environment(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Inject environment and version into every log event."""
    event_dict["environment"] = settings.RAIN_ENV
    event_dict["version"] = settings.RAIN_VERSION
    return event_dict


_LOG_LEVEL_MAP: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def _configure_structlog() -> None:
    """Configure structlog with JSON rendering, ISO timestamps, and log level."""
    log_level = _LOG_LEVEL_MAP.get(settings.RAIN_LOG_LEVEL.lower(), logging.DEBUG)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _add_correlation_id,
            _add_environment,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries go through structlog
    logging.basicConfig(format="%(message)s", level=log_level, force=True)


# ---------------------------------------------------------------------------
# Correlation ID middleware
# ---------------------------------------------------------------------------
class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Extracts or generates a correlation ID for every request.

    Reads from the ``X-Correlation-ID`` header if present; otherwise generates
    a new UUID4. The ID is stored in a contextvar for structured logging and
    returned in the response header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming_id = request.headers.get("X-Correlation-ID")
        cid = incoming_id if incoming_id else uuid.uuid4().hex
        token = correlation_id_ctx.set(cid)
        try:
            response = await call_next(request)
            response.headers["X-Correlation-ID"] = cid
            return response
        finally:
            correlation_id_ctx.reset(token)


# ---------------------------------------------------------------------------
# Health check router
# ---------------------------------------------------------------------------
health_router = APIRouter(tags=["health"])

logger = structlog.get_logger(__name__)


@health_router.get("/health")
async def health_check() -> dict[str, str]:
    """Shallow health check — confirms the service is up."""
    return {
        "status": "ok",
        "version": settings.RAIN_VERSION,
        "environment": settings.RAIN_ENV,
    }


@health_router.get("/health/deep")
async def deep_health_check() -> dict[str, Any]:
    """
    Deep health check — verifies connectivity to database, Valkey (Redis),
    and S3/R2 object storage.
    """
    results: dict[str, Any] = {
        "status": "ok",
        "version": settings.RAIN_VERSION,
        "checks": {},
    }

    # --- Database check ---
    db_status = await _check_database()
    results["checks"]["database"] = db_status
    if db_status["status"] != "ok":
        results["status"] = "degraded"

    # --- Valkey (Redis) check ---
    valkey_status = await _check_valkey()
    results["checks"]["valkey"] = valkey_status
    if valkey_status["status"] != "ok":
        results["status"] = "degraded"

    # --- S3 / R2 check ---
    s3_status = await _check_s3()
    results["checks"]["s3"] = s3_status
    if s3_status["status"] != "ok":
        results["status"] = "degraded"

    return results


async def _check_database() -> dict[str, Any]:
    """Verify database connectivity by executing SELECT 1."""
    start = time.monotonic()
    try:
        from sqlalchemy import text

        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "ok", "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        await logger.aerror(
            "health_check_database_failed",
            error_code="RAIN-E100",
            error=str(exc),
            duration_ms=duration_ms,
        )
        rain_error_total.labels(error_code="RAIN-E100").inc()
        return {"status": "error", "error": str(exc), "duration_ms": duration_ms}


async def _check_valkey() -> dict[str, Any]:
    """Verify Valkey (Redis) connectivity with a PING command."""
    start = time.monotonic()
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.REDIS_URL, socket_connect_timeout=5, decode_responses=True
        )
        try:
            pong = await client.ping()
            duration_ms = round((time.monotonic() - start) * 1000, 1)
            if not pong:
                raise ConnectionError("PING returned falsy response")
            return {"status": "ok", "duration_ms": duration_ms}
        finally:
            await client.aclose()
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        await logger.aerror(
            "health_check_valkey_failed",
            error_code="RAIN-E101",
            error=str(exc),
            duration_ms=duration_ms,
        )
        rain_error_total.labels(error_code="RAIN-E101").inc()
        return {"status": "error", "error": str(exc), "duration_ms": duration_ms}


async def _check_s3() -> dict[str, Any]:
    """Verify S3/R2 connectivity by issuing a HEAD request on the bucket."""
    start = time.monotonic()
    try:
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name="us-east-1",
        ) as s3:
            await s3.head_bucket(Bucket=settings.S3_BUCKET)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        return {"status": "ok", "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        await logger.aerror(
            "health_check_s3_failed",
            error_code="RAIN-E102",
            error=str(exc),
            duration_ms=duration_ms,
        )
        rain_error_total.labels(error_code="RAIN-E102").inc()
        return {"status": "error", "error": str(exc), "duration_ms": duration_ms}


# ---------------------------------------------------------------------------
# Setup entrypoint
# ---------------------------------------------------------------------------
def setup_observability(app: FastAPI) -> None:
    """
    Wire all observability components into the FastAPI application.

    Call this once during application startup (lifespan or on_event).
    """
    # 1. Configure structlog
    _configure_structlog()

    # 2. Add correlation ID middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Instrument with default Prometheus HTTP metrics and expose /metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # 4. Register health-check routes
    app.include_router(health_router)

    structlog.get_logger(__name__).info(
        "observability_initialized",
        environment=settings.RAIN_ENV,
        version=settings.RAIN_VERSION,
        log_level=settings.RAIN_LOG_LEVEL,
    )
