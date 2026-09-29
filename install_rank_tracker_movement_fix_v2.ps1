$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backendFile = Join-Path $root "backend\rank_tracking.py"
$frontendFile = Join-Path $root "frontend\src\components\RankTracker.tsx"
if (-not (Test-Path $backendFile)) { throw "backend/rank_tracking.py not found: $backendFile" }
if (-not (Test-Path $frontendFile)) { throw "frontend/src/components/RankTracker.tsx not found: $frontendFile" }
function Replace-Exact([string]$Path,[string]$Old,[string]$New,[string]$Label) {
  $text=Get-Content -Raw -LiteralPath $Path
  $count=([regex]::Matches($text,[regex]::Escape($Old))).Count
  if($count -ne 1){throw "Expected exactly 1 match for '$Label' in $Path, found $count. Aborting."}
  Set-Content -LiteralPath $Path -Value $text.Replace($Old,$New) -Encoding UTF8
}
Replace-Exact $backendFile 'from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func' 'from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, String, func, text' 'SQLAlchemy imports'
Replace-Exact $backendFile @'
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="google_search_console")
'@ @'
    ctr: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    measurement_start_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    measurement_end_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    comparison_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comparison_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    comparison_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="google_search_console")
'@ 'snapshot period fields'
Replace-Exact $backendFile @'
def _serialize_keyword(db: Session, row: RankTrackingKeyword) -> dict[str, Any]:
    snapshots = (
        db.query(RankTrackingSnapshot)
        .filter(RankTrackingSnapshot.keyword_id == row.id)
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .limit(2)
        .all()
    )
    latest = snapshots[0] if snapshots else None
    previous = snapshots[1] if len(snapshots) > 1 else None
    position = latest.position if latest else None
    previous_position = previous.position if previous else None
    change = round(previous_position - position, 2) if position is not None and previous_position is not None else None
'@ @'
def _serialize_keyword(db: Session, row: RankTrackingKeyword) -> dict[str, Any]:
    latest = (
        db.query(RankTrackingSnapshot)
        .filter(RankTrackingSnapshot.keyword_id == row.id, RankTrackingSnapshot.status == "ok")
        .order_by(RankTrackingSnapshot.checked_at.desc())
        .first()
    )
    position = latest.position if latest else None
    # Only use an explicitly measured preceding GSC period. Legacy snapshots
    # have no period metadata, so movement remains null until the next refresh.
    previous_position = latest.comparison_position if latest else None
    change = round(previous_position - position, 2) if position is not None and previous_position is not None else None
'@ 'movement serialization'
Replace-Exact $backendFile @'
def _date_window(days: int = 90) -> tuple[str, str]:
    # GSC data can lag by a few days. Exclude the most recent 3 days.
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()
'@ @'
def _period_windows(days: int = 90) -> tuple[date, date, date, date]:
    """Return non-overlapping current and previous GSC comparison periods."""
    current_end = date.today() - timedelta(days=3)
    current_start = current_end - timedelta(days=days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=days - 1)
    return current_start, current_end, previous_start, previous_end


def _date_window(days: int = 90) -> tuple[str, str]:
    start, end, _, _ = _period_windows(days)
    return start.isoformat(), end.isoformat()
'@ 'period windows'
Replace-Exact $backendFile @'
async def _refresh_keyword(db: Session, row: RankTrackingKeyword, company_id: str) -> dict[str, Any]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=400, detail="Google Search Console is not connected. Connect it in Google Integration first.")

    site_url, available_sites = await _resolve_gsc_property(connection, db)
    start_date, end_date = _date_window(90)
    try:
        data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=start_date, end_date=end_date, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        snapshot = RankTrackingSnapshot(
            keyword_id=row.id, checked_at=datetime.now(UTC), position=data["position"],
            ranking_url=data["ranking_url"], clicks=data["clicks"], impressions=data["impressions"],
            ctr=data["ctr"], source="google_search_console", status="ok",
            error_message=None if data["position"] is not None else data["message"],
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)
        result = _serialize_keyword(db, row)
        result["measurement_property"] = site_url
        result["available_properties"] = available_sites
        result["date_range"] = {"start": start_date, "end": end_date}
        result["measurement_message"] = data["message"]
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        snapshot = RankTrackingSnapshot(
            keyword_id=row.id, checked_at=datetime.now(UTC), source="google_search_console",
            status="error", error_message=str(exc)[:1000],
        )
        db.add(snapshot)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Rank check failed: {exc}") from exc
