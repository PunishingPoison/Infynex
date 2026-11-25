#!/usr/bin/env python3
"""
INFYNEX 5G Trajectory Coupler
Couples drone real-time 3D flight trajectory with 3GPP 5G NR propagation model.
Computes Line-of-Sight occlusion against canonical bridge geometry and maps to radio profiles.
"""

import json
import logging
import math
import os
import sys
import time
from typing import Dict, Any, Tuple

# Path resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [5GCoupler] %(message)s")

class TrajectoryCoupler:
    def __init__(self, profiles_path: str = None, broker_host: str = "localhost", broker_port: int = 1883):
        if profiles_path is None:
            profiles_path = os.path.join(os.path.dirname(__file__), "../profiles/radio_profiles.json")

        with open(profiles_path, "r") as f:
            self.config = json.load(f)

        self.gnb = self.config["gnb_location"]
        self.profiles = self.config["profiles"]
        self.broker_host = broker_host
        self.broker_port = broker_port

        # Canonical structure geometric bounding boxes for ray-occlusion check
        # Pier North: X in [-5.3, -3.7], Y in [-1.5, 1.5], Z in [0, 5.0]
        # Pier South: X in [3.7, 5.3], Y in [-1.5, 1.5], Z in [0, 5.0]
        # Deck: X in [-8.0, 8.0], Y in [-2.5, 2.5], Z in [5.0, 6.5]
        self.obstacles = [
            {"name": "pier_north", "bounds": ((-5.3, -1.5, 0.0), (-3.7, 1.5, 5.0))},
            {"name": "pier_south", "bounds": ((3.7, -1.5, 0.0), (5.3, 1.5, 5.0))},
            {"name": "deck_girder", "bounds": ((-8.0, -2.5, 5.0), (8.0, 2.5, 6.5))}
        ]

        self.mqtt_client = mqtt.Client(client_id="infynex_5g_coupler", protocol=mqtt.MQTTv311)
        self.is_connected = False

    def connect(self) -> bool:
        try:
            self.mqtt_client.connect(self.broker_host, self.broker_port, keepalive=60)
            self.mqtt_client.loop_start()
            self.is_connected = True
            logging.info(f"✓ Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            return True
        except Exception as e:
            logging.warning(f"Could not connect to MQTT: {e}")
            return False

    def _ray_box_intersect(self, origin: Tuple[float, float, float], target: Tuple[float, float, float], box: Tuple) -> bool:
        """Slab test for ray-segment intersection with an axis-aligned bounding box."""
        min_b, max_b = box
        d = (target[0] - origin[0], target[1] - origin[1], target[2] - origin[2])
        tmin = 0.0
        tmax = 1.0

        for i in range(3):
            if abs(d[i]) < 1e-6:
                if origin[i] < min_b[i] or origin[i] > max_b[i]:
                    return False
            else:
                ood = 1.0 / d[i]
                t1 = (min_b[i] - origin[i]) * ood
                t2 = (max_b[i] - origin[i]) * ood
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    return False
        return True

    def evaluate_link(self, drone_x: float, drone_y: float, drone_z: float, sim_time_ns: int = 0) -> Dict[str, Any]:
        """Calculates 5G channel profile based on drone 3D position relative to gNodeB."""
        p_drone = (drone_x, drone_y, drone_z)
        p_gnb = (self.gnb["x"], self.gnb["y"], self.gnb["z"])

        dist_3d = math.sqrt((p_drone[0] - p_gnb[0])**2 + (p_drone[1] - p_gnb[1])**2 + (p_drone[2] - p_gnb[2])**2)

        # Check line-of-sight occlusion
        is_occluded = False
        occluding_obj = None
        for obs in self.obstacles:
            if self._ray_box_intersect(p_drone, p_gnb, obs["bounds"]):
                is_occluded = True
                occluding_obj = obs["name"]
                break

        # Map to profile
        if is_occluded:
            if drone_z < 3.0:
                profile_key = "shadowed_degraded"
            else:
                profile_key = "nlos_moderate"
        else:
            if dist_3d < 18.0:
                profile_key = "los_optimal"
            elif dist_3d < 35.0:
                profile_key = "los_good"
            elif dist_3d < 60.0:
                profile_key = "cell_edge"
            else:
                profile_key = "handover_drop"

        profile_data = self.profiles[profile_key].copy()
        profile_data["profile_key"] = profile_key
        profile_data["distance_3d_m"] = round(dist_3d, 2)
        profile_data["is_los"] = not is_occluded
        profile_data["occluding_element"] = occluding_obj
        profile_data["drone_position"] = {"x": drone_x, "y": drone_y, "z": drone_z}
        profile_data["gnb_position"] = self.gnb
        profile_data["sim_time_ns"] = sim_time_ns
        profile_data["wall_time_ns"] = time.time_ns()

        # Publish link telemetry
        if self.is_connected:
            self.mqtt_client.publish("infynex/5g/telemetry", json.dumps(profile_data), qos=0)

        return profile_data

    def close(self):
        if self.is_connected:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
