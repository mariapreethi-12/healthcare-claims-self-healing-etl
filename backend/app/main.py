import io
from contextlib import asynccontextmanager
import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload
from .config import get_settings
from .database import Base, engine, get_db
from .mapping import EXPECTED_COLUMNS, suggest_mapping
from .models import Claim, PipelineRun, RejectedClaim, SchemaEvent
from .pipeline import process_run
from .schemas import ClaimOut, MappingApproval, Metrics, PaginatedClaims, RunDetail, RunSummary, SchemaEventOut, UploadResponse


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Healthcare Claims Self-Healing ETL", version="1.0.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[item.strip() for item in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def run_or_404(db: Session, run_id: str) -> PipelineRun:
    run = db.scalar(select(PipelineRun).options(selectinload(PipelineRun.events)).where(PipelineRun.id == run_id))
    if not run:
        raise HTTPException(404, "Pipeline run not found")
    return run


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/upload", response_model=UploadResponse, status_code=201)
async def upload(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit")
    try:
        text = content.decode("utf-8-sig")
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        columns = frame.columns.tolist()
        rows = frame.to_dict(orient="records")
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise HTTPException(400, f"Could not parse CSV: {exc}") from exc
    if not columns:
        raise HTTPException(400, "CSV must contain a header row")
    if len(rows) == 0:
        raise HTTPException(400, "CSV must contain at least one data row")

    mapping, confidence, source = suggest_mapping(columns)
    exact_schema = set(columns) == set(EXPECTED_COLUMNS) and len(columns) == len(EXPECTED_COLUMNS)
    run = PipelineRun(
        filename=file.filename, status="processing" if exact_schema else "awaiting_approval",
        mapping_source=source, detected_columns=columns, suggested_mapping=mapping,
        raw_records=rows, total_records=len(rows),
    )
    db.add(run)
    db.flush()
    for column in columns:
        target = mapping.get(column)
        if column not in EXPECTED_COLUMNS or target != column:
            db.add(SchemaEvent(
                run_id=run.id, source_column=column, target_column=target,
                event_type="renamed_column" if target else "unknown_column",
                confidence=confidence.get(column), resolution="suggested",
            ))
    db.commit()
    if exact_schema:
        run = process_run(db, run, {column: column for column in EXPECTED_COLUMNS})
        message = "Schema matched; records were validated and loaded."
    else:
        run = run_or_404(db, run.id)
        message = "Schema drift detected. Review and approve the suggested mapping."
    return UploadResponse(run=RunDetail.model_validate(run), message=message)


@app.get("/api/runs", response_model=list[RunSummary])
def list_runs(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    return db.scalars(select(PipelineRun).order_by(desc(PipelineRun.created_at)).limit(limit)).all()


@app.get("/api/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return run_or_404(db, run_id)


@app.post("/api/runs/{run_id}/approve-mapping", response_model=RunDetail)
def approve_mapping(run_id: str, payload: MappingApproval, db: Session = Depends(get_db)):
    run = run_or_404(db, run_id)
    if run.status != "awaiting_approval":
        raise HTTPException(409, "Only runs awaiting approval can be processed")
    try:
        return process_run(db, run, payload.mapping)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@app.get("/api/claims", response_model=PaginatedClaims)
def list_claims(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    status: str | None = None, search: str | None = None, db: Session = Depends(get_db),
):
    query = select(Claim)
    if status:
        query = query.where(Claim.claim_status == status.lower())
    if search:
        query = query.where(Claim.claim_id.ilike(f"%{search}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(desc(Claim.claim_date)).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedClaims(items=[ClaimOut.model_validate(item) for item in items], total=total, page=page, page_size=page_size)


@app.get("/api/schema-events", response_model=list[SchemaEventOut])
def schema_events(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    return db.scalars(select(SchemaEvent).order_by(desc(SchemaEvent.created_at)).limit(limit)).all()


@app.get("/api/metrics", response_model=Metrics)
def metrics(db: Session = Depends(get_db)):
    total_runs = db.scalar(select(func.count(PipelineRun.id))) or 0
    completed = db.scalar(select(func.count(PipelineRun.id)).where(PipelineRun.status == "completed")) or 0
    pending = db.scalar(select(func.count(PipelineRun.id)).where(PipelineRun.status == "awaiting_approval")) or 0
    claims = db.scalar(select(func.count(Claim.id))) or 0
    rejected = db.scalar(select(func.count(RejectedClaim.id))) or 0
    amount = db.scalar(select(func.coalesce(func.sum(Claim.claim_amount), 0))) or 0
    event_count = db.scalar(select(func.count(SchemaEvent.id))) or 0
    statuses = dict(db.execute(select(Claim.claim_status, func.count(Claim.id)).group_by(Claim.claim_status)).all())
    recent = db.scalars(select(PipelineRun).order_by(desc(PipelineRun.created_at)).limit(5)).all()
    return Metrics(
        total_runs=total_runs, completed_runs=completed, pending_approval_runs=pending,
        total_claims=claims, rejected_claims=rejected,
        acceptance_rate=round(claims / (claims + rejected) * 100, 1) if claims + rejected else 0,
        total_claim_amount=float(amount), schema_events=event_count, status_breakdown=statuses,
        recent_runs=[RunSummary.model_validate(run) for run in recent],
    )
