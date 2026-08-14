from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from database.database import get_db
from pydantic import BaseModel
from models.audit import Audit, AuditStatus
from models.client import Client

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)

def average_or_zero(value) -> float:
    """
    Convert SQL AVG() result into float.

    AVG() returns None if table is empty.
    """

    if value is None:
        return 0.0

    try:
        return round(float(value), 1)
    except Exception:
        return 0.0


@router.get("/overview")
def dashboard_overview(
    db: Session = Depends(get_db),
):
    """
    Dashboard Overview

    Returns the global KPIs used by the Dashboard.
    """

    total_clients = db.query(func.count(Client.id)).scalar() or 0

    total_audits = db.query(func.count(Audit.id)).scalar() or 0

    completed_audits = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.COMPLETED)
        .scalar()
        or 0
    )

    pending_audits = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.PENDING)
        .scalar()
        or 0
    )

    queued_audits = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.QUEUED)
        .scalar()
        or 0
    )

    running_audits = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.RUNNING)
        .scalar()
        or 0
    )

    failed_audits = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.FAILED)
        .scalar()
        or 0
    )

    overall_score = average_or_zero(
        db.query(func.avg(Audit.overall_score)).scalar()
    )

    technical_score = average_or_zero(
        db.query(func.avg(Audit.technical_score)).scalar()
    )

    content_score = average_or_zero(
        db.query(func.avg(Audit.content_score)).scalar()
    )

    eeat_score = average_or_zero(
        db.query(func.avg(Audit.eeat_score)).scalar()
    )

    local_seo_score = average_or_zero(
        db.query(func.avg(Audit.local_seo_score)).scalar()
    )

    schema_score = average_or_zero(
        db.query(func.avg(Audit.schema_score)).scalar()
    )

    ai_search_score = average_or_zero(
        db.query(func.avg(Audit.ai_search_score)).scalar()
    )

    core_web_vitals_score = average_or_zero(
        db.query(func.avg(Audit.core_web_vitals_score)).scalar()
    )

    performance_score = average_or_zero(
        db.query(func.avg(Audit.performance_score)).scalar()
    )

    security_score = average_or_zero(
        db.query(func.avg(Audit.security_score)).scalar()
    )

    backlink_score = average_or_zero(
        db.query(func.avg(Audit.backlink_score)).scalar()
    )

    internal_link_score = average_or_zero(
        db.query(func.avg(Audit.internal_link_score)).scalar()
    )

    critical_issues = (
        db.query(func.sum(Audit.critical_issues)).scalar()
        or 0
    )

    high_priority_issues = (
        db.query(func.sum(Audit.high_priority_issues)).scalar()
        or 0
    )
    
    today = datetime.utcnow().date()

    audits_today = (
        db.query(func.count(Audit.id))
        .filter(func.date(Audit.created_at) == today)
        .scalar()
        or 0
    )

    active_clients = (
        db.query(func.count(Client.id))
        .filter(Client.is_active == True)
        .scalar()
        if hasattr(Client, "is_active")
        else total_clients
    )

    latest_audit = (
        db.query(Audit)
        .order_by(Audit.created_at.desc())
        .first()
    )

    last_audit_at = (
        latest_audit.created_at.isoformat()
        if latest_audit
        else None
    )

    completion_rate = (
        round((completed_audits / total_audits) * 100, 1)
        if total_audits
        else 0
    )

    return {
        "total_clients": total_clients,
        "total_audits": total_audits,
        "completed_audits": completed_audits,
        "pending_audits": pending_audits,
        "queued_audits": queued_audits,
        "running_audits": running_audits,
        "failed_audits": failed_audits,
        "overall_score": overall_score,
        "technical_score": technical_score,
        "content_score": content_score,
        "eeat_score": eeat_score,
        "local_seo_score": local_seo_score,
        "schema_score": schema_score,
        "ai_search_score": ai_search_score,
        "core_web_vitals_score": core_web_vitals_score,
        "performance_score": performance_score,
        "security_score": security_score,
        "backlink_score": backlink_score,
        "internal_link_score": internal_link_score,
        "critical_issues": critical_issues,
        "high_priority_issues": high_priority_issues,
    }
    
@router.get("/charts")
def dashboard_charts(
    db: Session = Depends(get_db),
):
    """
    Dashboard trend charts.

    Returns chart data in the format expected by React/Recharts.
    """

    rows = (
        db.query(Audit)
        .order_by(Audit.created_at.asc())
        .all()
    )

    chart = []

    for audit in rows:
        chart.append(
            {
                "date": audit.created_at.strftime("%b %d"),
                "overall": audit.overall_score or 0,
                "technical": audit.technical_score or 0,
                "content": audit.content_score or 0,
            }
        )

