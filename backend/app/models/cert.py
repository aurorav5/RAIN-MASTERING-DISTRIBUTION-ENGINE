"""RAIN-CERT provenance certificate model."""
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import func
import uuid
from app.core.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from typing import Optional
from datetime import datetime


class RainCert(Base):
    __tablename__ = "rain_certs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    input_hash: Mapped[str] = mapped_column(String, nullable=False)
    output_hash: Mapped[str] = mapped_column(String, nullable=False)
    wasm_hash: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    processing_params_hash: Mapped[str] = mapped_column(String, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content_scan_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
