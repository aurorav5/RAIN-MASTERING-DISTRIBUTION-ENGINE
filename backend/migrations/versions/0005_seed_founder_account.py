"""Seed founder account (Phil / ARCOVEL) with enterprise tier — env-gated

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-05

This migration is idempotent and env-gated:
  - Reads RAIN_ADMIN_EMAIL (default: philippusbolke@gmail.com)
  - Reads RAIN_ADMIN_PASSWORD (REQUIRED on first run — no default)
  - Skips silently if RAIN_ADMIN_PASSWORD is not set (logs a NOTICE)
  - Never overwrites an existing password on subsequent runs

This avoids hardcoded credentials in source while letting `alembic upgrade head`
provision the founder account in one command when the env var is present.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Sequence, Union
from alembic import op


revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_EMAIL = "philippusbolke@gmail.com"


def upgrade() -> None:
    email = (os.environ.get("RAIN_ADMIN_EMAIL") or DEFAULT_EMAIL).strip().lower()
    password = os.environ.get("RAIN_ADMIN_PASSWORD", "")

    if not password or len(password) < 12:
        op.execute(
            f"DO $$ BEGIN RAISE NOTICE '0005_seed_founder_account skipped — "
            f"RAIN_ADMIN_PASSWORD env var not set (>=12 chars). "
            f"Run backend/scripts/seed_admin_user.py after setting it.'; END $$;"
        )
        return

    # Hash password in Python so the SQL stays portable
    import bcrypt
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=36500)
    user_id = str(uuid.uuid4())

    # Insert user if email doesn't exist. Never overwrite password.
    op.execute(
        f"""
        INSERT INTO users (id, email, email_verified, password_hash, is_active, is_admin, created_at, updated_at)
        VALUES ('{user_id}'::uuid, '{email}', TRUE, '{password_hash}', TRUE, TRUE, NOW(), NOW())
        ON CONFLICT (email) DO UPDATE SET is_admin = TRUE, is_active = TRUE, updated_at = NOW()
        """
    )

    # Fetch the canonical user id (in case the row already existed)
    op.execute(
        f"""
        DO $$
        DECLARE
            uid UUID;
            sub_count INT;
        BEGIN
            SELECT id INTO uid FROM users WHERE email = '{email}';
            SELECT COUNT(*) INTO sub_count FROM subscriptions
              WHERE user_id = uid AND status = 'active' AND tier = 'enterprise';
            IF sub_count = 0 THEN
                INSERT INTO subscriptions (
                    id, user_id, tier, status,
                    current_period_start, current_period_end,
                    cancel_at_period_end, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(), uid, 'enterprise', 'active',
                    NOW(), NOW() + INTERVAL '36500 days',
                    FALSE, NOW(), NOW()
                );
            ELSE
                UPDATE subscriptions
                  SET current_period_end = GREATEST(current_period_end, NOW() + INTERVAL '36500 days'),
                      cancel_at_period_end = FALSE,
                      updated_at = NOW()
                  WHERE user_id = uid AND status = 'active' AND tier = 'enterprise';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # No-op: we do not auto-delete the founder account on rollback.
    pass
