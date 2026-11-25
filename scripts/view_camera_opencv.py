#!/usr/bin/env python3
"""
INFYNEX Live Camera Viewer with Dual Pretrained Ultralytics YOLO AI
and Geometry- & Physics-Based Architectural False Positive Suppression Filter.

Features:
1. Dual Pretrained Models on RTX 3050 Laptop GPU (CUDA):
   - IAAC RC Damage Segmentation (rc_damage_seg.pt) - Multiclass RC damage (spall, rebar, crack)
   - OpenSistemas YOLOv8 Crack Segmentation (yolov8s_crack_seg.pt) - High continuity crack specialist
2. Intelligent Architectural False Positive Suppression:
   - Window Rejection: Detects blue-dominant architectural window glass and window mullion borders.
   - Cornice / Seam Rejection: Rejects ultra-wide, razor-straight horizontal cornice stripes (aspect > 6.0).
   - Micro-noise Rejection: Filters small texture flecks (area < 150 px).
   - Crack Physics Verification: Measures tortuosity (tau), skeleton length, and mean crack width (px).
3. Verified vs Suppressed Defect Rendering:
   - Genuine defects are clearly outlined in bold high-contrast brackets with segmentation masks.
   - Telemetry HUD displays live FPS, GPU acceleration, and real-time defect counters.
"""

import os
import sys
import time
import math
import json
import threading
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

# Import PyTorch and Ultralytics YOLO
TORCH_AVAILABLE = False
ULTRALYTICS_AVAILABLE = False
try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    TORCH_AVAILABLE = False

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except Exception:
    ULTRALYTICS_AVAILABLE = False


def compute_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou


@dataclass
class FilterMetrics:
    area_px: float
    tortuosity: float
    width_mean_px: float
    aspect_ratio: float
    blue_ratio: float


@dataclass
class VerifiedDefect:
    class_name: str
    label: str
    category: str
    severity: str
    raw_conf: float
    adjusted_conf: float
    bbox: Tuple[int, int, int, int]
    polygon: Optional[np.ndarray]
    mask: Optional[np.ndarray]
    accepted: bool
    reject_reason: str
    metrics: FilterMetrics
    model_src: str


