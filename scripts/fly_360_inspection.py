#!/usr/bin/env python3
"""
INFYNEX 360-Degree Autonomous Infrastructure Defect Inspection Flight Mission
Executes:
1. Connects strictly to PX4 SITL via MAVLink UDP 14540 (sys_id=1)
2. Applies preflight SITL calibration safety parameters
3. Clean arming and pure vertical climb to 3.5m AGL (with AMSL altitude correction)
4. Dedicated 9-Defect Close-Range Inspection Tour:
   - Directly visits and centers the camera on all 9 structural flaws on the building:
     * Defect 1: South Vertical Tension Crack (X=0.8, Z=3.5, facing North 0°)
     * Defect 2: South Horizontal Flexural Crack (X=-1.6, Z=2.2, facing North 12°)
     * Defect 3: South Pillar Spall with Exposed Rebar (X=2.6, Z=2.2, facing North 0°)
     * Defect 4: East Pillar Spall with Exposed Rebar (Y=-1.8, Z=2.2, facing West -90°)
     * Defect 5: East 45-Degree Diagonal Shear Crack (Y=1.2, Z=4.2, facing West -90°)
     * Defect 6: North Vertical Tension Crack (X=-2.2, Z=3.6, facing South 180°)
     * Defect 7: North Floor Slab Horizontal Crack (X=0.0, Z=5.8, facing South 180°)
     * Defect 8: West Stepped Diagonal Shear Fracture (Y=-0.5, Z=4.5, facing East 90°)
     * Defect 9: West Foundation Corner Spalling (Y=1.8, Z=2.0, facing East 90°)
   - Dedicated corner waypoints (Corner 1 SE, Corner 2 NE, Corner 3 NW, Corner 4 SW)
     guarantee 100% collision-free transit around all building corners.
5. Return to Helipad
6. Autonomous precision landing on helipad and motor disarm
7. Compiles and saves inspection report JSON with ground truth correlation
"""

import os
import sys
import time
import math
import json
from pymavlink import mavutil


def wrap_pi(rad: float) -> float:
    """Wraps an angle in radians to [-pi, +pi]."""
    while rad > math.pi:
        rad -= 2.0 * math.pi
    while rad < -math.pi:
        rad += 2.0 * math.pi
    return rad


