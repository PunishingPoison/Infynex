"""
INFYNEX Computer Vision Preprocessing Pipeline
Normalizes, resizes, and enhances inspection frames captured by the drone RGB camera.
"""

import cv2
import numpy as np
from typing import Tuple, Dict, Any


class ImagePreprocessor:
    def __init__(self, target_size: Tuple[int, int] = (640, 640), apply_clahe: bool = True):
        self.target_size = target_size
        self.apply_clahe = apply_clahe
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

    def process(self, image_bgr: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Preprocesses a raw camera frame for deep learning damage detection models.
        Returns:
            processed_tensor: Float32 normalized array (C, H, W) in [0.0, 1.0]
            metadata: Scaling and padding factors for accurate bounding box / mask re-projection
        """
        h_orig, w_orig = image_bgr.shape[:2]

        # 1. Contrast Limited Adaptive Histogram Equalization (CLAHE) in LAB space for crack visibility
        if self.apply_clahe:
            lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l_enhanced = self.clahe.apply(l)
            enhanced = cv2.merge((l_enhanced, a, b))
            image_bgr = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

        # 2. Letterbox resize maintaining aspect ratio
        target_w, target_h = self.target_size
        scale = min(target_w / w_orig, target_h / h_orig)
        new_w = int(w_orig * scale)
        new_h = int(h_orig * scale)

        resized = cv2.resize(image_bgr, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # Create padded canvas
        canvas = np.full((target_h, target_w, 3), 114, dtype=np.uint8)
        pad_x = (target_w - new_w) // 2
        pad_y = (target_h - new_h) // 2
        canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized

        # 3. Convert to RGB, normalize to [0, 1] and transpose to (C, H, W)
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(normalized, (2, 0, 1))

        metadata = {
            "orig_shape": (h_orig, w_orig),
            "target_shape": (target_h, target_w),
            "scale": scale,
            "pad_x": pad_x,
            "pad_y": pad_y
        }
        return tensor, metadata
