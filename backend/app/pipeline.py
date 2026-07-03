import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from sqlalchemy import select
from sqlalchemy.orm import Session
from .mapping import EXPECTED_COLUMNS
from .models import Claim, PipelineRun, RejectedClaim, SchemaEvent

ALLOWED_STATUSES = {"submitted", "pending", "approved", "denied", "paid", "rejected"}
CODE_PATTERN = re.compile(r"^[A-Za-z0-9.\-]{2,20}$")


def validate_mapping(mapping: dict[str, str], source_columns: list[str]) -> None:
    if any(source not in source_columns for source in mapping):
        raise ValueError("Mapping contains a source column not present in the file")
    if any(target not in EXPECTED_COLUMNS for target in mapping.values()):
        raise ValueError("Mapping contains an unsupported target column")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Each target column can only be mapped once")
    missing = set(EXPECTED_COLUMNS) - set(mapping.values())
    if missing:
        raise ValueError(f"Mapping is missing required columns: {', '.join(sorted(missing))}")


def normalize_and_validate(row: dict, mapping: dict[str, str]) -> tuple[dict, list[str]]:
    data = {target: str(row.get(source, "")).strip() for source, target in mapping.items()}
    errors = [f"{field} is required" for field in EXPECTED_COLUMNS if not data.get(field)]
    amount = None
    try:
        amount = Decimal(data.get("claim_amount", ""))
        if amount < 0:
            errors.append("claim_amount must be non-negative")
    except InvalidOperation:
        errors.append("claim_amount must be numeric")
    claim_date = None
    try:
        claim_date = datetime.strptime(data.get("claim_date", ""), "%Y-%m-%d").date()
    except ValueError:
        errors.append("claim_date must use YYYY-MM-DD")
    status = data.get("claim_status", "").lower()
    if status and status not in ALLOWED_STATUSES:
        errors.append(f"claim_status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}")
    for field in ("diagnosis_code", "procedure_code"):
        if data.get(field) and not CODE_PATTERN.match(data[field]):
            errors.append(f"{field} has an invalid format")
    data.update(claim_amount=amount, claim_date=claim_date, claim_status=status)
    return data, errors


def process_run(db: Session, run: PipelineRun, mapping: dict[str, str]) -> PipelineRun:
    validate_mapping(mapping, run.detected_columns)
    run.status = "processing"
    run.approved_mapping = mapping
    for event in run.events:
        event.target_column = mapping.get(event.source_column)
        event.resolution = "approved" if event.target_column else "ignored"

    accepted = rejected = 0
    for index, raw in enumerate(run.raw_records, start=2):
        normalized, reasons = normalize_and_validate(raw, mapping)
        claim_id = normalized.get("claim_id")
        if claim_id and db.scalar(select(Claim.id).where(Claim.claim_id == claim_id)):
            reasons.append("claim_id already exists")
        if reasons:
            db.add(RejectedClaim(run_id=run.id, row_number=index, raw_data=raw, reasons=sorted(set(reasons))))
            rejected += 1
        else:
            db.add(Claim(run_id=run.id, **normalized))
            db.flush()
            accepted += 1
    run.accepted_records = accepted
    run.rejected_records = rejected
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run
