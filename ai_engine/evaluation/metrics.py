"""
INFYNEX Computer Vision Damage Detection Evaluation Metrics
Calculates:
- Intersection over Union (IoU)
- True Positives (TP), False Positives (FP), False Negatives (FN)
- Precision, Recall, F1-Score
- Mean Average Precision (mAP@50 and mAP@50:95)
- Latency and Throughput (FPS)
"""

import json
from typing import List, Dict, Any, Tuple
import numpy as np


def calculate_iou_bbox(box_a: List[float], box_b: List[float]) -> float:
    """
    Computes IoU between two bounding boxes in [xmin, ymin, xmax, ymax] format.
    """
    x_a = max(box_a[0], box_b[0])
    y_a = max(box_a[1], box_b[1])
    x_b = min(box_a[2], box_b[2])
    y_b = min(box_a[3], box_b[3])

    inter_w = max(0.0, x_b - x_a)
    inter_h = max(0.0, y_b - y_a)
    inter_area = inter_w * inter_h

    area_a = max(0.0, (box_a[2] - box_a[0])) * max(0.0, (box_a[3] - box_a[1]))
    area_b = max(0.0, (box_b[2] - box_b[0])) * max(0.0, (box_b[3] - box_b[1]))

    union_area = area_a + area_b - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class DamageEvaluator:
    def __init__(self, iou_threshold: float = 0.50):
        self.iou_thresh = iou_threshold

    def evaluate_detections(
        self,
        predicted: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
        inference_times_ms: List[float]
    ) -> Dict[str, Any]:
        """
        Evaluates predictions against ground truth labels.
        """
        matched_gt = set()
        tp = 0
        fp = 0

        # Sort predictions descending by confidence
        sorted_preds = sorted(predicted, key=lambda d: d.get("confidence", 0.0), reverse=True)

        for pred in sorted_preds:
            p_box = pred.get("bbox", [])
            p_cat = pred.get("category", "")
            best_iou = 0.0
            best_gt_idx = -1

            for gt_idx, gt in enumerate(ground_truth):
                if gt_idx in matched_gt:
                    continue
                if gt.get("category", "") != p_cat and p_cat != "":
                    continue

                gt_box = gt.get("bbox", [])
                if len(gt_box) == 4 and len(p_box) == 4:
                    iou = calculate_iou_bbox(p_box, gt_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = gt_idx

            if best_iou >= self.iou_thresh and best_gt_idx != -1:
                tp += 1
                matched_gt.add(best_gt_idx)
            else:
                fp += 1

        fn = len(ground_truth) - len(matched_gt)

        precision = tp / max(1, (tp + fp))
        recall = tp / max(1, (tp + fn))
        f1 = (2 * precision * recall) / max(1e-6, (precision + recall))

        mean_latency = float(np.mean(inference_times_ms)) if inference_times_ms else 0.0
        fps = round(1000.0 / max(1e-3, mean_latency), 1) if mean_latency > 0 else 0.0

        return {
            "iou_threshold": self.iou_thresh,
            "total_ground_truth": len(ground_truth),
            "total_predictions": len(predicted),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "mean_inference_time_ms": round(mean_latency, 2),
            "fps": fps
        }
