-- ============================================================
--  TransitFlow PostgreSQL Schema
--  Seed data is loaded separately by: python skeleton/seed_postgres.py
--
--  TWO ROLES:
--    1. Relational  → dual-network transit data you design below
--    2. Vector      → policy documents for RAG (provided — do not modify)
-- ============================================================

-- ============================================================
--  STUDENT TASK — Design and create your relational tables here
--
--  Start from the mock data in train-mock-data/:
--    metro_stations.json, national_rail_stations.json
--    metro_schedules.json, national_rail_schedules.json
--    national_rail_seat_layouts.json
--    registered_users.json
--    bookings.json, metro_travel_history.json
--    payments.json, feedback.json
--
--  Think about:
--    - What tables do you need?
--    - What columns and data types?
--    - Which fields are primary keys? Which are foreign keys?
--    - What constraints make sense?
--
--  Apply your schema with:
--    docker-compose down -v && docker-compose up -d
-- ============================================================
CREATE TABLE users (
    user_id VARCHAR(10) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    secret_question TEXT,
    secret_answer TEXT,
    registered_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE user_credentials (
    user_id VARCHAR(10) PRIMARY KEY,
    password_hash TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE
);

CREATE TABLE user_salts (
    user_id VARCHAR(10) PRIMARY KEY,
    salt TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
    ON DELETE CASCADE
);

CREATE TABLE metro_stations (
    station_id VARCHAR(10) PRIMARY KEY,

    station_name VARCHAR(100) NOT NULL,

    is_interchange_metro BOOLEAN DEFAULT FALSE,

    is_interchange_national_rail BOOLEAN DEFAULT FALSE,

    interchange_national_rail_station_id VARCHAR(10)
);

CREATE TABLE metro_station_lines (
    station_id VARCHAR(10),

    line_code VARCHAR(10),

    PRIMARY KEY (station_id, line_code),

    FOREIGN KEY (station_id)
        REFERENCES metro_stations(station_id)
);

CREATE TABLE national_rail_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    station_name VARCHAR(100) NOT NULL,

    is_interchange_national_rail BOOLEAN DEFAULT FALSE,
    is_interchange_metro BOOLEAN DEFAULT FALSE,

    interchange_metro_station_id VARCHAR(10)
);

CREATE TABLE national_rail_station_lines (
    station_id VARCHAR(10),
    line_code VARCHAR(10),

    PRIMARY KEY (station_id, line_code),

    FOREIGN KEY (station_id)
        REFERENCES national_rail_stations(station_id)
);

CREATE TABLE metro_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,

    line VARCHAR(10),
    direction VARCHAR(20),

    origin_station_id VARCHAR(10),
    destination_station_id VARCHAR(10),

    first_train_time TIME,
    last_train_time TIME,

    base_fare_usd DECIMAL(10,2),
    per_stop_rate_usd DECIMAL(10,2),

    frequency_min INTEGER
);

CREATE TABLE metro_schedule_stops (
    schedule_id VARCHAR(20),
    station_id VARCHAR(10),

    stop_order INTEGER,
    travel_time_min INTEGER,

    PRIMARY KEY (schedule_id, station_id),

    FOREIGN KEY (schedule_id)
        REFERENCES metro_schedules(schedule_id),

    FOREIGN KEY (station_id)
        REFERENCES metro_stations(station_id)
);

CREATE TABLE metro_schedule_days (
    schedule_id VARCHAR(20),
    day_of_week VARCHAR(10),

    PRIMARY KEY (schedule_id, day_of_week),

    FOREIGN KEY (schedule_id)
        REFERENCES metro_schedules(schedule_id)
);

CREATE TABLE national_rail_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,

    line VARCHAR(10),
    service_type VARCHAR(20),
    direction VARCHAR(20),

    origin_station_id VARCHAR(10),
    destination_station_id VARCHAR(10),

    first_train_time TIME,
    last_train_time TIME,

    frequency_min INTEGER
);

