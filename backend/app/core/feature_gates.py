"""
RAIN Feature Gates — Tier-gated feature matrix and FastAPI dependencies.

Enforces per-tier access to features, upload limits, output formats,
QC checks, and track quotas. All gate checks use RAIN-B* error codes.

Error codes:
    RAIN-B005: Feature not available for current tier
    RAIN-B002: Track/download quota exceeded for current billing period
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import Depends, HTTPException
from sqlalchemy import select, func as sqla_func
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.api.dependencies import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.enums import SubscriptionState, SubscriptionTier
from app.models.quota import UsageQuota
from app.models.subscription import Subscription

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# QC check IDs available per tier
# ---------------------------------------------------------------------------

# All 18 QC checks
ALL_QC_CHECKS: frozenset[int] = frozenset(range(1, 19))

# Basic QC subset for Free / Spark / Creator
BASIC_QC_CHECKS: frozenset[int] = frozenset({1, 2, 3, 7, 8, 11, 12, 14, 16, 18})

# ---------------------------------------------------------------------------
# Tier feature definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierFeatures:
    """Immutable feature set for a subscription tier."""

    tier: SubscriptionTier
    max_upload_bytes: int
    output_formats: frozenset[str]
    qc_checks: frozenset[int]
    downloads_per_month: int  # 0 = listen only (free tier)
    renders_per_month: int
    claude_calls_per_month: int
    stem_separation: bool
    reference_matching: bool
    spatial_audio: bool
    ddp_export: bool
    ddex_distribution: bool
    vinyl_mastering: bool
    collaboration: bool
    custom_model_training: bool
    daw_plugin: bool
    distribution_intelligence: bool
    aie: bool  # Adaptive Intelligence Engine


# ---------------------------------------------------------------------------
# Canonical tier feature matrix
# ---------------------------------------------------------------------------

_100MB: int = 100 * 1024 * 1024
_500MB: int = 500 * 1024 * 1024

TIER_FEATURES: dict[SubscriptionTier, TierFeatures] = {
    SubscriptionTier.FREE: TierFeatures(
        tier=SubscriptionTier.FREE,
        max_upload_bytes=_100MB,
        output_formats=frozenset({"streaming_master"}),
        qc_checks=BASIC_QC_CHECKS,
        downloads_per_month=0,
        renders_per_month=0,
        claude_calls_per_month=0,
        stem_separation=False,
        reference_matching=False,
        spatial_audio=False,
        ddp_export=False,
        ddex_distribution=False,
        vinyl_mastering=False,
        collaboration=False,
        custom_model_training=False,
        daw_plugin=False,
        distribution_intelligence=False,
        aie=False,
    ),
    SubscriptionTier.SPARK: TierFeatures(
        tier=SubscriptionTier.SPARK,
        max_upload_bytes=_500MB,
        output_formats=frozenset({"streaming_master", "hi_res_master", "binaural"}),
        qc_checks=BASIC_QC_CHECKS,
        downloads_per_month=50,
        renders_per_month=50,
        claude_calls_per_month=0,
        stem_separation=False,
        reference_matching=False,
        spatial_audio=False,
        ddp_export=False,
        ddex_distribution=False,
        vinyl_mastering=False,
        collaboration=False,
        custom_model_training=False,
        daw_plugin=False,
        distribution_intelligence=False,
        aie=False,
    ),
    SubscriptionTier.CREATOR: TierFeatures(
        tier=SubscriptionTier.CREATOR,
        max_upload_bytes=_500MB,
        output_formats=frozenset({"streaming_master", "hi_res_master", "binaural", "podcast"}),
        qc_checks=BASIC_QC_CHECKS,
        downloads_per_month=10,
        renders_per_month=10,
        claude_calls_per_month=10,
        stem_separation=True,
        reference_matching=True,
        spatial_audio=False,
        ddp_export=False,
        ddex_distribution=False,
        vinyl_mastering=False,
        collaboration=False,
        custom_model_training=False,
        daw_plugin=False,
        distribution_intelligence=False,
        aie=False,
    ),
    SubscriptionTier.ARTIST: TierFeatures(
        tier=SubscriptionTier.ARTIST,
        max_upload_bytes=_500MB,
        output_formats=frozenset({
            "streaming_master", "hi_res_master", "binaural", "podcast",
            "vinyl_premaster", "developer_bundle",
        }),
        qc_checks=BASIC_QC_CHECKS,
        downloads_per_month=25,
        renders_per_month=25,
        claude_calls_per_month=25,
        stem_separation=True,
        reference_matching=True,
        spatial_audio=True,
        ddp_export=True,
        ddex_distribution=False,
        vinyl_mastering=True,
        collaboration=True,
        custom_model_training=False,
        daw_plugin=True,
        distribution_intelligence=True,
        aie=True,
    ),
    SubscriptionTier.STUDIO_PRO: TierFeatures(
        tier=SubscriptionTier.STUDIO_PRO,
        max_upload_bytes=_500MB,
        output_formats=frozenset({
            "streaming_master", "hi_res_master", "binaural", "podcast",
            "vinyl_premaster", "developer_bundle", "atmos", "ddp",
        }),
        qc_checks=ALL_QC_CHECKS,
        downloads_per_month=75,
        renders_per_month=75,
        claude_calls_per_month=75,
        stem_separation=True,
        reference_matching=True,
        spatial_audio=True,
        ddp_export=True,
        ddex_distribution=True,
        vinyl_mastering=True,
        collaboration=True,
        custom_model_training=False,
        daw_plugin=True,
        distribution_intelligence=True,
        aie=True,
    ),
    SubscriptionTier.ENTERPRISE: TierFeatures(
        tier=SubscriptionTier.ENTERPRISE,
        max_upload_bytes=_500MB,
        output_formats=frozenset({
            "streaming_master", "hi_res_master", "binaural", "podcast",
            "vinyl_premaster", "developer_bundle", "atmos", "ddp",
        }),
        qc_checks=ALL_QC_CHECKS,
        downloads_per_month=999_999,  # Effectively unlimited
        renders_per_month=999_999,
        claude_calls_per_month=999_999,
        stem_separation=True,
        reference_matching=True,
        spatial_audio=True,
        ddp_export=True,
        ddex_distribution=True,
        vinyl_mastering=True,
        collaboration=True,
        custom_model_training=True,
        daw_plugin=True,
        distribution_intelligence=True,
        aie=True,
    ),
}

# ---------------------------------------------------------------------------
# Map SubscriptionState -> effective SubscriptionTier
# ---------------------------------------------------------------------------

_STATE_TO_TIER: dict[SubscriptionState, SubscriptionTier] = {
    SubscriptionState.WAITLIST: SubscriptionTier.FREE,
    SubscriptionState.TRIAL: SubscriptionTier.CREATOR,
    SubscriptionState.TRIAL_EXPIRED: SubscriptionTier.FREE,
    SubscriptionState.ACTIVE_SPARK: SubscriptionTier.SPARK,
    SubscriptionState.ACTIVE_CREATOR: SubscriptionTier.CREATOR,
    SubscriptionState.ACTIVE_ARTIST: SubscriptionTier.ARTIST,
    SubscriptionState.ACTIVE_STUDIO_PRO: SubscriptionTier.STUDIO_PRO,
    SubscriptionState.ACTIVE_ENTERPRISE: SubscriptionTier.ENTERPRISE,
    SubscriptionState.PAST_DUE: SubscriptionTier.FREE,
    SubscriptionState.CANCELED: SubscriptionTier.FREE,
    SubscriptionState.EXPIRED: SubscriptionTier.FREE,
    SubscriptionState.SUSPENDED: SubscriptionTier.FREE,
}


def get_tier_key(subscription_state: str) -> SubscriptionTier:
    """Resolve the effective SubscriptionTier from a subscription state string.

    Lapsed, canceled, suspended, and expired states all resolve to FREE.
    Trial resolves to CREATOR (the trial experience tier).
    Unknown states resolve to FREE as a safe default.
    """
    try:
        state = SubscriptionState(subscription_state)
    except ValueError:
        logger.warning(
            "unknown_subscription_state",
            state=subscription_state,
            resolved_tier=SubscriptionTier.FREE.value,
        )
        return SubscriptionTier.FREE
    return _STATE_TO_TIER.get(state, SubscriptionTier.FREE)


def get_features_for_tier(tier: SubscriptionTier) -> TierFeatures:
    """Return the TierFeatures for a given tier. Defaults to FREE if unknown."""
    return TIER_FEATURES.get(tier, TIER_FEATURES[SubscriptionTier.FREE])


# ---------------------------------------------------------------------------
# Convenience: resolve tier from CurrentUser.tier string
# ---------------------------------------------------------------------------

def _resolve_tier(user: CurrentUser) -> SubscriptionTier:
    """Convert the user's tier string to a SubscriptionTier enum."""
    try:
        return SubscriptionTier(user.tier)
    except ValueError:
        return SubscriptionTier.FREE


