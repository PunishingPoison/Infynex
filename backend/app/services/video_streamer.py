"""
INFYNEX Real-Time Optical Camera & PyTorch AI Video Streamer
Renders continuous 20 FPS drone camera feed synchronized with 3D flight trajectory.
Continuously runs PyTorch neural network inference and draws dynamic detection squares (bounding boxes)
when structural defects enter the camera field of view.
"""

import asyncio
import cv2
import logging
import math
import numpy as np
import time
from typing import Generator, Optional

from ai_engine.inference.pytorch_damage_detector import PyTorchDamageDetector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [VideoStreamer] %(message)s")


class DroneCameraVideoStreamer:
    def __init__(self):
        self.detector = PyTorchDamageDetector()
        self.fps = 20
        self.frame_width = 1280
        self.frame_height = 720
        self.current_frame_jpeg: Optional[bytes] = None
        self.show_ai_overlay = True

        # Pre-generate high-res realistic concrete surface textures for each face
        self._init_surface_textures()

    def _init_surface_textures(self):
        """Generates realistic concrete inspection surfaces for all 4 infrastructure quadrants."""
        h, w = self.frame_height, self.frame_width

        # 1. Front Face (North): Smooth concrete wall with severe vertical crack
        np.random.seed(101)
        base = np.full((h, w), 155, dtype=np.uint8)
        noise = np.random.normal(0, 7, (h, w)).astype(np.int16)
        front = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        self.tex_front = cv2.cvtColor(front, cv2.COLOR_GRAY2BGR)
        # Vertical Jagged Crack (CRACK_001)
        cx = w // 2 - 30
        pts = []
        for y in range(140, 560, 6):
            jitter = int(np.sin(y * 0.07) * 8 + np.random.randint(-2, 3))
            pts.append((cx + jitter, y))
        for i in range(len(pts) - 1):
            cv2.line(self.tex_front, pts[i], pts[i+1], (30, 30, 30), 4)
            if i % 6 == 0:
                cv2.line(self.tex_front, pts[i], (pts[i][0] + 20, pts[i][1] + 10), (45, 45, 45), 2)

        # 2. Right Flank (East): Corner Pillar with Concrete Spalling & Exposed Rebar (SPALL_001)
        np.random.seed(102)
        base_e = np.full((h, w), 140, dtype=np.uint8)
        noise_e = np.random.normal(0, 9, (h, w)).astype(np.int16)
        east = np.clip(base_e.astype(np.int16) + noise_e, 0, 255).astype(np.uint8)
        self.tex_east = cv2.cvtColor(east, cv2.COLOR_GRAY2BGR)
        # Pillar joint edge
        cv2.line(self.tex_east, (w // 3, 0), (w // 3, h), (100, 100, 100), 3)
        # Deep Spalling Crater
        scx, scy = w // 2 + 40, h // 2
        cv2.ellipse(self.tex_east, (scx, scy), (150, 120), -10, 0, 360, (65, 65, 70), -1)
        cv2.ellipse(self.tex_east, (scx + 10, scy - 10), (130, 95), -10, 0, 360, (40, 40, 45), -1)
        # Corroded Rebar Rods
        cv2.line(self.tex_east, (scx - 90, scy - 25), (scx + 85, scy - 25), (30, 50, 140), 6)
        cv2.line(self.tex_east, (scx - 70, scy + 35), (scx + 95, scy + 35), (25, 45, 130), 6)

        # 3. Rear Face (South): Abutment Wall with Horizontal Seismic Fracture (CRACK_002)
        np.random.seed(103)
        base_s = np.full((h, w), 160, dtype=np.uint8)
        noise_s = np.random.normal(0, 6, (h, w)).astype(np.int16)
        south = np.clip(base_s.astype(np.int16) + noise_s, 0, 255).astype(np.uint8)
        self.tex_south = cv2.cvtColor(south, cv2.COLOR_GRAY2BGR)
        # Horizontal seismic fissure with efflorescence stain
        cy = h // 2 + 20
        h_pts = []
        for x in range(200, 1080, 8):
            jitter = int(np.sin(x * 0.05) * 6 + np.random.randint(-2, 3))
            h_pts.append((x, cy + jitter))
        for i in range(len(h_pts) - 1):
            cv2.line(self.tex_south, h_pts[i], h_pts[i+1], (35, 35, 35), 4)
            # White calcium efflorescence stain leaching below crack
            if i % 4 == 0:
                cv2.line(self.tex_south, h_pts[i], (h_pts[i][0] + 5, h_pts[i][1] + 35), (210, 215, 220), 2)

        # 4. Left Flank (West): Support Pier with Diagonal Shear Crack (CRACK_003)
        np.random.seed(104)
        base_w = np.full((h, w), 145, dtype=np.uint8)
        noise_w = np.random.normal(0, 8, (h, w)).astype(np.int16)
        west = np.clip(base_w.astype(np.int16) + noise_w, 0, 255).astype(np.uint8)
        self.tex_west = cv2.cvtColor(west, cv2.COLOR_GRAY2BGR)
        # Diagonal shear crack across load vector
        d_pts = []
        for step, x in enumerate(range(350, 920, 8)):
            y = int(180 + step * 4.5 + np.sin(step * 0.4) * 5)
            d_pts.append((x, y))
        for i in range(len(d_pts) - 1):
            cv2.line(self.tex_west, d_pts[i], d_pts[i+1], (35, 35, 40), 3)

        # 5. Clear Approach View (Clear concrete with construction expansion joint)
        np.random.seed(105)
        base_c = np.full((h, w), 150, dtype=np.uint8)
        noise_c = np.random.normal(0, 5, (h, w)).astype(np.int16)
        clear = np.clip(base_c.astype(np.int16) + noise_c, 0, 255).astype(np.uint8)
        self.tex_clear = cv2.cvtColor(clear, cv2.COLOR_GRAY2BGR)
        cv2.line(self.tex_clear, (w // 2, 0), (w // 2, h), (120, 120, 120), 2)

        # 6. Helipad Pad Ground View
        self.tex_helipad = np.full((h, w, 3), 30, dtype=np.uint8)
        # Dark tarmac asphalt with yellow boundary and H
        cv2.circle(self.tex_helipad, (w // 2, h // 2), 260, (20, 160, 240), 12)
        cv2.line(self.tex_helipad, (w // 2 - 90, h // 2 - 120), (w // 2 - 90, h // 2 + 120), (255, 255, 255), 24)
        cv2.line(self.tex_helipad, (w // 2 + 90, h // 2 - 120), (w // 2 + 90, h // 2 + 120), (255, 255, 255), 24)
        cv2.line(self.tex_helipad, (w // 2 - 90, h // 2), (w // 2 + 90, h // 2), (255, 255, 255), 24)

    def render_optical_frame(
        self,
        drone_pos: dict,
        drone_yaw: float,
        flight_status: str,
        waypoint_name: str
    ) -> np.ndarray:
        """
        Dynamically renders the optical scene matching drone position and viewing orientation.
        Runs PyTorch AI inference to detect cracks and overlays detection squares.
        """
        x, y, z = drone_pos.get("x", 0.0), drone_pos.get("y", 0.0), drone_pos.get("z", 0.05)
        h, w = self.frame_height, self.frame_width

        # Determine optical texture based on drone altitude and 360-degree angle
        if z < 0.3:
            # On Helipad pad
            frame = self.tex_helipad.copy()
        elif "W3" in waypoint_name or (x > 2.0 and -1.8 <= y <= -0.5):
            # Facing North Face: Front Wall Pier (CRACK_001)
            frame = self.tex_front.copy()
        elif "W4" in waypoint_name or (x > 3.0 and y > 0.8 and drone_yaw >= 60.0):
            # Facing East Face: Right Flank Spalling (SPALL_001)
            frame = self.tex_east.copy()
        elif "W5" in waypoint_name or (drone_yaw >= 150.0 and drone_yaw <= 210.0):
            # Facing South Face: Rear Seismic Fracture (CRACK_002)
            frame = self.tex_south.copy()
        elif "W6" in waypoint_name or (drone_yaw > 210.0 and drone_yaw <= 290.0):
            # Facing West Face: Left Flank Shear Crack (CRACK_003)
            frame = self.tex_west.copy()
        elif "W7" in waypoint_name or z > 4.0:
            # Overhead Cantilever Beam
            frame = self.tex_east.copy()
        else:
            # Approaching or In Transit (Clear concrete facade)
            frame = self.tex_clear.copy()

        # Add subtle flight vibration / optical motion blur jitter
        if z > 0.3:
            jitter_x = int(math.sin(time.time() * 14.0) * 2)
            jitter_y = int(math.cos(time.time() * 12.0) * 2)
            M = np.float32([[1, 0, jitter_x], [0, 1, jitter_y]])
            frame = cv2.warpAffine(frame, M, (w, h), borderMode=cv2.BORDER_REFLECT)

        # -------------------------------------------------------------
        # Real PyTorch AI Inference Pass
        # -------------------------------------------------------------
        raw_frame = frame.copy()
        detections = []
        if self.show_ai_overlay and z > 0.3:
            detections = self.detector.detect(raw_frame)
            if detections:
                frame = self.detector.draw_detections(frame, detections)

        # -------------------------------------------------------------
        # Telemetry & Camera HUD Overlay
        # -------------------------------------------------------------
        # 1. Camera Crosshairs
        cx, cy = w // 2, h // 2
        cv2.circle(frame, (cx, cy), 32, (0, 220, 120), 1, cv2.LINE_AA)
        cv2.line(frame, (cx - 45, cy), (cx - 10, cy), (0, 220, 120), 1, cv2.LINE_AA)
        cv2.line(frame, (cx + 10, cy), (cx + 45, cy), (0, 220, 120), 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy - 45), (cx, cy - 10), (0, 220, 120), 1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy + 10), (cx, cy + 45), (0, 220, 120), 1, cv2.LINE_AA)

        # 2. OSD Header & Telemetry
        cv2.rectangle(frame, (0, 0), (w, 36), (12, 18, 32), -1)
        osd_left = f"INFYNEX RGB8 | 1280x720 @ 20FPS | FOV 80.0 | POS: ({x:.2f}, {y:.2f}, {z:.2f})m | HDG: {drone_yaw:.0f}deg"
        cv2.putText(frame, osd_left, (16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (200, 220, 240), 1, cv2.LINE_AA)

        osd_right = f"STATE: {flight_status} | {waypoint_name.split(':')[0]}"
        (tw, _), _ = cv2.getTextSize(osd_right, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
        cv2.putText(frame, osd_right, (w - tw - 16, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 230, 140), 1, cv2.LINE_AA)

        # 3. AI Detection Status Flag at Bottom
        if detections:
            d = detections[0]
            flag_text = f"AI FLAGGED: {d['label'].upper()} ({d['severity'].upper()}) - CONFIDENCE {d['confidence']*100:.1f}% [PyTorch StructuralDamageCNN]"
            cv2.rectangle(frame, (0, h - 36), (w, h), (180, 20, 20) if d['severity'] == 'critical' else (200, 100, 0), -1)
            cv2.putText(frame, flag_text, (20, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)

        return frame

    def generate_mjpeg_stream(self, mission_runner) -> Generator[bytes, None, None]:
        """Continuously yields multipart MJPEG frames to browser clients."""
        while True:
            # Obtain active state from flight mission runner
            telemetry = mission_runner.current_telemetry or {
                "position": {"x": 0.0, "y": 0.0, "z": 0.05},
                "yaw": 0.0,
                "flight_status": "STANDBY",
                "waypoint": "Helipad Pad (Ready)"
            }

            frame_bgr = self.render_optical_frame(
                drone_pos=telemetry.get("position", {}),
                drone_yaw=telemetry.get("yaw", 0.0),
                flight_status=telemetry.get("flight_status", "ACTIVE"),
                waypoint_name=telemetry.get("waypoint", "SURVEY")
            )

            # Encode as JPEG
            success, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if success:
                jpeg_bytes = buffer.tobytes()
                self.current_frame_jpeg = jpeg_bytes
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes + b'\r\n'
                )

            time.sleep(1.0 / self.fps)
