#!/usr/bin/env python3
"""
Test Phase 5: IoT ESP32 Sensor Fleet & MQTT Fault Sim Gate
"""

import json
import os
import subprocess
import sys
import unittest

class TestPhase5IoTFleet(unittest.TestCase):
    def test_iot_fleet_and_fault_lwt(self):
        scenario_path = "simulation/scenarios/fault_sensor_drop.yaml"
        self.assertTrue(os.path.exists(scenario_path), f"Missing {scenario_path}")

        # Run IoT Fleet simulation runner
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{os.getcwd()}:/workspace",
            "-w", "/workspace",
            "--network", "host",
            "infynex-backend:latest",
            "python3", "/workspace/iot_simulation/runner.py", scenario_path
        ]
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        self.assertEqual(result.returncode, 0, "IoT Fleet runner failed")

        # Verify output json
        json_path = "data/phase5_iot_verification.json"
        self.assertTrue(os.path.exists(json_path), f"Missing {json_path}")
        with open(json_path, "r") as f:
            report = json.load(f)

        self.assertEqual(report["status"], "PASSED")
        self.assertGreater(report["total_telemetry_packets"], 40)
        self.assertTrue(report["fault_verification"]["thermal_drift_injected"])
        self.assertTrue(report["fault_verification"]["humidity_spike_injected"])
        self.assertTrue(report["fault_verification"]["lwt_alert_passed"])
        self.assertLessEqual(report["fault_verification"]["lwt_detection_latency_ms"], 5000.0)

if __name__ == "__main__":
    unittest.main()