# ---------------------------------------------------------------------------
# FastAPI dependency: require_feature
# ---------------------------------------------------------------------------

def require_feature(feature_name: str) -> Callable[..., Any]:
    """FastAPI dependency factory that gates an endpoint on a boolean feature flag.

    Usage::

        @router.post("/sessions/{sid}/spatial")
        async def apply_spatial(
            user: CurrentUser = Depends(require_feature("spatial_audio")),
        ):
            ...

    Raises HTTPException 403 with code RAIN-B005 if the feature is not
    available for the user's tier. Admin users bypass all feature gates.
    """
    async def _check_feature(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.is_admin:
            return current_user

        tier = _resolve_tier(current_user)
        features = get_features_for_tier(tier)

        if not hasattr(features, feature_name):
            logger.error(
                "invalid_feature_gate",
                feature=feature_name,
                user_id=str(current_user.user_id),
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "RAIN-E999",
                    "message": f"Internal error: unknown feature gate '{feature_name}'",
                },
            )

        if not getattr(features, feature_name):
            logger.info(
                "feature_gate_denied",
                feature=feature_name,
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "RAIN-B005",
                    "message": (
                        f"Feature '{feature_name}' is not available on the "
                        f"{tier.value} tier. Please upgrade your subscription."
                    ),
                },
            )

        return current_user

    return _check_feature


