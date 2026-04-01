from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.observability import setup_observability
from app.core.metrics import NORMALIZATION_GATE
from app.core import metrics as _metrics_module  # noqa: F401 — registers all Prometheus metrics at import
from app.api.routes import (
    auth, upload, billing, sessions, download, aie,
    distribution, suno_import, score, whitelabel, workspaces, lora,
    master, qc, separate, waitlist,
)

app = FastAPI(
    title="RAIN API",
    version=settings.RAIN_VERSION,
    docs_url="/docs" if settings.RAIN_ENV != "production" else None,
    redoc_url=None,
)

# CORS: explicit origins only — no wildcards (P0 security fix)
_cors_origins = [
    settings.FRONTEND_URL,
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_observability(app)

# Core routes
app.include_router(auth.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(billing.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
app.include_router(download.router, prefix="/api/v1")
app.include_router(aie.router, prefix="/api/v1")
app.include_router(distribution.router, prefix="/api/v1")
app.include_router(suno_import.router, prefix="/api/v1")
app.include_router(score.router, prefix="/api/v1")
app.include_router(whitelabel.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(lora.router, prefix="/api/v1")

app.include_router(waitlist.router, prefix="/api/v1")

# Prototype mastering routes
# WARNING: These routes have NO authentication. They use an in-memory session store
# and are intended for local development only. Before any network-exposed deployment,
# add Depends(get_current_user) and move the session store to PostgreSQL with user_id scoping.
app.include_router(master.router, prefix="/api/v1")
app.include_router(qc.router, prefix="/api/v1")
app.include_router(separate.router, prefix="/api/v1")


@app.on_event("startup")
async def set_metrics_on_startup() -> None:
    NORMALIZATION_GATE.set(1.0 if settings.RAIN_NORMALIZATION_VALIDATED else 0.0)


# Health endpoint is owned by observability.py via setup_observability().
# Do NOT add a duplicate @app.get("/health") here.
