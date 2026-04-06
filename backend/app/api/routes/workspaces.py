"""Workspace and team management routes for Enterprise tier."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
import structlog
from app.core.database import get_db
from app.api.dependencies import get_current_user, CurrentUser, require_tier
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User

logger = structlog.get_logger()
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("/")
async def create_workspace(
    name: str,
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new Enterprise workspace."""
    existing = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "RAIN-E101", "message": "Workspace already exists for this account"})

    workspace = Workspace(name=name, owner_id=current_user.user_id, tier="enterprise")
    db.add(workspace)
    await db.flush()

    member = WorkspaceMember(workspace_id=workspace.id, user_id=current_user.user_id, role="admin")
    db.add(member)
    await db.commit()
    await db.refresh(workspace)

    logger.info("workspace_created", workspace_id=str(workspace.id), user_id=str(current_user.user_id))
    return {"workspace_id": str(workspace.id), "name": workspace.name}


@router.get("/")
async def get_workspace(
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the current user's workspace."""
    result = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No workspace found"})

    members_result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace.id)
    )
    members = members_result.scalars().all()

    return {
        "workspace_id": str(workspace.id),
        "name": workspace.name,
        "custom_domain": workspace.custom_domain,
        "members": [
            {"user_id": str(m.user_id), "role": m.role, "invited_at": m.invited_at.isoformat()}
            for m in members
        ],
    }


@router.post("/members")
async def invite_member(
    email: str,
    role: str = "editor",
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Invite a user to the workspace by email."""
    if role not in ("admin", "editor", "viewer"):
        raise HTTPException(400, detail={"code": "RAIN-E101", "message": "Role must be admin, editor, or viewer"})

    result = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No workspace found"})

    member_check = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.user_id,
            WorkspaceMember.role == "admin",
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(403, detail={"code": "RAIN-E101", "message": "Only admins can invite members"})

    user_result = await db.execute(select(User).where(User.email == email))
    target_user = user_result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(404, detail={"code": "RAIN-E100", "message": "User not found"})

    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == target_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "RAIN-E101", "message": "User already a workspace member"})

    member = WorkspaceMember(workspace_id=workspace.id, user_id=target_user.id, role=role)
    db.add(member)
    await db.commit()

    logger.info("member_invited", workspace_id=str(workspace.id), invited_user=email, role=role)
    return {"status": "invited", "user_id": str(target_user.id), "role": role}


@router.delete("/members/{user_id}")
async def remove_member(
    user_id: UUID,
    current_user: CurrentUser = Depends(require_tier("enterprise")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a member from the workspace."""
    result = await db.execute(
        select(Workspace).where(Workspace.owner_id == current_user.user_id, Workspace.is_active == True)  # noqa: E712
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "No workspace found"})

    if user_id == current_user.user_id:
        raise HTTPException(400, detail={"code": "RAIN-E101", "message": "Cannot remove workspace owner"})

    member_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, detail={"code": "RAIN-E101", "message": "Member not found"})

    await db.delete(member)
    await db.commit()

    logger.info("member_removed", workspace_id=str(workspace.id), removed_user=str(user_id))
    return {"status": "removed", "user_id": str(user_id)}