'@ @'
async def _refresh_keyword(db: Session, row: RankTrackingKeyword, company_id: str) -> dict[str, Any]:
    connection = get_connection(db, company_id, "search_console")
    if connection is None:
        raise HTTPException(status_code=400, detail="Google Search Console is not connected. Connect it in Google Integration first.")

    site_url, available_sites = await _resolve_gsc_property(connection, db)
    current_start, current_end, previous_start, previous_end = _period_windows(90)
    current_start_text, current_end_text = current_start.isoformat(), current_end.isoformat()
    previous_start_text, previous_end_text = previous_start.isoformat(), previous_end.isoformat()
    try:
        current_data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=current_start_text, end_date=current_end_text, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        previous_data = await _query_gsc_keyword(
            connection, db, site_url=site_url, keyword=row.keyword,
            start_date=previous_start_text, end_date=previous_end_text, country=row.country,
            device=row.device, target_url=row.target_url,
        )
        snapshot = (
            db.query(RankTrackingSnapshot)
            .filter(
                RankTrackingSnapshot.keyword_id == row.id,
                RankTrackingSnapshot.measurement_start_date == current_start,
                RankTrackingSnapshot.measurement_end_date == current_end,
            )
            .order_by(RankTrackingSnapshot.checked_at.desc())
            .first()
        )
        if snapshot is None:
            snapshot = RankTrackingSnapshot(
                keyword_id=row.id,
                measurement_start_date=current_start,
                measurement_end_date=current_end,
                comparison_start_date=previous_start,
                comparison_end_date=previous_end,
            )
            db.add(snapshot)
        snapshot.checked_at = datetime.now(UTC)
        snapshot.position = current_data["position"]
        snapshot.ranking_url = current_data["ranking_url"]
        snapshot.clicks = current_data["clicks"]
        snapshot.impressions = current_data["impressions"]
        snapshot.ctr = current_data["ctr"]
        snapshot.comparison_position = previous_data["position"]
        snapshot.source = "google_search_console"
        snapshot.status = "ok"
        if current_data["position"] is None:
            snapshot.error_message = current_data["message"]
        elif previous_data["position"] is None:
            snapshot.error_message = f"Current period matched data, but comparison period has no Search Console position: {previous_data['message']}"
        else:
            snapshot.error_message = None
        db.commit()
        db.refresh(snapshot)
        result = _serialize_keyword(db, row)
        result["measurement_property"] = site_url
        result["available_properties"] = available_sites
        result["date_range"] = {"start": current_start_text, "end": current_end_text}
        result["comparison_date_range"] = {"start": previous_start_text, "end": previous_end_text}
        result["measurement_message"] = current_data["message"]
        result["comparison_message"] = previous_data["message"]
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        snapshot = RankTrackingSnapshot(
            keyword_id=row.id, checked_at=datetime.now(UTC), source="google_search_console",
            status="error", error_message=str(exc)[:1000],
        )
        db.add(snapshot)
        db.commit()
        raise HTTPException(status_code=502, detail=f"Rank check failed: {exc}") from exc
