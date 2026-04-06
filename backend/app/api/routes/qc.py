"""
RAIN QC API — Quality Control endpoints

GET /api/v1/qc/platforms       — List all 27 platform targets
GET /api/v1/qc/{session}/report — Get QC report for a mastered session
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.platform_targets import list_platform_targets

router = APIRouter(prefix="/qc", tags=["quality-control"])


@router.get("/platforms")
async def get_platforms() -> list[dict]:
    """List all 27 platform loudness targets."""
    return list_platform_targets()
