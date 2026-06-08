import uuid
from datetime import datetime
from sqlalchemy import (
    String, Boolean, Integer, Float, Text,
    DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from core.database import Base


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(500))
    city: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Pakistan")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Karachi")
    api_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    gates: Mapped[list["Gate"]] = relationship(back_populates="facility")
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="facility")
    employees: Mapped[list["Employee"]] = relationship(back_populates="facility")


class Gate(Base):
    __tablename__ = "gates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    camera_rtsp: Mapped[str | None] = mapped_column(String(500))
    gate_type: Mapped[str] = mapped_column(String(20), default="entry")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    facility: Mapped["Facility"] = relationship(back_populates="gates")


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("facility_id", "plate_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"))
    plate_number: Mapped[str] = mapped_column(String(20), nullable=False)
    plate_country: Mapped[str] = mapped_column(String(10), default="PK")
    owner_name: Mapped[str | None] = mapped_column(String(200))
    owner_phone: Mapped[str | None] = mapped_column(String(20))
    vehicle_type: Mapped[str | None] = mapped_column(String(50))
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="approved")
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    facility: Mapped["Facility"] = relationship(back_populates="vehicles")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"))
    employee_code: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[str | None] = mapped_column(String(100))
    designation: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    face_embedding: Mapped[list[float] | None] = mapped_column(Vector(512))
    face_image_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    access_level: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    facility: Mapped["Facility"] = relationship(back_populates="employees")


class Visitor(Base):
    __tablename__ = "visitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cnic: Mapped[str | None] = mapped_column(String(20))
    phone: Mapped[str | None] = mapped_column(String(20))
    purpose: Mapped[str | None] = mapped_column(String(500))
    host_employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"))
    pre_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    face_embedding: Mapped[list[float] | None] = mapped_column(Vector(512))
    face_image_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntryLog(Base):
    __tablename__ = "entry_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("facilities.id"))
    gate_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("gates.id"))
    # vehicle
    plate_number: Mapped[str | None] = mapped_column(String(20))
    plate_confidence: Mapped[float | None] = mapped_column(Float)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"))
    vehicle_status: Mapped[str | None] = mapped_column(String(20))
    # persons
    driver_employee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("employees.id"))
    driver_visitor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("visitors.id"))
    driver_name: Mapped[str | None] = mapped_column(String(200))
    driver_confidence: Mapped[float | None] = mapped_column(Float)
    passenger_count: Mapped[int] = mapped_column(Integer, default=0)
    # decision
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(String(500))
    alert_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    # timestamps
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # media
    capture_image_url: Mapped[str | None] = mapped_column(String(500))
    video_clip_url: Mapped[str | None] = mapped_column(String(500))
    # edge sync
    synced_from_edge: Mapped[bool] = mapped_column(Boolean, default=False)
    edge_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    facility_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="guard")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
