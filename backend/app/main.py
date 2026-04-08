from uuid import UUID

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.observability import setup_observability
from app.core.metrics import NORMALIZATION_GATE
from app.core import metrics as _metrics_module  # noqa: F401 — registers all Prometheus metrics at import
from app.core.rate_limit import limiter
from app.api.dependencies import get_current_user, CurrentUser
from app.api.routes import (
    auth, upload, billing, sessions, download, aie, distribution,
    suno_import, score, whitelabel, workspaces, lora,
    master, qc, separate, waitlist, provenance_routes,
)


# Routers that do NOT require authentication. Everything else is gated globally.
PUBLIC_ROUTERS = {"auth"}


app = FastAPI(
    title="RAIN API",
    version=settings.RAIN_VERSION,
    docs_url="/docs" if settings.RAIN_ENV != "production" else None,
    redoc_url=None,
)

# SlowAPI rate limiter — per-tier limits resolved dynamically via request.state.user
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS: explicit origins from FRONTEND_URL (comma-separated) + localhost/127.0.0.1 fallbacks
_cors_origins = list({
    *[o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()],
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://localhost:4173",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dev middleware: inject a synthetic enterprise user on every request so routes
# that read request.state.user (rate limiter, tier checks, etc.) work without JWT.
if settings.RAIN_ENV == "development":
    _DEV_USER = CurrentUser(
        user_id=UUID("00000000-0000-0000-0000-000000000001"),
        tier="enterprise",
        is_admin=True,
    )

    class DevAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if not hasattr(request.state, "user"):
                request.state.user = _DEV_USER
            return await call_next(request)

    app.add_middleware(DevAuthMiddleware)

setup_observability(app)

# Public routes (no auth dependency)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(waitlist.router, prefix="/api/v1")

# Auth dependency — only applied in production. In development ALL routes are
# open so the stack can be exercised without Postgres user records or JWTs.
_protected_deps = [Depends(get_current_user)] if settings.RAIN_ENV != "development" else []

app.include_router(upload.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(billing.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(sessions.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(download.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(aie.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(distribution.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(suno_import.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(score.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(whitelabel.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(workspaces.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(lora.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(provenance_routes.router, prefix="/api/v1")
app.include_router(master.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(qc.router, prefix="/api/v1", dependencies=_protected_deps)
app.include_router(separate.router, prefix="/api/v1", dependencies=_protected_deps)


@app.on_event("startup")
async def set_metrics_on_startup() -> None:
    NORMALIZATION_GATE.set(1.0 if settings.RAIN_NORMALIZATION_VALIDATED else 0.0)


# Health endpoint is owned by observability.py via setup_observability().
# Do NOT add a duplicate @app.get("/health") here.
