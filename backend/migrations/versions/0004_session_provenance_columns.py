"""Session columns for provenance, AIE, separation, stamped output

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-05

"""
from typing import Sequence, Union
from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotency gates for async background tasks
    op.execute("""
        ALTER TABLE sessions
            ADD COLUMN IF NOT EXISTS provenance_stamped_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS aie_updated_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS stems_separated_at TIMESTAMPTZ NULL,
            ADD COLUMN IF NOT EXISTS stamped_output_key TEXT NULL,
            ADD COLUMN IF NOT EXISTS stamped_output_hash TEXT NULL,
            ADD COLUMN IF NOT EXISTS c2pa_manifest_id TEXT NULL,
            ADD COLUMN IF NOT EXISTS audioseal_message_hex TEXT NULL,
            ADD COLUMN IF NOT EXISTS chromaprint_fingerprint TEXT NULL,
            ADD COLUMN IF NOT EXISTS measured_bpm NUMERIC(6,2) NULL,
            ADD COLUMN IF NOT EXISTS measured_bpm_raw NUMERIC(6,2) NULL
    """)
    # Helpful partial indexes for sweep jobs
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_needs_provenance
        ON sessions(id) WHERE status = 'complete' AND provenance_stamped_at IS NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_needs_aie
        ON sessions(id) WHERE status = 'complete' AND aie_updated_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sessions_needs_aie")
    op.execute("DROP INDEX IF EXISTS idx_sessions_needs_provenance")
    op.execute("""
        ALTER TABLE sessions
            DROP COLUMN IF EXISTS measured_bpm_raw,
            DROP COLUMN IF EXISTS measured_bpm,
            DROP COLUMN IF EXISTS chromaprint_fingerprint,
            DROP COLUMN IF EXISTS audioseal_message_hex,
            DROP COLUMN IF EXISTS c2pa_manifest_id,
            DROP COLUMN IF EXISTS stamped_output_hash,
            DROP COLUMN IF EXISTS stamped_output_key,
            DROP COLUMN IF EXISTS stems_separated_at,
            DROP COLUMN IF EXISTS aie_updated_at,
            DROP COLUMN IF EXISTS provenance_stamped_at
    """)