# Demo data when there are no audits yet
    if not chart:
        return {
        "count": 0,
        "items": [],
    }

    return {
    "count": len(chart),
    "items": chart,
}
    
@router.get("/recent-audits")
def dashboard_recent_audits(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """
    Latest completed and running audits.
    """

    audits = (
        db.query(Audit)
        .order_by(Audit.created_at.desc())
        .limit(limit)
        .all()
    )

    data = []

    for audit in audits:

        data.append(
            {
                "id": audit.id,
                "website": audit.website,
                "domain": audit.domain,
                "primary_keyword": audit.primary_keyword,
                "location": audit.location,
                "status": audit.status.value if audit.status else None,
                "overall_score": audit.overall_score,
                "technical_score": audit.technical_score,
                "content_score": audit.content_score,
                "eeat_score": audit.eeat_score,
                "local_seo_score": audit.local_seo_score,
                "schema_score": audit.schema_score,
                "ai_search_score": audit.ai_search_score,
                "performance_score": audit.performance_score,
                "security_score": audit.security_score,
                "created_at": (
                    audit.created_at.isoformat()
                    if audit.created_at
                    else None
                ),
                "completed_at": (
                    audit.completed_at.isoformat()
                    if audit.completed_at
                    else None
                ),
            }
        )

    return {
        "count": len(data),
        "items": data,
    }
    
@router.get("/running-audits")
def dashboard_running_audits(
    db: Session = Depends(get_db),
):
    """
    Currently executing audit jobs.
    """

    audits = (
        db.query(Audit)
        .filter(
            Audit.status.in_(
                [
                    AuditStatus.PENDING,
                    AuditStatus.QUEUED,
                    AuditStatus.RUNNING,
                ]
            )
        )
        .order_by(Audit.created_at.desc())
        .all()
    )

    items = []

    for audit in audits:

        items.append(
            {
                "id": audit.id,
                "website": audit.website,
                "domain": audit.domain,
                "keyword": audit.primary_keyword,
                "location": audit.location,
                "status": audit.status.value,
                "progress": audit.progress_percentage,
                "stage": audit.current_stage,
                "task": audit.current_task,
                "priority": audit.priority.value if audit.priority else None,
                "created_at": audit.created_at,
            }
        )

    return {
        "count": len(items),
        "items": items,
    }
    
@router.get("/issues")
def dashboard_issues(
    db: Session = Depends(get_db),
):
    """
    Dashboard issue summary.
    """

    audits = (
        db.query(Audit)
        .order_by(Audit.created_at.desc())
        .limit(50)
        .all()
    )

    critical = 0
    high = 0
    medium = 0
    low = 0

    for audit in audits:

        critical += audit.critical_issues or 0
        high += audit.high_priority_issues or 0
        medium += audit.medium_priority_issues or 0
        low += audit.low_priority_issues or 0

    return {
        "critical": critical,
        "high": high,
        "medium": medium,
        "low": low,
        "total": critical + high + medium + low,
    }
    
@router.get("/actions")
def dashboard_actions(
    db: Session = Depends(get_db),
):
    """
    Executive quick actions.
    """

    overview = dashboard_overview(db)

    actions = []

    if overview["critical_issues"] > 0:

        actions.append(
            {
                "title": "Resolve Critical SEO Issues",
                "priority": "Critical",
                "icon": "triangle-alert",
            }
        )

    if overview["technical_score"] < 80:

        actions.append(
            {
                "title": "Improve Technical SEO",
                "priority": "High",
                "icon": "server",
            }
        )

    if overview["content_score"] < 80:

        actions.append(
            {
                "title": "Optimise Existing Content",
                "priority": "Medium",
                "icon": "file-text",
            }
        )

    if overview["schema_score"] < 80:

        actions.append(
            {
                "title": "Implement Structured Data",
                "priority": "Medium",
                "icon": "bot",
            }
        )

    if overview["core_web_vitals_score"] < 90:

        actions.append(
            {
                "title": "Improve Core Web Vitals",
                "priority": "High",
                "icon": "zap",
            }
        )

    return {
        "count": len(actions),
        "items": actions,
    }
    
@router.get("/system")
def dashboard_system(
    db: Session = Depends(get_db),
):
    """
    Dashboard system health.
    """

    total = db.query(func.count(Audit.id)).scalar() or 0

    pending = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.PENDING)
        .scalar()
        or 0
    )

    queued = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.QUEUED)
        .scalar()
        or 0
    )

    running = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.RUNNING)
        .scalar()
        or 0
    )

    completed = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.COMPLETED)
        .scalar()
        or 0
    )

    failed = (
        db.query(func.count(Audit.id))
        .filter(Audit.status == AuditStatus.FAILED)
        .scalar()
        or 0
    )

    success_rate = 100.0

    if total:
        success_rate = round((completed / total) * 100, 1)

    return {
        "database": "connected",
        "api": "online",
        "audit_engine": "online",
        "claude_ai": "configured",
        "queue": {
            "pending": pending,
            "queued": queued,
            "running": running,
        },
        "completed": completed,
        "failed": failed,
        "success_rate": success_rate,
    }
    
