from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.disaster_report import DisasterReport
from app.schemas.report import ReportListResponse, ReportResponse

router = APIRouter()


@router.get("/reports", response_model=ReportListResponse)
def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.query(DisasterReport).count()
    reports = (
        db.query(DisasterReport)
        .order_by(DisasterReport.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        ReportResponse(
            id=r.id,
            event_id=r.event_id,
            reporter_name=r.reporter_name,
            reporter_phone=r.reporter_phone,
            raw_message=r.raw_message,
            extracted_data=r.extracted_data,
            location_text=r.location_text,
            geocoded_address=r.geocoded_address,
            created_at=r.created_at,
        )
        for r in reports
    ]
    return {"items": items, "total": total}


@router.get("/reports/{report_id}", response_model=ReportResponse)
def get_report(report_id: UUID, db: Session = Depends(get_db)):
    report = db.query(DisasterReport).filter(DisasterReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ReportResponse(
        id=report.id,
        event_id=report.event_id,
        reporter_name=report.reporter_name,
        reporter_phone=report.reporter_phone,
        raw_message=report.raw_message,
        extracted_data=report.extracted_data,
        location_text=report.location_text,
        geocoded_address=report.geocoded_address,
        created_at=report.created_at,
    )
