"""
Unit Tests for INFYNEX 5G NR Network Simulation Model
"""

import unittest
import importlib.util
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_sim_path = os.path.abspath(os.path.join(_script_dir, "../../network_simulation/5g_lena/sim_5g_nr.py"))
spec = importlib.util.spec_from_file_location("sim_5g_nr", _sim_path)
sim_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim_module)
FiveGNetworkSimulator = sim_module.FiveGNetworkSimulator


class Test5GNetwork(unittest.TestCase):
    def setUp(self):
        self.sim = FiveGNetworkSimulator(fc_ghz=3.5, bandwidth_mhz=100.0, gnb_height_m=20.0)

    def test_baseline_good_signal(self):
        metrics = self.sim.compute_link_metrics(drone_pos={"x": 5.0, "y": 0.0, "z": 2.5}, scenario="good_signal")
        self.assertIn("latency_ms", metrics)
        self.assertIn("throughput_mbps", metrics)
        self.assertIn("sinr_db", metrics)
        self.assertLess(metrics["latency_ms"], 20.0)
        self.assertGreater(metrics["throughput_mbps"], 80.0)
        self.assertAlmostEqual(metrics["packet_loss_percent"], 0.0, delta=0.5)

    def test_degraded_network_congestion(self):
        metrics = self.sim.compute_link_metrics(drone_pos={"x": 5.0, "y": 0.0, "z": 2.5}, scenario="congestion")
        self.assertGreater(metrics["latency_ms"], 15.0)
        self.assertLessEqual(metrics["pdr"], 100.0)


if __name__ == "__main__":
    unittest.main()
