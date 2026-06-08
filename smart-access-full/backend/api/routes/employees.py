from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
import uuid
import io
import numpy as np

from core.database import get_db
from models.models import Employee, User
from api.routes.auth import get_current_user, require_admin
from services.storage import upload_to_r2

router = APIRouter()


class EmployeeCreate(BaseModel):
    employee_code: str | None = None
    name: str
    department: str | None = None
    designation: str | None = None
    phone: str | None = None
    email: str | None = None
    access_level: int = 1


class EmployeeUpdate(BaseModel):
    name: str | None = None
    department: str | None = None
    designation: str | None = None
    phone: str | None = None
    email: str | None = None
    is_active: bool | None = None
    access_level: int | None = None


@router.get("/")
async def list_employees(
    search: str | None = None,
    department: str | None = None,
    is_active: bool = True,
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Employee).where(
        Employee.facility_id == current_user.facility_id,
        Employee.is_active == is_active,
    )
    if search:
        q = q.where(Employee.name.ilike(f"%{search}%"))
    if department:
        q = q.where(Employee.department == department)

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(Employee.name).offset((page - 1) * limit).limit(limit)
    )
    employees = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": str(e.id),
                "name": e.name,
                "employee_code": e.employee_code,
                "department": e.department,
                "designation": e.designation,
                "has_face": e.face_embedding is not None,
                "face_image_url": e.face_image_url,
            }
            for e in employees
        ],
    }


@router.post("/", status_code=201)
async def create_employee(
    body: EmployeeCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    employee = Employee(
        facility_id=current_user.facility_id,
        **body.model_dump(),
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return {"id": str(employee.id), "name": employee.name}


@router.post("/{employee_id}/enroll-face")
async def enroll_face(
    employee_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a clear face photo of the employee.
    Extracts InsightFace ArcFace embedding and stores it.
    """
    result = await db.execute(
        select(Employee).where(
            Employee.id == uuid.UUID(employee_id),
            Employee.facility_id == current_user.facility_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Read image bytes
    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")

    # Extract face embedding using InsightFace
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=(640, 640))

        img_array = np.frombuffer(contents, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        faces = app.get(img)
        if not faces:
            raise HTTPException(status_code=422, detail="No face detected in the uploaded image")
        if len(faces) > 1:
            raise HTTPException(status_code=422, detail="Multiple faces detected — upload a solo portrait")

        embedding = faces[0].normed_embedding.tolist()

    except ImportError:
        raise HTTPException(status_code=500, detail="InsightFace not installed on server")

    # Upload photo to R2
    image_url = await upload_to_r2(
        content=contents,
        key=f"employees/{employee_id}/face.jpg",
        content_type=file.content_type or "image/jpeg",
    )

    employee.face_embedding = embedding
    employee.face_image_url = image_url
    await db.commit()

    return {"message": "Face enrolled successfully", "employee_id": employee_id}


@router.patch("/{employee_id}")
async def update_employee(
    employee_id: str,
    body: EmployeeUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Employee).where(
            Employee.id == uuid.UUID(employee_id),
            Employee.facility_id == current_user.facility_id,
        )
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(employee, field, value)

    await db.commit()
    return {"id": str(employee.id), "name": employee.name}
