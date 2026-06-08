from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime
import uuid

from core.database import get_db
from models.models import Visitor, User
from api.routes.auth import get_current_user, require_admin

router = APIRouter()


class VisitorCreate(BaseModel):
    name: str
    cnic: str | None = None
    phone: str | None = None
    purpose: str | None = None
    host_employee_id: str | None = None
    pre_approved: bool = False
    approved_from: datetime | None = None
    approved_until: datetime | None = None


class VisitorUpdate(BaseModel):
    pre_approved: bool | None = None
    approved_from: datetime | None = None
    approved_until: datetime | None = None
    purpose: str | None = None


@router.get("/")
async def list_visitors(
    search: str | None = None,
    active_only: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Visitor).where(Visitor.facility_id == current_user.facility_id)

    if search:
        q = q.where(Visitor.name.ilike(f"%{search}%"))
    if active_only:
        now = datetime.utcnow()
        q = q.where(
            Visitor.pre_approved == True,
            Visitor.approved_until >= now,
        )

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(Visitor.created_at.desc()).offset((page - 1) * limit).limit(limit)
    )
    visitors = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": str(v.id),
                "name": v.name,
                "cnic": v.cnic,
                "phone": v.phone,
                "purpose": v.purpose,
                "pre_approved": v.pre_approved,
                "approved_until": v.approved_until.isoformat() if v.approved_until else None,
                "has_face": v.face_embedding is not None,
            }
            for v in visitors
        ],
    }


@router.post("/", status_code=201)
async def create_visitor(
    body: VisitorCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    visitor = Visitor(
        facility_id=current_user.facility_id,
        name=body.name,
        cnic=body.cnic,
        phone=body.phone,
        purpose=body.purpose,
        host_employee_id=uuid.UUID(body.host_employee_id) if body.host_employee_id else None,
        pre_approved=body.pre_approved,
        approved_from=body.approved_from,
        approved_until=body.approved_until,
    )
    db.add(visitor)
    await db.commit()
    await db.refresh(visitor)
    return {"id": str(visitor.id), "name": visitor.name}


@router.patch("/{visitor_id}/approve")
async def approve_visitor(
    visitor_id: str,
    body: VisitorUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Grant or revoke pre-approval for a visitor."""
    result = await db.execute(
        select(Visitor).where(
            Visitor.id == uuid.UUID(visitor_id),
            Visitor.facility_id == current_user.facility_id,
        )
    )
    visitor = result.scalar_one_or_none()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(visitor, field, value)

    await db.commit()
    return {
        "id": str(visitor.id),
        "pre_approved": visitor.pre_approved,
        "approved_until": visitor.approved_until.isoformat() if visitor.approved_until else None,
    }


@router.get("/active")
async def active_visitors(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All visitors with a currently active pre-approval."""
    now = datetime.utcnow()
    result = await db.execute(
        select(Visitor).where(
            Visitor.facility_id == current_user.facility_id,
            Visitor.pre_approved == True,
            Visitor.approved_until >= now,
        ).order_by(Visitor.approved_until)
    )
    visitors = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "name": v.name,
            "purpose": v.purpose,
            "approved_until": v.approved_until.isoformat(),
        }
        for v in visitors
    ]
