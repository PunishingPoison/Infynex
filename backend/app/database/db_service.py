"""
INFYNEX TimescaleDB Database Service
Provides connection pooling and high-throughput time-series ingestion for drone telemetry,
ESP32 sensor readings, 5G network metrics, and defect detections.
"""

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [TimescaleDB] %(message)s")

class TimescaleDBService:
    def __init__(self, db_url: str = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "postgresql://infynex:infynex_pass@timescaledb:5432/infynex_db")
        self._conn = None
        self._connect()

    def _connect(self):
        try:
            self._conn = psycopg2.connect(self.db_url)
            self._conn.autocommit = True
            logging.info("✓ Connected to TimescaleDB cluster.")
        except Exception as e:
            logging.warning(f"Could not connect to TimescaleDB at {self.db_url}: {e}")
            self._conn = None

    def _get_connection(self):
        if self._conn is None or self._conn.closed:
            self._connect()
        return self._conn

    def record_drone_telemetry(self, telemetry: Dict[str, Any]):
        conn = self._get_connection()
        if not conn:
            return
        try:
            pos = telemetry.get("position", {})
            vel = telemetry.get("velocity", {})
            att = telemetry.get("attitude", {})
            ts = datetime.now(timezone.utc)

            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO drone_telemetry (
                        time, pos_x, pos_y, pos_z, roll, pitch, yaw, vx, vy, vz, battery_percent, flight_mode
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    ts,
                    pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0),
                    att.get("roll", 0.0), att.get("pitch", 0.0), att.get("yaw", 0.0),
                    vel.get("vx", 0.0), vel.get("vy", 0.0), vel.get("vz", 0.0),
                    telemetry.get("battery_percent", 100.0),
                    telemetry.get("flight_status", "ACTIVE")
                ))
        except Exception as e:
            logging.error(f"Error inserting drone telemetry: {e}")

    def record_sensor_reading(self, reading: Dict[str, Any]):
        conn = self._get_connection()
        if not conn:
            return
        try:
            node_id = reading.get("node_id", "UNKNOWN")
            sensor_model = reading.get("sensor_type", reading.get("sensor_model", "GENERIC"))
            location = reading.get("location", "structure")
            status = reading.get("status", "normal")
            ts = datetime.now(timezone.utc)

            with conn.cursor() as cur:
                # Upsert sensor node
                cur.execute("""
                    INSERT INTO sensor_nodes (node_id, sensor_model, location, status, last_seen)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (node_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        last_seen = EXCLUDED.last_seen;
                """, (node_id, sensor_model, location, status, ts))

                # Insert hypertable reading
                cur.execute("""
                    INSERT INTO sensor_readings (
                        time, node_id, temperature_c, humidity_percent, pressure_hpa, battery_voltage, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    ts,
                    node_id,
                    reading.get("temperature_c"),
                    reading.get("humidity_pct", reading.get("humidity_percent")),
                    reading.get("pressure_hpa"),
                    reading.get("battery_voltage", 3.30),
                    status
                ))
        except Exception as e:
            logging.error(f"Error inserting sensor reading: {e}")

    def record_network_metrics(self, metrics: Dict[str, Any]):
        conn = self._get_connection()
        if not conn:
            return
        try:
            ts = datetime.now(timezone.utc)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO network_metrics (
                        time, scenario, latency_ms, jitter_ms, throughput_mbps, packet_loss_percent, pdr
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    ts,
                    metrics.get("profile_key", metrics.get("scenario", "standard")),
                    metrics.get("latency_ms", 10.0),
                    metrics.get("jitter_ms", 1.0),
                    metrics.get("throughput_mbps", 100.0),
                    metrics.get("packet_loss_pct", metrics.get("packet_loss_percent", 0.0)),
                    100.0 - metrics.get("packet_loss_pct", metrics.get("packet_loss_percent", 0.0))
                ))
        except Exception as e:
            logging.error(f"Error inserting network metrics: {e}")

    def record_damage_detection(self, det: Dict[str, Any]):
        conn = self._get_connection()
        if not conn:
            return
        try:
            pos = det.get("position", {})
            ts = datetime.now(timezone.utc)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO damage_detections (
                        damage_id, category, severity, confidence, pos_x, pos_y, pos_z, surface, image_path, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    det.get("damage_id", f"DEFECT_{int(ts.timestamp())}"),
                    det.get("category", "crack"),
                    det.get("severity", "moderate"),
                    det.get("confidence", 0.95),
                    pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0),
                    det.get("surface", "concrete_pier"),
                    det.get("image_path", ""),
                    ts
                ))
        except Exception as e:
            logging.error(f"Error inserting damage detection: {e}")

    def get_latest_telemetry(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM drone_telemetry ORDER BY time DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
                for r in rows:
                    if "time" in r and r["time"]:
                        r["time"] = r["time"].isoformat()
                return rows
        except Exception as e:
            logging.error(f"Query error: {e}")
            return []

    def get_latest_sensors(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM sensor_readings ORDER BY time DESC LIMIT %s", (limit,))
                rows = cur.fetchall()
                for r in rows:
                    if "time" in r and r["time"]:
                        r["time"] = r["time"].isoformat()
                return rows
        except Exception as e:
            logging.error(f"Query error: {e}")
            return []

    def get_all_damages(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        if not conn:
            return []
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM damage_detections ORDER BY detected_at DESC")
                rows = cur.fetchall()
                for r in rows:
                    if "detected_at" in r and r["detected_at"]:
                        r["detected_at"] = r["detected_at"].isoformat()
                    if "id" in r:
                        r["id"] = str(r["id"])
                    if "mission_id" in r and r["mission_id"]:
                        r["mission_id"] = str(r["mission_id"])
                    r["position"] = {"x": r["pos_x"], "y": r["pos_y"], "z": r["pos_z"]}
                return rows
        except Exception as e:
            logging.error(f"Query error: {e}")
            return []
