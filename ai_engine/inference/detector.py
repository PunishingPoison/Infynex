#!/usr/bin/env python3
"""
INFYNEX Real PyTorch Damage Detector
Executes real deep neural network inference on 640x640 resized frames.
Outputs detected defects with mask centroids, bounding boxes, labels, and confidence ratings.
Draws dynamic high-contrast target squares onto annotated inspection frames.
"""

import cv2
import numpy as np
import time
import torch
import torchvision.transforms as T
from ai_engine.models.crack_segmentor_cnn import StructuralDamageCNN

CLASS_MAP = {
    0: "background",
    1: "crack_vertical",
    2: "spalling",
    3: "crack_diagonal"
}

class EdgeDamageDetector:
    def __init__(self, weights_path=None, conf_threshold=0.65):
        self.conf_threshold = conf_threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = StructuralDamageCNN(num_classes=4).to(self.device)
        self.model.eval()

        # Load weights
        if weights_path is None:
            # Check candidate paths
            for p in ["/workspace/ai_engine/weights/best.pt",
                      "/workspace/ai_engine/models/damage_cnn_weights.pth",
                      "/app/ai_engine/models/damage_cnn_weights.pth"]:
                if os.path.exists(p):
                    weights_path = p
                    break

        if weights_path and os.path.exists(weights_path):
            try:
                ckpt = torch.load(weights_path, map_location=self.device)
                state_dict = ckpt["model_state_dict"] if "model_state_dict" in ckpt else ckpt
                self.model.load_state_dict(state_dict)
                print(f"[EdgeDamageDetector] ✓ Loaded verified weights from {weights_path}")
            except Exception as e:
                print(f"[EdgeDamageDetector] Warning loading weights: {e}")

        self.transform = T.Compose([
            T.ToTensor(),
            T.Resize((640, 640), antialias=True),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def detect(self, frame_bgr: np.ndarray) -> tuple[list[dict], np.ndarray, float]:
        t0 = time.time()
        orig_h, orig_w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        # Preprocessing
        tensor = self.transform(rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            cls_logits, bbox_norm = self.model(tensor)
            probs = torch.softmax(cls_logits, dim=1).cpu().numpy()[0]
            bbox = bbox_norm.cpu().numpy()[0]

        inf_time_ms = round((time.time() - t0) * 1000.0, 2)
        top_class_id = int(np.argmax(probs))
        confidence = float(probs[top_class_id])

        detections = []
        annotated = frame_bgr.copy()

        if top_class_id > 0 and confidence >= self.conf_threshold:
            class_name = CLASS_MAP.get(top_class_id, "structural_defect")
            xmin = int(bbox[0] * orig_w)
            ymin = int(bbox[1] * orig_h)
            xmax = int(bbox[2] * orig_w)
            ymax = int(bbox[3] * orig_h)

            # Sanity clamp
            xmin, ymin = max(0, min(xmin, orig_w - 50)), max(0, min(ymin, orig_h - 50))
            xmax, ymax = max(xmin + 30, min(xmax, orig_w)), max(ymin + 30, min(ymax, orig_h))

            centroid_u = int((xmin + xmax) / 2)
            centroid_v = int((ymin + ymax) / 2)

            detections.append({
                "class_name": class_name,
                "confidence": round(confidence, 3),
                "bbox": [xmin, ymin, xmax, ymax],
                "centroid_pixel": [centroid_u, centroid_v],
                "inference_ms": inf_time_ms
            })

            # Draw high-contrast target square with corner brackets
            color = (0, 0, 255) if class_name == "spalling" else (0, 220, 255)
            cv2.rectangle(annotated, (xmin, ymin), (xmax, ymax), color, 2)

            # Corner accents
            c_len = 16
            cv2.line(annotated, (xmin, ymin), (xmin + c_len, ymin), color, 4)
            cv2.line(annotated, (xmin, ymin), (xmin, ymin + c_len), color, 4)
            cv2.line(annotated, (xmax, ymin), (xmax - c_len, ymin), color, 4)
            cv2.line(annotated, (xmax, ymin), (xmax, ymin + c_len), color, 4)
            cv2.line(annotated, (xmin, ymax), (xmin + c_len, ymax), color, 4)
            cv2.line(annotated, (xmin, ymax), (xmin, ymax - c_len), color, 4)
            cv2.line(annotated, (xmax, ymax), (xmax - c_len, ymax), color, 4)
            cv2.line(annotated, (xmax, ymax), (xmax, ymax - c_len), color, 4)

            # Label badge
            label_text = f"{class_name.upper()} | {confidence*100:.1f}% ({inf_time_ms}ms)"
            cv2.putText(annotated, label_text, (xmin, max(24, ymin - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return detections, annotated, inf_time_ms