'@ 'GSC period comparison refresh'
Replace-Exact $backendFile @'
@router.get("/keywords/{keyword_id}/history")
def keyword_history(keyword_id: str, limit: int = Query(90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user); row = _get_keyword(db, company_id, keyword_id)
    snapshots = db.query(RankTrackingSnapshot).filter(RankTrackingSnapshot.keyword_id == row.id).order_by(RankTrackingSnapshot.checked_at.desc()).limit(limit).all()
    snapshots.reverse()
    return {"keyword": _serialize_keyword(db, row), "history": [{
        "id": item.id, "checked_at": item.checked_at.isoformat(), "position": item.position,
        "ranking_url": item.ranking_url, "clicks": item.clicks, "impressions": item.impressions,
        "ctr": item.ctr, "source": item.source, "status": item.status, "error_message": item.error_message,
    } for item in snapshots]}
'@ @'
@router.get("/keywords/{keyword_id}/history")
def keyword_history(keyword_id: str, limit: int = Query(90, ge=1, le=365), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    company_id = _company_id(current_user)
    row = _get_keyword(db, company_id, keyword_id)
    snapshots = db.query(RankTrackingSnapshot).filter(RankTrackingSnapshot.keyword_id == row.id).order_by(RankTrackingSnapshot.checked_at.desc()).limit(limit).all()
    snapshots.reverse()
    return {"keyword": _serialize_keyword(db, row), "history": [{
        "id": item.id, "checked_at": item.checked_at.isoformat(), "position": item.position,
        "ranking_url": item.ranking_url, "clicks": item.clicks, "impressions": item.impressions,
        "ctr": item.ctr, "source": item.source, "status": item.status, "error_message": item.error_message,
        "measurement_start_date": item.measurement_start_date.isoformat() if item.measurement_start_date else None,
        "measurement_end_date": item.measurement_end_date.isoformat() if item.measurement_end_date else None,
        "comparison_start_date": item.comparison_start_date.isoformat() if item.comparison_start_date else None,
        "comparison_end_date": item.comparison_end_date.isoformat() if item.comparison_end_date else None,
    } for item in snapshots]}
'@ 'history period metadata'
Replace-Exact $backendFile @'
@router.on_event("startup")
def ensure_rank_tracking_tables() -> None:
    RankTrackingKeyword.__table__.create(bind=engine, checkfirst=True)
    RankTrackingSnapshot.__table__.create(bind=engine, checkfirst=True)
'@ @'
@router.on_event("startup")
def ensure_rank_tracking_tables() -> None:
    RankTrackingKeyword.__table__.create(bind=engine, checkfirst=True)
    RankTrackingSnapshot.__table__.create(bind=engine, checkfirst=True)
    # Existing installations need idempotent column creation because CREATE TABLE
    # IF NOT EXISTS does not evolve an already-existing table.
    with engine.begin() as connection:
        for statement in (
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS measurement_start_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS measurement_end_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_start_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_end_date DATE",
            "ALTER TABLE rank_tracking_snapshots ADD COLUMN IF NOT EXISTS comparison_position DOUBLE PRECISION",
            "CREATE INDEX IF NOT EXISTS ix_rank_tracking_snapshots_keyword_measurement_period ON rank_tracking_snapshots (keyword_id, measurement_start_date, measurement_end_date)",
        ):
            connection.execute(text(statement))
'@ 'idempotent rank tracking schema upgrade'
Replace-Exact $frontendFile @'
interface HistoryPoint {
  checked_at: string;
  position: number | null;
  ranking_url: string | null;
}
'@ @'
interface HistoryPoint {
  checked_at: string;
  position: number | null;
  ranking_url: string | null;
  measurement_start_date?: string | null;
  measurement_end_date?: string | null;
  comparison_start_date?: string | null;
  comparison_end_date?: string | null;
}
'@ 'frontend history type'
Replace-Exact $frontendFile @'
function movementClass(change: number | null): string {
  if (change == null || change === 0) return "text-slate-500";
  return change > 0 ? "text-emerald-600" : "text-rose-600";
}
'@ @'
function movementClass(change: number | null): string {
  if (change == null || change === 0) return "text-slate-500";
  return change > 0 ? "text-emerald-600" : "text-rose-600";
}

function movementLabel(change: number | null): string {
  if (change == null) return "No comparison";
  if (change > 0) return "Improved";
  if (change < 0) return "Declined";
  return "Unchanged";
}
'@ 'frontend movement label'
Replace-Exact $frontendFile '<CardHeader><CardTitle>Tracked Keywords</CardTitle><CardDescription>Current position, previous snapshot, movement and ranking URL.</CardDescription></CardHeader>' '<CardHeader><CardTitle>Tracked Keywords</CardTitle><CardDescription>Current 90-day GSC average position compared with the preceding 90-day period.</CardDescription></CardHeader>' 'frontend table description'
Replace-Exact $frontendFile @'
                        <td className={`px-4 py-4 font-medium ${movementClass(item.change)}`}>{item.change == null ? "—" : <span className="inline-flex items-center gap-1">{item.change > 0 ? <ArrowUp className="size-3.5" /> : item.change < 0 ? <ArrowDown className="size-3.5" /> : null}{Math.abs(item.change).toFixed(1)}</span>}</td>
'@ @'
                        <td className={`px-4 py-4 font-medium ${movementClass(item.change)}`}>
                          {item.change == null ? "—" : <span className="inline-flex flex-col gap-0.5"><span className="inline-flex items-center gap-1">{item.change > 0 ? <ArrowUp className="size-3.5" /> : item.change < 0 ? <ArrowDown className="size-3.5" /> : null}{Math.abs(item.change).toFixed(1)}</span><span className="text-[10px] font-normal">{movementLabel(item.change)}</span></span>}
                        </td>
'@ 'frontend movement status'
Push-Location (Split-Path $backendFile)
try {
  if (Test-Path ".\.venv\Scripts\python.exe") { & ".\.venv\Scripts\python.exe" -m py_compile ".\rank_tracking.py" }
  else { & python -m py_compile ".\rank_tracking.py" }
  if ($LASTEXITCODE -ne 0) { throw "Python syntax validation failed." }
} finally { Pop-Location }
Write-Host "Rank Tracker movement fix applied successfully." -ForegroundColor Green
Write-Host "Current = latest completed 90-day GSC period; Previous = immediately preceding 90-day period."
Write-Host "Positive change = Improved; negative change = Declined; zero = Unchanged."
Write-Host "Restart Uvicorn and Vite, then click Check Rankings."
