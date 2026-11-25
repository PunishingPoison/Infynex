"""
INFYNEX Backend MQTT Bridge Service
Connects to Eclipse Mosquitto and forwards real-time drone and IoT telemetry to WebSockets.
"""

import os
import json
import logging
import threading
import time
import asyncio
from typing import Dict, Any, List
import paho.mqtt.client as mqtt
from app.database.db_service import TimescaleDBService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MQTT-Bridge] %(message)s")


class MqttBridgeService:
    def __init__(self, broker_host: str = None, broker_port: int = None, ws_hub=None):
        self.broker_host = broker_host or os.getenv("MQTT_BROKER_HOST", "localhost")
        self.broker_port = broker_port or int(os.getenv("MQTT_BROKER_PORT", 1883))
        self.ws_hub = ws_hub
        self.client = mqtt.Client(client_id="infynex_backend_gateway", protocol=mqtt.MQTTv311)
        self.db = TimescaleDBService()

        # In-memory live cache for instant REST responses
        self.latest_drone_telemetry: Dict[str, Any] = {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "battery_percent": 100.0,
            "flight_status": "DISARMED"
        }
        self.latest_sensor_readings: Dict[str, Dict[str, Any]] = {}
        self.detected_damages: List[Dict[str, Any]] = self._load_initial_damages()
        self.latest_network_metrics: Dict[str, Any] = {
            "scenario": "good_signal",
            "latency_ms": 10.5,
            "jitter_ms": 1.2,
            "packet_loss_percent": 0.0,
            "throughput_mbps": 498.5,
            "pdr": 100.0
        }

    def _load_initial_damages(self) -> List[Dict[str, Any]]:
        candidate_paths = [
            "/app/data/detections/inspection_damages.json",
            "data/detections/inspection_damages.json",
            os.path.join(os.path.dirname(__file__), "../../../data/detections/inspection_damages.json")
        ]
        for p in candidate_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        data = json.load(f)
                    damages = []
                    for i, det in enumerate(data.get("detections", [])):
                        coords = det.get("world_coordinates", {})
                        damages.append({
                            "damage_id": f"DEFECT_{i+1:03d}",
                            "category": det.get("category", "crack"),
                            "severity": det.get("severity", "moderate"),
                            "confidence": det.get("confidence", 0.9),
                            "position": {"x": coords.get("x", 4.74), "y": coords.get("y", 0.0), "z": coords.get("z", 2.5)},
                            "surface": f"Station {det.get('station', 'W3')}",
                            "bbox": det.get("bbox", [])
                        })
                    if damages:
                        logging.info(f"Loaded {len(damages)} verified damage detections from {p}")
                        return damages
                except Exception as e:
                    logging.warning(f"Could not load damages from {p}: {e}")
        return [
            {"damage_id": "CRACK_001", "category": "crack", "severity": "severe", "confidence": 0.952, "position": {"x": 4.74, "y": -1.15, "z": 2.54}, "surface": "Station W3"},
            {"damage_id": "SPALL_001", "category": "spalling", "severity": "critical", "confidence": 0.861, "position": {"x": 4.74, "y": 0.20, "z": 3.20}, "surface": "Station W4"},
            {"damage_id": "CRACK_002", "category": "crack", "severity": "moderate", "confidence": 0.760, "position": {"x": 4.74, "y": 1.75, "z": 3.15}, "surface": "Station W5"}
        ]

    def start(self):
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        try:
            self.client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logging.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}...")
        except Exception as e:
            logging.warning(f"Could not connect to MQTT broker: {e}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logging.info("✓ Backend successfully connected to Mosquitto MQTT broker.")
            client.subscribe("infynex/#")
        else:
            logging.warning(f"MQTT connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except Exception:
            return

        # Route by topic
        if topic == "infynex/drone/telemetry":
            self.latest_drone_telemetry = payload
            self.db.record_drone_telemetry(payload)
            if self.ws_hub:
                asyncio_broadcast(self.ws_hub, {"type": "drone_telemetry", "data": payload})

        elif "infynex/sensors/" in topic and "/telemetry" in topic:
            node_id = payload.get("node_id", "UNKNOWN")
            self.latest_sensor_readings[node_id] = payload
            self.db.record_sensor_reading(payload)
            if self.ws_hub:
                asyncio_broadcast(self.ws_hub, {"type": "sensor_reading", "data": payload})

        elif topic in ["infynex/inspection/detections", "infynex/detections"]:
            self.detected_damages.append(payload)
            self.db.record_damage_detection(payload)
            if self.ws_hub:
                asyncio_broadcast(self.ws_hub, {"type": "damage_detection", "data": payload})

        elif topic in ["infynex/network/metrics", "infynex/5g/telemetry"]:
            self.latest_network_metrics = payload
            self.db.record_network_metrics(payload)
            if self.ws_hub:
                asyncio_broadcast(self.ws_hub, {"type": "network_metrics", "data": payload})


def asyncio_broadcast(ws_hub, message: dict):
    """Safely dispatches async broadcast from synchronous MQTT thread."""
    try:
        if ws_hub and hasattr(ws_hub, "loop") and ws_hub.loop and ws_hub.loop.is_running():
            asyncio.run_coroutine_threadsafe(ws_hub.broadcast(message), ws_hub.loop)
    except Exception:
        pass