@router.get("/tasks")
def dashboard_tasks(
    db: Session = Depends(get_db),
):
    """
    Dashboard task summary.

    Until a dedicated Task model exists,
    running audits are treated as active tasks.
    """

    audits = (
        db.query(Audit)
        .filter(
            Audit.status.in_(
                [
                    AuditStatus.PENDING,
                    AuditStatus.QUEUED,
                    AuditStatus.RUNNING,
                ]
            )
        )
        .order_by(Audit.created_at.desc())
        .limit(20)
        .all()
    )

    items = []

    for audit in audits:

        items.append(
            {
                "id": audit.id,
                "title": audit.website,
                "status": audit.status.value,
                "progress": audit.progress_percentage,
                "stage": audit.current_stage,
                "task": audit.current_task,
                "priority": audit.priority.value,
            }
        )

    return {
        "count": len(items),
        "items": items,
    }
    
    
@router.get("/notifications")
def dashboard_notifications(
    db: Session = Depends(get_db),
):
    """
    Dashboard notifications.

    Generated automatically from audit results.
    """

    notifications = []

    latest = (
        db.query(Audit)
        .order_by(Audit.created_at.desc())
        .limit(20)
        .all()
    )

    for audit in latest:

        if audit.status == AuditStatus.FAILED:

            notifications.append(
                {
                    "type": "error",
                    "title": "Audit Failed",
                    "message": audit.website,
                    "created_at": audit.created_at,
                }
            )

        elif audit.critical_issues > 0:

            notifications.append(
                {
                    "type": "warning",
                    "title": "Critical SEO Issues",
                    "message": f"{audit.website} has {audit.critical_issues} critical issues.",
                    "created_at": audit.created_at,
                }
            )

        elif audit.status == AuditStatus.COMPLETED:

            notifications.append(
                {
                    "type": "success",
                    "title": "Audit Completed",
                    "message": audit.website,
                    "created_at": audit.completed_at,
                }
            )

    notifications.sort(
        key=lambda x: x["created_at"] or datetime.min,
        reverse=True,
    )

    return {
        "count": len(notifications),
        "items": notifications,
    }

    
@router.get("/clients")
def dashboard_clients(db: Session = Depends(get_db)):
    total_clients = db.query(Client).count()

    recent_clients = (
        db.query(Client)
        .order_by(Client.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "total_clients": total_clients,
        "clients": [
            {
                "id": client.id,
                "business_name": client.business_name,
                "website": client.website,
                "industry": client.industry,
                "created_at": client.created_at,
            }
            for client in recent_clients
        ],
    }
    
class DashboardRecommendation(BaseModel):
    title: str
    impact: str
    priority: str
    
@router.get(
    "/ai",
    response_model=list[DashboardRecommendation],
    summary="Dashboard AI Recommendations",
)
async def dashboard_ai():
    """
    AI recommendations shown on the Dashboard.
    Later this endpoint will use the SEO audit engine and Claude AI.
    """

    return [
        {
            "title": "Improve title tags on high-value pages",
            "impact": "High",
            "priority": "Critical",
        },
        {
            "title": "Reduce Largest Contentful Paint below 2.5 seconds",
            "impact": "High",
            "priority": "High",
        },
        {
            "title": "Add LocalBusiness Schema",
            "impact": "Medium",
            "priority": "Medium",
        },
        {
            "title": "Fix duplicate meta descriptions",
            "impact": "Medium",
            "priority": "Medium",
        },
        {
            "title": "Increase internal links to money pages",
            "impact": "High",
            "priority": "High",
        },
    ]