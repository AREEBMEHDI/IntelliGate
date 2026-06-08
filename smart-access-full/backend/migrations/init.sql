-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────
-- FACILITIES  (one row per physical location)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS facilities (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name          VARCHAR(200) NOT NULL,
    location      VARCHAR(500),
    city          VARCHAR(100),
    country       VARCHAR(100) DEFAULT 'Pakistan',
    timezone      VARCHAR(50)  DEFAULT 'Asia/Karachi',
    api_key       VARCHAR(128) UNIQUE NOT NULL,   -- edge node uses this
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- GATES  (one facility can have multiple gates)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS gates (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id   UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    name          VARCHAR(100) NOT NULL,          -- e.g. "Main Entrance", "Gate B"
    camera_rtsp   VARCHAR(500),                   -- rtsp://192.168.1.x:554/stream
    gate_type     VARCHAR(20) DEFAULT 'entry',    -- entry | exit | both
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- VEHICLES
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vehicles (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id   UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    plate_number  VARCHAR(20) NOT NULL,
    plate_country VARCHAR(10) DEFAULT 'PK',
    owner_name    VARCHAR(200),
    owner_phone   VARCHAR(20),
    vehicle_type  VARCHAR(50),                    -- car | truck | motorcycle | van
    make          VARCHAR(100),
    model         VARCHAR(100),
    color         VARCHAR(50),
    status        VARCHAR(20) DEFAULT 'approved', -- approved | blacklisted | suspended
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(facility_id, plate_number)
);

CREATE INDEX idx_vehicles_plate ON vehicles(plate_number);
CREATE INDEX idx_vehicles_facility ON vehicles(facility_id);
CREATE INDEX idx_vehicles_status ON vehicles(status);

-- ─────────────────────────────────────────────
-- EMPLOYEES
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employees (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id     UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    employee_code   VARCHAR(50),
    name            VARCHAR(200) NOT NULL,
    department      VARCHAR(100),
    designation     VARCHAR(100),
    phone           VARCHAR(20),
    email           VARCHAR(200),
    -- face embedding stored as a 512-dim vector (InsightFace ArcFace output)
    face_embedding  vector(512),
    face_image_url  VARCHAR(500),                 -- stored in R2
    is_active       BOOLEAN DEFAULT TRUE,
    access_level    INTEGER DEFAULT 1,            -- 1=basic, 2=supervisor, 3=admin
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_employees_facility ON employees(facility_id);
-- IVFFlat index for fast ANN face search
CREATE INDEX idx_employees_face ON employees USING ivfflat (face_embedding vector_cosine_ops) WITH (lists = 100);

-- ─────────────────────────────────────────────
-- VISITORS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visitors (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id     UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    name            VARCHAR(200) NOT NULL,
    cnic            VARCHAR(20),                  -- Pakistan CNIC / passport
    phone           VARCHAR(20),
    purpose         VARCHAR(500),
    host_employee_id UUID REFERENCES employees(id),
    pre_approved    BOOLEAN DEFAULT FALSE,
    approved_from   TIMESTAMPTZ,
    approved_until  TIMESTAMPTZ,
    face_embedding  vector(512),
    face_image_url  VARCHAR(500),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_visitors_facility ON visitors(facility_id);
CREATE INDEX idx_visitors_approved ON visitors(facility_id, pre_approved, approved_until);

-- ─────────────────────────────────────────────
-- ENTRY LOGS  (main audit table — never delete rows)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entry_logs (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id       UUID NOT NULL REFERENCES facilities(id),
    gate_id           UUID REFERENCES gates(id),
    -- vehicle
    plate_number      VARCHAR(20),
    plate_confidence  FLOAT,                      -- OCR confidence 0.0–1.0
    vehicle_id        UUID REFERENCES vehicles(id),
    vehicle_status    VARCHAR(20),               -- approved | blacklisted | unknown
    -- persons detected
    driver_employee_id UUID REFERENCES employees(id),
    driver_visitor_id  UUID REFERENCES visitors(id),
    driver_name       VARCHAR(200),
    driver_confidence FLOAT,                     -- face match confidence
    passenger_count   INTEGER DEFAULT 0,
    -- decision
    decision          VARCHAR(20) NOT NULL,       -- allowed | denied | allowed_with_alert
    decision_reason   VARCHAR(500),
    alert_sent        BOOLEAN DEFAULT FALSE,
    -- timestamps
    entry_time        TIMESTAMPTZ DEFAULT NOW(),
    exit_time         TIMESTAMPTZ,
    -- media
    capture_image_url VARCHAR(500),              -- R2 URL of the gate capture
    video_clip_url    VARCHAR(500),
    -- sync
    synced_from_edge  BOOLEAN DEFAULT FALSE,
    edge_created_at   TIMESTAMPTZ               -- original timestamp on edge node
);

CREATE INDEX idx_logs_facility_time ON entry_logs(facility_id, entry_time DESC);
CREATE INDEX idx_logs_plate ON entry_logs(plate_number);
CREATE INDEX idx_logs_decision ON entry_logs(decision);
CREATE INDEX idx_logs_gate ON entry_logs(gate_id);

-- ─────────────────────────────────────────────
-- EDGE SYNC QUEUE  (logs queued offline, push when online)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS edge_sync_queue (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id   UUID NOT NULL REFERENCES facilities(id),
    gate_id       UUID REFERENCES gates(id),
    payload       JSONB NOT NULL,
    synced        BOOLEAN DEFAULT FALSE,
    retry_count   INTEGER DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    synced_at     TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- USERS  (dashboard logins — guards, admins)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id   UUID REFERENCES facilities(id),  -- NULL = super admin
    name          VARCHAR(200) NOT NULL,
    email         VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role          VARCHAR(20) DEFAULT 'guard',      -- guard | admin | superadmin
    is_active     BOOLEAN DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- ROW-LEVEL SECURITY  (guards can only see their facility)
-- ─────────────────────────────────────────────
ALTER TABLE vehicles    ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees   ENABLE ROW LEVEL SECURITY;
ALTER TABLE visitors    ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_logs  ENABLE ROW LEVEL SECURITY;
ALTER TABLE gates       ENABLE ROW LEVEL SECURITY;

-- updated_at auto-update trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_vehicles_updated   BEFORE UPDATE ON vehicles   FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_employees_updated  BEFORE UPDATE ON employees  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_facilities_updated BEFORE UPDATE ON facilities FOR EACH ROW EXECUTE FUNCTION update_updated_at();
