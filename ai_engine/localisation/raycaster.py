"""
INFYNEX 3D Damage Localisation Engine
Performs optical raycasting from the drone camera optical center into 3D world space
to map 2D pixel bounding-box coordinates to physical 3D structure surface coordinates.
"""

import math
import numpy as np
from typing import Tuple, Dict, Any, Optional


class DamageLocaliser:
    def __init__(self, camera_hfov_deg: float = 80.0, image_width: int = 1280, image_height: int = 720):
        self.img_w = image_width
        self.img_h = image_height
        self.hfov_rad = math.radians(camera_hfov_deg)
        # Compute focal length from horizontal FOV: fx = (w / 2) / tan(hfov / 2)
        self.fx = (self.img_w / 2.0) / math.tan(self.hfov_rad / 2.0)
        self.fy = self.fx # Square pixels assumption
        self.cx = self.img_w / 2.0
        self.cy = self.img_h / 2.0

    def localise_to_surface(
        self,
        pixel_x: float,
        pixel_y: float,
        drone_pos: Tuple[float, float, float],
        drone_yaw_deg: float,
        surface_plane_x: Optional[float] = 4.74,
        standoff_distance_m: Optional[float] = None
    ) -> Optional[Dict[str, float]]:
        """
        Casts a ray from camera focal point through (pixel_x, pixel_y) and intersects
        with known structure plane or uses rangefinder standoff distance.
        """
        dx_cam = (pixel_x - self.cx) / self.fx
        dy_cam = (pixel_y - self.cy) / self.fy
        dz_cam = 1.0 # Optical ray forward

        # Normalise ray vector in camera coordinate frame (Z forward, X right, Y down)
        norm = math.sqrt(dx_cam**2 + dy_cam**2 + dz_cam**2)
        ray_cam = np.array([dz_cam / norm, -dx_cam / norm, -dy_cam / norm]) # Transform to ROS NWU frame

        # Rotate ray by drone yaw
        yaw_rad = math.radians(drone_yaw_deg)
        cos_y = math.cos(yaw_rad)
        sin_y = math.sin(yaw_rad)

        rot_matrix = np.array([
            [cos_y, -sin_y, 0.0],
            [sin_y,  cos_y, 0.0],
            [0.0,    0.0,   1.0]
        ])
        ray_world = rot_matrix @ ray_cam

        if standoff_distance_m is not None:
            t = float(standoff_distance_m)
        elif surface_plane_x is not None and abs(ray_world[0]) > 0.05:
            t = (surface_plane_x - drone_pos[0]) / ray_world[0]
            if t <= 0:
                t = 1.35
        else:
            t = 1.35

        hit_x = drone_pos[0] + t * ray_world[0]
        hit_y = drone_pos[1] + t * ray_world[1]
        hit_z = drone_pos[2] + t * ray_world[2]

        return {
            "x": round(float(hit_x), 3),
            "y": round(float(hit_y), 3),
            "z": round(float(hit_z), 3),
            "ray_distance_m": round(float(t), 2)
        }
