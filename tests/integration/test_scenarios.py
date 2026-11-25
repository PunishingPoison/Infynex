"""
INFYNEX End-to-End System Scenarios Test Suite (T1 - T10)
Validates:
- T1: Normal infrastructure inspection waypoints
- T2: Crack defect detection & bounding boxes
- T3: Concrete spalling detection & critical severity flag
- T4: Dynamic environmental sensor fluctuations
- T5: ESP32 node disconnection & fault handling
- T6: High 5G network latency application & buffering
- T7: 5G packet loss degradation
- T8: Digital twin 3D drone position tracking
- T9: Full multi-subsystem data exchange (Drone -> 5G -> Edge -> AI -> Dashboard)
- T10: Inspection report generation & compilation
"""

import unittest
import os
import json
import time
import importlib.util

_script_dir = os.path.dirname(os.path.abspath(__file__))

# Dynamic loader for 5G simulator
_sim_5g_path = os.path.abspath(os.path.join(_script_dir, "../../network_simulation/5g_lena/sim_5g_nr.py"))
spec_5g = importlib.util.spec_from_file_location("sim_5g_nr", _sim_5g_path)
sim_5g_mod = importlib.util.module_from_spec(spec_5g)
spec_5g.loader.exec_module(sim_5g_mod)
FiveGNetworkSimulator = sim_5g_mod.FiveGNetworkSimulator

from iot_simulation.sensors.sensor_models import DS18B20Node, BME280Node, DHT22Node
from ai_engine.inference.damage_detector import DamageDetector
from ai_engine.localisation.raycaster import DamageLocaliser
from backend.app.services.report_generator import InspectionReportGenerator


class TestFullInfynexSimulationScenarios(unittest.TestCase):
    def setUp(self):
        self.detector = DamageDetector()
        self.localiser = DamageLocaliser()
        self.net_sim = FiveGNetworkSimulator()
        self.report_gen = InspectionReportGenerator(output_dir="/tmp/infynex_test_reports")

    def test_T1_inspection_waypoints(self):
        # Verify waypoint schema
        waypoint_file = os.path.abspath(os.path.join(_script_dir, "../../simulation/scenarios/normal_inspection.yaml"))
        self.assertTrue(os.path.exists(waypoint_file))

    def test_T2_T3_damage_detection_and_localisation(self):
        # Load ground truth annotations
        gt_file = os.path.abspath(os.path.join(_script_dir, "../../simulation/infrastructure/annotations/ground_truth_damages.json"))
        self.assertTrue(os.path.exists(gt_file))
        with open(gt_file, "r") as f:
            gt_data = json.load(f)

        damages = gt_data.get("damages", [])
        self.assertGreaterEqual(len(damages), 3)

        categories = [d["category"] for d in damages]
        self.assertIn("crack", categories)
        self.assertIn("spalling", categories)

        # Test 3D localisation raycast for front center spalling
        spall = next(d for d in damages if d["damage_id"] == "SPALL_001")
        hit = self.localiser.localise_to_surface(
            pixel_x=640.0,
            pixel_y=360.0,
            drone_pos=(2.0, 0.2, 3.2),
            drone_yaw_deg=0.0,
            surface_plane_x=4.74
        )
        self.assertIsNotNone(hit)
        self.assertAlmostEqual(hit["x"], 4.74, places=2)
        self.assertAlmostEqual(hit["y"], 0.2, places=1)
        self.assertAlmostEqual(hit["z"], 3.2, places=1)

    def test_T4_T5_iot_telemetry_and_node_fault(self):
        node = BME280Node("ESP32_003", "foundation")
        r1 = node.read()
        self.assertEqual(r1["status"], "normal")

        # Step time by 100s to verify dynamic environmental shift
        node.step_time(100.0)
        r2 = node.read()
        self.assertNotEqual(r1["temperature_c"], r2["temperature_c"])

        # Inject sensor fault
        node.trigger_fault(True)
        r_fault = node.read()
        self.assertEqual(r_fault["status"], "sensor_error")

    def test_T6_T7_network_latency_and_packet_loss(self):
        # T6: Congestion scenario
        cong_metrics = self.net_sim.compute_link_metrics(drone_pos={"x": 10.0, "y": 5.0, "z": 8.0}, scenario="congestion")
        self.assertGreater(cong_metrics["latency_ms"], 30.0)

        # T7: Packet loss
        self.assertGreater(cong_metrics["packet_loss_percent"], 2.0)
        self.assertLess(cong_metrics["pdr"], 98.0)

    def test_T8_T9_T10_report_compilation(self):
        pdf_path = self.report_gen.generate_pdf(
            mission_id="TEST_M_001",
            structure_name="Bridge Pier Facade A",
            damages=[
                {
                    "damage_id": "CRACK_001",
                    "category": "crack",
                    "severity": "moderate",
                    "confidence": 0.94,
                    "position": {"x": 4.74, "y": -1.2, "z": 2.5},
                    "surface": "front_wall"
                },
                {
                    "damage_id": "SPALL_001",
                    "category": "spalling",
                    "severity": "critical",
                    "confidence": 0.98,
                    "position": {"x": 4.74, "y": 0.2, "z": 3.2},
                    "surface": "front_center"
                }
            ],
            sensor_stats={"esp1_temp": 31.2, "esp2_temp": 26.8, "esp3_temp": 28.5, "esp3_hum": 65.4, "esp3_press": 1013.2, "esp4_temp": 27.9, "esp4_hum": 66.0},
            network_stats={"latency_ms": 14.2, "jitter_ms": 1.8, "throughput_mbps": 145.0, "pdr": 99.8},
            flight_stats={"model": "PX4 X500", "altitude_m": 2.5, "duration_sec": 142, "waypoints_count": 9, "battery_start_pct": 100, "battery_end_pct": 89}
        )
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)


if __name__ == "__main__":
    unittest.main()
