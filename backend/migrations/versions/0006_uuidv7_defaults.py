"""Switch default UUID generation from gen_random_uuid() to UUIDv7.

Requires PostgreSQL 18+ (native uuid_generate_v7 support).

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-06
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables with UUID primary keys that should use UUIDv7 for timestamp-ordered inserts.
_TABLES = [
    "users",
    "sessions",
    "stems",
    "subscriptions",
    "releases",
    "rain_certs",
    "content_scans",
    "workspaces",
    "lora_models",
]


def upgrade() -> None:
    # PostgreSQL 18 provides uuid_generate_v7() natively.
    # For PG < 18, the pgcrypto gen_random_uuid() fallback remains valid.
    # Check PG version before attempting — graceful no-op on older versions.
    op.execute("""
        DO $$
        BEGIN
            -- Verify uuid_generate_v7 is available (PG 18+)
            PERFORM uuid_generate_v7();
        EXCEPTION WHEN undefined_function THEN
            RAISE NOTICE '0006_uuidv7: uuid_generate_v7() not available — skipping (requires PG 18+)';
            RETURN;
        END $$;
    """)

    for table in _TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                ALTER TABLE {table}
                    ALTER COLUMN id SET DEFAULT uuid_generate_v7();
                RAISE NOTICE '0006_uuidv7: {table}.id default set to uuid_generate_v7()';
            EXCEPTION WHEN undefined_function THEN
                NULL; -- graceful skip
            WHEN undefined_column THEN
                NULL; -- table may not have 'id' column
            END $$;
        """)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                ALTER TABLE {table}
                    ALTER COLUMN id SET DEFAULT gen_random_uuid();
            EXCEPTION WHEN undefined_column THEN
                NULL;
            END $$;
        """)
