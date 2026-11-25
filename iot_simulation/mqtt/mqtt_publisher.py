"""
INFYNEX IoT Sensor Swarm Manager & MQTT Publisher
Orchestrates virtual ESP32 sensor nodes and streams real-time telemetry to Mosquitto.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../sensors")))
import paho.mqtt.client as mqtt
from sensor_models import DS18B20Node, BME280Node, DHT22Node

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [IoT] %(message)s")


class SensorNetworkSimulator:
    def __init__(self, broker_host: str = "localhost", broker_port: int = 1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(client_id="infynex_iot_gateway", protocol=mqtt.MQTTv311)

        # 4 Standard ESP32 Nodes as specified in INFYNEX Architecture
        self.nodes = {
            "ESP32_001": DS18B20Node("ESP32_001", "front_wall_pillar_1", base_temp=29.2, sample_interval=1.0),
            "ESP32_002": DS18B20Node("ESP32_002", "structural_core_beam", base_temp=26.8, sample_interval=1.0),
            "ESP32_003": BME280Node("ESP32_003", "foundation_anchor_south", sample_interval=1.0),
            "ESP32_004": DHT22Node("ESP32_004", "upper_deck_ambient", sample_interval=2.0)
        }
        self.running = False

    def connect(self):
        logging.info(f"Connecting to MQTT Broker at {self.broker_host}:{self.broker_port}...")
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.client.loop_start()
            logging.info("✓ Connected to Mosquitto MQTT Broker.")
            # Publish birth messages
            for node_id, node in self.nodes.items():
                self.client.publish(f"infynex/sensors/{node_id}/status", json.dumps({"status": "online"}), retain=True)
            return True
        except Exception as e:
            logging.error(f"MQTT connection failed: {e}")
            return False

    def start(self, duration_sec: Optional[int] = None):
        self.running = True
        start_time = time.time()
        last_ticks = {node_id: 0.0 for node_id in self.nodes}

        logging.info("Starting sensor emulation loop...")
        try:
            while self.running:
                now = time.time()
                dt = 0.5
                time.sleep(dt)

                for node_id, node in self.nodes.items():
                    node.step_time(dt)
                    if now - last_ticks[node_id] >= node.sample_interval:
                        last_ticks[node_id] = now
                        reading = node.read()
                        if reading:
                            topic = f"infynex/sensors/{node_id}/telemetry"
                            payload = json.dumps(reading)
                            self.client.publish(topic, payload)
                            logging.debug(f"Published {topic} -> {payload}")

                if duration_sec and (time.time() - start_time) >= duration_sec:
                    break

        except KeyboardInterrupt:
            logging.info("Stopping sensor network simulator...")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        for node_id in self.nodes:
            self.client.publish(f"infynex/sensors/{node_id}/status", json.dumps({"status": "offline"}), retain=True)
        self.client.loop_stop()
        self.client.disconnect()
        logging.info("✓ Sensor network simulation stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="INFYNEX ESP32 IoT Node Network")
    parser.add_argument("--broker", default="localhost", help="MQTT Broker Host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker Port")
    parser.add_argument("--duration", type=int, default=None, help="Run duration in seconds")
    args = parser.parse_args()

    sim = SensorNetworkSimulator(broker_host=args.broker, broker_port=args.port)
    if sim.connect():
        sim.start(duration_sec=args.duration)
