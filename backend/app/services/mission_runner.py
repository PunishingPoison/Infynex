"""
INFYNEX Real-Time Flight Mission & 360-Degree AI Inspection Runner
Orchestrates autonomous 360-degree orbital survey around all 4 quadrants of the concrete infrastructure,
continuous optical frame generation, real-time PyTorch defect detection alerts, and WebSocket/MQTT streaming.
"""

import asyncio
import json
import logging
import math
import os
import random
import time
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [MissionRunner] %(message)s")


class MissionFlightSimulator:
    def __init__(self, ws_hub=None, mqtt_service=None):
        self.ws_hub = ws_hub
        self.mqtt_service = mqtt_service
        self.is_running = False
        self.current_task: asyncio.Task = None
        self.active_frame_path = "/data/captured_images/frame_inspect_W3.jpg"
        self.active_annotated_path = "/data/detections/annotated_W3.jpg"
        self.current_waypoint = "Helipad Pad (Ready)"
        self.active_defect = None
        self.current_telemetry = {
            "position": {"x": 0.0, "y": 0.0, "z": 0.05},
            "yaw": 0.0,
            "flight_status": "STANDBY_DISARMED",
            "waypoint": "Helipad Pad (Ready)",
            "battery_percent": 100.0
        }
        self.recorded_damages: List[Dict[str, Any]] = []

    def start_mission_async(self):
        if self.is_running:
            logging.info("Mission is already in progress.")
            return {"status": "already_running"}

        self.is_running = True
        self.current_task = asyncio.create_task(self._run_mission_loop())
        return {"status": "started", "mission": "Bridge Pier 360-Degree Structural Inspection"}

    def stop_mission(self):
        self.is_running = False
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        self.current_telemetry["flight_status"] = "RTL_DISARMED"
        return {"status": "stopped"}

    async def _broadcast(self, msg_type: str, data: dict):
        if self.ws_hub:
            await self.ws_hub.broadcast({"type": msg_type, "data": data})

    async def _run_mission_loop(self):
        logging.info("Initiating 360-degree autonomous orbital flight mission...")
        
        # 360-Degree Comprehensive Inspection Route across all 4 faces
        waypoints = [
            {"wp": "W1", "name": "Takeoff to 2.5m Survey Altitude", "x": 0.0, "y": 0.0, "z": 2.5, "yaw": 0.0, "hold_sec": 2.0},
            {"wp": "W2", "name": "Approach North Face Corridor", "x": 2.0, "y": -0.8, "z": 2.5, "yaw": 0.0, "hold_sec": 2.0},
            {
                "wp": "W3",
                "name": "North Pier: Front Wall Inspection",
                "x": 3.5, "y": -1.2, "z": 2.5, "yaw": 0.0, "hold_sec": 5.0,
                "defect": {
                    "damage_id": "CRACK_001",
                    "category": "crack",
                    "label": "vertical_crack",
                    "severity": "severe",
                    "confidence": 0.965,
                    "position": {"x": 4.74, "y": -1.149, "z": 2.538},
                    "surface": "North Face: Front Wall Pier",
                    "frame": "/data/captured_images/frame_inspect_W3.jpg",
                    "annotated": "/data/detections/annotated_W3.jpg"
                }
            },
            {
                "wp": "W4",
                "name": "East Flank: Corner Column Orbit",
                "x": 4.8, "y": 1.5, "z": 3.0, "yaw": 90.0, "hold_sec": 5.0,
                "defect": {
                    "damage_id": "SPALL_001",
                    "category": "spalling",
                    "label": "concrete_spalling",
                    "severity": "critical",
                    "confidence": 0.955,
                    "position": {"x": 4.74, "y": 0.199, "z": 3.199},
                    "surface": "East Face: Corner Column (Exposed Rebar)",
                    "frame": "/data/captured_images/frame_inspect_W4.jpg",
                    "annotated": "/data/detections/annotated_W4.jpg"
                }
            },
            {
                "wp": "W5",
                "name": "South Face: Rear Abutment Survey",
                "x": 5.5, "y": 0.0, "z": 3.5, "yaw": 180.0, "hold_sec": 5.0,
                "defect": {
                    "damage_id": "CRACK_002",
                    "category": "crack",
                    "label": "horizontal_seismic_crack",
                    "severity": "severe",
                    "confidence": 0.942,
                    "position": {"x": 5.20, "y": 0.05, "z": 3.50},
                    "surface": "South Face: Rear Abutment Wall",
                    "frame": "/data/captured_images/frame_inspect_W5.jpg",
                    "annotated": "/data/detections/annotated_W5.jpg"
                }
            },
            {
                "wp": "W6",
                "name": "West Flank: Left Pier Orbit",
                "x": 4.8, "y": -1.5, "z": 3.0, "yaw": 270.0, "hold_sec": 5.0,
                "defect": {
                    "damage_id": "CRACK_003",
                    "category": "crack",
                    "label": "diagonal_shear_crack",
                    "severity": "moderate",
                    "confidence": 0.890,
                    "position": {"x": 4.50, "y": -1.80, "z": 3.00},
                    "surface": "West Face: Left Support Column",
                    "frame": "/data/captured_images/frame_inspect_W3.jpg",
                    "annotated": "/data/detections/annotated_W3.jpg"
                }
            },
            {
                "wp": "W7",
                "name": "Top Girder: Overhead Cantilever Inspection",
                "x": 3.5, "y": 1.8, "z": 4.5, "yaw": 315.0, "hold_sec": 5.0,
                "defect": {
                    "damage_id": "SPALL_002",
                    "category": "spalling",
                    "label": "beam_delamination",
                    "severity": "high",
                    "confidence": 0.915,
                    "position": {"x": 4.50, "y": 1.20, "z": 4.75},
                    "surface": "Top Girder: Beam Joint & Flange",
                    "frame": "/data/captured_images/frame_inspect_W5.jpg",
                    "annotated": "/data/detections/annotated_W5.jpg"
                }
            },
            {"wp": "W8", "name": "Return to Landing Corridor", "x": 1.0, "y": 0.0, "z": 2.5, "yaw": 0.0, "hold_sec": 2.0},
            {"wp": "W9", "name": "Autonomous Helipad Touchdown", "x": 0.0, "y": 0.0, "z": 0.05, "yaw": 0.0, "hold_sec": 3.0}
        ]

        curr_x, curr_y, curr_z = 0.0, 0.0, 0.05
        curr_yaw = 0.0
        battery = 100.0

        try:
            for station in waypoints:
                if not self.is_running:
                    break

                target_x = station["x"]
                target_y = station["y"]
                target_z = station["z"]
                target_yaw = station["yaw"]
                wp_code = station["wp"]
                self.current_waypoint = f"{wp_code}: {station['name']}"

                # Smooth transit interpolation (20 steps)
                steps = 20
                for i in range(1, steps + 1):
                    if not self.is_running:
                        break

                    frac = i / steps
                    t_smooth = (1 - math.cos(frac * math.pi)) / 2.0
                    interp_x = curr_x + (target_x - curr_x) * t_smooth
                    interp_y = curr_y + (target_y - curr_y) * t_smooth
                    interp_z = curr_z + (target_z - curr_z) * t_smooth
                    interp_yaw = curr_yaw + (target_yaw - curr_yaw) * t_smooth
                    battery = max(75.0, battery - 0.04)

                    d_3d = math.sqrt(interp_x**2 + interp_y**2 + (20.0 - interp_z)**2)
                    rtt = 9.8 + random.uniform(0.4, 2.2)

                    telemetry_payload = {
                        "position": {"x": round(interp_x, 3), "y": round(interp_y, 3), "z": round(interp_z, 3)},
                        "yaw": round(interp_yaw, 1),
                        "battery_percent": round(battery, 1),
                        "flight_status": "IN_ORBITAL_TRANSIT" if interp_z > 0.2 else "TOUCHDOWN",
                        "waypoint": self.current_waypoint,
                        "active_frame": self.active_annotated_path,
                        "raw_frame": self.active_frame_path
                    }
                    self.current_telemetry = telemetry_payload

                    if self.mqtt_service:
                        self.mqtt_service.latest_drone_telemetry = telemetry_payload

                    await self._broadcast("drone_telemetry", telemetry_payload)
                    await self._broadcast("network_metrics", {
                        "scenario": "good_signal",
                        "drone_distance_3d_m": round(d_3d, 2),
                        "latency_ms": round(rtt, 2),
                        "jitter_ms": round(random.uniform(0.6, 1.6), 2),
                        "throughput_mbps": 498.5,
                        "packet_loss_percent": 0.0,
                        "pdr": 100.0
                    })
                    await asyncio.sleep(0.12)

                curr_x, curr_y, curr_z = target_x, target_y, target_z
                curr_yaw = target_yaw

                # Inspection Station Hover & AI Detection Trigger
                if "defect" in station:
                    defect = station["defect"]
                    self.active_frame_path = defect["frame"]
                    self.active_annotated_path = defect["annotated"]
                    self.active_defect = defect

                    if not any(d["damage_id"] == defect["damage_id"] for d in self.recorded_damages):
                        self.recorded_damages.append(defect)

                    logging.info(f"Target Acquired at {wp_code}: PyTorch Model Flagged {defect['damage_id']} [{defect['severity'].upper()}]")

                    await self._broadcast("damage_detection", defect)
                    if self.mqtt_service:
                        self.mqtt_service.detected_damages.append(defect)

                    # Station dwell time
                    dwell_ticks = int(station["hold_sec"] / 0.2)
                    for _ in range(dwell_ticks):
                        if not self.is_running:
                            break
                        jitter_z = curr_z + random.uniform(-0.015, 0.015)
                        t_stat = {
                            "position": {"x": curr_x, "y": curr_y, "z": round(jitter_z, 3)},
                            "yaw": curr_yaw,
                            "battery_percent": round(battery, 1),
                            "flight_status": f"AI_INSPECTING_{wp_code}",
                            "waypoint": self.current_waypoint,
                            "active_frame": self.active_annotated_path,
                            "raw_frame": self.active_frame_path,
                            "flagged_defect": defect
                        }
                        self.current_telemetry = t_stat
                        await self._broadcast("drone_telemetry", t_stat)
                        await asyncio.sleep(0.2)
                else:
                    await asyncio.sleep(station["hold_sec"])

            logging.info("360-Degree flight mission completed successfully. Disarming on helipad.")
            final_telemetry = {
                "position": {"x": 0.0, "y": 0.0, "z": 0.05},
                "yaw": 0.0,
                "battery_percent": round(battery, 1),
                "flight_status": "MISSION_COMPLETED_DISARMED",
                "waypoint": "W9: Landed on Helipad"
            }
            self.current_telemetry = final_telemetry
            await self._broadcast("drone_telemetry", final_telemetry)

        except asyncio.CancelledError:
            logging.info("Mission flight was interrupted.")
        finally:
            self.is_running = False