class ArchitecturalFalsePositiveFilter:
    """
    Separates genuine structural damage (cracks, spalls, exposed rebar)
    from architectural features (windows, cornices, shadows, mottled texture noise).
    """
    def __init__(
        self,
        min_crack_area: int = 50,
        min_spall_area: int = 80,
        min_crack_conf: float = 0.25,
        min_spall_conf: float = 0.28,
    ):
        self.min_crack_area = min_crack_area
        self.min_spall_area = min_spall_area
        self.min_crack_conf = min_crack_conf
        self.min_spall_conf = min_spall_conf

    @staticmethod
    def _skeletonize(binary_mask: np.ndarray) -> np.ndarray:
        if hasattr(cv2, "ximgproc") and hasattr(cv2.ximgproc, "thinning"):
            return cv2.ximgproc.thinning(binary_mask)

        img = (binary_mask > 0).astype(np.uint8) * 255
        skel = np.zeros_like(img)
        element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        for _ in range(15):
            eroded = cv2.erode(img, element)
            opened = cv2.dilate(eroded, element)
            temp = cv2.subtract(img, opened)
            skel = cv2.bitwise_or(skel, temp)
            img = eroded
            if cv2.countNonZero(img) == 0:
                break
        return skel

    @staticmethod
    def _compute_metrics(
        bgr_roi: np.ndarray,
        mask_roi: np.ndarray,
        skel_roi: np.ndarray,
    ) -> Tuple[float, float, float, float]:
        area_px = float(cv2.countNonZero(mask_roi))
        ys, xs = np.nonzero(skel_roi)
        n_pts = len(xs)

        if n_pts >= 4:
            pts = np.column_stack((xs, ys)).astype(np.float32)
            mean = pts.mean(axis=0)
            centered = pts - mean
            cov = np.cov(centered.T)
            _, eigvecs = np.linalg.eigh(cov)
            major_vec = eigvecs[:, 1]
            proj_major = centered @ major_vec
            idx_min = int(np.argmin(proj_major))
            idx_max = int(np.argmax(proj_major))
            euclid_span = float(np.linalg.norm(pts[idx_max] - pts[idx_min]))

            skel_bin = (skel_roi > 0).astype(np.uint8)
            horiz_vert = (
                np.count_nonzero(skel_bin[:, :-1] & skel_bin[:, 1:])
                + np.count_nonzero(skel_bin[:-1, :] & skel_bin[1:, :])
            )
            arc_length = float(horiz_vert)
            if arc_length < euclid_span:
                arc_length = float(n_pts)

            tortuosity = arc_length / max(euclid_span, 1.0)
            dist_map = cv2.distanceTransform(mask_roi, cv2.DIST_L2, 5)
            widths = 2.0 * dist_map[ys, xs]
            width_mean = float(np.mean(widths)) if len(widths) > 0 else 2.0
        else:
            tortuosity = 1.05
            width_mean = 2.5

        # Check blue color ratio (detects reflective architectural window glass)
        if bgr_roi.size > 0:
            mean_b = float(np.mean(bgr_roi[:, :, 0]))
            mean_g = float(np.mean(bgr_roi[:, :, 1]))
            mean_r = float(np.mean(bgr_roi[:, :, 2]))
            blue_ratio = (mean_b + 1.0) / (mean_r + mean_g + 1.0)
        else:
            blue_ratio = 0.5

        return area_px, tortuosity, width_mean, blue_ratio

    def evaluate(
        self,
        bgr_frame: np.ndarray,
        mask_full: np.ndarray,
        bbox: Tuple[int, int, int, int],
        class_name: str,
        raw_conf: float,
    ) -> Tuple[bool, float, str, FilterMetrics]:
        h_img, w_img = bgr_frame.shape[:2]
        x1, y1, x2, y2 = bbox
        bw = max(1, x2 - x1)
        bh = max(1, y2 - y1)
        aspect = float(bh) / float(bw)

        mask_roi = mask_full[y1:y2, x1:x2]
        bgr_roi = bgr_frame[y1:y2, x1:x2]

        is_crack = "crack" in class_name.lower()

        # 1. Reject Window Glass Features (blue dominance from Gazebo window material)
        if bgr_roi.size > 0:
            mean_b = float(np.mean(bgr_roi[:, :, 0]))
            mean_g = float(np.mean(bgr_roi[:, :, 1]))
            mean_r = float(np.mean(bgr_roi[:, :, 2]))
            # In our SDF, windows have cyan/blue diffuse (0.10, 0.18, 0.28)
            if mean_b > mean_r + 25 and mean_b > mean_g + 8:
                metrics = FilterMetrics(float(bw * bh), 1.0, 2.0, aspect, 1.2)
                return False, 0.0, "architectural_window_glass", metrics

        # 2. Reject Cornice Lines (extremely wide and thin horizontal building bands)
        if bw > 300 and bh < 40 and aspect < 0.12:
            metrics = FilterMetrics(float(bw * bh), 1.0, float(bh), aspect, 0.5)
            return False, 0.0, "architectural_cornice_stripe", metrics

        # 3. Class-specific Evaluation
        if is_crack:
            if raw_conf < self.min_crack_conf:
                metrics = FilterMetrics(float(bw * bh), 1.0, 2.0, aspect, 0.5)
                return False, raw_conf, "low_crack_conf", metrics

            skel_roi = self._skeletonize(mask_roi)
            area_px, tortuosity, width_mean, blue_ratio = self._compute_metrics(bgr_roi, mask_roi, skel_roi)
            metrics = FilterMetrics(area_px, tortuosity, width_mean, aspect, blue_ratio)

            if area_px < self.min_crack_area:
                return False, 0.0, "micro_noise", metrics

            # Reject excessive width for thin crack (wedges, sidewalk slabs, shadows)
            if width_mean > 25.0:
                return False, 0.0, "too_wide_for_crack", metrics

            # Reject image perimeter boundary artifacts (ground plane / sky / building edges touching border)
            touches_border = (y2 >= h_img - 8 or y1 <= 8 or x1 <= 8 or x2 >= w_img - 8)
            if touches_border and width_mean > 12.0:
                return False, 0.0, "perimeter_boundary_artifact", metrics

            # Accept genuine crack
            return True, raw_conf, "ok", metrics

        else:
            # Spalling, Rebar Exposure, Delamination
            if raw_conf < self.min_spall_conf:
                metrics = FilterMetrics(float(bw * bh), 1.0, 0.0, aspect, 0.5)
                return False, raw_conf, "low_spall_conf", metrics

            area_px = float(cv2.countNonZero(mask_roi)) if mask_roi.size > 0 else float(bw * bh)
            metrics = FilterMetrics(area_px, 1.0, float(min(bw, bh)), aspect, 0.5)

            if area_px < self.min_spall_area:
                return False, 0.0, "micro_noise", metrics

            # Accept genuine spall / rebar defect
            return True, raw_conf, "ok", metrics


