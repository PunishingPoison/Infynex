#!/usr/bin/env python3
"""
INFYNEX IoT Fleet Runner & Fault Injection Simulator
Executes the fault scenario, orchestrates the 4 ESP32 nodes, and validates broker LWT response.
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Dict, List, Any
import yaml
import paho.mqtt.client as mqtt

# Ensure module path resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from iot_simulation.sensors.ds18b20 import DS18B20Node
from iot_simulation.sensors.bme280 import BME280Node
from iot_simulation.sensors.dht22 import DHT22Node

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [IoTRunner] %(message)s")

class IoTFleetRunner:
    def __init__(self, scenario_path: str):
        self.scenario_path = scenario_path
        with open(scenario_path, "r") as f:
            self.scenario = yaml.safe_load(f)

        self.broker_host = self.scenario["mqtt_broker"]["host"]
        self.broker_port = self.scenario["mqtt_broker"]["port"]

        self.nodes = {}
        self._init_nodes()

        # Telemetry & status logs captured by independent listener
        self.telemetry_received = {node_id: [] for node_id in self.nodes}
        self.status_received = []
        self.listener_client = mqtt.Client(client_id="infynex_iot_verifier", protocol=mqtt.MQTTv311)
        self.listener_client.on_message = self._on_verify_message

    def _init_nodes(self):
        for node_cfg in self.scenario["nodes"]:
            nid = node_cfg["node_id"]
            stype = node_cfg["sensor_type"]
            loc = node_cfg["location"]
            interval = node_cfg["sample_interval_sec"]

            if stype == "DS18B20":
                node = DS18B20Node(
                    node_id=nid,
                    location=loc,
                    base_temp_c=node_cfg.get("base_temp_c", 25.0),
                    sample_interval_sec=interval,
                    broker_host=self.broker_host,
                    broker_port=self.broker_port
                )
            elif stype == "BME280":
                node = BME280Node(
                    node_id=nid,
                    location=loc,
                    base_temp_c=node_cfg.get("base_temp_c", 26.0),
                    base_humidity_pct=node_cfg.get("base_humidity_pct", 60.0),
                    base_pressure_hpa=node_cfg.get("base_pressure_hpa", 1013.25),
                    sample_interval_sec=interval,
                    broker_host=self.broker_host,
                    broker_port=self.broker_port
                )
            elif stype == "DHT22":
                node = DHT22Node(
                    node_id=nid,
                    location=loc,
                    base_temp_c=node_cfg.get("base_temp_c", 27.0),
                    base_humidity_pct=node_cfg.get("base_humidity_pct", 55.0),
                    sample_interval_sec=interval,
                    broker_host=self.broker_host,
                    broker_port=self.broker_port
                )
            self.nodes[nid] = node

    def _on_verify_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic
            recv_time = time.time()

            if "status" in topic:
                self.status_received.append({
                    "topic": topic,
                    "payload": payload,
                    "recv_time_sec": recv_time
                })
                logging.info(f"⚡ [STATUS EVENT] {topic} -> {payload.get('status')} ({payload.get('reason', 'N/A')})")
            elif "telemetry" in topic:
                node_id = payload.get("node_id")
                if node_id in self.telemetry_received:
                    self.telemetry_received[node_id].append(payload)
        except Exception as e:
            logging.error(f"Error parsing MQTT msg: {e}")

    def run(self) -> Dict[str, Any]:
        logging.info("Starting verification listener...")
        self.listener_client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.listener_client.subscribe("infynex/sensors/+/status", qos=1)
        self.listener_client.subscribe("infynex/sensors/+/telemetry", qos=0)
        self.listener_client.loop_start()

        # Connect all nodes
        for nid, node in self.nodes.items():
            node.connect()
            time.sleep(0.1)

        sim_start_time = time.time()
        kill_timestamp = None
        lwt_offline_timestamp = None
        last_publish = {nid: 0.0 for nid in self.nodes}

        schedule = sorted(self.scenario.get("schedule", []), key=lambda x: x["time_sec"])
        next_event_idx = 0
        run_sim = True

        logging.info("Starting simulation tick loop (dt=0.2s)...")
        while run_sim:
            now = time.time()
            elapsed = now - sim_start_time

            # Check scheduled events
            while next_event_idx < len(schedule) and elapsed >= schedule[next_event_idx]["time_sec"]:
                event = schedule[next_event_idx]
                act = event["action"]
                logging.info(f"⏰ [T={elapsed:.1f}s] SCHEDULED ACTION: {act}")

                if act == "inject_fault":
                    target = event["target_node"]
                    self.nodes[target].set_fault(event["fault_type"], event.get("magnitude", 0.0))
                elif act == "socket_kill":
                    target = event["target_node"]
                    kill_timestamp = time.time()
                    self.nodes[target].simulate_hardware_kill()
                    logging.warning(f"💥 Forced socket termination on {target} at {kill_timestamp}")
                elif act == "terminate":
                    run_sim = False
                    break

                next_event_idx += 1

            if not run_sim:
                break

            # Step and publish each active node
            dt = 0.2
            for nid, node in self.nodes.items():
                if node.is_online:
                    node.step_time(dt)
                    if (now - last_publish[nid]) >= node.sample_interval_sec:
                        last_publish[nid] = now
                        raw = node.read_raw()
                        node.publish_telemetry(raw)

            # Check if LWT event has arrived for ESP32_004
            if kill_timestamp and not lwt_offline_timestamp:
                for s in self.status_received:
                    if s["recv_time_sec"] >= kill_timestamp:
                        payload = s.get("payload", {})
                        if payload.get("node_id") == "ESP32_004" and payload.get("status") == "offline":
                            lwt_offline_timestamp = s["recv_time_sec"]
                            lwt_delay_ms = round((lwt_offline_timestamp - kill_timestamp) * 1000.0, 2)
                            logging.info(f"✓ Broker LWT Disconnect detected in {lwt_delay_ms} ms (< 5000 ms limit)")

            time.sleep(dt)

        # Clean shutdown remaining nodes
        for nid, node in self.nodes.items():
            if node.is_online:
                node.disconnect_clean()

        self.listener_client.loop_stop()
        self.listener_client.disconnect()

        # Calculate metrics
        lwt_latency_ms = None
        lwt_passed = False
        if kill_timestamp and lwt_offline_timestamp:
            lwt_latency_ms = round((lwt_offline_timestamp - kill_timestamp) * 1000.0, 2)
            lwt_passed = lwt_latency_ms <= 5000.0
        elif kill_timestamp:
            # Check if status arrived during loop stop
            for s in self.status_received:
                if s["recv_time_sec"] >= kill_timestamp and s.get("payload", {}).get("node_id") == "ESP32_004":
                    lwt_offline_timestamp = s["recv_time_sec"]
                    lwt_latency_ms = round((lwt_offline_timestamp - kill_timestamp) * 1000.0, 2)
                    lwt_passed = lwt_latency_ms <= 5000.0
                    break

        total_telemetry = sum(len(pkts) for pkts in self.telemetry_received.values())
        drift_pkts = [p for p in self.telemetry_received.get("ESP32_001", []) if p.get("temperature_c", 0) > 35.0]
        spike_pkts = [p for p in self.telemetry_received.get("ESP32_003", []) if p.get("humidity_pct", 0) > 95.0]

        summary = {
            "phase": "Phase 5: IoT ESP32 Sensor Fleet & MQTT Fault Sim",
            "scenario": self.scenario["scenario_name"],
            "status": "PASSED" if lwt_passed and len(drift_pkts) > 0 and len(spike_pkts) > 0 else "FAILED",
            "total_nodes": len(self.nodes),
            "total_telemetry_packets": total_telemetry,
            "packets_per_node": {nid: len(pkts) for nid, pkts in self.telemetry_received.items()},
            "fault_verification": {
                "thermal_drift_injected": len(drift_pkts) > 0,
                "thermal_drift_sample": drift_pkts[0] if drift_pkts else None,
                "humidity_spike_injected": len(spike_pkts) > 0,
                "humidity_spike_sample": spike_pkts[0] if spike_pkts else None,
                "socket_kill_timestamp": kill_timestamp,
                "lwt_offline_timestamp": lwt_offline_timestamp,
                "lwt_detection_latency_ms": lwt_latency_ms,
                "lwt_latency_threshold_ms": 5000.0,
                "lwt_alert_passed": lwt_passed
            }
        }

        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/phase5_iot_verification.json"))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(summary, f, indent=2)

        logging.info("=" * 64)
        logging.info(f" PHASE 5 EXIT GATE OUTCOME: {summary['status']}")
        logging.info(f" Telemetry Packets: {total_telemetry} | LWT Latency: {lwt_latency_ms} ms")
        logging.info("=" * 64)

        return summary

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "simulation/scenarios/fault_sensor_drop.yaml"
    runner = IoTFleetRunner(scenario)
    res = runner.run()
    if res["status"] != "PASSED":
        sys.exit(1)
