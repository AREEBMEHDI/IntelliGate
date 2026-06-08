from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import uuid
import secrets

from core.database import get_db
from models.models import Facility, User
from api.routes.auth import require_admin

router = APIRouter()


class FacilityCreate(BaseModel):
    name: str
    location: str | None = None
    city: str | None = None
    country: str = "Pakistan"
    timezone: str = "Asia/Karachi"


@router.get("/")
async def list_facilities(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "superadmin":
        # Admins only see their own facility
        result = await db.execute(
            select(Facility).where(Facility.id == current_user.facility_id)
        )
    else:
        result = await db.execute(select(Facility).order_by(Facility.name))

    facilities = result.scalars().all()
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "location": f.location,
            "city": f.city,
            "is_active": f.is_active,
        }
        for f in facilities
    ]


@router.post("/", status_code=201)
async def create_facility(
    body: FacilityCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    api_key = secrets.token_urlsafe(48)  # 64-char secure key for edge node

    facility = Facility(
        name=body.name,
        location=body.location,
        city=body.city,
        country=body.country,
        timezone=body.timezone,
        api_key=api_key,
    )
    db.add(facility)
    await db.commit()
    await db.refresh(facility)

    return {
        "id": str(facility.id),
        "name": facility.name,
        "api_key": api_key,  # only shown once — tell client to save this
    }


@router.post("/{facility_id}/rotate-key")
async def rotate_api_key(
    facility_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for the facility's edge node."""
    if current_user.role != "superadmin":
        raise HTTPException(status_code=403, detail="Superadmin only")

    result = await db.execute(
        select(Facility).where(Facility.id == uuid.UUID(facility_id))
    )
    facility = result.scalar_one_or_none()
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    new_key = secrets.token_urlsafe(48)
    facility.api_key = new_key
    await db.commit()

    return {"api_key": new_key, "warning": "Update .env on edge node immediately"}
