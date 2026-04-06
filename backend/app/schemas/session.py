from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class SessionCreateRequest(BaseModel):
    target_platform: str = "spotify"
    simple_mode: bool = True
    genre: Optional[str] = None
    ai_generated: bool = False
    ai_source: Optional[str] = None  # "suno", "udio", "other"


class FreeSessionResponse(BaseModel):
    """Response for free-tier uploads — no server-side processing."""
    status: str = "local_only"
    tier: str = "free"
    message: str = "Free-tier processing runs locally in WASM. No server-side rendering."
    file_hash: str
    target_platform: str
    genre: Optional[str] = None
    simple_mode: bool = True


class SessionResponse(BaseModel):
    id: UUID
    status: str
    tier_at_creation: str
    input_duration_ms: Optional[int] = None
    input_lufs: Optional[float] = None
    input_true_peak: Optional[float] = None
    output_lufs: Optional[float] = None
    output_true_peak: Optional[float] = None
    target_platform: Optional[str] = None
    rain_score: Optional[dict] = None
    rain_cert_id: Optional[UUID] = None
    error_code: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
