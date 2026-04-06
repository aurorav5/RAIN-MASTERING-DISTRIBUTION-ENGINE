"""Celery task for LoRA model training (Enterprise tier).

CLAUDE.md rule: No Fake Data — Zero Tolerance.
This task does not fabricate training results. If the training pipeline is not
provisioned (PyTorch + RainNet checkpoints not available), the task marks the
model row as `status='failed'` with error_code RAIN-E409 and logs a clear diagnostic.
"""
from __future__ import annotations
import structlog
from app.worker import celery_app

logger = structlog.get_logger()


@celery_app.task(bind=True, name="app.tasks.lora_training.train_lora_model", max_retries=1)
def train_lora_model(self, model_id: str, user_id: str) -> dict:
    """
    Train a custom LoRA adapter on the user's data. Enterprise tier only.
    Routed to `gpu_priority_high` queue via worker.py task_routes.

    Requires: PyTorch, ml.rainnet.RainNetV2 checkpoint, user training data in S3.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.core.config import settings
    from app.models.lora import LoraModel
    from datetime import datetime, timezone
    from pathlib import Path

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    logger.info("lora_training_started", model_id=model_id, user_id=user_id, stage="lora_training")

    try:
        with Session(engine) as db:
            model = db.query(LoraModel).filter(LoraModel.id == model_id).first()
            if not model:
                logger.error("lora_model_not_found", model_id=model_id, error_code="RAIN-E401")
                return {"status": "failed", "error": "RAIN-E401"}

            if model.status != "training":
                logger.warning("lora_model_wrong_status", model_id=model_id, status=model.status)
                return {"status": "skipped", "reason": f"Model status is {model.status}"}

            config = model.training_config or {}
            lora_rank = int(config.get("lora_rank", 16))
            lora_alpha = int(config.get("lora_alpha", 32))
            epochs = int(config.get("epochs", 50))

            logger.info(
                "lora_training_config",
                model_id=model_id, lora_rank=lora_rank, lora_alpha=lora_alpha, epochs=epochs,
                stage="lora_training",
            )

            # Pre-flight: verify the training runtime is actually provisioned.
            # Per CLAUDE.md "No Fake Data", we fail fast if the pipeline is not ready
            # rather than writing a fake "ready" row.
            base_checkpoint = Path("/models/rainnet_v2.pt")
            try:
                import torch  # noqa: F401
                from peft import LoraConfig, get_peft_model  # type: ignore  # noqa: F401
            except ImportError as exc:
                logger.error(
                    "lora_training_runtime_missing",
                    model_id=model_id, user_id=user_id,
                    error=str(exc), error_code="RAIN-E409",
                    stage="lora_training",
                )
                model.status = "failed"
                model.metrics = {
                    "error_code": "RAIN-E409",
                    "error": "LoRA training runtime not provisioned — install torch + peft on GPU worker",
                }
                db.commit()
                return {"status": "failed", "error": "RAIN-E409"}

            if not base_checkpoint.exists():
                logger.error(
                    "lora_base_checkpoint_missing",
                    model_id=model_id, path=str(base_checkpoint), error_code="RAIN-E410",
                    stage="lora_training",
                )
                model.status = "failed"
                model.metrics = {
                    "error_code": "RAIN-E410",
                    "error": f"Base RainNet checkpoint not found at {base_checkpoint}",
                }
                db.commit()
                return {"status": "failed", "error": "RAIN-E410"}

            # Training pipeline (hand-off to ml.rainnet.lora_trainer when implemented).
            # Until the trainer module exists we fail explicitly rather than fake completion.
            try:
                from ml.rainnet.lora_trainer import train_lora_adapter  # type: ignore
            except ImportError:
                logger.error(
                    "lora_trainer_module_missing",
                    model_id=model_id, error_code="RAIN-E411", stage="lora_training",
                )
                model.status = "failed"
                model.metrics = {
                    "error_code": "RAIN-E411",
                    "error": "ml.rainnet.lora_trainer not yet implemented — training pipeline pending",
                }
                db.commit()
                return {"status": "failed", "error": "RAIN-E411"}

            result = train_lora_adapter(
                base_checkpoint=str(base_checkpoint),
                user_id=user_id,
                model_id=model_id,
                lora_rank=lora_rank,
                lora_alpha=lora_alpha,
                epochs=epochs,
            )

            model.s3_key = result["s3_key"]
            model.status = "ready"
            model.completed_at = datetime.now(timezone.utc)
            model.metrics = result["metrics"]
            db.commit()

            logger.info(
                "lora_training_complete",
                model_id=model_id, user_id=user_id,
                final_loss=result["metrics"].get("final_loss"),
                stage="lora_training",
            )
            return {"status": "ready", "model_id": model_id, "s3_key": result["s3_key"]}

    except Exception as exc:
        logger.error("lora_training_failed", model_id=model_id, error=str(exc), error_code="RAIN-E401")
        try:
            with Session(engine) as db:
                model = db.query(LoraModel).filter(LoraModel.id == model_id).first()
                if model:
                    model.status = "failed"
                    model.metrics = {"error_code": "RAIN-E401", "error": str(exc)}
                    db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60)
