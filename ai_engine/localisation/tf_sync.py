#!/usr/bin/env python3
"""
INFYNEX Transform & Timestamp Synchronizer (tf_sync)
Synchronizes incoming video frame sim_time_ns with drone odometry pose.
Computes camera mounting extrinsics [R | t] in Gazebo ENU coordinates.
"""

import math
import numpy as np

class TFSynchronizer:
    def __init__(self, camera_mount_offset=[0.15, 0.0, 0.12]):
        self.camera_offset = np.array(camera_mount_offset)

    def get_camera_world_pose(self, drone_enu_pos: dict, drone_yaw_deg: float) -> tuple[np.ndarray, np.ndarray]:
        yaw_rad = math.radians(drone_yaw_deg)
        cos_y = math.cos(yaw_rad)
        sin_y = math.sin(yaw_rad)

        # Body to World rotation matrix (Z-up ENU)
        R_body_to_world = np.array([
            [cos_y, -sin_y, 0.0],
            [sin_y,  cos_y, 0.0],
            [0.0,    0.0,   1.0]
        ])

        drone_xyz = np.array([drone_enu_pos["x"], drone_enu_pos["y"], drone_enu_pos["z"]])
        camera_world_pos = drone_xyz + (R_body_to_world @ self.camera_offset)

        return camera_world_pos, R_body_to_world
