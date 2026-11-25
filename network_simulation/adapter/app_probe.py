#!/usr/bin/env python3
"""
INFYNEX 5G Active Application Probe
Actively probes HTTP / WebSocket endpoints under current 5G network profile to measure RTT, jitter, and delivery.
"""

import json
import logging
import os
import random
import sys
import time
import urllib.request
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AppProbe] %(message)s")

class ApplicationProbe:
    def __init__(self, target_url: str = "http://localhost:8000/api/v1/health", controller=None):
        self.target_url = target_url
        self.controller = controller

    def probe_rtt(self, num_probes: int = 10, sim_delay_ms: float = 0.0, sim_loss_pct: float = 0.0) -> Dict[str, Any]:
        """Performs HTTP probes to measure actual round-trip latency and packet loss."""
        latencies_ms = []
        failures = 0

        for i in range(num_probes):
            # Check simulated loss
            if sim_loss_pct > 0 and (random.random() * 100.0) < sim_loss_pct:
                failures += 1
                time.sleep(0.01)
                continue

            t0 = time.time()
            # Add radio delay if using software emulation
            if sim_delay_ms > 0:
                time.sleep(sim_delay_ms / 1000.0)

            try:
                req = urllib.request.Request(self.target_url, headers={"User-Agent": "INFYNEX-5G-Probe"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        rtt_ms = round((time.time() - t0) * 1000.0, 2)
                        latencies_ms.append(rtt_ms)
                    else:
                        failures += 1
            except Exception as e:
                failures += 1
            time.sleep(0.02)

        valid_count = len(latencies_ms)
        avg_rtt = round(sum(latencies_ms) / valid_count, 2) if valid_count > 0 else 999.0
        min_rtt = min(latencies_ms) if valid_count > 0 else 999.0
        max_rtt = max(latencies_ms) if valid_count > 0 else 999.0
        jitter = round(max_rtt - min_rtt, 2) if valid_count > 1 else 0.0
        actual_loss_pct = round((failures / num_probes) * 100.0, 1)

        result = {
            "probes_sent": num_probes,
            "probes_received": valid_count,
            "avg_rtt_ms": avg_rtt,
            "min_rtt_ms": min_rtt,
            "max_rtt_ms": max_rtt,
            "jitter_ms": jitter,
            "packet_loss_pct": actual_loss_pct,
            "target_url": self.target_url
        }
        return result
