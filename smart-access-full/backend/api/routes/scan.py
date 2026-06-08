from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
import uuid

from core.database import get_db
from models.models import Vehicle, Employee, Visitor, EntryLog, Facility
from api.routes.auth import verify_edge_api_key
from services.decision import DecisionEngine
from services.storage import upload_capture
from services.alerts import send_alert
from services.websocket_manager import ws_manager

router = APIRouter()


class PersonDetected(BaseModel):
    face_embedding: list[float] | None = None
    face_confidence: float | None = None


class ScanPayload(BaseModel):
    gate_id: str
    plate_number: str | None = None
    plate_confidence: float | None = None
    persons: list[PersonDetected] = []
    edge_timestamp: str | None = None   # ISO string from edge node


class ScanResult(BaseModel):
    log_id: str
    decision: str           # allowed | denied | allowed_with_alert
    decision_reason: str
    vehicle_status: str | None
    driver_name: str | None
    gate_action: str        # OPEN | KEEP_CLOSED


@router.post("/", response_model=ScanResult)
async def process_scan(
    payload: ScanPayload,
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    # 1. Verify the edge node's API key and get its facility
    facility = await verify_edge_api_key(x_api_key, db)

    # 2. Look up the vehicle in DB
    vehicle = None
    vehicle_status = "unknown"
    if payload.plate_number:
        result = await db.execute(
            select(Vehicle).where(
                Vehicle.facility_id == facility.id,
                Vehicle.plate_number == payload.plate_number.upper().strip(),
            )
        )
        vehicle = result.scalar_one_or_none()
        vehicle_status = vehicle.status if vehicle else "unknown"

    # 3. Match faces against employees and visitors
    driver_employee = None
    driver_visitor = None
    driver_name = None
    driver_confidence = None

    if payload.persons and payload.persons[0].face_embedding:
        embedding = payload.persons[0].face_embedding
        confidence = payload.persons[0].face_confidence

        # pgvector cosine similarity search
        emp_result = await db.execute(
            select(Employee)
            .where(Employee.facility_id == facility.id, Employee.is_active == True)
            .order_by(Employee.face_embedding.cosine_distance(embedding))
            .limit(1)
        )
        best_emp = emp_result.scalar_one_or_none()

        if best_emp and confidence and confidence > 0.75:
            driver_employee = best_emp
            driver_name = best_emp.name
            driver_confidence = confidence
        else:
            # try visitors
            vis_result = await db.execute(
                select(Visitor)
                .where(
                    Visitor.facility_id == facility.id,
                    Visitor.pre_approved == True,
                    Visitor.approved_until >= datetime.utcnow(),
                )
                .order_by(Visitor.face_embedding.cosine_distance(embedding))
                .limit(1)
            )
            best_vis = vis_result.scalar_one_or_none()
            if best_vis and confidence and confidence > 0.75:
                driver_visitor = best_vis
                driver_name = best_vis.name
                driver_confidence = confidence

    # 4. Run decision engine
    engine = DecisionEngine()
    decision, reason = engine.decide(
        vehicle_status=vehicle_status,
        driver_employee=driver_employee,
        driver_visitor=driver_visitor,
    )

    # 5. Write to entry_logs
    log = EntryLog(
        facility_id=facility.id,
        gate_id=uuid.UUID(payload.gate_id) if payload.gate_id else None,
        plate_number=payload.plate_number,
        plate_confidence=payload.plate_confidence,
        vehicle_id=vehicle.id if vehicle else None,
        vehicle_status=vehicle_status,
        driver_employee_id=driver_employee.id if driver_employee else None,
        driver_visitor_id=driver_visitor.id if driver_visitor else None,
        driver_name=driver_name,
        driver_confidence=driver_confidence,
        passenger_count=max(0, len(payload.persons) - 1),
        decision=decision,
        decision_reason=reason,
        synced_from_edge=True,
        edge_created_at=datetime.fromisoformat(payload.edge_timestamp) if payload.edge_timestamp else None,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)

    # 6. Push real-time event to dashboard via WebSocket
    await ws_manager.broadcast_to_facility(
        facility_id=str(facility.id),
        message={
            "type": "scan_result",
            "log_id": str(log.id),
            "decision": decision,
            "plate": payload.plate_number,
            "driver": driver_name,
            "timestamp": log.entry_time.isoformat(),
        }
    )

    # 7. Send alert if needed
    if decision in ("denied", "allowed_with_alert"):
        await send_alert(facility=facility, log=log, reason=reason)

    return ScanResult(
        log_id=str(log.id),
        decision=decision,
        decision_reason=reason,
        vehicle_status=vehicle_status,
        driver_name=driver_name,
        gate_action="OPEN" if decision == "allowed" else "KEEP_CLOSED",
    )
