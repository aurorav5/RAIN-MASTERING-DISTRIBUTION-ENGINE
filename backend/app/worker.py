"""Celery worker with tier-based queue routing.

Queues:
- cpu_standard        → free/spark tasks, CPU-only analysis, content scan
- gpu_priority_low    → creator tasks, shared GPU pool
- gpu_priority_medium → artist/studio_pro tasks
- gpu_priority_high   → enterprise tasks, dedicated GPU
- distribution        → DDEX/LabelGrid delivery (IO-bound)
- certification       → RAIN-CERT Ed25519 signing (CPU, fast)

GPU workers run with: celery -A app.worker worker --pool solo --concurrency 1
  --prefetch-multiplier 1 -Q gpu_priority_high
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "rain_worker",
    broker=settings.VALKEY_URL,
    backend=settings.VALKEY_URL,
    include=[
        "app.tasks.analysis",
        "app.tasks.render",
        "app.tasks.demucs",
        "app.tasks.separation",
        "app.tasks.certification",
        "app.tasks.content_scan",
        "app.tasks.distribution",
        "app.tasks.aie",
        "app.tasks.lora_training",
        "app.tasks.provenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        # GPU-bound separation/inference — routed by tier at dispatch time via
        # `apply_async(queue=queue_for_tier(user.tier))`. Defaults below are fallbacks.
        "app.tasks.separation.*": {"queue": "gpu_priority_medium"},
        "app.tasks.demucs.*": {"queue": "gpu_priority_medium"},
        "app.tasks.render.*": {"queue": "gpu_priority_medium"},
        "app.tasks.lora_training.*": {"queue": "gpu_priority_high"},
        # IO/CPU-bound
        "app.tasks.distribution.*": {"queue": "distribution"},
        "app.tasks.certification.*": {"queue": "certification"},
        "app.tasks.provenance.*": {"queue": "certification"},
        "app.tasks.analysis.*": {"queue": "cpu_standard"},
        "app.tasks.content_scan.*": {"queue": "cpu_standard"},
        "app.tasks.aie.*": {"queue": "cpu_standard"},
        "*": {"queue": "cpu_standard"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # GPU worker safety — prevents CUDA fork issues
    worker_pool="solo" if settings.RAIN_ENV != "development" else "prefork",
)
