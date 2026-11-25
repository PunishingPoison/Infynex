#!/usr/bin/env python3
"""
INFYNEX ESP32 Base Sensor Node
Abstract base class representing an ESP32 microcontroller running sensor firmware.
Manages:
- Dual timestamping: sim_time_ns & wall_time_ns
- Packet sequencing
- Battery voltage discharge curve
- Fault injection modes (drift, thermal spikes, intermittent packet drop)
- Native MQTT client connection with Last Will and Testament (LWT)
"""

import json
import logging
import math
import os
import random
import time
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

class BaseSensorNode:
    def __init__(
        self,
        node_id: str,
        sensor_type: str,
        location: str,
        sample_interval_sec: float = 1.0,
        broker_host: str = "localhost",
        broker_port: int = 1883
    ):
        self.node_id = node_id
        self.sensor_type = sensor_type
        self.location = location
        self.sample_interval_sec = sample_interval_sec
        self.broker_host = broker_host
        self.broker_port = broker_port

        self.sequence = 0
        self.battery_voltage = 3.30
        self.is_online = False
        self.fault_mode = "none" # "none", "drift", "spike", "drop"
        self.drift_offset = 0.0
        self.sim_time_sec = 0.0

        self.logger = logging.getLogger(f"ESP32:{self.node_id}")

        # Initialize MQTT client
        self.client = mqtt.Client(
            client_id=f"infynex_esp32_{self.node_id}",
            protocol=mqtt.MQTTv311
        )
        self._configure_lwt()

    def _configure_lwt(self):
        """Set MQTT Last Will and Testament before connection."""
        lwt_payload = json.dumps({
            "node_id": self.node_id,
            "status": "offline",
            "reason": "unexpected_disconnect",
            "sensor_type": self.sensor_type,
            "location": self.location,
            "wall_time_ns": time.time_ns()
        })
        self.client.will_set(
            topic=f"infynex/sensors/{self.node_id}/status",
            payload=lwt_payload,
            qos=1,
            retain=True
        )

    def connect(self) -> bool:
        """Connect to Mosquitto broker and publish online birth status."""
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=10)
            self.client.loop_start()
            self.is_online = True
            
            # Publish online birth status
            birth_payload = json.dumps({
                "node_id": self.node_id,
                "status": "online",
                "sensor_type": self.sensor_type,
                "location": self.location,
                "sample_interval_sec": self.sample_interval_sec,
                "wall_time_ns": time.time_ns()
            })
            self.client.publish(
                f"infynex/sensors/{self.node_id}/status",
                payload=birth_payload,
                qos=1,
                retain=True
            )
            self.logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def step_time(self, dt: float):
        """Advance time and deplete battery slightly."""
        self.sim_time_sec += dt
        # Deplete ~0.0001V per minute
        self.battery_voltage = max(2.4, self.battery_voltage - (0.0000016 * dt))

    def set_fault(self, mode: str, magnitude: float = 0.0):
        """Inject fault into sensor reading."""
        self.fault_mode = mode
        if mode == "drift":
            self.drift_offset = magnitude
        elif mode == "none":
            self.drift_offset = 0.0
        self.logger.warning(f"Fault mode set to: {mode} (mag={magnitude})")

    def simulate_hardware_kill(self):
        """Simulate unexpected hardware power loss / network drop without clean disconnect."""
        self.logger.warning("Simulating sudden power loss / socket kill to trigger broker LWT...")
        self.is_online = False
        try:
            # Force abrupt socket shutdown to trigger broker LWT
            if self.client._sock:
                self.client._sock.close()
        except Exception:
            pass
        self.client.loop_stop()

    def disconnect_clean(self):
        """Clean shutdown publishing graceful offline status."""
        if self.is_online:
            offline_payload = json.dumps({
                "node_id": self.node_id,
                "status": "offline",
                "reason": "clean_shutdown",
                "sensor_type": self.sensor_type,
                "location": self.location,
                "wall_time_ns": time.time_ns()
            })
            self.client.publish(
                f"infynex/sensors/{self.node_id}/status",
                payload=offline_payload,
                qos=1,
                retain=True
            )
            self.client.loop_stop()
            self.client.disconnect()
            self.is_online = False
            self.logger.info("Clean disconnect complete.")

    def publish_telemetry(self, data: Dict[str, Any]) -> bool:
        """Enrich data with protocol headers and publish over MQTT."""
        if not self.is_online:
            return False

        if self.fault_mode == "drop" and random.random() < 0.6:
            self.logger.debug("Packet dropped due to simulated RF interference")
            return False

        self.sequence += 1
        now_ns = time.time_ns()
        sim_ns = int(self.sim_time_sec * 1e9)

        payload = {
            "node_id": self.node_id,
            "sensor_type": self.sensor_type,
            "location": self.location,
            "sequence": self.sequence,
            "battery_voltage": round(self.battery_voltage, 2),
            "sim_time_ns": sim_ns,
            "wall_time_ns": now_ns,
            **data
        }

        topic = f"infynex/sensors/{self.node_id}/telemetry"
        res = self.client.publish(topic, json.dumps(payload), qos=0)
        return res.rc == mqtt.MQTT_ERR_SUCCESS

    def read_raw(self) -> Dict[str, Any]:
        """Override in subclasses to provide sensor-specific readings."""
        raise NotImplementedError
