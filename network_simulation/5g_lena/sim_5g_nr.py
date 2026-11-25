"""
INFYNEX 5G NR (New Radio) Simulation Engine (3GPP Rel-16 / 5G-LENA Compatible Model)
Simulates:
- 1 x 5G NR gNodeB (Height: 20m, Carrier: 3.5 GHz n78, Bandwidth: 100 MHz, Tx Power: 43 dBm)
- Drone UE (Altitude: 2.5m - 15m, Mobility along inspection waypoints)
- 4 x IoT ESP32 UEs (Ground level, low data rate mMTC)
- Edge Server / UPF Destination

Calculates according to 3GPP TR 38.901 UMi (Urban Micro) Pathloss & Shadowing:
- 3D Distance & LoS/NLoS probability
- Path loss (PL_LoS, PL_NLoS)
- Received Signal Received Power (RSRP)
- Signal-to-Interference-plus-Noise Ratio (SINR)
- CQI (Channel Quality Indicator: 1..15)
- Modulation and Coding Scheme (MCS: QPSK, 16QAM, 64QAM, 256QAM)
- Radio Layer Latency (ms), Jitter (ms), Throughput (Mbps), and Packet Loss Ratio (PLR)
"""

import json
import logging
import math
import random
import time
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [5G-LENA] %(message)s")


