"""Identifier counters, AIE 64-dim vectors, refresh token families, loudness penalties

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-05

"""
from typing import Sequence, Union
from alembic import op


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. identifier_counters — atomic sequential allocation for ISRC/UPC
    op.execute("""
        CREATE TABLE identifier_counters (
            scope TEXT PRIMARY KEY,
            next_value BIGINT NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # 2. aie_vectors — 64-dim artist identity preference vectors
    op.execute("""
        CREATE TABLE aie_vectors (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            vector DOUBLE PRECISION[] NOT NULL,
            observation_count INTEGER NOT NULL DEFAULT 0,
            cold_start_sessions_remaining INTEGER NOT NULL DEFAULT 5,
            genre_centroid TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT aie_vector_dim_check CHECK (array_length(vector, 1) = 64)
        )
    """)
    op.execute("ALTER TABLE aie_vectors ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY aie_vectors_user_isolation ON aie_vectors
        USING (user_id = current_setting('app.user_id', true)::uuid)
    """)

    # 3. refresh_token_families — for rotation + theft detection
    op.execute("""
        CREATE TABLE refresh_token_families (
            family_id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            current_token_hash TEXT NOT NULL,
            issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_rotated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            revoked_reason TEXT
        )
    """)
    op.execute("CREATE INDEX idx_refresh_families_user ON refresh_token_families(user_id)")
    op.execute("CREATE INDEX idx_refresh_families_hash ON refresh_token_families(current_token_hash)")

    # 4. loudness_penalty_cache — precomputed per (input_hash, platform) pair
    op.execute("""
        CREATE TABLE loudness_penalty_cache (
            input_hash TEXT NOT NULL,
            platform TEXT NOT NULL,
            measured_lufs DOUBLE PRECISION NOT NULL,
            penalty_db DOUBLE PRECISION NOT NULL,
            target_lufs DOUBLE PRECISION NOT NULL,
            applies_limiter BOOLEAN NOT NULL DEFAULT FALSE,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (input_hash, platform)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS loudness_penalty_cache")
    op.execute("DROP TABLE IF EXISTS refresh_token_families")
    op.execute("DROP POLICY IF EXISTS aie_vectors_user_isolation ON aie_vectors")
    op.execute("DROP TABLE IF EXISTS aie_vectors")
    op.execute("DROP TABLE IF EXISTS identifier_counters")
