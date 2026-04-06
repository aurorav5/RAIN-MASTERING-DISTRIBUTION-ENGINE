"""Custom RainNet LoRA model management routes for Enterprise tier."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import structlog
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser, require_tier
from app.models.lora import LoraModel
from app.models.workspace import Workspace

logger = structlog.get_logger()
router = APIRouter(prefix="/lora", tags=["lora"])


@router.get("/models")
async def list_lora_models(
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all custom LoRA models for the user's workspace."""
    ws_result = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No Enterprise workspace found"})

    result = await db.execute(
        select(LoraModel).where(LoraModel.workspace_id == workspace.id)
    )
    models = result.scalars().all()

    return {
        "models": [
            {
                "id": str(m.id),
                "name": m.name,
                "description": m.description,
                "base_model_version": m.base_model_version,
                "status": m.status,
                "metrics": m.metrics,
                "created_at": m.created_at.isoformat(),
                "completed_at": m.completed_at.isoformat() if m.completed_at else None,
            }
            for m in models
        ]
    }


@router.post("/models")
async def create_lora_model(
    name: str,
    description: str = "",
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new custom LoRA model training job."""
    from app.core.config import settings

    ws_result = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    workspace = ws_result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No Enterprise workspace found"})

    model = LoraModel(
        workspace_id=workspace.id,
        user_id=current_user.user_id,
        name=name,
        description=description or None,
        base_model_version=settings.RAIN_VERSION,
        status="pending",
        training_config={
            "base_model": "rainnet_v2",
            "lora_rank": 16,
            "lora_alpha": 32,
            "learning_rate": 1e-4,
            "epochs": 50,
            "batch_size": 8,
        },
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    logger.info("lora_model_created", model_id=str(model.id), workspace_id=str(workspace.id), user_id=str(current_user.user_id))
    return {
        "model_id": str(model.id),
        "name": model.name,
        "status": model.status,
        "training_config": model.training_config,
    }


@router.post("/models/{model_id}/training-data")
async def upload_training_data(
    model_id: UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload training data for a custom LoRA model."""
    result = await db.execute(
        select(LoraModel).where(
            LoraModel.id == model_id,
            LoraModel.user_id == current_user.user_id,
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, detail={"code": "RAIN-E401", "message": "LoRA model not found"})
    if model.status != "pending":
        raise HTTPException(400, detail={"code": "RAIN-E401", "message": f"Model is {model.status}, cannot upload data"})

    data = await file.read()
    if len(data) > 500 * 1024 * 1024:
        raise HTTPException(413, detail={"code": "RAIN-E201", "message": "Training data exceeds 500MB limit"})

    from app.services.storage import upload_to_s3
    s3_key = f"users/{current_user.user_id}/lora/{model_id}/training_data/{file.filename}"
    await upload_to_s3(data, s3_key)

    logger.info("lora_training_data_uploaded", model_id=str(model_id), size_bytes=len(data), user_id=str(current_user.user_id))
    return {"status": "uploaded", "filename": file.filename, "size_bytes": len(data)}


@router.post("/models/{model_id}/start")
async def start_lora_training(
    model_id: UUID,
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start training a custom LoRA model."""
    result = await db.execute(
        select(LoraModel).where(
            LoraModel.id == model_id,
            LoraModel.user_id == current_user.user_id,
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, detail={"code": "RAIN-E401", "message": "LoRA model not found"})
    if model.status != "pending":
        raise HTTPException(400, detail={"code": "RAIN-E401", "message": f"Model is {model.status}, cannot start training"})

    model.status = "training"
    await db.commit()

    from app.tasks.lora_training import train_lora_model
    train_lora_model.delay(str(model.id), str(current_user.user_id))

    logger.info("lora_training_started", model_id=str(model_id), user_id=str(current_user.user_id))
    return {"model_id": str(model_id), "status": "training"}


@router.get("/models/{model_id}")
async def get_lora_model(
    model_id: UUID,
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get details of a specific LoRA model."""
    result = await db.execute(
        select(LoraModel).where(
            LoraModel.id == model_id,
            LoraModel.user_id == current_user.user_id,
        )
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(404, detail={"code": "RAIN-E401", "message": "LoRA model not found"})

    return {
        "id": str(model.id),
        "name": model.name,
        "description": model.description,
        "base_model_version": model.base_model_version,
        "status": model.status,
        "training_config": model.training_config,
        "metrics": model.metrics,
        "created_at": model.created_at.isoformat(),
        "completed_at": model.completed_at.isoformat() if model.completed_at else None,
    }
