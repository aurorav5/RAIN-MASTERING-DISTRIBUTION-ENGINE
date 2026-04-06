"""ContentScan model — three-layer content verification results."""
import sqlalchemy as sa
from sqlalchemy import String, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.sql import func
import uuid
from app.core.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from typing import Optional
from datetime import datetime


class ContentScan(Base):
    __tablename__ = "content_scans"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    chromaprint_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acoustid_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    audd_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    acrcloud_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    overall_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    match_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    match_artist: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    match_confidence: Mapped[Optional[float]] = mapped_column(sa.Numeric(4, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