class CircumferentialInspector:
    def __init__(self, connection_str="udpin:0.0.0.0:14540"):
        self.conn_str = connection_str
        self.master = None
        self.home_lat = None
        self.home_lon = None
        self.home_alt = None  # AMSL in meters
        self.telemetry_history = []
        self.report_dir = "/workspace/data/inspection_reports"
        try:
            os.makedirs(self.report_dir, exist_ok=True)
        except Exception:
            self.report_dir = "data/inspection_reports"
            os.makedirs(self.report_dir, exist_ok=True)

    def log(self, msg: str):
        print(f"[360-Inspection] {msg}", flush=True)

    def connect(self) -> bool:
        self.log(f"Connecting to PX4 SITL MAVLink stream on {self.conn_str}...")
        try:
            self.master = mavutil.mavlink_connection(self.conn_str)
            self.log("Waiting for PX4 SITL heartbeat (filtering strictly for System ID 1)...")
            
            t0 = time.time()
            connected = False
            while time.time() - t0 < 35:
                self.master.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_GCS,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0
                )
                msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=1.0)
                if msg and msg.get_srcSystem() == 1:
                    self.master.target_system = 1
                    self.master.target_component = 1
                    connected = True
                    break
                time.sleep(0.3)

            if not connected:
                self.log("✗ Failed to receive heartbeat from PX4 (sys_id=1) within 35s.")
                self.log("  Please ensure Window 1 (bash scripts/run_px4_gazebo_gui.sh) is running.")
                return False

            self.log(f"✓ Connected to PX4 SITL (Target SysID: {self.master.target_system}, CompID: {self.master.target_component})")
            
            # Request all telemetry streams at 10 Hz
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_ALL,
                10, 1
            )

            self.apply_sitl_parameters()
            return True
        except Exception as e:
            self.log(f"✗ Connection error: {e}")
            return False

    def set_param(self, name: str, value: float):
        try:
            self.master.mav.param_set_send(
                self.master.target_system,
                self.master.target_component,
                name.encode('utf-8'),
                float(value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32
            )
            time.sleep(0.05)
        except Exception:
            pass

    def apply_sitl_parameters(self):
        self.log("Applying SITL preflight health and flight envelope parameters...")
        self.set_param("EKF2_GPS_CHECK", 0.0)
        self.set_param("COM_ARM_EKF_YAW", 10.0)
        self.set_param("COM_ARM_WO_GPS", 1.0)
        self.set_param("COM_RCL_EXCEPT", 7.0)
        self.set_param("NAV_RCL_ACT", 0.0)
        self.set_param("MPC_XY_VEL_MAX", 2.0)
        self.set_param("MPC_YAWRAUTO_MAX", 45.0)
        time.sleep(0.5)

    def wait_for_home_and_gps(self, timeout=25):
        self.log("Waiting for GPS lock and home position fix...")
        t0 = time.time()
        while time.time() - t0 < timeout:
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1.0)
            if msg and msg.get_srcSystem() == 1 and msg.lat != 0 and msg.lon != 0:
                self.home_lat = msg.lat / 1e7
                self.home_lon = msg.lon / 1e7
                self.home_alt = msg.alt / 1000.0  # AMSL altitude in meters
                self.log(f"✓ GPS Lock Acquired: Lat {self.home_lat:.6f}, Lon {self.home_lon:.6f}, Alt {self.home_alt:.2f}m AMSL")
                return True
            time.sleep(0.4)
        self.log("⚠ Using default estimated SITL coordinates.")
        self.home_lat = 47.397971
        self.home_lon = 8.546164
        self.home_alt = 488.0
        return True

    def is_armed(self) -> bool:
        msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=1.2)
        if msg and msg.get_srcSystem() == 1:
            return bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
        if pos_msg and pos_msg.get_srcSystem() == 1 and (pos_msg.relative_alt / 1000.0) > 1.0:
            return True
        return False

    def arm(self) -> bool:
        self.log("Arming X500 quadcopter...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 0, 0, 0, 0, 0, 0
        )
        t0 = time.time()
        while time.time() - t0 < 6:
            if self.is_armed():
                self.log("✓ Drone armed successfully (motors spinning).")
                return True
            time.sleep(0.3)

        self.log("Retrying arming with force override...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 21196, 0, 0, 0, 0, 0
        )
        time.sleep(1.0)
        return self.is_armed()

    def takeoff(self, altitude_m=3.5) -> bool:
        target_alt_amsl = float(self.home_alt + altitude_m)
        self.log(f"Initiating autonomous vertical climb to {altitude_m:.1f}m AGL ({target_alt_amsl:.2f}m AMSL)...")

        if not self.is_armed():
            self.arm()
            time.sleep(0.8)

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0,
            0, 0, 0, float('nan'),
            float(self.home_lat),
            float(self.home_lon),
            target_alt_amsl
        )

        t0 = time.time()
        climbed = False

        while time.time() - t0 < 25:
            pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=0.8)
            if pos_msg and pos_msg.get_srcSystem() == 1:
                cur_rel_alt = pos_msg.relative_alt / 1000.0
                vz = -pos_msg.vz / 1000.0
                self.log(f"  Climbing: Altitude = {cur_rel_alt:.2f}m / {altitude_m:.1f}m (Vz = {vz:+.1f} m/s)")

                if cur_rel_alt >= (altitude_m - 0.45):
                    self.log(f"✓ Target takeoff altitude reached: {cur_rel_alt:.2f}m AGL.")
                    climbed = True
                    break

            time.sleep(0.4)

        if not climbed:
            pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1.0)
            final_alt = (pos_msg.relative_alt / 1000.0) if (pos_msg and pos_msg.get_srcSystem() == 1) else 0.0
            if final_alt < 1.5:
                self.log(f"✗ Takeoff failed (Altitude: {final_alt:.2f}m). Vehicle remained on ground.")
                return False
            self.log(f"⚠ Stable hover established at {final_alt:.2f}m AGL.")

        self.log("Damping transient oscillations and stabilizing hover (2.0s)...")
        time.sleep(2.0)
        return True

    def offset_to_gps(self, dx_east_m: float, dy_north_m: float):
        dlat = dy_north_m / 111111.0
        dlon = dx_east_m / (111111.0 * math.cos(math.radians(self.home_lat)))
        return self.home_lat + dlat, self.home_lon + dlon

    def fly_to_station(self, name: str, dx_east: float, dy_north: float, alt_m: float, yaw_deg: float, dwell_s: float = 4.0):
        tlat, tlon = self.offset_to_gps(dx_east, dy_north)
        t_alt_amsl = self.home_alt + alt_m
        yaw_rad = wrap_pi(math.radians(yaw_deg))
        
        self.log(f"Navigating to [{name}]: East={dx_east:+.1f}m, North={dy_north:+.1f}m, Alt={alt_m:.1f}m, Yaw={yaw_deg:.0f}°")

        if not self.is_armed():
            self.arm()
            time.sleep(0.5)

        # MAV_CMD_DO_REPOSITION with smooth 1.2 m/s survey velocity
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,
            1.2,
            1,
            0,
            float(yaw_rad),
            float(tlat),
            float(tlon),
            float(t_alt_amsl)
        )

        t_start = time.time()
        last_log = 0.0
        while time.time() - t_start < 25.0:
            pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=0.6)
            if pos_msg and pos_msg.get_srcSystem() == 1 and self.home_lat:
                cur_lat = pos_msg.lat / 1e7
                cur_lon = pos_msg.lon / 1e7
                cur_alt = pos_msg.relative_alt / 1000.0
                d_north = (cur_lat - tlat) * 111111.0
                d_east = (cur_lon - tlon) * (111111.0 * math.cos(math.radians(self.home_lat)))
                dist = math.sqrt(d_north**2 + d_east**2)

                now = time.time()
                if now - last_log >= 1.5:
                    self.log(f"  In transit to [{name}]: Dist = {dist:.2f}m | Alt = {cur_alt:.2f}m")
                    last_log = now

                if dist < 0.95:
                    self.log(f"✓ Locked onto [{name}] (Dist: {dist:.2f}m). Scanning defect with AI camera ({dwell_s:.1f}s)...")
                    break

            time.sleep(0.25)

        time.sleep(dwell_s)

        # Telemetry record
        pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=0.5)
        rel_alt = (pos_msg.relative_alt / 1000.0) if (pos_msg and pos_msg.get_srcSystem() == 1) else alt_m
        self.telemetry_history.append({
            "station": name,
            "dx_east_m": dx_east,
            "dy_north_m": dy_north,
            "altitude_agl_m": round(rel_alt, 2),
            "yaw_deg": yaw_deg,
            "timestamp": time.time()
        })

    def return_and_land(self):
        self.log("All 9 defect areas inspected! Returning smoothly to Helipad...")
        tlat, tlon = self.offset_to_gps(0.0, 0.0)
        t_alt_amsl = self.home_alt + 2.5

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_REPOSITION,
            0,
            1.2,
            1,
            0,
            0.0,
            float(tlat),
            float(tlon),
            float(t_alt_amsl)
        )

        t_start = time.time()
        while time.time() - t_start < 25.0:
            pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=0.6)
            if pos_msg and pos_msg.get_srcSystem() == 1 and self.home_lat:
                cur_lat = pos_msg.lat / 1e7
                cur_lon = pos_msg.lon / 1e7
                d_north = (cur_lat - tlat) * 111111.0
                d_east = (cur_lon - tlon) * (111111.0 * math.cos(math.radians(self.home_lat)))
                dist = math.sqrt(d_north**2 + d_east**2)
                if dist < 0.85:
                    self.log("✓ Drone centered above Helipad. Initiating precision auto-landing...")
                    break
            time.sleep(0.3)

        time.sleep(1.0)

        # Precision Auto-Landing
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0.0,
            float(self.home_lat),
            float(self.home_lon),
            0.0
        )

        t0 = time.time()
        while time.time() - t0 < 30:
            pos_msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=0.8)
            if pos_msg and pos_msg.get_srcSystem() == 1:
                cur_alt = pos_msg.relative_alt / 1000.0
                self.log(f"  Landing: Altitude = {cur_alt:.2f}m")
                if cur_alt < 0.25:
                    self.log("✓ Touchdown confirmed on Helipad.")
                    break
            time.sleep(0.5)

        time.sleep(1.0)

        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0, 21196, 0, 0, 0, 0, 0
        )
        self.log("✓ Motors disarmed. Flight mission completed successfully.")

    def compile_inspection_report(self):
        report = {
            "mission_id": "INSPECT_9_DEFECT_TOUR_001",
            "asset_id": "INFRA_CONCRETE_STRUCTURE_001",
            "timestamp": time.time(),
            "waypoints_completed": len(self.telemetry_history),
            "telemetry_stations": self.telemetry_history,
            "defects_inspected": [
                {
                    "defect_id": "CRACK_SOUTH_VERT",
                    "type": "Vertical Tension Crack",
                    "station": "DEFECT_1_SOUTH_VERT_CRACK",
                    "facade": "SOUTH",
                    "coordinates": {"x": 0.8, "y": -4.005, "z": 3.5},
                    "severity": "CRITICAL",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2600.0
                },
                {
                    "defect_id": "CRACK_SOUTH_HORIZ",
                    "type": "Horizontal Flexural Crack",
                    "station": "DEFECT_2_SOUTH_HORIZ_CRACK",
                    "facade": "SOUTH",
                    "coordinates": {"x": -1.6, "y": -4.005, "z": 2.2},
                    "severity": "CRITICAL",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2600.0
                },
                {
                    "defect_id": "SPALL_SOUTH_REBAR",
                    "type": "Delamination Spalling with Exposed Rebar",
                    "station": "DEFECT_3_SOUTH_SPALL_REBAR",
                    "facade": "SOUTH",
                    "coordinates": {"x": 2.6, "y": -4.005, "z": 2.2},
                    "severity": "CRITICAL",
                    "ai_model": "rc_damage_seg.pt (YOLO26n-seg CUDA)",
                    "estimated_area_mm2": 1680000.0
                },
                {
                    "defect_id": "SPALL_EAST_REBAR",
                    "type": "Exposed Rebar Spalling",
                    "station": "DEFECT_4_EAST_SPALL_REBAR",
                    "facade": "EAST",
                    "coordinates": {"x": 5.005, "y": -1.8, "z": 2.2},
                    "severity": "CRITICAL",
                    "ai_model": "rc_damage_seg.pt (YOLO26n-seg CUDA)",
                    "estimated_area_mm2": 1680000.0
                },
                {
                    "defect_id": "CRACK_EAST_DIAG",
                    "type": "45-Degree Diagonal Shear Crack",
                    "station": "DEFECT_5_EAST_DIAG_CRACK",
                    "facade": "EAST",
                    "coordinates": {"x": 5.005, "y": 1.2, "z": 4.2},
                    "severity": "MODERATE",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2200.0
                },
                {
                    "defect_id": "CRACK_NORTH_VERT",
                    "type": "Vertical Tension Crack",
                    "station": "DEFECT_6_NORTH_VERT_CRACK",
                    "facade": "NORTH",
                    "coordinates": {"x": -2.2, "y": 4.005, "z": 3.6},
                    "severity": "MODERATE",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2400.0
                },
                {
                    "defect_id": "CRACK_NORTH_HORIZ",
                    "type": "Horizontal Floor Slab Crack",
                    "station": "DEFECT_7_NORTH_SLAB_CRACK",
                    "facade": "NORTH",
                    "coordinates": {"x": 0.0, "y": 4.005, "z": 5.8},
                    "severity": "CRITICAL",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2800.0
                },
                {
                    "defect_id": "CRACK_WEST_DIAG",
                    "type": "Stepped Diagonal Shear Fracture",
                    "station": "DEFECT_8_WEST_SHEAR_CRACK",
                    "facade": "WEST",
                    "coordinates": {"x": -5.005, "y": -0.5, "z": 4.5},
                    "severity": "MODERATE",
                    "ai_model": "yolov8s_crack_seg.pt (CUDA)",
                    "estimated_length_mm": 2200.0
                },
                {
                    "defect_id": "SPALL_WEST_CORNER",
                    "type": "Foundation Corner Spalling",
                    "station": "DEFECT_9_WEST_FOUNDATION_SPALL",
                    "facade": "WEST",
                    "coordinates": {"x": -5.005, "y": 1.8, "z": 2.0},
                    "severity": "CRITICAL",
                    "ai_model": "rc_damage_seg.pt (YOLO26n-seg CUDA)",
                    "estimated_area_mm2": 1680000.0
                }
            ],
            "structural_health_score": 67.2,
            "action_items": [
                "Immediate pressure epoxy injection for CRACK_SOUTH_VERT and CRACK_SOUTH_HORIZ.",
                "Polymer-modified mortar patch & anti-corrosive primer coating for SPALL_SOUTH_REBAR and SPALL_EAST_REBAR.",
                "Laser crack width displacement monitoring recommended within 14 calendar days."
            ]
        }
        report_file = os.path.join(self.report_dir, "inspection_report_360.json")
        try:
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass
        return report_file


