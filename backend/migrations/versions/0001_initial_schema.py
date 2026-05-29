"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-29

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email TEXT UNIQUE NOT NULL,
            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            password_hash TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_login_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            is_admin BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY users_self ON users USING (id = current_setting('app.user_id')::UUID)"
    )

    # 2. subscriptions
    op.execute("""
        CREATE TABLE subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tier TEXT NOT NULL CHECK (tier IN ('free','spark','creator','artist','studio_pro','enterprise')),
            stripe_subscription_id TEXT UNIQUE,
            stripe_customer_id TEXT,
            status TEXT NOT NULL CHECK (status IN ('active','past_due','canceled','trialing')),
            current_period_start TIMESTAMPTZ NOT NULL,
            current_period_end TIMESTAMPTZ NOT NULL,
            cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY subscriptions_owner ON subscriptions USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id)")
    op.execute("CREATE INDEX idx_subscriptions_stripe_sub ON subscriptions(stripe_subscription_id)")

    # 3. usage_quotas
    op.execute("""
        CREATE TABLE usage_quotas (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            period_start TIMESTAMPTZ NOT NULL,
            period_end TIMESTAMPTZ NOT NULL,
            renders_used INTEGER NOT NULL DEFAULT 0,
            downloads_used INTEGER NOT NULL DEFAULT 0,
            claude_calls_used INTEGER NOT NULL DEFAULT 0,
            stem_renders_used INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE usage_quotas ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY usage_quotas_owner ON usage_quotas USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE UNIQUE INDEX idx_usage_quotas_user_period ON usage_quotas(user_id, period_start)")

    # 4. sessions (mastering sessions — NOT auth sessions)
    op.execute("""
        CREATE TABLE sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('uploading','analyzing','processing','complete','failed')),
            tier_at_creation TEXT NOT NULL,
            input_file_key TEXT,
            input_file_hash TEXT,
            input_duration_ms INTEGER,
            input_lufs NUMERIC(6,2),
            input_true_peak NUMERIC(6,2),
            output_file_key TEXT,
            output_file_hash TEXT,
            output_lufs NUMERIC(6,2),
            output_true_peak NUMERIC(6,2),
            target_platform TEXT,
            simple_mode BOOLEAN NOT NULL DEFAULT TRUE,
            genre TEXT,
            aie_applied BOOLEAN NOT NULL DEFAULT FALSE,
            rain_score JSONB,
            rain_cert_id UUID,
            wasm_binary_hash TEXT NOT NULL,
            rainnet_model_version TEXT,
            processing_params JSONB,
            error_code TEXT,
            error_detail TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY sessions_owner ON sessions USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_sessions_user_id ON sessions(user_id)")
    op.execute("CREATE INDEX idx_sessions_status ON sessions(status)")

    # 5. stems
    op.execute("""
        CREATE TABLE stems (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            stem_role TEXT NOT NULL CHECK (stem_role IN ('vocals','drums','bass','instruments','fx','accompaniment','mix','other')),
            file_key TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            duration_ms INTEGER,
            source TEXT CHECK (source IN ('uploaded','demucs','bsroformer','suno','udio')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE stems ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY stems_owner ON stems USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_stems_session_id ON stems(session_id)")

    # 6. aie_profiles
    op.execute("""
        CREATE TABLE aie_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            voice_vector JSONB NOT NULL DEFAULT '[]',
            session_count INTEGER NOT NULL DEFAULT 0,
            genre_distribution JSONB NOT NULL DEFAULT '{}',
            platform_preferences JSONB NOT NULL DEFAULT '{}',
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE aie_profiles ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY aie_profiles_owner ON aie_profiles USING (user_id = current_setting('app.user_id')::UUID)"
    )

    # 7. rain_certs
    op.execute("""
        CREATE TABLE rain_certs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES sessions(id),
            user_id UUID NOT NULL REFERENCES users(id),
            input_hash TEXT NOT NULL,
            output_hash TEXT NOT NULL,
            wasm_hash TEXT NOT NULL,
            model_version TEXT NOT NULL,
            processing_params_hash TEXT NOT NULL,
            ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
            ai_source TEXT,
            content_scan_passed BOOLEAN,
            signature TEXT NOT NULL,
            issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE rain_certs ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rain_certs_owner ON rain_certs USING (user_id = current_setting('app.user_id')::UUID)"
    )

    # 8. content_scans
    op.execute("""
        CREATE TABLE content_scans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES sessions(id),
            user_id UUID NOT NULL REFERENCES users(id),
            chromaprint_fingerprint TEXT,
            acoustid_result JSONB,
            audd_result JSONB,
            acrcloud_result JSONB,
            overall_status TEXT NOT NULL CHECK (overall_status IN ('clear','match_found','error','pending')),
            match_title TEXT,
            match_artist TEXT,
            match_confidence NUMERIC(4,2),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE content_scans ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY content_scans_owner ON content_scans USING (user_id = current_setting('app.user_id')::UUID)"
    )

    # 9. releases
    op.execute("""
        CREATE TABLE releases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id),
            session_id UUID REFERENCES sessions(id),
            title TEXT NOT NULL,
            artist_name TEXT NOT NULL,
            album_title TEXT,
            isrc TEXT UNIQUE,
            upc TEXT,
            release_date DATE,
            genre TEXT,
            explicit BOOLEAN NOT NULL DEFAULT FALSE,
            ai_generated BOOLEAN NOT NULL DEFAULT FALSE,
            ai_source TEXT,
            ddex_status TEXT CHECK (ddex_status IN ('pending','submitted','delivered','error')),
            labelgrid_release_id TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE releases ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY releases_owner ON releases USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_releases_user_id ON releases(user_id)")

    # RLS helper function
    op.execute("""
        CREATE OR REPLACE FUNCTION set_app_user_id(user_id UUID) RETURNS VOID AS $$
        BEGIN
            PERFORM set_config('app.user_id', user_id::TEXT, TRUE);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS set_app_user_id(UUID)")
    op.execute("DROP TABLE IF EXISTS releases CASCADE")
    op.execute("DROP TABLE IF EXISTS content_scans CASCADE")
    op.execute("DROP TABLE IF EXISTS rain_certs CASCADE")
    op.execute("DROP TABLE IF EXISTS aie_profiles CASCADE")
    op.execute("DROP TABLE IF EXISTS stems CASCADE")
    op.execute("DROP TABLE IF EXISTS sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS usage_quotas CASCADE")
    op.execute("DROP TABLE IF EXISTS subscriptions CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
