"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── facilities ────────────────────────────────────────────
    op.create_table(
        "facilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("location", sa.String(500)),
        sa.Column("city", sa.String(100)),
        sa.Column("country", sa.String(100), nullable=False, server_default="Pakistan"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Karachi"),
        sa.Column("api_key", sa.String(128), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── gates ─────────────────────────────────────────────────
    op.create_table(
        "gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("camera_rtsp", sa.String(500)),
        sa.Column("gate_type", sa.String(20), nullable=False, server_default="entry"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── vehicles ──────────────────────────────────────────────
    op.create_table(
        "vehicles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plate_number", sa.String(20), nullable=False),
        sa.Column("plate_country", sa.String(10), nullable=False, server_default="PK"),
        sa.Column("owner_name", sa.String(200)),
        sa.Column("owner_phone", sa.String(20)),
        sa.Column("vehicle_type", sa.String(50)),
        sa.Column("make", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("color", sa.String(50)),
        sa.Column("status", sa.String(20), nullable=False, server_default="approved"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("facility_id", "plate_number", name="uq_vehicles_facility_plate"),
    )
    op.create_index("idx_vehicles_plate", "vehicles", ["plate_number"])
    op.create_index("idx_vehicles_facility", "vehicles", ["facility_id"])
    op.create_index("idx_vehicles_status", "vehicles", ["status"])

    # ── employees ─────────────────────────────────────────────
    op.create_table(
        "employees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_code", sa.String(50)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("department", sa.String(100)),
        sa.Column("designation", sa.String(100)),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(200)),
        sa.Column("face_embedding", sa.Text()),  # stored as vector(512) via raw SQL below
        sa.Column("face_image_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("access_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # Alter face_embedding column to vector(512) after table creation
    op.execute("ALTER TABLE employees ALTER COLUMN face_embedding TYPE vector(512) USING face_embedding::vector")
    op.create_index("idx_employees_facility", "employees", ["facility_id"])
    op.execute(
        "CREATE INDEX idx_employees_face ON employees "
        "USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # ── visitors ──────────────────────────────────────────────
    op.create_table(
        "visitors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cnic", sa.String(20)),
        sa.Column("phone", sa.String(20)),
        sa.Column("purpose", sa.String(500)),
        sa.Column("host_employee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employees.id")),
        sa.Column("pre_approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("approved_from", sa.DateTime(timezone=True)),
        sa.Column("approved_until", sa.DateTime(timezone=True)),
        sa.Column("face_embedding", sa.Text()),
        sa.Column("face_image_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.execute("ALTER TABLE visitors ALTER COLUMN face_embedding TYPE vector(512) USING face_embedding::vector")
    op.create_index("idx_visitors_facility", "visitors", ["facility_id"])
    op.execute(
        "CREATE INDEX idx_visitors_approved ON visitors(facility_id, pre_approved, approved_until)"
    )

    # ── entry_logs ────────────────────────────────────────────
    op.create_table(
        "entry_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("gate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gates.id")),
        sa.Column("plate_number", sa.String(20)),
        sa.Column("plate_confidence", sa.Float()),
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vehicles.id")),
        sa.Column("vehicle_status", sa.String(20)),
        sa.Column("driver_employee_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("employees.id")),
        sa.Column("driver_visitor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("visitors.id")),
        sa.Column("driver_name", sa.String(200)),
        sa.Column("driver_confidence", sa.Float()),
        sa.Column("passenger_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("decision_reason", sa.String(500)),
        sa.Column("alert_sent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entry_time", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("exit_time", sa.DateTime(timezone=True)),
        sa.Column("capture_image_url", sa.String(500)),
        sa.Column("video_clip_url", sa.String(500)),
        sa.Column("synced_from_edge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("edge_created_at", sa.DateTime(timezone=True)),
    )
    op.execute("CREATE INDEX idx_logs_facility_time ON entry_logs(facility_id, entry_time DESC)")
    op.create_index("idx_logs_plate", "entry_logs", ["plate_number"])
    op.create_index("idx_logs_decision", "entry_logs", ["decision"])
    op.create_index("idx_logs_gate", "entry_logs", ["gate_id"])

    # ── edge_sync_queue ───────────────────────────────────────
    op.create_table(
        "edge_sync_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id"), nullable=False),
        sa.Column("gate_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gates.id")),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("synced_at", sa.DateTime(timezone=True)),
    )

    # ── users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("facility_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("facilities.id")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="guard"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Row-Level Security ────────────────────────────────────
    for table in ("vehicles", "employees", "visitors", "entry_logs", "gates"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # ── updated_at trigger ────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    for table in ("vehicles", "employees", "facilities"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated "
            f"BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION update_updated_at()"
        )


def downgrade() -> None:
    for table in ("vehicles", "employees", "facilities"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated ON {table}")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at")

    for table in ("users", "edge_sync_queue", "entry_logs", "visitors",
                  "employees", "vehicles", "gates", "facilities"):
        op.drop_table(table)
