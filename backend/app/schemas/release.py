"""Release request/response schemas."""
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ReleaseCreateRequest(BaseModel):
    session_id: UUID
    title: str
    artist_name: str
    genre: str = "default"
    release_date: str  # YYYY-MM-DD
    territory: str = "Worldwide"
    label_name: str = "ARCOVEL RAIN Distribution"
    explicit: bool = False
    ai_generated: bool = False
    ai_source: Optional[str] = None  # "suno", "udio", "other"
    isrc: Optional[str] = None  # Pre-assigned ISRC; auto-generated if omitted


class ReleaseResponse(BaseModel):
    id: UUID
    session_id: UUID
    title: str
    artist_name: str
    isrc: str
    upc: str
    genre: Optional[str]
    status: str
    labelgrid_release_id: Optional[str] = None
    labelgrid_status: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