CREATE TABLE national_rail_schedule_stops (
    schedule_id VARCHAR(20),
    station_id VARCHAR(10),

    stop_order INTEGER,
    travel_time_min INTEGER,

    PRIMARY KEY (schedule_id, station_id),

    FOREIGN KEY (schedule_id)
        REFERENCES national_rail_schedules(schedule_id),

    FOREIGN KEY (station_id)
        REFERENCES national_rail_stations(station_id)
);

CREATE TABLE national_rail_schedule_days (
    schedule_id VARCHAR(20),
    day_of_week VARCHAR(10),

    PRIMARY KEY (schedule_id, day_of_week),

    FOREIGN KEY (schedule_id)
        REFERENCES national_rail_schedules(schedule_id)
);

CREATE TABLE national_rail_fares (
    schedule_id VARCHAR(20),
    fare_class VARCHAR(20),

    base_fare_usd DECIMAL(10,2),
    per_stop_rate_usd DECIMAL(10,2),

    PRIMARY KEY (schedule_id, fare_class),

    FOREIGN KEY (schedule_id)
        REFERENCES national_rail_schedules(schedule_id)
);

CREATE TABLE national_rail_seat_layouts (
    layout_id VARCHAR(10) PRIMARY KEY,

    schedule_id VARCHAR(20) UNIQUE NOT NULL,

    FOREIGN KEY (schedule_id)
        REFERENCES national_rail_schedules(schedule_id)
);

CREATE TABLE national_rail_seats (
    seat_id VARCHAR(10),

    layout_id VARCHAR(10),

    coach VARCHAR(10),

    fare_class VARCHAR(20),

    row_no INTEGER,

    column_no VARCHAR(5),

    PRIMARY KEY (layout_id, seat_id),

    FOREIGN KEY (layout_id)
        REFERENCES national_rail_seat_layouts(layout_id)
);

CREATE TABLE national_rail_bookings (
    booking_id VARCHAR(10) PRIMARY KEY,

    user_id VARCHAR(10) NOT NULL,
    schedule_id VARCHAR(20) NOT NULL,

    origin_station_id VARCHAR(10),
    destination_station_id VARCHAR(10),

    travel_date DATE,
    departure_time TIME,

    ticket_type VARCHAR(20),
    fare_class VARCHAR(20),

    coach VARCHAR(10),
    seat_id VARCHAR(10),

    stops_travelled INTEGER,

    amount_usd DECIMAL(10,2),

    status VARCHAR(20),

    booked_at TIMESTAMP,
    travelled_at TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

CREATE TABLE metro_travel_history (
    trip_id VARCHAR(10) PRIMARY KEY,

    user_id VARCHAR(10) NOT NULL,

    schedule_id VARCHAR(20) NOT NULL,

    origin_station_id VARCHAR(10),
    destination_station_id VARCHAR(10),

    travel_date DATE,

    ticket_type VARCHAR(20),

    day_pass_ref VARCHAR(50),

    stops_travelled INTEGER,

    amount_usd DECIMAL(10,2),

    status VARCHAR(20),

    purchased_at TIMESTAMP,
    travelled_at TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

CREATE TABLE payments (
    payment_id VARCHAR(10) PRIMARY KEY,

    booking_id VARCHAR(10) NOT NULL,

    amount_usd DECIMAL(10,2),

    method VARCHAR(30),

    status VARCHAR(20),

    paid_at TIMESTAMP
);

CREATE TABLE feedback (
    feedback_id VARCHAR(10) PRIMARY KEY,

    booking_id VARCHAR(10) NOT NULL,

    user_id VARCHAR(10) NOT NULL,

    rating INTEGER NOT NULL
        CHECK (rating BETWEEN 1 AND 5),

    comment TEXT,

    submitted_at TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
);

-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do not modify
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  -- 'refund', 'booking', 'conduct'
    content     TEXT         NOT NULL,
    -- 768-dim  → Ollama nomic-embed-text (default)
    -- 3072-dim → Gemini gemini-embedding-001
    -- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_policy_documents_embedding
ON policy_documents
USING hnsw (embedding vector_cosine_ops);
