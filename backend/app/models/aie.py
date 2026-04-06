"""AIE (Artist Identity Engine) profile model.

DEPRECATION NOTICE:
  This model (AIEProfile → aie_profiles table) is the LEGACY AIE system.
  The canonical AIE is the 64-dim aie_vectors table (migration 0003) with
  strict Pydantic validation in services/aie_vector.py.

  Migration path:
  1. New sessions use aie_vectors via update_vector_from_session task
  2. Old sessions still read AIEProfile via render.py artist_vec lookup
  3. Once aie_vectors has data for a user, it takes priority
  4. AIEProfile will be removed in a future migration after data is migrated

  DO NOT add new features to AIEProfile. Use aie_vectors + aie_vector.py.
"""
from sqlalchemy import String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, REAL, JSONB
from sqlalchemy.sql import func
import uuid
import numpy as np
from app.core.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from typing import Optional
from datetime import datetime


def validate_voice_vector(v: list[float]) -> list[float]:
    """
    Enforce voice vector invariants before every DB write.
    - Length must be 64
    - All values clamped to [-1.0, 1.0]
    - L2-normalized (‖v‖₂ = 1.0 ± 1e-6)
    Returns the validated, normalized vector.
    Raises ValueError if length ≠ 64.
    """
    if len(v) != 64:
        raise ValueError(f"Voice vector length must be 64, got {len(v)}")
    arr = np.clip(np.array(v, dtype=np.float64), -1.0, 1.0)
    norm = np.linalg.norm(arr)
    if norm < 1e-8:
        raise ValueError("Voice vector is near-zero — cannot normalize (cold-start vectors must not be written through validate_voice_vector)")
    arr = arr / norm
    return arr.tolist()


class AIEProfile(Base):
    __tablename__ = "aie_profiles"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    voice_vector: Mapped[Optional[list]] = mapped_column(ARRAY(REAL), nullable=True)
    session_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    genre_distribution: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    platform_preferences: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=dict)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
