from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB, NUMERIC
from sqlalchemy.sql import func
import uuid
from app.core.database import Base
from sqlalchemy.orm import mapped_column, Mapped
from typing import Optional
from datetime import datetime


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_status", "user_id", "status"),
        Index("ix_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    tier_at_creation: Mapped[str] = mapped_column(String, nullable=False)
    input_file_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    input_file_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    input_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_lufs: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
    input_true_peak: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
    output_file_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    output_file_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    output_lufs: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
    output_true_peak: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
    target_platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    simple_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    genre: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    aie_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rain_score: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    rain_cert_id: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    wasm_binary_hash: Mapped[str] = mapped_column(String, nullable=False)
    rainnet_model_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    processing_params: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Idempotency gates (migration 0004)
    provenance_stamped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    aie_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stems_separated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stamped_output_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stamped_output_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    c2pa_manifest_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    audioseal_message_hex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    chromaprint_fingerprint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    measured_bpm: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
    measured_bpm_raw: Mapped[Optional[float]] = mapped_column(NUMERIC(6, 2), nullable=True)
