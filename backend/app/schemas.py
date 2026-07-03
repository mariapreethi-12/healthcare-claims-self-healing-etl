from datetime import date, datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MappingApproval(BaseModel):
    mapping: dict[str, str]


class RunSummary(ORMModel):
    id: str
    filename: str
    status: str
    mapping_source: str | None
    total_records: int
    accepted_records: int
    rejected_records: int
    created_at: datetime
    completed_at: datetime | None


class SchemaEventOut(ORMModel):
    id: str
    run_id: str
    source_column: str
    target_column: str | None
    event_type: str
    confidence: Decimal | None
    resolution: str
    created_at: datetime


class RunDetail(RunSummary):
    detected_columns: list[str]
    suggested_mapping: dict[str, str]
    approved_mapping: dict[str, str] | None
    error_message: str | None
    events: list[SchemaEventOut]


class ClaimOut(ORMModel):
    id: str
    run_id: str
    claim_id: str
    patient_id: str
    provider_id: str
    diagnosis_code: str
    procedure_code: str
    claim_amount: Decimal
    claim_date: date
    claim_status: str


class PaginatedClaims(BaseModel):
    items: list[ClaimOut]
    total: int
    page: int
    page_size: int


class Metrics(BaseModel):
    total_runs: int
    completed_runs: int
    pending_approval_runs: int
    total_claims: int
    rejected_claims: int
    acceptance_rate: float
    total_claim_amount: float
    schema_events: int
    status_breakdown: dict[str, int]
    recent_runs: list[RunSummary]


class UploadResponse(BaseModel):
    run: RunDetail
    message: str
