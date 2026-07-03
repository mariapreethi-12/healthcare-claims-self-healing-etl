import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="analyzing", index=True)
    mapping_source: Mapped[str | None] = mapped_column(String(30))
    detected_columns: Mapped[list] = mapped_column(JSON, default=list)
    suggested_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_mapping: Mapped[dict | None] = mapped_column(JSON)
    raw_records: Mapped[list] = mapped_column(JSON, default=list)
    total_records: Mapped[int] = mapped_column(default=0)
    accepted_records: Mapped[int] = mapped_column(default=0)
    rejected_records: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    events: Mapped[list["SchemaEvent"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class SchemaEvent(Base):
    __tablename__ = "schema_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    source_column: Mapped[str] = mapped_column(String(255))
    target_column: Mapped[str | None] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    resolution: Mapped[str] = mapped_column(String(40), default="suggested")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    run: Mapped[PipelineRun] = relationship(back_populates="events")


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    claim_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(100), index=True)
    provider_id: Mapped[str] = mapped_column(String(100), index=True)
    diagnosis_code: Mapped[str] = mapped_column(String(20))
    procedure_code: Mapped[str] = mapped_column(String(20))
    claim_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    claim_date: Mapped[date] = mapped_column(Date)
    claim_status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class RejectedClaim(Base):
    __tablename__ = "rejected_claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id"), index=True)
    row_number: Mapped[int]
    raw_data: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
