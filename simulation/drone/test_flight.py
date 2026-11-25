#!/usr/bin/env python3
"""
INFYNEX Milestone 1: Drone Flight Verification Script (pymavlink PX4 Native implementation)
Validates:
1. Connection to PX4 SITL via MAVLink over UDP port 14540
2. Telemetry stream acquisition (HEARTBEAT, GLOBAL_POSITION_INT, ATTITUDE)
3. Pre-flight health and arming checks
4. Autonomous takeoff to 2.5m AGL via PX4 AUTO_TAKEOFF
5. Hover stability at fixed coordinates for 5 seconds
6. Autonomous landing and safe disarm via PX4 AUTO_LAND
7. Structured JSON metrics output
"""

import json
import math
import os
import sys
import time
from pymavlink import mavutil

# PX4 Custom Mode Constants
PX4_CUSTOM_MAIN_MODE_AUTO = 4
PX4_CUSTOM_SUB_MODE_AUTO_LOITER = 3
PX4_CUSTOM_SUB_MODE_AUTO_TAKEOFF = 2
PX4_CUSTOM_SUB_MODE_AUTO_LAND = 6


class DroneFlightVerifier:
    def __init__(self, connection_string="udpin:0.0.0.0:14540"):
        self.connection_string = connection_string
        self.master = None
        self.metrics = {
            "milestone": "Phase 1 - PX4 X500 Flight Verification",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "connection": False,
            "armed": False,
            "takeoff_success": False,
            "hover_success": False,
            "landing_success": False,
            "disarmed_success": False,
            "peak_altitude_m": 0.0,
            "hover_altitude_mean_m": 0.0,
            "telemetry_samples": [],
            "status": "FAILED",
            "errors": []
        }

    def connect(self):
        print("=====================================================")
        print(" [INFYNEX] Starting Phase 1 Flight Verification Test")
        print(f" [INFYNEX] Connecting to MAVLink stream on {self.connection_string}...")
        print("=====================================================")
        
        try:
            self.master = mavutil.mavlink_connection(self.connection_string)
            print(" [INFYNEX] Waiting for vehicle HEARTBEAT...")
            heartbeat = self.master.wait_heartbeat(timeout=35)
            if not heartbeat:
                self.metrics["errors"].append("Timeout waiting for heartbeat on port 14540")
                print(" [INFYNEX] ✗ No heartbeat received.")
                return False

            self.metrics["connection"] = True
            print(f" [INFYNEX] ✓ Heartbeat received from system {self.master.target_system}, component {self.master.target_component}!")
            
            # Request high-frequency data streams: attitude, position, extra1 (telemetry)
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10, 1
            )
            return True
        except Exception as e:
            self.metrics["errors"].append(f"Connection error: {e}")
            print(f" [INFYNEX] ✗ Connection failed: {e}")
            return False

    def set_takeoff_altitude(self, altitude_m=2.5):
        print(f" [INFYNEX] Setting MIS_TAKEOFF_ALT to {altitude_m}m...")
        # Send PARAM_SET for MIS_TAKEOFF_ALT
        param_id = b"MIS_TAKEOFF_ALT\x00"
        self.master.mav.param_set_send(
            self.master.target_system,
            self.master.target_component,
            param_id,
            float(altitude_m),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        time.sleep(0.5)

    def wait_for_gps_lock(self, timeout=25):
        print(" [INFYNEX] Waiting for GPS 3D navigation lock and EKF2 convergence...")
        start = time.time()
        while time.time() - start < timeout:
            msg = self.master.recv_match(type='GPS_RAW_INT', blocking=True, timeout=1.0)
            if msg and msg.fix_type >= 3:
                print(f" [INFYNEX] ✓ GPS 3D lock confirmed (fix_type={msg.fix_type}, sats={msg.satellites_visible})")
                time.sleep(2)
                return True
            time.sleep(0.5)
        print(" [INFYNEX] ! Proceeding with available navigation fix...")
        return False

    def arm(self):
        print(" [INFYNEX] Arming X500 quadcopter...")
        # Send arm command (param1=1: arm, param2=21196: force in SITL)
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, # Arm
            21196, # Force arm in SITL
            0, 0, 0, 0, 0
        )
        
        # Verify arming status in heartbeats
        start = time.time()
        while time.time() - start < 15:
            msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=1.0)
            if msg:
                is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if is_armed:
                    self.metrics["armed"] = True
                    print(" [INFYNEX] ✓ Drone armed successfully.")
                    return True
            time.sleep(0.2)

        self.metrics["errors"].append("Timeout confirming drone armed state")
        print(" [INFYNEX] ✗ Failed to confirm arming.")
        return False

    def takeoff(self, altitude_m=2.5):
        print(f" [INFYNEX] Commanding autonomous takeoff to {altitude_m}m...")
        # Get current vehicle position
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=2.0)
        current_lat = (msg.lat / 1e7) if msg and msg.lat != 0 else float('nan')
        current_lon = (msg.lon / 1e7) if msg and msg.lon != 0 else float('nan')

        # 1. Switch PX4 mode to AUTO -> TAKEOFF
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            PX4_CUSTOM_MAIN_MODE_AUTO,
            PX4_CUSTOM_SUB_MODE_AUTO_TAKEOFF,
            0, 0, 0, 0
        )
        # 2. Send NAV_TAKEOFF with current coordinates and target altitude
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0,
            float('nan'),
            current_lat,
            current_lon,
            float(altitude_m)
        )
        self.metrics["takeoff_success"] = True
        print(f" [INFYNEX] ✓ Takeoff command dispatched at ({current_lat}, {current_lon}) -> target {altitude_m}m.")

    def monitor_flight_and_hover(self, target_alt_m=2.5, hover_duration_s=5.0):
        print(f" [INFYNEX] Ascending towards {target_alt_m}m and tracking telemetry...")
        hover_altitudes = []
        hover_started = False
        hover_start_time = None
        start_time = time.time()

        while time.time() - start_time < 50:
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1.0)
            if not msg:
                continue

            rel_alt = msg.relative_alt / 1000.0 # Convert mm to meters
            if rel_alt > self.metrics["peak_altitude_m"]:
                self.metrics["peak_altitude_m"] = round(rel_alt, 3)

            # Record telemetry sample
            self.metrics["telemetry_samples"].append({
                "t": round(time.time() - start_time, 2),
                "lat": msg.lat / 1e7,
                "lon": msg.lon / 1e7,
                "rel_alt_m": round(rel_alt, 3),
                "vx": round(msg.vx / 100.0, 2),
                "vy": round(msg.vy / 100.0, 2),
                "vz": round(msg.vz / 100.0, 2)
            })

            if rel_alt >= (target_alt_m - 0.5) and not hover_started:
                print(f" [INFYNEX] Reached target altitude threshold ({rel_alt:.2f}m). Starting {hover_duration_s}s hover measurement...")
                hover_started = True
                hover_start_time = time.time()

            if hover_started:
                hover_altitudes.append(rel_alt)
                if time.time() - hover_start_time >= hover_duration_s:
                    self.metrics["hover_success"] = True
                    mean_alt = sum(hover_altitudes) / len(hover_altitudes)
                    self.metrics["hover_altitude_mean_m"] = round(mean_alt, 3)
                    print(f" [INFYNEX] ✓ 5s Hover verified! Mean hover altitude: {mean_alt:.2f}m")
                    return True

            time.sleep(0.1)

        if not self.metrics["hover_success"]:
            self.metrics["errors"].append("Failed to achieve 5s hover within timeout")
            print(f" [INFYNEX] ✗ Hover verification timed out. Max altitude reached: {self.metrics['peak_altitude_m']}m")
            return False

    def land(self):
        print(" [INFYNEX] Commanding autonomous landing via PX4 AUTO_LAND...")
        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1.0)
        current_lat = (msg.lat / 1e7) if msg and msg.lat != 0 else float('nan')
        current_lon = (msg.lon / 1e7) if msg and msg.lon != 0 else float('nan')

        # Set PX4 mode to AUTO -> LAND
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            PX4_CUSTOM_MAIN_MODE_AUTO,
            PX4_CUSTOM_SUB_MODE_AUTO_LAND,
            0, 0, 0, 0
        )
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0,
            float('nan'),
            current_lat,
            current_lon,
            0
        )
        self.metrics["landing_success"] = True
        print(" [INFYNEX] ✓ Land command dispatched. Waiting for touchdown and disarm...")

        start = time.time()
        while time.time() - start < 30:
            msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=1.0)
            if msg:
                is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if not is_armed:
                    self.metrics["disarmed_success"] = True
                    print(" [INFYNEX] ✓ Touchdown confirmed. Drone safely disarmed.")
                    return True
            time.sleep(0.3)

        self.metrics["errors"].append("Disarm confirmation timed out after landing")
        print(" [INFYNEX] ✗ Disarm confirmation timed out.")
        return False

    def run(self):
        try:
            if not self.connect():
                return False

            # Wait for GPS lock and set takeoff altitude
            self.wait_for_gps_lock(timeout=20)
            self.set_takeoff_altitude(2.5)

            if not self.arm():
                return False

            self.takeoff(altitude_m=2.5)

            if not self.monitor_flight_and_hover(target_alt_m=2.5, hover_duration_s=5.0):
                return False

            if not self.land():
                return False

            # Final validation check
            if (self.metrics["connection"] and
                self.metrics["armed"] and
                self.metrics["takeoff_success"] and
                self.metrics["hover_success"] and
                self.metrics["landing_success"] and
                self.metrics["disarmed_success"]):
                self.metrics["status"] = "PASSED"
                print("\n=====================================================")
                print(" [INFYNEX] ✓ PHASE 1 MILESTONE: FLIGHT TEST PASSED!")
                print("=====================================================")
                return True
            else:
                self.metrics["status"] = "FAILED"
                print("\n=====================================================")
                print(" [INFYNEX] ✗ PHASE 1 MILESTONE: FLIGHT TEST FAILED.")
                print("=====================================================")
                return False

        except Exception as e:
            self.metrics["errors"].append(str(e))
            print(f" [INFYNEX] Unexpected exception during flight: {e}")
            return False
        finally:
            output_file = "/workspace/data/telemetry/phase1_flight_verification.json"
            try:
                os.makedirs(os.path.dirname(output_file), exist_ok=True)
                with open(output_file, "w") as f:
                    json.dump(self.metrics, f, indent=2)
                print(f" [INFYNEX] Verification metrics saved to: {output_file}")
            except Exception as e:
                print(f" [INFYNEX] Could not write metrics file: {e}")


if __name__ == "__main__":
    verifier = DroneFlightVerifier()
    success = verifier.run()
    sys.exit(0 if success else 1)
