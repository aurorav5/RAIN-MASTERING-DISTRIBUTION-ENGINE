"""Canonical tier definitions. Single source of truth — shared with frontend via openapi-typescript.
Per CLAUDE.md Pricing Model v4 (FINAL). Do not add, rename, or reorder without Phil Bölke approval.
"""
from __future__ import annotations
from enum import Enum


class Tier(str, Enum):
    FREE = "free"
    SPARK = "spark"
    CREATOR = "creator"
    ARTIST = "artist"
    STUDIO_PRO = "studio_pro"
    ENTERPRISE = "enterprise"


# Rank ordering for tier_gte comparisons. Must match Tier enum order.
TIER_RANK: dict[Tier, int] = {
    Tier.FREE: 0,
    Tier.SPARK: 1,
    Tier.CREATOR: 2,
    Tier.ARTIST: 3,
    Tier.STUDIO_PRO: 4,
    Tier.ENTERPRISE: 5,
}


# Rate limits per CLAUDE.md tier architecture. Requests/hour.
TIER_RATE_LIMITS: dict[Tier, str] = {
    Tier.FREE: "20/hour",
    Tier.SPARK: "100/hour",
    Tier.CREATOR: "500/hour",
    Tier.ARTIST: "1500/hour",
    Tier.STUDIO_PRO: "5000/hour",
    Tier.ENTERPRISE: "50000/hour",
}


# Celery queue routing by tier (see worker.py task_routes).
TIER_QUEUE: dict[Tier, str] = {
    Tier.FREE: "cpu_standard",
    Tier.SPARK: "cpu_standard",
    Tier.CREATOR: "gpu_priority_low",
    Tier.ARTIST: "gpu_priority_medium",
    Tier.STUDIO_PRO: "gpu_priority_medium",
    Tier.ENTERPRISE: "gpu_priority_high",
}


def tier_gte(tier: str, minimum: str) -> bool:
    """Return True if `tier` has at least the rank of `minimum`."""
    try:
        t = Tier(tier)
        m = Tier(minimum)
    except ValueError:
        return False
    return TIER_RANK[t] >= TIER_RANK[m]


def queue_for_tier(tier: str) -> str:
    try:
        return TIER_QUEUE[Tier(tier)]
    except ValueError:
        return TIER_QUEUE[Tier.FREE]


def rate_limit_for_tier(tier: str) -> str:
    try:
        return TIER_RATE_LIMITS[Tier(tier)]
    except ValueError:
        return TIER_RATE_LIMITS[Tier.FREE]
