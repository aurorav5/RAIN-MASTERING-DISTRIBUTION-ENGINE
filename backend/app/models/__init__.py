"""
RAIN Models — Re-export all models for Alembic autogenerate detection.

Alembic's env.py uses `target_metadata = Base.metadata` which only detects
models that have been imported. This module ensures all models are imported.
"""

from app.core.database import Base  # noqa: F401

from app.models.user import User  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.session import Session  # noqa: F401
from app.models.quota import UsageQuota  # noqa: F401
from app.models.stem import Stem  # noqa: F401
from app.models.cert import RainCertRecord  # noqa: F401
from app.models.aie import ArtistProfile  # noqa: F401
from app.models.release import Release  # noqa: F401
from app.models.content_scan import ContentScanResult  # noqa: F401
from app.models.lora import LoraModel  # noqa: F401
from app.models.workspace import Workspace, WorkspaceMember  # noqa: F401
from app.models.enums import (  # noqa: F401
    SubscriptionState,
    SubscriptionTier,
    RenderStatus,
    SessionStatus,
    UserRole,
    MacroSource,
    LimiterMode,
    QCCheckStatus,
    StemType,
)