# ---------------------------------------------------------------------------
# FastAPI dependency: require_output_format
# ---------------------------------------------------------------------------

def require_output_format(format_name: str) -> Callable[..., Any]:
    """FastAPI dependency factory that gates an endpoint on an output format.

    Raises HTTPException 403 with code RAIN-B005 if the format is not
    available for the user's tier.
    """
    async def _check_format(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.is_admin:
            return current_user

        tier = _resolve_tier(current_user)
        features = get_features_for_tier(tier)

        if format_name not in features.output_formats:
            logger.info(
                "format_gate_denied",
                format=format_name,
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "RAIN-B005",
                    "message": (
                        f"Output format '{format_name}' is not available on the "
                        f"{tier.value} tier. Please upgrade your subscription."
                    ),
                },
            )

        return current_user

    return _check_format


# ---------------------------------------------------------------------------
# FastAPI dependency: require_qc_check
# ---------------------------------------------------------------------------

def require_qc_check(check_id: int) -> Callable[..., Any]:
    """FastAPI dependency factory that gates a QC check by its numeric ID.

    Raises HTTPException 403 with code RAIN-B005 if the check is not
    available for the user's tier.
    """
    async def _check_qc(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.is_admin:
            return current_user

        tier = _resolve_tier(current_user)
        features = get_features_for_tier(tier)

        if check_id not in features.qc_checks:
            logger.info(
                "qc_check_gate_denied",
                check_id=check_id,
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "RAIN-B005",
                    "message": (
                        f"QC check #{check_id} is not available on the "
                        f"{tier.value} tier. Please upgrade your subscription."
                    ),
                },
            )

        return current_user

    return _check_qc


