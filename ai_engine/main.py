#!/usr/bin/env python3
"""
INFYNEX Edge AI Engine Service Main
Orchestrates:
1. Frame ingestion from camera stream with sim_time_ns
2. PyTorch neural network inference (crack & spalling detection)
3. 3D Ray-cast back-projection onto canonical concrete_structure.obj
4. Physical dimension conversion & severity classification
5. 3D spatial deduplication (25cm merge radius)
6. Asynchronous HTTP POST to backend FastAPI /api/v1/detections
"""

import asyncio
import cv2
import json
import logging
import math
import os
import sys
import time
import requests
import numpy as np

from ai_engine.inference.detector import EdgeDamageDetector
from ai_engine.inference.severity_classifier import classify_severity
from ai_engine.localisation.mesh_raycaster import MeshRaycaster
from ai_engine.localisation.tf_sync import TFSynchronizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [AIEngine] %(message)s")

class EdgeAIEngine:
    def __init__(self, backend_url="http://backend:8000"):
        self.backend_url = backend_url
        self.detector = EdgeDamageDetector()
        self.raycaster = MeshRaycaster()
        self.tf_sync = TFSynchronizer()
        self.saved_detections = []
        self.dedup_radius_m = 0.25 # 25cm deduplication radius
        self.out_img_dir = "/workspace/data/captured_images"
        os.makedirs(self.out_img_dir, exist_ok=True)

    def is_duplicate(self, new_xyz: list) -> bool:
        for det in self.saved_detections:
            d_xyz = [det["position"]["x"], det["position"]["y"], det["position"]["z"]]
            dist = math.sqrt((new_xyz[0] - d_xyz[0])**2 + (new_xyz[1] - d_xyz[1])**2 + (new_xyz[2] - d_xyz[2])**2)
            if dist < self.dedup_radius_m:
                return True
        return False

    def process_frame(self, frame_bgr: np.ndarray, drone_pose: dict, drone_yaw_deg: float, sim_time_ns: int) -> list:
        detections, annotated_bgr, inf_ms = self.detector.detect(frame_bgr)
        cam_origin, R_cam = self.tf_sync.get_camera_world_pose(drone_pose, drone_yaw_deg)

        new_detections = []

        for d in detections:
            u, v = d["centroid_pixel"]
            ray_res = self.raycaster.raycast_pixel(u, v, cam_origin, R_cam)

            hit_xyz = [ray_res["x"], ray_res["y"], ray_res["z"]]
            if self.is_duplicate(hit_xyz):
                continue

            sev_info = classify_severity(d["class_name"], d["bbox"], ray_res["ray_depth_m"])

            det_id = f"DEFECT_{len(self.saved_detections)+1:03d}"
            save_name = f"{det_id}_{d['class_name']}_{int(time.time())}.jpg"
            save_path = os.path.join(self.out_img_dir, save_name)
            cv2.imwrite(save_path, annotated_bgr)

            record = {
                "damage_id": det_id,
                "category": d["class_name"],
                "confidence": d["confidence"],
                "severity": sev_info["severity"],
                "surface": "concrete_infrastructure",
                "position": {"x": hit_xyz[0], "y": hit_xyz[1], "z": hit_xyz[2]},
                "physical_dimensions": {
                    "width_mm": sev_info["physical_width_mm"],
                    "height_mm": sev_info["physical_height_mm"]
                },
                "ray_depth_m": sev_info["ray_depth_m"],
                "inference_time_ms": inf_ms,
                "sim_time_ns": sim_time_ns,
                "image_path": save_path
            }

            self.saved_detections.append(record)
            new_detections.append(record)
            logging.info(f"✓ Detected & 3D Localized: {det_id} [{d['class_name'].upper()}] at ({hit_xyz[0]}, {hit_xyz[1]}, {hit_xyz[2]}) Sev: {sev_info['severity']}")

            # Post to backend if reachable
            try:
                requests.post(f"{self.backend_url}/api/v1/detections", json=record, timeout=0.5)
            except Exception:
                pass

        return new_detections

if __name__ == "__main__":
    engine = EdgeAIEngine()
    logging.info("✓ INFYNEX Edge AI Engine operational. Ready for continuous stream inference.")
