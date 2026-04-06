"""White-label API routes for Enterprise tier."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog
import hashlib
import secrets
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser, require_tier
from app.models.workspace import Workspace

logger = structlog.get_logger()
router = APIRouter(prefix="/whitelabel", tags=["whitelabel"])


@router.get("/config")
async def get_whitelabel_config(
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get white-label configuration for the current user's workspace."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.owner_id == current_user.user_id,
            Workspace.is_active == True,  # noqa: E712
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No Enterprise workspace found"})
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "custom_domain": workspace.custom_domain,
        "branding_config": workspace.branding_config or {},
        "has_api_key": workspace.api_key_hash is not None,
    }


@router.put("/config")
async def update_whitelabel_config(
    config: dict,
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update white-label branding and domain configuration."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.owner_id == current_user.user_id,
            Workspace.is_active == True,  # noqa: E712
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No Enterprise workspace found"})

    if "custom_domain" in config:
        workspace.custom_domain = config["custom_domain"]
    if "branding_config" in config:
        workspace.branding_config = config["branding_config"]
    if "name" in config:
        workspace.name = config["name"]

    await db.commit()
    await db.refresh(workspace)

    logger.info("whitelabel_config_updated", workspace_id=str(workspace.id), user_id=str(current_user.user_id))
    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "custom_domain": workspace.custom_domain,
        "branding_config": workspace.branding_config or {},
    }


@router.post("/api-key/rotate")
async def rotate_api_key(
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a new API key for the Enterprise workspace. Returns the key only once."""
    result = await db.execute(
        select(Workspace).where(
            Workspace.owner_id == current_user.user_id,
            Workspace.is_active == True,  # noqa: E712
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No Enterprise workspace found"})

    raw_key = f"rain_ent_{secrets.token_urlsafe(48)}"
    workspace.api_key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    await db.commit()

    logger.info("api_key_rotated", workspace_id=str(workspace.id), user_id=str(current_user.user_id))
    return {
        "api_key": raw_key,
        "warning": "Store this key securely. It cannot be retrieved after this response.",
    }