# ---------------------------------------------------------------------------
# FastAPI dependency: require_upload_size
# ---------------------------------------------------------------------------

def require_upload_size(content_length: int) -> Callable[..., Any]:
    """FastAPI dependency factory that gates upload by file size in bytes.

    Raises HTTPException 413 with code RAIN-B005 if the upload exceeds
    the tier's max_upload_bytes.
    """
    async def _check_size(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        if current_user.is_admin:
            return current_user

        tier = _resolve_tier(current_user)
        features = get_features_for_tier(tier)

        if content_length > features.max_upload_bytes:
            max_mb = features.max_upload_bytes // (1024 * 1024)
            logger.info(
                "upload_size_gate_denied",
                content_length=content_length,
                max_bytes=features.max_upload_bytes,
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "RAIN-B005",
                    "message": (
                        f"Upload size exceeds the {max_mb}MB limit for the "
                        f"{tier.value} tier. Please upgrade your subscription."
                    ),
                },
            )

        return current_user

    return _check_size


# ---------------------------------------------------------------------------
# FastAPI dependency: require_track_quota
# ---------------------------------------------------------------------------

def require_track_quota() -> Callable[..., Any]:
    """FastAPI dependency that checks the user has remaining download/render quota.

    Queries the usage_quotas table for the current billing period and compares
    against the tier's downloads_per_month limit.

    Raises HTTPException 429 with code RAIN-B002 if the quota is exhausted.
    Admin users bypass quota checks.

    Usage::

        @router.post("/sessions/{sid}/download")
        async def download_render(
            user: CurrentUser = Depends(require_track_quota()),
        ):
            ...
    """
    async def _check_quota(
        current_user: CurrentUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        if current_user.is_admin:
            return current_user

        tier = _resolve_tier(current_user)
        features = get_features_for_tier(tier)

        # Free tier has zero downloads — always deny
        if features.downloads_per_month == 0:
            logger.info(
                "track_quota_denied_free",
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RAIN-B002",
                    "message": (
                        "Downloads are not available on the free tier. "
                        "Please upgrade your subscription."
                    ),
                },
            )

        # Look up the user's current-period quota row
        now = sqla_func.now()
        stmt = (
            select(UsageQuota)
            .where(
                UsageQuota.user_id == current_user.user_id,
                UsageQuota.period_start <= now,
                UsageQuota.period_end > now,
            )
            .order_by(UsageQuota.period_start.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        quota: UsageQuota | None = result.scalar_one_or_none()

        if quota is None:
            # No quota row for this period — first usage, allow it
            logger.debug(
                "track_quota_no_row",
                user_id=str(current_user.user_id),
                tier=tier.value,
            )
            return current_user

        if quota.downloads_used >= features.downloads_per_month:
            logger.info(
                "track_quota_exceeded",
                user_id=str(current_user.user_id),
                tier=tier.value,
                downloads_used=quota.downloads_used,
                downloads_limit=features.downloads_per_month,
            )
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RAIN-B002",
                    "message": (
                        f"Monthly download quota reached ({quota.downloads_used}/"
                        f"{features.downloads_per_month}). Upgrade your tier or "
                        f"wait until the next billing period."
                    ),
                },
            )

        return current_user

    return _check_quota


# ---------------------------------------------------------------------------
# Utility: get available QC checks for a tier (non-dependency usage)
# ---------------------------------------------------------------------------

def get_qc_checks_for_tier(tier: SubscriptionTier) -> frozenset[int]:
    """Return the set of QC check IDs available for the given tier."""
    return get_features_for_tier(tier).qc_checks


def get_output_formats_for_tier(tier: SubscriptionTier) -> frozenset[str]:
    """Return the set of output format names available for the given tier."""
    return get_features_for_tier(tier).output_formats
