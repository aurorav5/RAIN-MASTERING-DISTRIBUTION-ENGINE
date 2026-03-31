from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.observability import setup_observability
from app.core.metrics import NORMALIZATION_GATE
from app.core import metrics as _metrics_module  # noqa: F401 — registers all Prometheus metrics at import
from app.api.routes import (
    auth, upload, billing, sessions, download, aie,
    distribution, suno_import, score, whitelabel, workspaces, lora,
    master, qc, separate,
)

app = FastAPI(
    title="RAIN API",
    version=settings.RAIN_VERSION,
    docs_url="/docs" if settings.RAIN_ENV != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000", "*"],
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

# Prototype mastering routes
app.include_router(master.router, prefix="/api/v1")
app.include_router(qc.router, prefix="/api/v1")
app.include_router(separate.router, prefix="/api/v1")


@app.on_event("startup")
async def set_metrics_on_startup() -> None:
    NORMALIZATION_GATE.set(1.0 if settings.RAIN_NORMALIZATION_VALIDATED else 0.0)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.RAIN_VERSION, "env": settings.RAIN_ENV}
