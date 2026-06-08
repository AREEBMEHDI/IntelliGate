from fastapi import APIRouter, Depends, Query, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime, date
import uuid

from core.database import get_db
from models.models import EntryLog, Vehicle, Employee, User, Facility
from api.routes.auth import get_current_user, verify_edge_api_key

router = APIRouter()


@router.get("/")
async def list_logs(
    date_from: date | None = None,
    date_to: date | None = None,
    decision: str | None = None,
    plate: str | None = None,
    gate_id: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(100, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(EntryLog).where(EntryLog.facility_id == current_user.facility_id)

    if date_from:
        q = q.where(EntryLog.entry_time >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(EntryLog.entry_time <= datetime.combine(date_to, datetime.max.time()))
    if decision:
        q = q.where(EntryLog.decision == decision)
    if plate:
        q = q.where(EntryLog.plate_number.ilike(f"%{plate}%"))
    if gate_id:
        q = q.where(EntryLog.gate_id == uuid.UUID(gate_id))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(EntryLog.entry_time.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": str(log.id),
                "plate_number": log.plate_number,
                "plate_confidence": log.plate_confidence,
                "driver_name": log.driver_name,
                "driver_confidence": log.driver_confidence,
                "vehicle_status": log.vehicle_status,
                "decision": log.decision,
                "decision_reason": log.decision_reason,
                "entry_time": log.entry_time.isoformat(),
                "exit_time": log.exit_time.isoformat() if log.exit_time else None,
                "capture_image_url": log.capture_image_url,
                "alert_sent": log.alert_sent,
            }
            for log in logs
        ],
    }


@router.get("/stats")
async def log_stats(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Summary stats for dashboard widgets."""
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=days)

    base = select(EntryLog).where(
        EntryLog.facility_id == current_user.facility_id,
        EntryLog.entry_time >= since,
    )

    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    allowed = await db.scalar(
        select(func.count()).select_from(
            base.where(EntryLog.decision == "allowed").subquery()
        )
    )
    denied = await db.scalar(
        select(func.count()).select_from(
            base.where(EntryLog.decision == "denied").subquery()
        )
    )
    alerts = await db.scalar(
        select(func.count()).select_from(
            base.where(EntryLog.decision == "allowed_with_alert").subquery()
        )
    )

    return {
        "period_days": days,
        "total": total,
        "allowed": allowed,
        "denied": denied,
        "alerts": alerts,
        "allow_rate": round((allowed / total * 100), 1) if total else 0,
    }


@router.patch("/{log_id}/exit")
async def record_exit(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark exit time when vehicle leaves."""
    result = await db.execute(
        select(EntryLog).where(
            EntryLog.id == uuid.UUID(log_id),
            EntryLog.facility_id == current_user.facility_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Log not found")

    log.exit_time = datetime.utcnow()
    await db.commit()
    return {"exit_time": log.exit_time.isoformat()}


# ─── Whitelist endpoints for edge node sync ───────────────────

@router.get("/whitelist/plates", include_in_schema=False)
async def whitelist_plates(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Edge node calls this to sync its local plate cache."""
    facility = await verify_edge_api_key(x_api_key, db)
    result = await db.execute(
        select(Vehicle).where(Vehicle.facility_id == facility.id)
    )
    vehicles = result.scalars().all()
    return [
        {
            "plate_number": v.plate_number,
            "status": v.status,
            "owner_name": v.owner_name,
            "updated_at": v.updated_at.isoformat(),
        }
        for v in vehicles
    ]


@router.get("/whitelist/faces", include_in_schema=False)
async def whitelist_faces(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """Edge node calls this to sync face embeddings."""
    facility = await verify_edge_api_key(x_api_key, db)
    result = await db.execute(
        select(Employee).where(
            Employee.facility_id == facility.id,
            Employee.is_active == True,
            Employee.face_embedding.isnot(None),
        )
    )
    employees = result.scalars().all()
    return [
        {
            "employee_id": str(e.id),
            "name": e.name,
            "embedding": e.face_embedding,
            "is_active": e.is_active,
            "updated_at": e.updated_at.isoformat(),
        }
        for e in employees
    ]
