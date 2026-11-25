#!/usr/bin/env python3
"""
INFYNEX Linux tc netem & Adaptive Traffic Shaper Controller
Translates 5G NR Radio Profiles into active Linux kernel netem qdisc rules or socket emulation.
"""

import json
import logging
import os
import subprocess
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NetEmController] %(message)s")

class NetemController:
    def __init__(self, interface: str = "lo", profiles_path: str = None):
        self.interface = interface
        if profiles_path is None:
            profiles_path = os.path.join(os.path.dirname(__file__), "../profiles/radio_profiles.json")

        with open(profiles_path, "r") as f:
            self.config = json.load(f)
        self.profiles = self.config["profiles"]
        self.current_profile_name = "direct"
        self.active_metrics = {
            "latency_ms": 0.0,
            "jitter_ms": 0.0,
            "packet_loss_pct": 0.0,
            "rate_mbps": 1000.0
        }

    def reset(self):
        """Removes root qdisc from interface."""
        try:
            subprocess.run(["tc", "qdisc", "del", "dev", self.interface, "root"],
                           capture_output=True, text=True)
        except Exception:
            pass
        self.current_profile_name = "direct"
        self.active_metrics = {
            "latency_ms": 0.0,
            "jitter_ms": 0.0,
            "packet_loss_pct": 0.0,
            "rate_mbps": 1000.0
        }

    def apply_profile(
        self,
        latency_ms: float = 0.0,
        jitter_ms: float = 0.0,
        packet_loss_pct: float = 0.0,
        rate_mbps: Optional[float] = None
    ) -> bool:
        """Applies traffic shaping via tc netem command."""
        self.reset()
        self.active_metrics = {
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "packet_loss_pct": packet_loss_pct,
            "rate_mbps": rate_mbps or 1000.0
        }

        if latency_ms <= 0 and packet_loss_pct <= 0 and (rate_mbps is None or rate_mbps <= 0):
            logging.info(f"Traffic shaping cleared on {self.interface} (unimpaired path).")
            return True

        # Find tc binary
        tc_bin = "/usr/sbin/tc" if os.path.exists("/usr/sbin/tc") else "tc"
        cmd = [tc_bin, "qdisc", "add", "dev", self.interface, "root", "netem"]
        if latency_ms > 0:
            cmd.extend(["delay", f"{latency_ms}ms"])
            if jitter_ms > 0:
                cmd.extend([f"{jitter_ms}ms", "distribution", "normal"])

        if packet_loss_pct > 0:
            cmd.extend(["loss", f"{packet_loss_pct}%"])

        if rate_mbps and rate_mbps > 0:
            cmd.extend(["rate", f"{rate_mbps}mbit"])

        logging.info(f"Applying Kernel NetEm: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                logging.info(f"✓ Kernel NetEm Active on {self.interface}: {latency_ms}ms, {packet_loss_pct}% loss")
                return True
            else:
                logging.warning(f"tc returned {res.returncode}: {res.stderr.strip()} (Operating in software emulation mode)")
                return False
        except Exception as e:
            logging.warning(f"tc execution skipped: {e} (Operating in software emulation mode)")
            return False

    def apply_profile_by_name(self, profile_name: str) -> Dict[str, Any]:
        """Applies a named 5G profile from the catalog."""
        if profile_name not in self.profiles:
            raise ValueError(f"Unknown profile: {profile_name}. Available: {list(self.profiles.keys())}")

        prof = self.profiles[profile_name]
        self.current_profile_name = profile_name
        self.apply_profile(
            latency_ms=prof["latency_ms"],
            jitter_ms=prof["jitter_ms"],
            packet_loss_pct=prof["packet_loss_pct"],
            rate_mbps=prof["throughput_mbps"]
        )
        return prof
