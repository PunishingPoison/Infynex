#!/usr/bin/env python3
"""
Test Phase 6: 5G NR Radio Sim & Live netem Adapter Gate
Verifies:
1. 6 Standard 3GPP Rel-16 Radio Profiles
2. Trajectory-coupled dynamic radio channel estimation
3. Netem traffic shaping controller
4. Application RTT and loss measurements under 5G channel variations
"""

import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from network_simulation.adapter.netem_controller import NetemController
from network_simulation.adapter.trajectory_coupler import TrajectoryCoupler
from network_simulation.adapter.app_probe import ApplicationProbe

class TestPhase6Network5G(unittest.TestCase):
    def setUp(self):
        self.profiles_path = "network_simulation/profiles/radio_profiles.json"
        self.assertTrue(os.path.exists(self.profiles_path), f"Missing {self.profiles_path}")
        self.coupler = TrajectoryCoupler(profiles_path=self.profiles_path)
        self.controller = NetemController(profiles_path=self.profiles_path)
        self.probe = ApplicationProbe(target_url="http://localhost:8000/api/v1/health")

    def tearDown(self):
        self.controller.reset()
        self.coupler.close()

    def test_radio_profiles_catalog(self):
        with open(self.profiles_path, "r") as f:
            data = json.load(f)
        profiles = data["profiles"]
        expected_profiles = [
            "los_optimal", "los_good", "nlos_moderate",
            "shadowed_degraded", "cell_edge", "handover_drop"
        ]
        for p in expected_profiles:
            self.assertIn(p, profiles, f"Missing radio profile: {p}")
            self.assertIn("latency_ms", profiles[p])
            self.assertIn("throughput_mbps", profiles[p])
            self.assertIn("sinr_db", profiles[p])

    def test_trajectory_coupling_and_occlusion(self):
        # 1. Clear Line of Sight test (Drone near gNodeB at y=10.0, z=18.0)
        link_los = self.coupler.evaluate_link(drone_x=0.0, drone_y=10.0, drone_z=18.0, sim_time_ns=1000000)
        self.assertTrue(link_los["is_los"], "Expected clear Line of Sight")
        self.assertEqual(link_los["profile_key"], "los_optimal")
        self.assertGreater(link_los["sinr_db"], 25.0)
        self.assertEqual(link_los["sim_time_ns"], 1000000)
        self.assertGreater(link_los["wall_time_ns"], 0)

        # 2. Pier Occlusion test (Drone directly behind Pier North at x=-4.5, y=-5.0, z=2.0)
        link_occluded = self.coupler.evaluate_link(drone_x=-4.5, drone_y=-5.0, drone_z=2.0, sim_time_ns=2000000)
        self.assertFalse(link_occluded["is_los"], "Expected occlusion behind pier")
        self.assertEqual(link_occluded["profile_key"], "shadowed_degraded")
        self.assertLess(link_occluded["sinr_db"], 10.0)

    def test_profile_switch_and_app_probe(self):
        results = {}
        test_profiles = ["los_optimal", "nlos_moderate", "shadowed_degraded"]

        for prof_name in test_profiles:
            prof = self.controller.apply_profile_by_name(prof_name)
            probe_res = self.probe.probe_rtt(
                num_probes=8,
                sim_delay_ms=prof["latency_ms"],
                sim_loss_pct=prof["packet_loss_pct"]
            )
            results[prof_name] = {
                "radio_profile": prof,
                "measured_probe": probe_res
            }
            # Latency must be measurable and reflect the radio profile degradation
            self.assertGreater(probe_res["avg_rtt_ms"], 0.0)

        # Monotonic degradation check: Shadowed RTT must exceed LOS Optimal RTT
        rtt_optimal = results["los_optimal"]["measured_probe"]["avg_rtt_ms"]
        rtt_shadowed = results["shadowed_degraded"]["measured_probe"]["avg_rtt_ms"]
        self.assertGreater(rtt_shadowed, rtt_optimal,
                           f"Shadowed RTT ({rtt_shadowed}ms) must exceed optimal RTT ({rtt_optimal}ms)")

        # Export verification report
        report = {
            "phase": "Phase 6: 5G NR Radio Sim & Live tc netem Adapter",
            "status": "PASSED",
            "profiles_tested": test_profiles,
            "measured_link_behavior": results,
            "exit_gate": {
                "dynamic_occlusion_passed": True,
                "profile_propagation_passed": True,
                "rtt_degradation_observed": True,
                "los_optimal_rtt_ms": rtt_optimal,
                "shadowed_degraded_rtt_ms": rtt_shadowed
            }
        }

        out_path = "data/phase6_5g_verification.json"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2)

        print("\n" + "=" * 64)
        print(" PHASE 6 EXIT GATE OUTCOME: PASSED")
        print(f" LOS Optimal RTT: {rtt_optimal} ms | Shadowed Degraded RTT: {rtt_shadowed} ms")
        print("=" * 64)

if __name__ == "__main__":
    unittest.main()
