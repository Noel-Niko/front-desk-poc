-- BrightWheel AI Front Desk — Database Schema
-- All dates use day_offset (0=today, 1=yesterday) for evergreen demo data.

PRAGMA journal_mode=WAL;  -- Allow concurrent reads (backend + dashboard)

CREATE TABLE IF NOT EXISTS children (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    age             INTEGER NOT NULL,
    classroom       TEXT NOT NULL,
    teacher_name    TEXT NOT NULL,
    teacher_role    TEXT NOT NULL,
    room_number     TEXT NOT NULL,
    security_code   TEXT NOT NULL,
    enrolled_date   TEXT NOT NULL,
    doctor_name     TEXT,
    doctor_phone    TEXT
);

CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        INTEGER NOT NULL REFERENCES children(id),
    day_offset      INTEGER NOT NULL,
    check_in_time   TEXT,
    check_out_time  TEXT,
    checked_in_by   TEXT,
    checked_out_by  TEXT,
    status          TEXT NOT NULL CHECK(status IN ('present', 'absent', 'field_trip'))
);

CREATE TABLE IF NOT EXISTS meals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        INTEGER NOT NULL REFERENCES children(id),
    day_offset      INTEGER NOT NULL,
    meal_type       TEXT NOT NULL CHECK(meal_type IN ('breakfast', 'snack_am', 'lunch', 'snack_pm')),
    scheduled_time  TEXT NOT NULL,
    description     TEXT NOT NULL,
    recorded_by     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS allergies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        INTEGER NOT NULL REFERENCES children(id),
    allergy_type    TEXT NOT NULL CHECK(allergy_type IN ('food', 'environmental', 'medication')),
    description     TEXT NOT NULL,
    doctor_confirmed INTEGER NOT NULL DEFAULT 0,
    recorded_by     TEXT NOT NULL,
    recorded_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id        INTEGER NOT NULL REFERENCES children(id),
    contact_name    TEXT NOT NULL,
    relationship    TEXT NOT NULL,
    phone           TEXT NOT NULL,
    is_primary      INTEGER NOT NULL DEFAULT 0,
    recorded_by     TEXT NOT NULL,
    recorded_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id                    INTEGER NOT NULL REFERENCES children(id),
    current_balance             REAL NOT NULL DEFAULT 0.0,
    next_payment_days_ahead     INTEGER NOT NULL,
    last_payment_amount         REAL,
    last_payment_date_offset    INTEGER,
    fee_type                    TEXT NOT NULL,
    weekly_fee                  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS field_trips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    day_offset      INTEGER NOT NULL,
    description     TEXT NOT NULL,
    departure_time  TEXT NOT NULL,
    return_time     TEXT NOT NULL,
    classrooms      TEXT NOT NULL,
    recorded_by     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tour_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_name     TEXT NOT NULL,
    parent_phone    TEXT NOT NULL,
    parent_email    TEXT,
    child_age       INTEGER,
    preferred_date  TEXT NOT NULL,
    notes           TEXT,
    created_at      TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id                      TEXT PRIMARY KEY,
    started_at              TEXT NOT NULL,
    ended_at                TEXT,
    security_code_used      TEXT,
    child_id                INTEGER REFERENCES children(id),
    previous_session_id     TEXT REFERENCES sessions(id),
    summary                 TEXT,
    rating                  INTEGER CHECK(rating BETWEEN 1 AND 5),
    rating_feedback         TEXT,
    transferred_to_human    INTEGER NOT NULL DEFAULT 0,
    transfer_reason         TEXT,
    input_mode              TEXT NOT NULL DEFAULT 'text' CHECK(input_mode IN ('voice', 'text'))
);

CREATE TABLE IF NOT EXISTS messages (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id              TEXT NOT NULL REFERENCES sessions(id),
    role                    TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content                 TEXT NOT NULL,
    citations               TEXT,
    tool_used               TEXT,
    transcript_confidence   REAL,
    raw_audio_path          TEXT,
    timestamp               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operator_faq_overrides (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_pattern TEXT NOT NULL,
    answer          TEXT NOT NULL,
    created_by      TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    updated_at      TEXT,
    active          INTEGER NOT NULL DEFAULT 1
);
