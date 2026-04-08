from enum import Enum


class SubscriptionState(str, Enum):
    WAITLIST = "waitlist"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    ACTIVE_SPARK = "active_spark"
    ACTIVE_CREATOR = "active_creator"
    ACTIVE_ARTIST = "active_artist"
    ACTIVE_STUDIO_PRO = "active_studio_pro"
    ACTIVE_ENTERPRISE = "active_enterprise"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


class SubscriptionTier(str, Enum):
    FREE = "free"
    SPARK = "spark"
    CREATOR = "creator"
    ARTIST = "artist"
    STUDIO_PRO = "studio_pro"
    ENTERPRISE = "enterprise"


class RenderStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class UserRole(str, Enum):
    ADMIN = "admin"
    ENGINEER = "engineer"
    REVIEWER = "reviewer"
    VIEWER = "viewer"
    API = "api"


class MacroSource(str, Enum):
    MODEL = "model"
    HEURISTIC = "heuristic"
    MANUAL = "manual"


class LimiterMode(str, Enum):
    TRANSPARENT = "transparent"
    PUNCHY = "punchy"
    DENSE = "dense"
    BROADCAST = "broadcast"
    VINYL = "vinyl"


class QCCheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    REMEDIATED = "remediated"
    SKIPPED = "skipped"


class StemType(str, Enum):
    LEAD_VOCALS = "lead_vocals"
    BACKING_VOCALS = "backing_vocals"
    BASS = "bass"
    KICK = "kick"
    SNARE = "snare"
    HIHATS = "hihats"
    CYMBALS = "cymbals"
    ROOM = "room"
    GUITAR = "guitar"
    PIANO = "piano"
    SYNTHS_PADS = "synths_pads"
    FX_ATMOSPHERE = "fx_atmosphere"
