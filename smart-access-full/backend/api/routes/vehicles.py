from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Literal
import uuid

from core.database import get_db
from models.models import Vehicle, User
from api.routes.auth import get_current_user, require_admin

router = APIRouter()


class VehicleCreate(BaseModel):
    plate_number: str
    plate_country: str = "PK"
    owner_name: str | None = None
    owner_phone: str | None = None
    vehicle_type: str | None = None
    make: str | None = None
    model: str | None = None
    color: str | None = None
    status: Literal["approved", "blacklisted", "suspended"] = "approved"
    notes: str | None = None


class VehicleUpdate(BaseModel):
    owner_name: str | None = None
    owner_phone: str | None = None
    status: Literal["approved", "blacklisted", "suspended"] | None = None
    notes: str | None = None


class VehicleOut(BaseModel):
    id: str
    facility_id: str
    plate_number: str
    plate_country: str
    owner_name: str | None
    owner_phone: str | None
    vehicle_type: str | None
    make: str | None
    model: str | None
    color: str | None
    status: str

    class Config:
        from_attributes = True


@router.get("/")
async def list_vehicles(
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Vehicle).where(Vehicle.facility_id == current_user.facility_id)

    if status:
        q = q.where(Vehicle.status == status)
    if search:
        q = q.where(Vehicle.plate_number.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    q = q.order_by(Vehicle.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(q)
    vehicles = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": str(v.id),
                "plate_number": v.plate_number,
                "status": v.status,
                "owner_name": v.owner_name,
                "vehicle_type": v.vehicle_type,
                "make": v.make,
                "color": v.color,
            }
            for v in vehicles
        ],
    }


@router.post("/", status_code=201)
async def create_vehicle(
    body: VehicleCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(
        select(Vehicle).where(
            Vehicle.facility_id == current_user.facility_id,
            Vehicle.plate_number == body.plate_number.upper().strip(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Plate number already registered")

    vehicle = Vehicle(
        facility_id=current_user.facility_id,
        plate_number=body.plate_number.upper().strip(),
        **body.model_dump(exclude={"plate_number"}),
    )
    db.add(vehicle)
    await db.commit()
    await db.refresh(vehicle)
    return {"id": str(vehicle.id), "plate_number": vehicle.plate_number}


@router.get("/{vehicle_id}")
async def get_vehicle(
    vehicle_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == uuid.UUID(vehicle_id),
            Vehicle.facility_id == current_user.facility_id,
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {
        "id": str(vehicle.id),
        "plate_number": vehicle.plate_number,
        "plate_country": vehicle.plate_country,
        "owner_name": vehicle.owner_name,
        "owner_phone": vehicle.owner_phone,
        "vehicle_type": vehicle.vehicle_type,
        "make": vehicle.make,
        "model": vehicle.model,
        "color": vehicle.color,
        "status": vehicle.status,
        "notes": vehicle.notes,
        "created_at": vehicle.created_at.isoformat(),
    }


@router.patch("/{vehicle_id}")
async def update_vehicle(
    vehicle_id: str,
    body: VehicleUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == uuid.UUID(vehicle_id),
            Vehicle.facility_id == current_user.facility_id,
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(vehicle, field, value)

    await db.commit()
    return {"id": str(vehicle.id), "status": vehicle.status}


@router.delete("/{vehicle_id}", status_code=204)
async def delete_vehicle(
    vehicle_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Vehicle).where(
            Vehicle.id == uuid.UUID(vehicle_id),
            Vehicle.facility_id == current_user.facility_id,
        )
    )
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    await db.delete(vehicle)
    await db.commit()
