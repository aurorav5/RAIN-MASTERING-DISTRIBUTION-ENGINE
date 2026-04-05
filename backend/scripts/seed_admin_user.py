"""Seed an admin account with a top-tier (enterprise) subscription.

Usage (from backend/ directory, with env vars set or a `.env` loaded):
    python scripts/seed_admin_user.py

Required env vars:
    RAIN_ADMIN_EMAIL       — email to provision (required)
    RAIN_ADMIN_PASSWORD    — initial password (required; min 12 chars)

Optional env vars:
    RAIN_ADMIN_TIER        — default "enterprise"
    RAIN_ADMIN_IS_ADMIN    — default "true"
    DATABASE_URL           — standard RAIN DB URL (postgresql+asyncpg://...)

This script is idempotent: if the email already exists, it upgrades the user's
active subscription to the requested tier and optionally flips is_admin.
Password is only set if the user is new OR if RAIN_ADMIN_RESET_PASSWORD=true.

The script never writes a default password. It fails fast if RAIN_ADMIN_PASSWORD
is missing — per CLAUDE.md "No Fake Data" rule.
"""
from __future__ import annotations
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Make the `app` package importable when running as a script
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.tiers import Tier  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402


VALID_TIERS = {t.value for t in Tier}


async def seed_admin() -> int:
    email = os.environ.get("RAIN_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("RAIN_ADMIN_PASSWORD", "")
    tier = os.environ.get("RAIN_ADMIN_TIER", Tier.ENTERPRISE.value).strip().lower()
    is_admin = os.environ.get("RAIN_ADMIN_IS_ADMIN", "true").lower() == "true"
    reset_password = os.environ.get("RAIN_ADMIN_RESET_PASSWORD", "false").lower() == "true"

    if not email:
        print("ERROR: RAIN_ADMIN_EMAIL env var is required", file=sys.stderr)
        return 2
    if not password or len(password) < 12:
        print(
            "ERROR: RAIN_ADMIN_PASSWORD env var is required and must be >= 12 chars",
            file=sys.stderr,
        )
        return 2
    if tier not in VALID_TIERS:
        print(
            f"ERROR: RAIN_ADMIN_TIER must be one of {sorted(VALID_TIERS)}, got {tier!r}",
            file=sys.stderr,
        )
        return 2

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        user = existing.scalar_one_or_none()

        if user is None:
            user = User(
                id=uuid.uuid4(),
                email=email,
                email_verified=True,
                password_hash=hash_password(password),
                is_active=True,
                is_admin=is_admin,
            )
            db.add(user)
            await db.flush()
            created = True
        else:
            created = False
            if reset_password:
                user.password_hash = hash_password(password)
            # Always sync is_admin flag per the env var
            user.is_admin = is_admin

        # Upsert active subscription at requested tier
        now = datetime.now(timezone.utc)
        sub_result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.current_period_end.desc())
        )
        sub = sub_result.scalar_one_or_none()

        if sub is None:
            sub = Subscription(
                user_id=user.id,
                tier=tier,
                status="active",
                current_period_start=now,
                current_period_end=now + timedelta(days=36500),  # ~100 years
                cancel_at_period_end=False,
            )
            db.add(sub)
        else:
            sub.tier = tier
            sub.status = "active"
            sub.current_period_end = max(
                sub.current_period_end, now + timedelta(days=36500)
            )
            sub.cancel_at_period_end = False

        await db.commit()

    await engine.dispose()

    print(
        f"OK: {'created' if created else 'updated'} {email} "
        f"tier={tier} is_admin={is_admin} "
        f"{'(password reset)' if reset_password and not created else ''}".strip()
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(seed_admin()))