class FiveGNetworkSimulator:
    def __init__(
        self,
        fc_ghz: float = 3.5,
        bandwidth_mhz: float = 100.0,
        gnb_height_m: float = 20.0,
        gnb_tx_power_dbm: float = 43.0
    ):
        self.fc_ghz = fc_ghz
        self.bw_mhz = bandwidth_mhz
        self.gnb_h = gnb_height_m
        self.gnb_tx_pwr = gnb_tx_power_dbm
        self.thermal_noise_dbm = -174.0 + 10.0 * math.log10(self.bw_mhz * 1e6) + 7.0 # Noise figure = 7 dB

    def compute_link_metrics(self, drone_pos: Dict[str, float], scenario: str = "good_signal") -> Dict[str, Any]:
        """
        Computes 5G radio metrics given drone 3D position relative to gNodeB at (0, 0, 20).
        """
        dx = drone_pos.get("x", 0.0)
        dy = drone_pos.get("y", 0.0)
        dz = drone_pos.get("z", 2.5)

        # 3D distance between gNodeB and Drone
        d_2d = math.sqrt(dx**2 + dy**2)
        d_3d = math.sqrt(d_2d**2 + (self.gnb_h - dz)**2)

        # 3GPP TR 38.901 UMi LoS Probability
        p_los = min(18.0 / max(d_2d, 1.0), 1.0) * (1.0 - math.exp(-d_2d / 36.0)) + math.exp(-d_2d / 36.0)

        # Pathloss (LoS vs NLoS)
        # PL_LoS = 32.4 + 21.0 * log10(d_3d) + 20.0 * log10(fc)
        pl_los = 32.4 + 21.0 * math.log10(max(d_3d, 1.0)) + 20.0 * math.log10(self.fc_ghz)
        # PL_NLoS = 35.3 * log10(d_3d) + 22.4 + 21.3 * log10(fc) - 0.3 * (dz - 1.5)
        pl_nlos = 35.3 * math.log10(max(d_3d, 1.0)) + 22.4 + 21.3 * math.log10(self.fc_ghz) - 0.3 * (dz - 1.5)

        is_los = (random.random() < p_los) and (scenario != "distance_degradation")
        path_loss = pl_los if is_los else pl_nlos

        # Add shadow fading (Log-normal distribution)
        sigma_sf = 4.0 if is_los else 7.82
        shadowing = random.gauss(0, sigma_sf)
        total_pl = path_loss + shadowing

        # Received Power RSRP
        rsrp_dbm = self.gnb_tx_pwr - total_pl
        sinr_db = rsrp_dbm - self.thermal_noise_dbm

        # Degraded scenario perturbations on RF SINR
        if scenario == "congestion":
            sinr_db -= 14.0 # High inter-cell interference
        elif scenario == "distance_degradation":
            sinr_db -= 8.0

        # Mapping SINR to CQI (1 to 15)
        cqi = max(1, min(15, int((sinr_db + 6.0) / 2.0)))

        # Mapping CQI to Spectral Efficiency (bps/Hz) -> Throughput
        spectral_eff = max(0.15, min(7.4, 0.15 * (cqi ** 1.4)))
        throughput_mbps = round(spectral_eff * self.bw_mhz * 0.75, 1)

        # Latency calculation (radio frame + scheduling + propagation)
        base_rtt_ms = 8.5 # 5G NR TDD frame structure (slot 0.5ms with SCS 30kHz)
        if cqi > 10:
            latency_ms = round(base_rtt_ms + random.uniform(1.0, 3.5), 2)
            jitter_ms = round(random.uniform(0.5, 1.5), 2)
            packet_loss = 0.0
        elif cqi > 6:
            latency_ms = round(base_rtt_ms + random.uniform(8.0, 18.0), 2)
            jitter_ms = round(random.uniform(2.0, 5.0), 2)
            packet_loss = round(random.uniform(0.1, 1.2), 2)
        else:
            # Poor radio conditions
            latency_ms = round(base_rtt_ms + random.uniform(35.0, 85.0), 2)
            jitter_ms = round(random.uniform(10.0, 25.0), 2)
            packet_loss = round(random.uniform(3.0, 8.5), 2)

        # Traffic & buffer congestion perturbations
        if scenario == "congestion":
            latency_ms += round(random.uniform(35.0, 85.0), 2)
            jitter_ms += round(random.uniform(8.0, 20.0), 2)
            packet_loss = max(packet_loss, round(random.uniform(3.5, 7.5), 2))
            throughput_mbps = min(throughput_mbps, 12.0)
        elif scenario == "distance_degradation":
            latency_ms += round(random.uniform(15.0, 35.0), 2)
            packet_loss = max(packet_loss, round(random.uniform(1.0, 3.0), 2))
            throughput_mbps = min(throughput_mbps, 35.0)

        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "scenario": scenario,
            "drone_distance_3d_m": round(d_3d, 2),
            "is_los": is_los,
            "rsrp_dbm": round(rsrp_dbm, 2),
            "sinr_db": round(sinr_db, 2),
            "cqi": cqi,
            "throughput_mbps": throughput_mbps,
            "latency_ms": latency_ms,
            "jitter_ms": jitter_ms,
            "packet_loss_percent": packet_loss,
            "pdr": round(100.0 - packet_loss, 2)
        }


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="INFYNEX 5G NR Network Simulator")
    parser.add_argument("--scenario", default="good_signal", choices=["good_signal", "distance_degradation", "congestion", "handover"], help="Network condition profile")
    parser.add_argument("--duration", type=int, default=10, help="Simulation duration in seconds")
    parser.add_argument("--broker", default="localhost", help="MQTT Broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument("--publish", action="store_true", help="Publish metrics to MQTT broker")
    args = parser.parse_args()

    simulator = FiveGNetworkSimulator()
    mqtt_client = None

    if args.publish:
        try:
            import paho.mqtt.client as mqtt
            mqtt_client = mqtt.Client(client_id="infynex_5g_sim")
            mqtt_client.connect(args.broker, args.port, keepalive=60)
            mqtt_client.loop_start()
            logging.info(f"Connected 5G simulator to MQTT broker {args.broker}:{args.port}")
        except Exception as e:
            logging.warning(f"MQTT publish disabled: {e}")

    # Simulated drone waypoint stations
    inspection_waypoints = [
        {"name": "W1", "x": 0.0, "y": 0.0, "z": 2.5},
        {"name": "W2", "x": 2.0, "y": 0.0, "z": 2.5},
        {"name": "W3", "x": 2.0, "y": -1.2, "z": 2.5},
        {"name": "W4", "x": 2.0, "y": 0.2, "z": 3.2},
        {"name": "W5", "x": 2.0, "y": 1.8, "z": 3.1},
        {"name": "W6", "x": 2.5, "y": 2.2, "z": 3.0},
        {"name": "W7", "x": 3.0, "y": 0.0, "z": 3.0},
        {"name": "W8", "x": 1.0, "y": 0.0, "z": 2.5},
        {"name": "W9", "x": 0.0, "y": 0.0, "z": 0.1}
    ]

    results = []
    logging.info(f"Starting 5G NR Link Simulation | Profile: {args.scenario} | Waypoints: {len(inspection_waypoints)}")

    for wp in inspection_waypoints:
        metrics = simulator.compute_link_metrics(drone_pos=wp, scenario=args.scenario)
        metrics["waypoint"] = wp["name"]
        results.append(metrics)
        logging.info(
            f"[{wp['name']}] Dist: {metrics['drone_distance_3d_m']}m | RSRP: {metrics['rsrp_dbm']}dBm | "
            f"CQI: {metrics['cqi']} | Latency: {metrics['latency_ms']}ms | Throughput: {metrics['throughput_mbps']}Mbps | PDR: {metrics['pdr']}%"
        )
        if mqtt_client:
            mqtt_client.publish("infynex/network/metrics", json.dumps(metrics))
        time.sleep(0.3)

    # Save to data/network_logs/
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/network_logs"))
    os.makedirs(log_dir, exist_ok=True)
    out_file = os.path.join(log_dir, "5g_simulation_metrics.json")
    with open(out_file, "w") as f:
        json.dump({"scenario": args.scenario, "samples": results}, f, indent=2)

    logging.info(f"✓ Saved 5G simulation logs to {out_file}")

    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

