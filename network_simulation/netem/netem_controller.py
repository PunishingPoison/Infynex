"""
INFYNEX Linux tc netem Network Emulation Controller
Dynamically configures kernel-level traffic shaping for latency, packet loss, bandwidth, and jitter.
"""

import subprocess
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [NetEm] %(message)s")


class NetemController:
    def __init__(self, interface: str = "lo"):
        self.interface = interface
        self.active_scenario = "direct"

    def apply_profile(
        self,
        latency_ms: float = 0.0,
        jitter_ms: float = 0.0,
        packet_loss_percent: float = 0.0,
        rate_mbps: Optional[float] = None
    ) -> bool:
        """
        Applies delay, jitter, loss and rate limits to network interface using Linux tc.
        """
        self.reset()
        if latency_ms <= 0 and packet_loss_percent <= 0 and (rate_mbps is None or rate_mbps <= 0):
            logging.info(f"NetEm cleared on {self.interface} (unimpaired path).")
            return True

        cmd = ["tc", "qdisc", "add", "dev", self.interface, "root", "netem"]
        if latency_ms > 0:
            cmd.extend(["delay", f"{latency_ms}ms"])
            if jitter_ms > 0:
                cmd.extend([f"{jitter_ms}ms", "distribution", "normal"])

        if packet_loss_percent > 0:
            cmd.extend(["loss", f"{packet_loss_percent}%"])

        if rate_mbps and rate_mbps > 0:
            cmd.extend(["rate", f"{rate_mbps}mbit"])

        logging.info(f"Executing: {' '.join(cmd)}")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                logging.info(f"✓ Applied NetEm: Latency={latency_ms}ms (±{jitter_ms}ms), Loss={packet_loss_percent}%, Rate={rate_mbps}Mbps")
                return True
            else:
                logging.warning(f"tc command returned {res.returncode}: {res.stderr.strip()}")
                return False
        except Exception as e:
            logging.error(f"Failed to execute tc netem: {e}")
            return False

    def reset(self):
        """Clears all qdisc traffic shaping on interface."""
        subprocess.run(["tc", "qdisc", "del", "dev", self.interface, "root"], capture_output=True)
