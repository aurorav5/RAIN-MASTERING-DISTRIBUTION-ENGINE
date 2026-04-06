from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.observability import setup_observability
from app.core.metrics import NORMALIZATION_GATE
from app.core import metrics as _metrics_module  # noqa: F401 — registers all Prometheus metrics at import
from app.core.rate_limit import limiter
from app.api.dependencies import get_current_user
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

setup_observability(app)

# Public routes (no auth dependency)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(waitlist.router, prefix="/api/v1")

# Protected routes — global auth dependency applied at router inclusion.
# Every endpoint in these routers receives CurrentUser on request.state and
# is gated behind a valid JWT. Individual routes can still layer require_min_tier.
_protected_deps = [Depends(get_current_user)]

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

# Provenance public key (no auth — anyone can verify certs)
app.include_router(provenance_routes.router, prefix="/api/v1")

# Prototype mastering routes (master_engine + qc_engine + separation from origin/main).
# WARNING: These routes have NO authentication in this merge state. They use an in-memory
# session store and are intended for local development only. Before any network-exposed
# deployment, add Depends(get_current_user) and move the session store to PostgreSQL
# with user_id scoping + RLS.
app.include_router(master.router, prefix="/api/v1")
app.include_router(qc.router, prefix="/api/v1")
app.include_router(separate.router, prefix="/api/v1")


@app.on_event("startup")
async def set_metrics_on_startup() -> None:
    NORMALIZATION_GATE.set(1.0 if settings.RAIN_NORMALIZATION_VALIDATED else 0.0)


# Health endpoint is owned by observability.py via setup_observability().
# Do NOT add a duplicate @app.get("/health") here.
