"""
Unit Tests for INFYNEX AI Damage Detection Engine and 3D Localisation
"""

import unittest
import numpy as np
from ai_engine.preprocessing.image_preprocessor import ImagePreprocessor
from ai_engine.inference.damage_detector import DamageDetector
from ai_engine.localisation.raycaster import DamageLocaliser
from ai_engine.evaluation.metrics import DamageEvaluator, calculate_iou_bbox


class TestAiDamageEngine(unittest.TestCase):
    def setUp(self):
        self.preprocessor = ImagePreprocessor(target_size=(640, 640))
        self.detector = DamageDetector(confidence_threshold=0.60)
        self.localiser = DamageLocaliser(camera_hfov_deg=80.0, image_width=1280, image_height=720)
        self.evaluator = DamageEvaluator(iou_threshold=0.50)

    def test_image_preprocessing(self):
        # Create dummy 1280x720 BGR image
        dummy_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        tensor, meta = self.preprocessor.process(dummy_img)

        self.assertEqual(tensor.shape, (3, 640, 640))
        self.assertEqual(meta["orig_shape"], (720, 1280))
        self.assertAlmostEqual(tensor.max(), 0.0, delta=1.0)

    def test_synthetic_crack_detection(self):
        # Create concrete-like canvas with a vertical crack
        canvas = np.full((720, 1280, 3), 128, dtype=np.uint8)
        # Draw high-contrast vertical crack line
        canvas[200:450, 638:642] = [20, 20, 20]

        detections = self.detector.detect(canvas, frame_id="test_001")
        self.assertGreaterEqual(len(detections), 1)
        det = detections[0]
        self.assertIn("crack", det["category"])
        self.assertGreaterEqual(det["confidence"], 0.60)

    def test_raycast_surface_localisation(self):
        # Camera pointed straight forward at facade at X = 4.74m
        # Drone at (2.0, 0.0, 2.5), optical center at pixel (640, 360)
        hit = self.localiser.localise_to_surface(
            pixel_x=640.0,
            pixel_y=360.0,
            drone_pos=(2.0, 0.0, 2.5),
            drone_yaw_deg=0.0,
            surface_plane_x=4.74
        )
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit["x"], 4.74, places=2)
        self.assertAlmostEqual(hit["y"], 0.0, places=1)
        self.assertAlmostEqual(hit["z"], 2.5, places=1)
        self.assertAlmostEqual(hit["ray_distance_m"], 2.74, places=1)

    def test_metrics_evaluation(self):
        gt = [{"category": "crack", "bbox": [100, 100, 150, 300]}]
        pred = [{"category": "crack", "bbox": [105, 98, 152, 305], "confidence": 0.92}]

        res = self.evaluator.evaluate_detections(pred, gt, inference_times_ms=[24.5])
        self.assertEqual(res["true_positives"], 1)
        self.assertEqual(res["false_positives"], 0)
        self.assertEqual(res["false_negatives"], 0)
        self.assertAlmostEqual(res["precision"], 1.0)
        self.assertAlmostEqual(res["recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
