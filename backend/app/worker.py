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
        "app.tasks.certification",
        "app.tasks.content_scan",
        "app.tasks.distribution",
        "app.tasks.aie",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_routes={
        "app.tasks.demucs.*": {"queue": "demucs"},
        "app.tasks.distribution.*": {"queue": "distribution"},
        "app.tasks.certification.*": {"queue": "certification"},
        "*": {"queue": "default"},
    },
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
