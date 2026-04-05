from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.database import get_db
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_refresh_token, hash_refresh_token,
)
from app.core.config import settings
from app.models.user import User
from app.models.subscription import Subscription
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest
from datetime import datetime, timezone, timedelta
from uuid import UUID
import uuid
import jwt
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["auth"])


async def _persist_refresh_family(
    db: AsyncSession,
    user_id: UUID,
    family_id: UUID,
    token_hash: str,
) -> None:
    """Upsert the refresh-token family's current active hash."""
    await db.execute(
        text(
            """
            INSERT INTO refresh_token_families (family_id, user_id, current_token_hash)
            VALUES (:family_id, :user_id, :token_hash)
            ON CONFLICT (family_id)
            DO UPDATE SET current_token_hash = :token_hash,
                          last_rotated_at = NOW(),
                          revoked = FALSE,
                          revoked_reason = NULL
            """
        ),
        {"family_id": str(family_id), "user_id": str(user_id), "token_hash": token_hash},
    )


async def _revoke_family(db: AsyncSession, family_id: UUID, reason: str) -> None:
    await db.execute(
        text(
            "UPDATE refresh_token_families SET revoked=TRUE, revoked_reason=:r WHERE family_id=:f"
        ),
        {"r": reason, "f": str(family_id)},
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Set refresh token as httpOnly cookie (not returned in body for new clients)."""
    response.set_cookie(
        key="rain_refresh",
        value=token,
        httponly=True,
        secure=settings.RAIN_ENV != "development",
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/api/v1/auth",
    )


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    req: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail={"code": "RAIN-E100", "message": "Email already registered"})

    user = User(id=uuid.uuid4(), email=req.email, password_hash=hash_password(req.password))
    db.add(user)
    await db.flush()

    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user.id, tier="free", status="active",
        current_period_start=now, current_period_end=now + timedelta(days=36500),
    )
    db.add(sub)

    refresh, family_id, token_hash = create_refresh_token(user.id)
    await _persist_refresh_family(db, user.id, family_id, token_hash)
    await db.commit()

    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=create_access_token(user.id, "free"),
        refresh_token=refresh,
        tier="free",
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Invalid credentials"})
    if not user.is_active:
        raise HTTPException(403, detail={"code": "RAIN-E100", "message": "Account deactivated"})

    sub_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    sub = sub_result.scalar_one_or_none()
    tier = sub.tier if sub else "free"

    user.last_login_at = datetime.now(timezone.utc)

    refresh, family_id, token_hash = create_refresh_token(user.id)
    await _persist_refresh_family(db, user.id, family_id, token_hash)
    await db.commit()

    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=create_access_token(user.id, tier),
        refresh_token=refresh,
        tier=tier,
        user_id=user.id,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Rotate refresh token. On reuse of an already-rotated token, revoke the entire family
    (theft detection). Accepts token from httpOnly cookie OR request body (legacy clients).
    """
    body_token: str | None = None
    try:
        payload = await request.json()
        body_token = (payload or {}).get("refresh_token") if isinstance(payload, dict) else None
    except Exception:
        body_token = None
    token = request.cookies.get("rain_refresh") or body_token
    if not token:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Missing refresh token"})

    try:
        claims = decode_refresh_token(token)
    except jwt.PyJWTError:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Invalid refresh token"})

    user_id = UUID(claims["sub"])
    family_id = UUID(claims["fam"])
    token_hash = hash_refresh_token(token)

    row = (
        await db.execute(
            text(
                "SELECT current_token_hash, revoked FROM refresh_token_families WHERE family_id=:f"
            ),
            {"f": str(family_id)},
        )
    ).first()
    if row is None:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Unknown token family"})
    current_hash, revoked = row[0], row[1]
    if revoked:
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Token family revoked"})
    if current_hash != token_hash:
        # Theft indicator: a rotated-out token was reused. Revoke entire family.
        await _revoke_family(db, family_id, reason="reuse_detected")
        await db.commit()
        logger.warning("refresh_token_reuse_detected", user_id=str(user_id), family_id=str(family_id))
        raise HTTPException(401, detail={"code": "RAIN-E100", "message": "Token reuse detected — family revoked"})

    # Resolve tier
    sub_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    sub = sub_result.scalar_one_or_none()
    tier = sub.tier if sub else "free"

    # Rotate: issue new token in the same family, update hash
    new_token, _fam, new_hash = create_refresh_token(user_id, family_id=family_id)
    await _persist_refresh_family(db, user_id, family_id, new_hash)
    await db.commit()

    _set_refresh_cookie(response, new_token)
    return TokenResponse(
        access_token=create_access_token(user_id, tier),
        refresh_token=new_token,
        tier=tier,
        user_id=user_id,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> Response:
    token = request.cookies.get("rain_refresh")
    if token:
        try:
            claims = decode_refresh_token(token)
            family_id = UUID(claims["fam"])
            await _revoke_family(db, family_id, reason="logout")
            await db.commit()
        except jwt.PyJWTError:
            pass
    response.delete_cookie("rain_refresh", path="/api/v1/auth")
    return Response(status_code=204)