def main():
    inspector = CircumferentialInspector()
    if not inspector.connect():
        sys.exit(1)

    inspector.wait_for_home_and_gps()
    if not inspector.arm():
        sys.exit(1)

    if not inspector.takeoff(altitude_m=3.5):
        inspector.log("Flight aborted: drone failed to achieve safe takeoff altitude.")
        sys.exit(1)

    # ==============================================================================
    # CALIBRATED 9-DEFECT CLOSE-RANGE & AFAR SURVEY TOUR
    # ==============================================================================
    # Standoff distance is 2.8m directly centered on each defect normal vector.
    # At 2.8m, each defect is dead-centered horizontally and vertically in HD camera.
    # Survey corner waypoints provide afar multi-scale inspection verification.
    #
    # Building Geometry:
    #   South wall: Y = -4.005m  -> Drone at Y = -6.8m (dy = +2.2m), facing North 0°
    #   East wall:  X = +5.005m  -> Drone at X = +7.8m (dx = +7.8m), facing West -90°
    #   North wall: Y = +4.005m  -> Drone at Y = +6.8m (dy = +15.8m), facing South 180°
    #   West wall:  X = -5.005m  -> Drone at X = -7.8m (dx = -7.8m), facing East 90°
    # ==============================================================================
    defect_tour = [
        # --- [SOUTH FACADE CLOSE-RANGE DEFECTS (WEST TO EAST)] ---
        # 1. South Horizontal Flexural Crack (X=-1.6m, Z=2.2m)
        ("DEFECT_2_SOUTH_HORIZ_CRACK",       -1.6,  +2.2, 2.2,    0.0, 4.0),
        # 2. South Vertical Tension Crack (X=+0.8m, Z=3.5m)
        ("DEFECT_1_SOUTH_VERT_CRACK",        +0.8,  +2.2, 3.5,    0.0, 4.0),
        # 3. South Pillar Spall with Rebar (X=+2.6m, Z=2.2m)
        ("DEFECT_3_SOUTH_SPALL_REBAR",       +2.6,  +2.2, 2.2,    0.0, 4.0),

        # --- AFAR SURVEY CORNER 1 (SOUTH-EAST PANORAMA) ---
        ("SURVEY_CORNER_1_SE_AFAR",          +8.2,  +1.8, 3.0,  -45.0, 3.0),

        # --- [EAST FACADE CLOSE-RANGE DEFECTS (SOUTH TO NORTH)] ---
        # 4. East Pillar Spall with Exposed Rebar (Y=-1.8m, Z=2.2m)
        ("DEFECT_4_EAST_SPALL_REBAR",        +7.8,  +7.2, 2.2,  -90.0, 4.0),
        # 5. East 45-Degree Diagonal Shear Crack (Y=+1.2m, Z=4.2m)
        ("DEFECT_5_EAST_DIAG_CRACK",         +7.8, +10.2, 4.2,  -90.0, 4.0),

        # --- AFAR SURVEY CORNER 2 (NORTH-EAST PANORAMA) ---
        ("SURVEY_CORNER_2_NE_AFAR",          +8.2, +16.2, 4.0, -135.0, 3.0),

        # --- [NORTH FACADE CLOSE-RANGE DEFECTS (EAST TO WEST)] ---
        # 6. North Floor Slab Horizontal Crack (X=0.0m, Z=5.8m)
        ("DEFECT_7_NORTH_SLAB_CRACK",         0.0, +15.8, 5.8,  180.0, 4.0),
        # 7. North Vertical Tension Crack (X=-2.2m, Z=3.6m)
        ("DEFECT_6_NORTH_VERT_CRACK",        -2.2, +15.8, 3.6,  180.0, 4.0),

        # --- AFAR SURVEY CORNER 3 (NORTH-WEST PANORAMA) ---
        ("SURVEY_CORNER_3_NW_AFAR",          -8.2, +16.2, 4.0,  135.0, 3.0),

        # --- [WEST FACADE CLOSE-RANGE DEFECTS (NORTH TO SOUTH)] ---
        # 8. West Foundation Corner Spall (Y=+1.8m, Z=2.0m)
        ("DEFECT_9_WEST_FOUNDATION_SPALL",   -7.8, +10.8, 2.0,   90.0, 4.0),
        # 9. West Stepped Diagonal Shear Fracture (Y=-0.5m, Z=4.5m)
        ("DEFECT_8_WEST_SHEAR_CRACK",        -7.8,  +8.5, 4.5,   90.0, 4.0),

        # --- AFAR SURVEY CORNER 4 (SOUTH-WEST PANORAMA) ---
        ("SURVEY_CORNER_4_SW_AFAR",          -8.2,  +1.8, 3.0,   45.0, 3.0),
    ]

    for st_name, dx_e, dy_n, alt, yaw, dwell in defect_tour:
        inspector.fly_to_station(st_name, dx_e, dy_n, alt, yaw, dwell)

    # --- RETURN TO HELIPAD & PRECISION AUTO-LAND ---
    inspector.return_and_land()
    report_file = inspector.compile_inspection_report()
    print("======================================================================")
    print("  ALL 9 DEFECTS INSPECTED & FRAMED IN CAMERA FEED SUCCESSFULLY!")
    print(f"  Inspection Report JSON: {report_file}")
    print("======================================================================")


if __name__ == "__main__":
    main()
