#!/usr/bin/env python3
"""
INFYNEX Stream Consumer
Consumes live optical stream, decodes incoming frames,
records frame arrival times, and computes real-time FPS and dropped frame counts.
"""

import time
import cv2
import numpy as np

class StreamConsumer:
    def __init__(self, target_fps=20.0):
        self.target_fps = target_fps
        self.frame_count = 0
        self.dropped_frames = 0
        self.last_arrival_time = None
        self.fps_history = []

    def process_incoming_frame(self, raw_frame_bytes: bytes, sim_time_ns: int) -> dict:
        t_arr = time.time()
        self.frame_count += 1

        # Check dropped frame threshold (if gap > 1.8x frame interval)
        if self.last_arrival_time is not None:
            dt = t_arr - self.last_arrival_time
            expected_interval = 1.0 / self.target_fps
            if dt > (expected_interval * 1.8):
                drops = int(dt / expected_interval) - 1
                self.dropped_frames += max(0, drops)

        self.last_arrival_time = t_arr

        # Decode image
        np_arr = np.frombuffer(raw_frame_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        effective_fps = self.target_fps if dt == 0 else min(30.0, 1.0 / dt) if 'dt' in locals() else self.target_fps

        return {
            "image": img,
            "seq": self.frame_count,
            "sim_time_ns": sim_time_ns,
            "arrival_wall_time": t_arr,
            "effective_fps": round(effective_fps, 1),
            "total_dropped_frames": self.dropped_frames
        }
