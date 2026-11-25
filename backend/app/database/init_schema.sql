-- INFYNEX TimescaleDB Schema Initialization

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Inspection Missions
CREATE TABLE IF NOT EXISTS missions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    target_structure VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    total_waypoints INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Drone Telemetry (Hypertable)
CREATE TABLE IF NOT EXISTS drone_telemetry (
    time TIMESTAMPTZ NOT NULL,
    mission_id UUID REFERENCES missions(id) ON DELETE CASCADE,
    pos_x FLOAT NOT NULL,
    pos_y FLOAT NOT NULL,
    pos_z FLOAT NOT NULL,
    roll FLOAT,
    pitch FLOAT,
    yaw FLOAT,
    vx FLOAT,
    vy FLOAT,
    vz FLOAT,
    battery_percent FLOAT,
    flight_mode VARCHAR(50)
);
SELECT create_hypertable('drone_telemetry', 'time', if_not_exists => TRUE);

-- 3. Sensor Nodes
CREATE TABLE IF NOT EXISTS sensor_nodes (
    node_id VARCHAR(50) PRIMARY KEY,
    sensor_model VARCHAR(50) NOT NULL,
    location VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'normal',
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Sensor Readings (Hypertable)
CREATE TABLE IF NOT EXISTS sensor_readings (
    time TIMESTAMPTZ NOT NULL,
    node_id VARCHAR(50) REFERENCES sensor_nodes(node_id) ON DELETE CASCADE,
    temperature_c FLOAT,
    humidity_percent FLOAT,
    pressure_hpa FLOAT,
    battery_voltage FLOAT,
    status VARCHAR(50)
);
SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);

-- 5. Damage Detections
CREATE TABLE IF NOT EXISTS damage_detections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id UUID REFERENCES missions(id) ON DELETE CASCADE,
    damage_id VARCHAR(50) NOT NULL,
    category VARCHAR(50) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    pos_x FLOAT NOT NULL,
    pos_y FLOAT NOT NULL,
    pos_z FLOAT NOT NULL,
    surface VARCHAR(100),
    image_path VARCHAR(512),
    detected_at TIMESTAMPTZ NOT NULL
);

-- 6. Network Performance Metrics (Hypertable)
CREATE TABLE IF NOT EXISTS network_metrics (
    time TIMESTAMPTZ NOT NULL,
    scenario VARCHAR(100) NOT NULL,
    latency_ms FLOAT NOT NULL,
    jitter_ms FLOAT NOT NULL,
    throughput_mbps FLOAT NOT NULL,
    packet_loss_percent FLOAT NOT NULL,
    pdr FLOAT NOT NULL
);
SELECT create_hypertable('network_metrics', 'time', if_not_exists => TRUE);
