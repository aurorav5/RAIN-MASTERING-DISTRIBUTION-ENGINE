"""Enterprise tables: workspaces, workspace_members, lora_models + releases alignment

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. workspaces
    op.execute("""
        CREATE TABLE workspaces (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tier TEXT NOT NULL DEFAULT 'enterprise',
            custom_domain TEXT,
            branding_config JSONB,
            api_key_hash TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workspaces_owner ON workspaces USING (owner_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id)")

    # 2. workspace_members
    op.execute("""
        CREATE TABLE workspace_members (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('admin','editor','viewer')),
            invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            accepted_at TIMESTAMPTZ,
            UNIQUE(workspace_id, user_id)
        )
    """)
    op.execute("ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workspace_members_member ON workspace_members "
        "USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_workspace_members_workspace ON workspace_members(workspace_id)")
    op.execute("CREATE INDEX idx_workspace_members_user ON workspace_members(user_id)")

    # 3. lora_models
    op.execute("""
        CREATE TABLE lora_models (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            base_model_version TEXT NOT NULL,
            s3_key TEXT,
            status TEXT NOT NULL CHECK (status IN ('pending','training','ready','failed')),
            training_config JSONB NOT NULL DEFAULT '{}',
            metrics JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
    """)
    op.execute("ALTER TABLE lora_models ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY lora_models_owner ON lora_models "
        "USING (user_id = current_setting('app.user_id')::UUID)"
    )
    op.execute("CREATE INDEX idx_lora_models_workspace ON lora_models(workspace_id)")

    # 4. Align releases table with model (add missing columns from model)
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS territory TEXT DEFAULT 'Worldwide'")
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS label_name TEXT DEFAULT 'ARCOVEL RAIN Distribution'")
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS ddex_xml TEXT")
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS labelgrid_status TEXT")
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMPTZ")
    op.execute("ALTER TABLE releases ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'")


def downgrade() -> None:
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS submitted_at")
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS labelgrid_status")
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS ddex_xml")
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS label_name")
    op.execute("ALTER TABLE releases DROP COLUMN IF EXISTS territory")
    op.execute("DROP TABLE IF EXISTS lora_models CASCADE")
    op.execute("DROP TABLE IF EXISTS workspace_members CASCADE")
    op.execute("DROP TABLE IF EXISTS workspaces CASCADE")