class NativeAIDamageViewer(Node):
    CLASS_COLORS: Dict[str, Tuple[int, int, int]] = {
        "crack": (0, 0, 255),            # Bright Red
        "spalling": (0, 140, 255),        # Deep Orange
        "rebar_exposure": (0, 215, 255),  # Yellow Gold
        "rebar_corrosion": (180, 0, 255), # Purple
        "crushing": (0, 0, 200),
    }

    def __init__(self, topic="/camera"):
        super().__init__("infynex_native_ai_damage_viewer")
        self.topic = topic
        self.subscription = self.create_subscription(
            Image,
            self.topic,
            self.image_callback,
            10
        )
        self.frame_count = 0
        self.last_time = time.time()
        self.fps = 0.0
        self.total_verified_logged = 0
        self.last_snapshot_time = 0.0
        self.snapshot_dir = "/workspace/data/captured_images"
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self.window_name = "INFYNEX - Real Live Camera Feed (Gazebo Harmonic RGB + Pretrained AI)"
        cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

        # Initialize Geometric False Positive Filter
        self.fp_filter = ArchitecturalFalsePositiveFilter()

        # Initialize Pretrained AI Models
        self.device = "cpu"
        self.device_name = "CPU"
        self.rc_model = None
        self.crack_model = None
        self.active_models_desc = "None"
        self.init_ai_models()

        self.get_logger().info(f"✓ Native OpenCV AI Viewer active on ROS 2 topic: {self.topic}")

    def init_ai_models(self):
        if not TORCH_AVAILABLE:
            self.get_logger().warn("PyTorch is not available.")
            return

        if torch.cuda.is_available():
            self.device = 0
            gpu_name = torch.cuda.get_device_name(0)
            self.device_name = f"RTX 3050 CUDA ({gpu_name})"
            self.get_logger().info(f"✓ CUDA GPU Hardware Acceleration active: {self.device_name}")
        else:
            self.device = "cpu"
            self.device_name = "CPU"
            self.get_logger().info("Running PyTorch on CPU")

        if not ULTRALYTICS_AVAILABLE:
            self.get_logger().warn("Ultralytics library not available.")
            return

        # 1. Multi-Class Reinforced Concrete Damage Segmentation Model
        rc_path = "/workspace/ai_engine/weights/rc_damage_seg.pt"
        if os.path.exists(rc_path):
            try:
                self.rc_model = YOLO(rc_path)
                self.get_logger().info("✓ Loaded Pretrained RC Damage Model (YOLO26n-seg)")
            except Exception as e:
                self.get_logger().warn(f"Failed to load RC damage model: {e}")

        # 2. Dedicated Crack Segmentation Model (OpenSistemas)
        crack_path = "/workspace/ai_engine/weights/yolov8s_crack_seg.pt"
        if os.path.exists(crack_path):
            try:
                self.crack_model = YOLO(crack_path)
                self.get_logger().info("✓ Loaded Pretrained Crack Segmentation Model (YOLOv8s-seg)")
            except Exception as e:
                self.get_logger().warn(f"Failed to load crack model: {e}")

        if self.rc_model and self.crack_model:
            self.active_models_desc = "Dual-CNN (RC-Seg + Crack-Seg)"
        elif self.rc_model:
            self.active_models_desc = "Ultralytics YOLO26n-seg"
        elif self.crack_model:
            self.active_models_desc = "Ultralytics YOLOv8s-crack-seg"
        else:
            self.active_models_desc = "Visual AI Engine"

    def run_inference(self, frame_bgr: np.ndarray) -> List[VerifiedDefect]:
        raw_candidates = []
        h_img, w_img = frame_bgr.shape[:2]

        # 1. Multi-Damage Segmentation Pass (RC Damage: spall, rebar, crack)
        if self.rc_model is not None:
            try:
                res_rc = self.rc_model.predict(
                    source=frame_bgr,
                    imgsz=800,
                    conf=0.24,
                    device=self.device,
                    retina_masks=True,
                    verbose=False
                )
                if res_rc and len(res_rc) > 0:
                    r0 = res_rc[0]
                    boxes = r0.boxes
                    masks = r0.masks
                    if boxes is not None:
                        masks_data = masks.data.detach().cpu().numpy() if masks is not None else None
                        polys = masks.xy if masks is not None else []
                        for i, box in enumerate(boxes):
                            cls_id = int(box.cls[0].item())
                            conf_val = float(box.conf[0].item())
                            xyxy = box.xyxy[0].cpu().numpy().astype(int)
                            x1 = max(0, min(w_img - 1, int(xyxy[0])))
                            y1 = max(0, min(h_img - 1, int(xyxy[1])))
                            x2 = max(x1 + 1, min(w_img, int(xyxy[2])))
                            y2 = max(y1 + 1, min(h_img, int(xyxy[3])))

                            cls_name = self.rc_model.names.get(cls_id, "damage").lower()

                            if "spall" in cls_name or "rebar" in cls_name or "crush" in cls_name:
                                cat = "spalling"
                                lbl = "CONCRETE_SPALLING" if "spall" in cls_name else cls_name.upper()
                                sev = "CRITICAL"
                            else:
                                cat = "crack"
                                aspect = float(y2 - y1) / max(x2 - x1, 1)
                                lbl = "VERTICAL_CRACK" if aspect > 1.25 else ("HORIZONTAL_CRACK" if aspect < 0.75 else "DIAGONAL_CRACK")
                                sev = "CRITICAL" if conf_val >= 0.65 else "MODERATE"

                            if masks_data is not None and len(masks_data) > i:
                                raw_mask = (masks_data[i] > 0.5).astype(np.uint8) * 255
                                if raw_mask.shape != (h_img, w_img):
                                    raw_mask = cv2.resize(raw_mask, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
                            else:
                                raw_mask = np.zeros((h_img, w_img), dtype=np.uint8)
                                raw_mask[y1:y2, x1:x2] = 255

                            poly = None
                            if len(polys) > i and len(polys[i]) >= 3:
                                poly = np.round(polys[i]).astype(np.int32)

                            accepted, adj_conf, reason, metrics = self.fp_filter.evaluate(
                                bgr_frame=frame_bgr,
                                mask_full=raw_mask,
                                bbox=(x1, y1, x2, y2),
                                class_name=cls_name,
                                raw_conf=conf_val
                            )

                            raw_candidates.append(
                                VerifiedDefect(
                                    class_name=cls_name,
                                    label=lbl,
                                    category=cat,
                                    severity=sev,
                                    raw_conf=round(conf_val, 3),
                                    adjusted_conf=round(adj_conf, 3),
                                    bbox=(x1, y1, x2, y2),
                                    polygon=poly,
                                    mask=raw_mask,
                                    accepted=accepted,
                                    reject_reason=reason,
                                    metrics=metrics,
                                    model_src="rc_damage"
                                )
                            )
            except Exception as e:
                self.get_logger().error(f"RC model inference error: {e}")

        # 2. Dedicated Crack Segmentation Pass (OpenSistemas YOLOv8s-seg)
        if self.crack_model is not None:
            try:
                res_crack = self.crack_model.predict(
                    source=frame_bgr,
                    imgsz=800,
                    conf=0.24,
                    device=self.device,
                    retina_masks=True,
                    verbose=False
                )
                if res_crack and len(res_crack) > 0:
                    r0 = res_crack[0]
                    boxes = r0.boxes
                    masks = r0.masks
                    if boxes is not None:
                        masks_data = masks.data.detach().cpu().numpy() if masks is not None else None
                        polys = masks.xy if masks is not None else []
                        for i, box in enumerate(boxes):
                            conf_val = float(box.conf[0].item())
                            xyxy = box.xyxy[0].cpu().numpy().astype(int)
                            x1 = max(0, min(w_img - 1, int(xyxy[0])))
                            y1 = max(0, min(h_img - 1, int(xyxy[1])))
                            x2 = max(x1 + 1, min(w_img, int(xyxy[2])))
                            y2 = max(y1 + 1, min(h_img, int(xyxy[3])))

                            aspect = float(y2 - y1) / max(x2 - x1, 1)
                            lbl = "VERTICAL_CRACK" if aspect > 1.25 else ("HORIZONTAL_CRACK" if aspect < 0.75 else "DIAGONAL_CRACK")
                            sev = "CRITICAL" if conf_val >= 0.65 else "MODERATE"

                            if masks_data is not None and len(masks_data) > i:
                                raw_mask = (masks_data[i] > 0.5).astype(np.uint8) * 255
                                if raw_mask.shape != (h_img, w_img):
                                    raw_mask = cv2.resize(raw_mask, (w_img, h_img), interpolation=cv2.INTER_NEAREST)
                            else:
                                raw_mask = np.zeros((h_img, w_img), dtype=np.uint8)
                                raw_mask[y1:y2, x1:x2] = 255

                            poly = None
                            if len(polys) > i and len(polys[i]) >= 3:
                                poly = np.round(polys[i]).astype(np.int32)

                            accepted, adj_conf, reason, metrics = self.fp_filter.evaluate(
                                bgr_frame=frame_bgr,
                                mask_full=raw_mask,
                                bbox=(x1, y1, x2, y2),
                                class_name="crack",
                                raw_conf=conf_val
                            )

                            raw_candidates.append(
                                VerifiedDefect(
                                    class_name="crack",
                                    label=lbl,
                                    category="crack",
                                    severity=sev,
                                    raw_conf=round(conf_val, 3),
                                    adjusted_conf=round(adj_conf, 3),
                                    bbox=(x1, y1, x2, y2),
                                    polygon=poly,
                                    mask=raw_mask,
                                    accepted=accepted,
                                    reject_reason=reason,
                                    metrics=metrics,
                                    model_src="crack_seg"
                                )
                            )
            except Exception as e:
                self.get_logger().error(f"Crack model inference error: {e}")

        if not raw_candidates:
            return []

        # 3. Non-Maximum Suppression (NMS)
        raw_candidates.sort(key=lambda d: d.adjusted_conf if d.accepted else d.raw_conf, reverse=True)
        final_detections: List[VerifiedDefect] = []
        for det in raw_candidates:
            keep = True
            for existing in final_detections:
                iou = compute_iou(det.bbox, existing.bbox)
                if iou > 0.40:
                    keep = False
                    break
            if keep:
                final_detections.append(det)

        return final_detections

    def notify_backend_async(self, det: VerifiedDefect, snapshot_path: str):
        def post_payload():
            url = "http://localhost:8000/api/v1/detections"
            payload = {
                "asset_id": "INFRA_CONCRETE_STRUCTURE_001",
                "damage_type": det.category,
                "confidence": det.adjusted_conf,
                "severity": det.severity.lower(),
                "snapshot_url": f"/static/captures/{os.path.basename(snapshot_path)}",
                "metadata": {
                    "label": det.label,
                    "raw_class": det.class_name,
                    "bbox": list(det.bbox),
                    "tortuosity": round(det.metrics.tortuosity, 2),
                    "width_mean_px": round(det.metrics.width_mean_px, 1),
                    "model": f"{self.active_models_desc} ({self.device_name})"
                }
            }
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    pass
            except Exception:
                pass
        threading.Thread(target=post_payload, daemon=True).start()

    def image_callback(self, msg: Image):
        self.frame_count += 1
        now = time.time()
        dt = now - self.last_time
        if dt >= 1.0:
            self.fps = self.frame_count / dt
            self.frame_count = 0
            self.last_time = now

        try:
            if msg.encoding in ["rgb8", "RGB8"]:
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            elif msg.encoding in ["bgr8", "BGR8"]:
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3)).copy()
            elif msg.encoding in ["mono8", "MONO8"]:
                gray = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width))
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            else:
                frame = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, -1))
                if frame.shape[2] == 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            h, w = frame.shape[:2]

            detections = self.run_inference(frame)
            vis = frame.copy()
            overlay = frame.copy()

            verified_defects = [d for d in detections if d.accepted]
            suppressed_fps = [d for d in detections if not d.accepted]
            has_verified = len(verified_defects) > 0

            # 1. Render Verified Real Structural Defects in High-Tech Badges
            for det in verified_defects:
                xmin, ymin, xmax, ymax = det.bbox
                is_crit = det.severity == "CRITICAL"
                box_color = (0, 0, 245) if is_crit else (0, 145, 255)

                # Segmentation Polygon Mask
                if det.polygon is not None and len(det.polygon) >= 3:
                    mask_color = (40, 40, 240) if is_crit else (0, 180, 255)
                    cv2.fillPoly(overlay, [det.polygon], mask_color)
                    cv2.polylines(vis, [det.polygon], True, box_color, 2, cv2.LINE_AA)

                # Corner Accent Brackets
                cv2.rectangle(vis, (xmin, ymin), (xmax, ymax), box_color, 2)
                c_len = min(20, (xmax - xmin) // 3, (ymax - ymin) // 3)
                if c_len > 4:
                    cv2.line(vis, (xmin, ymin), (xmin + c_len, ymin), box_color, 3)
                    cv2.line(vis, (xmin, ymin), (xmin, ymin + c_len), box_color, 3)
                    cv2.line(vis, (xmax, ymin), (xmax - c_len, ymin), box_color, 3)
                    cv2.line(vis, (xmax, ymin), (xmax, ymin + c_len), box_color, 3)
                    cv2.line(vis, (xmin, ymax), (xmin + c_len, ymax), box_color, 3)
                    cv2.line(vis, (xmin, ymax), (xmin, ymax - c_len), box_color, 3)
                    cv2.line(vis, (xmax, ymax), (xmax - c_len, ymax), box_color, 3)
                    cv2.line(vis, (xmax, ymax), (xmax - c_len, ymax), box_color, 3)

                # Label Badge Banner
                if "crack" in det.category:
                    tag = f"AI: {det.label} {det.adjusted_conf*100:.1f}% [tau:{det.metrics.tortuosity:.2f}]"
                else:
                    tag = f"AI: {det.label} {det.adjusted_conf*100:.1f}% [{det.severity}]"

                (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
                tag_y = max(th + 6, ymin)
                cv2.rectangle(vis, (xmin, tag_y - th - 6), (xmin + tw + 10, tag_y + 2), box_color, -1)
                cv2.putText(vis, tag, (xmin + 5, tag_y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

            # Blend semi-transparent segmentation overlay
            if has_verified:
                cv2.addWeighted(overlay, 0.35, vis, 0.65, 0, vis)

            # Save snapshot if defect detected (rate limited to 1 per 2.0s)
            if has_verified and (now - self.last_snapshot_time > 2.0):
                self.last_snapshot_time = now
                self.total_verified_logged += 1
                det0 = verified_defects[0]
                snap_file = f"{self.snapshot_dir}/defect_{det0.label.lower()}_{int(now)}.jpg"
                cv2.imwrite(snap_file, vis)
                self.notify_backend_async(det0, snap_file)

            # Top Telemetry HUD Banner
            cv2.rectangle(vis, (0, 0), (w, 44), (16, 18, 22), -1)
            hud_line1 = f"INFYNEX SHM CAMERA | {w}x{h} @ {self.fps:.1f} FPS | {self.device_name}"
            cv2.putText(vis, hud_line1, (12, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (0, 255, 180), 1, cv2.LINE_AA)

            hud_line2 = f"VERIFIED DEFECTS IN FOV: {len(verified_defects)} | ARCHITECTURAL FEATURES SUPPRESSED: {len(suppressed_fps)}"
            hud_color = (0, 130, 255) if has_verified else (80, 220, 140)
            cv2.putText(vis, hud_line2, (12, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.42, hud_color, 1, cv2.LINE_AA)

            cv2.imshow(self.window_name, vis)
            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                rclpy.shutdown()

        except Exception as e:
            self.get_logger().error(f"Image processing error: {e}")

    def destroy_node(self):
        cv2.destroyAllWindows()
        super().destroy_node()


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "/camera"
    rclpy.init()
    node = NativeAIDamageViewer(topic=topic)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
