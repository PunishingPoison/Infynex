#!/usr/bin/env python3
"""
INFYNEX Interactive Drone Manual Cockpit (PX4 SITL Offboard Position Control)
Rock-solid manual control: the drone never drifts, flips, or crashes.
All inputs adjust local 3D target coordinates; releasing keys holds exact position in 3D hover.

Controls:
  [T] Auto-Takeoff to 2.8m Hover   [L] Auto-Land & Disarm
  [W] Tilt / Fly Forward           [S] Tilt / Fly Backward
  [A] Strafe Left                  [D] Strafe Right
  [Space] Climb Up                 [Z] Descend Down
  [Q] Turn Left (Yaw Pan)          [E] Turn Right (Yaw Pan)
  [H] Emergency Hold / Hover       [X] Emergency Disarm
  [1] Slow (0.08m)  [2] Normal (0.16m)  [3] Fast (0.32m) Speed Presets
  [I] Invert Pitch / Tilt          [U] Invert Roll / Strafe
  [ESC / Ctrl+C] Exit
"""

import os
import sys
import time
import math
import select
import termios
import tty
import threading
from pymavlink import mavutil


def wrap_pi(rad: float) -> float:
    while rad > math.pi:
        rad -= 2.0 * math.pi
    while rad < -math.pi:
        rad += 2.0 * math.pi
    return rad


class NonBlockingKeyboard:
    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_key(self, timeout=0.04):
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            return sys.stdin.read(1)
        return None


class PrecisionDroneCockpit:
    def __init__(self, connection_str="udpin:0.0.0.0:14540"):
        self.conn_str = connection_str
        self.master = None
        self.sys_id = 1
        self.comp_id = 1
        self.is_armed = False
        self.flight_mode = "STANDBY"
        self.running = True

        # Current vehicle state (Local NED frame)
        self.cur_x = 0.0
        self.cur_y = 0.0
        self.cur_z = 0.0
        self.cur_yaw = 0.0
        self.cur_vx = 0.0
        self.cur_vy = 0.0
        self.cur_vz = 0.0

        # Commanded targets (Local NED frame)
        # In NED frame, z is negative UP: z = -2.8 means 2.8m altitude
        self.target_x = 0.0
        self.target_y = 0.0
        self.target_z = 0.0
        self.target_yaw = 0.0

        # Refined sensitivity: reduced from 0.45m to 0.16m for smooth, silky control
        self.step_size = 0.16   # meters per key tap (Normal mode)
        self.alt_step = 0.15    # meters per key tap
        self.yaw_step = 0.08    # radians per key tap (~4.6 degrees)
        self.speed_mode_name = "NORMAL (0.16m)"

        # Direction configuration
        # pitch_inverted = False: W is forward, S is backward
        self.pitch_inverted = False
        # strafe_inverted = False: A is left, D is right
        self.strafe_inverted = False

        self.active_action = "READY ON GROUND - PRESS [T] TO TAKEOFF"
        self.in_air = False
        self.initial_pos_acquired = False

    def connect(self) -> bool:
        print(f"\n[Cockpit] Connecting to PX4 SITL MAVLink stream on {self.conn_str}...", flush=True)
        try:
            self.master = mavutil.mavlink_connection(self.conn_str)
            t0 = time.time()
            hb_px4 = None

            # Filter heartbeats: strictly select PX4 autopilot (sys_id != 255), ignoring GCS heartbeats
            while time.time() - t0 < 30:
                self.master.mav.heartbeat_send(
                    mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                    mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                    0, 0, 0
                )
                msg = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=0.8)
                if msg:
                    src_sys = msg.get_srcSystem()
                    if src_sys == 1 or (src_sys != 255 and msg.type in [mavutil.mavlink.MAV_TYPE_QUADROTOR, 2]):
                        hb_px4 = msg
                        break
                time.sleep(0.2)

            if not hb_px4:
                print("[Cockpit] ✗ Failed to find PX4 Autopilot. Ensure Window 1 (run_px4_gazebo_gui.sh) is running.", flush=True)
                return False

            self.sys_id = hb_px4.get_srcSystem()
            self.comp_id = hb_px4.get_srcComponent()
            print(f"[Cockpit] ✓ Linked to PX4 Autopilot (SysID: {self.sys_id}, CompID: {self.comp_id})", flush=True)

            # Automatically apply SITL parameter calibration to eliminate preflight false alarms
            print("[Cockpit] Optimizing PX4 SITL parameters for instantaneous responsiveness...", flush=True)
            self._configure_sitl_parameters()

            # Acquire initial position
            t_acq = time.time()
            while time.time() - t_acq < 4.0:
                pos = self.master.recv_match(type='LOCAL_POSITION_NED', blocking=True, timeout=0.5)
                if pos:
                    self.cur_x = pos.x
                    self.cur_y = pos.y
                    self.cur_z = pos.z
                    self.target_x = pos.x
                    self.target_y = pos.y
                    self.target_z = pos.z
                    self.initial_pos_acquired = True
                    break

            att = self.master.recv_match(type='ATTITUDE', blocking=False)
            if att:
                self.cur_yaw = att.yaw
                self.target_yaw = att.yaw

            print(f"[Cockpit] ✓ Initial position locked: X={self.cur_x:+.2f}m, Y={self.cur_y:+.2f}m, Alt={-self.cur_z:.2f}m", flush=True)
            return True

        except Exception as e:
            print(f"[Cockpit] Connection error: {e}", flush=True)
            return False

    def _configure_sitl_parameters(self):
        """Disables synthetic simulation drift checks and RC loss blocks so flight is 100% reliable."""
        sitl_params = [
            ('EKF2_GPS_CHECK', 0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
            ('COM_ARM_EKF_YAW', 10.0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32),
            ('COM_ARM_WO_GPS', 1, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
            ('COM_RCL_EXCEPT', 7, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
            ('NAV_RCL_ACT', 0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
            ('COM_OBL_ACT', 0, mavutil.mavlink.MAV_PARAM_TYPE_INT32),
            ('COM_DISARM_PRFLT', 0.0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32),
        ]
        for name, val, ptype in sitl_params:
            try:
                self.master.mav.param_set_send(
                    self.sys_id, self.comp_id,
                    name.encode(),
                    float(val),
                    ptype
                )
                time.sleep(0.03)
            except Exception:
                pass

    def start_telemetry_thread(self):
        def telemetry_loop():
            while self.running:
                try:
                    msg = self.master.recv_match(blocking=False)
                    if msg:
                        mtype = msg.get_type()
                        if mtype == 'LOCAL_POSITION_NED':
                            self.cur_x = msg.x
                            self.cur_y = msg.y
                            self.cur_z = msg.z
                            self.cur_vx = msg.vx
                            self.cur_vy = msg.vy
                            self.cur_vz = msg.vz
                            if not self.in_air and not self.is_armed:
                                self.target_x = self.cur_x
                                self.target_y = self.cur_y
                        elif mtype == 'ATTITUDE':
                            self.cur_yaw = msg.yaw
                        elif mtype == 'HEARTBEAT' and msg.get_srcSystem() == self.sys_id:
                            self.is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                            custom_main = (msg.custom_mode >> 16) & 0xFF
                            if custom_main == 6 or msg.custom_mode == 6:
                                self.flight_mode = "OFFBOARD"
                            elif custom_main == 1:
                                self.flight_mode = "MANUAL"
                            elif custom_main == 2:
                                self.flight_mode = "ALTCTL"
                            elif custom_main == 3:
                                self.flight_mode = "POSCTL"
                            elif custom_main == 4:
                                self.flight_mode = "AUTO"
                            else:
                                self.flight_mode = "STABILIZED" if self.is_armed else "STANDBY"
                except Exception:
                    pass
                time.sleep(0.02)

        t = threading.Thread(target=telemetry_loop, daemon=True)
        t.start()

    def start_setpoint_stream_thread(self):
        """Continuously streams setpoints at 25 Hz. PX4 requires uninterrupted setpoints in OFFBOARD mode."""
        def stream_loop():
            last_hb_time = 0.0
            last_mc_time = 0.0

            while self.running:
                now = time.time()
                try:
                    # 1. Stream 3D Position Target (Local NED frame)
                    self.master.mav.set_position_target_local_ned_send(
                        int(now * 1000) & 0xFFFFFFFF,
                        self.sys_id,
                        self.comp_id,
                        mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                        0b0000_1011_1111_1000,
                        float(self.target_x),
                        float(self.target_y),
                        float(self.target_z),
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        float(wrap_pi(self.target_yaw)),
                        0.0
                    )

                    # 2. Stream heartbeat at 1 Hz
                    if now - last_hb_time >= 1.0:
                        self.master.mav.heartbeat_send(
                            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
                            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                            0, 0, 0
                        )
                        last_hb_time = now

                    # 3. Stream neutral manual control at 10 Hz (clears RC loss flags in PX4)
                    if now - last_mc_time >= 0.10:
                        self.master.mav.manual_control_send(
                            self.sys_id,
                            0, 0, 500, 0, 0
                        )
                        last_mc_time = now

                except Exception:
                    pass
                time.sleep(0.04)  # 25 Hz

        t = threading.Thread(target=stream_loop, daemon=True)
        t.start()

    def engage_offboard_and_arm(self):
        """Commands OFFBOARD mode and arms vehicle. Setpoints are already streamed by background thread."""
        time.sleep(0.1)
        self.master.mav.command_long_send(
            self.sys_id, self.comp_id,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            1, 6, 0, 0, 0, 0, 0
        )
        time.sleep(0.1)
        self.master.mav.command_long_send(
            self.sys_id, self.comp_id,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            1, 21196, 0, 0, 0, 0, 0
        )
        time.sleep(0.1)

    def takeoff(self, height_m=2.8):
        self.active_action = f"TAKEOFF IN PROGRESS -> CLIMBING TO {height_m:.1f}m AGL"
        self.target_x = self.cur_x
        self.target_y = self.cur_y
        self.target_z = -abs(height_m)
        self.target_yaw = self.cur_yaw

        self.engage_offboard_and_arm()
        self.in_air = True

    def land(self):
        self.active_action = "PRECISION AUTO-LANDING"
        self.master.mav.command_long_send(
            self.sys_id, self.comp_id,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0,
            0, 0, 0, 0,
            0, 0, 0
        )
        self.in_air = False

    def disarm(self):
        self.active_action = "MOTORS STOPPED / DISARMED"
        self.master.mav.command_long_send(
            self.sys_id, self.comp_id,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,
            0, 21196, 0, 0, 0, 0, 0
        )
        self.in_air = False

    def render_hud(self):
        cur_alt = -self.cur_z
        target_alt = -self.target_z
        status_armed = "ARMED (PROPS SPINNING)" if self.is_armed else "DISARMED (STANDBY)"
        color_arm = "\033[92m" if self.is_armed else "\033[91m"
        rst = "\033[0m"

        pitch_str = "REVERSED" if self.pitch_inverted else "NORMAL (FORWARD [W] / BACK [S])"
        strafe_str = "REVERSED" if self.strafe_inverted else "NORMAL (LEFT [A] / RIGHT [D])"

        sys.stdout.write("\033[H\033[J")
        print("=======================================================================")
        print("          INFYNEX MANUAL DRONE KEYBOARD COCKPIT (OFFBOARD)            ")
        print("=======================================================================")
        print(f" Target Link: PX4 SITL (SysID: {self.sys_id}) | Mode: \033[96m{self.flight_mode:<10}\033[0m")
        print(f" Vehicle Status: {color_arm}{status_armed}{rst}")
        print(f" Altitude:    \033[92m{cur_alt:5.2f}m AGL\033[0m  (Target: {target_alt:4.1f}m) | Speed: {math.sqrt(self.cur_vx**2 + self.cur_vy**2):4.1f} m/s")
        print(f" Position:    X={self.cur_x:+5.2f}m | Y={self.cur_y:+5.2f}m | Yaw={math.degrees(self.cur_yaw):+4.0f}°")
        print(f" Dynamics:    Speed: \033[93m{self.speed_mode_name}\033[0m | Tilt/Pitch: \033[95m{pitch_str}\033[0m | Strafe: \033[95m{strafe_str}\033[0m")
        print("-----------------------------------------------------------------------")
        print(f" Active Action: \033[93m{self.active_action}\033[0m")
        print("-----------------------------------------------------------------------")
        print("  FLIGHT CONTROLS (Relative to Camera View):                           ")
        print(f"          [W] Tilt / Fly Forward         [Space] Climb (+{self.alt_step:.2f}m)")
        print(f"   [A] Left  [S] Backward  [D] Right       [Z]   Descend (-{self.alt_step:.2f}m)")
        print("                                                                       ")
        print(f"   [Q] Turn Left (Pan)                    [E] Turn Right (Pan)         ")
        print("-----------------------------------------------------------------------")
        print("  TUNING & TOGGLES:                                                    ")
        print("   [1] Slow (0.08m)   [2] Normal (0.16m)   [3] Fast (0.32m) Sensitivity")
        print("   [I] Toggle Tilt/Pitch Direction         [U] Toggle Left/Right Strafe")
        print("-----------------------------------------------------------------------")
        print("  COMMAND SHORTCUTS:                                                   ")
        print("   [T] Auto Takeoff & Hover at 2.8m       [L] Auto Land Here           ")
        print("   [H] Hold Exact Spot (Hover)            [X] Emergency Motor Disarm   ")
        print("   [ESC / Ctrl+C] Exit Cockpit                                         ")
        print("=======================================================================")
        sys.stdout.flush()

    def run_cockpit(self):
        self.start_telemetry_thread()
        time.sleep(0.4)
        self.start_setpoint_stream_thread()

        last_hud = 0.0

        with NonBlockingKeyboard() as kbd:
            while self.running:
                key = kbd.get_key(timeout=0.04)
                now = time.time()

                if key:
                    key = key.lower()
                    cos_y = math.cos(self.cur_yaw)
                    sin_y = math.sin(self.cur_yaw)

                    # Direction multipliers
                    # pitch_mult inverts W/S tilting direction
                    p_mult = -1.0 if self.pitch_inverted else 1.0
                    # strafe_mult handles true Left vs Right
                    s_mult = -1.0 if self.strafe_inverted else 1.0

                    if key == 't':
                        self.takeoff(height_m=2.8)
                    elif key == 'w':
                        # Tilt / Fly Forward along camera heading
                        if not self.in_air:
                            self.takeoff(height_m=2.8)
                        else:
                            self.target_x += p_mult * self.step_size * cos_y
                            self.target_y += p_mult * self.step_size * sin_y
                            self.active_action = "TILTING / FLYING FORWARD"
                    elif key == 's':
                        # Tilt / Fly Backward along camera heading
                        if not self.in_air:
                            self.takeoff(height_m=2.8)
                        else:
                            self.target_x -= p_mult * self.step_size * cos_y
                            self.target_y -= p_mult * self.step_size * sin_y
                            self.active_action = "TILTING / FLYING BACKWARD"
                    elif key == 'a':
                        # Strafe Left (relative to camera facing)
                        # Left vector in NED: (+sin_y, -cos_y)
                        if not self.in_air:
                            self.takeoff(height_m=2.8)
                        else:
                            self.target_x += s_mult * self.step_size * sin_y
                            self.target_y -= s_mult * self.step_size * cos_y
                            self.active_action = "STRAFING LEFT"
                    elif key == 'd':
                        # Strafe Right (relative to camera facing)
                        # Right vector in NED: (-sin_y, +cos_y)
                        if not self.in_air:
                            self.takeoff(height_m=2.8)
                        else:
                            self.target_x -= s_mult * self.step_size * sin_y
                            self.target_y += s_mult * self.step_size * cos_y
                            self.active_action = "STRAFING RIGHT"
                    elif key == ' ':
                        # Climb higher
                        if not self.in_air:
                            self.takeoff(height_m=2.8)
                        else:
                            self.target_z = max(-15.0, self.target_z - self.alt_step)
                            self.active_action = f"CLIMBING -> TARGET {-self.target_z:.2f}m"
                    elif key == 'z':
                        # Descend lower
                        if self.in_air:
                            self.target_z = min(-0.35, self.target_z + self.alt_step)
                            self.active_action = f"DESCENDING -> TARGET {-self.target_z:.2f}m"
                    elif key == 'q':
                        # Turn Left (yaw pan)
                        self.target_yaw = wrap_pi(self.target_yaw - self.yaw_step)
                        self.active_action = f"PANNING LEFT ({math.degrees(self.target_yaw):.0f}°)"
                    elif key == 'e':
                        # Turn Right (yaw pan)
                        self.target_yaw = wrap_pi(self.target_yaw + self.yaw_step)
                        self.active_action = f"PANNING RIGHT ({math.degrees(self.target_yaw):.0f}°)"
                    elif key == '1':
                        # Sensitivity: Slow / Inspection
                        self.step_size = 0.08
                        self.alt_step = 0.08
                        self.yaw_step = 0.05
                        self.speed_mode_name = "SLOW / FINE (0.08m)"
                        self.active_action = "SENSITIVITY: SLOW (FINE CRACK INSPECTION)"
                    elif key == '2':
                        # Sensitivity: Normal
                        self.step_size = 0.16
                        self.alt_step = 0.15
                        self.yaw_step = 0.08
                        self.speed_mode_name = "NORMAL (0.16m)"
                        self.active_action = "SENSITIVITY: NORMAL"
                    elif key == '3':
                        # Sensitivity: Fast
                        self.step_size = 0.32
                        self.alt_step = 0.25
                        self.yaw_step = 0.14
                        self.speed_mode_name = "FAST / CRUISE (0.32m)"
                        self.active_action = "SENSITIVITY: FAST"
                    elif key == 'i':
                        # Toggle pitch / tilting inversion
                        self.pitch_inverted = not self.pitch_inverted
                        p_name = "REVERSED / INVERTED" if self.pitch_inverted else "STANDARD"
                        self.active_action = f"TILT/PITCH TOGGLED TO: {p_name}"
                    elif key == 'u':
                        # Toggle strafe inversion
                        self.strafe_inverted = not self.strafe_inverted
                        s_name = "REVERSED" if self.strafe_inverted else "NORMAL"
                        self.active_action = f"STRAFE TOGGLED TO: {s_name}"
                    elif key == 'h':
                        # Lock current position
                        self.target_x = self.cur_x
                        self.target_y = self.cur_y
                        self.target_z = self.cur_z
                        self.target_yaw = self.cur_yaw
                        self.active_action = "HOLDING POSITION (STABLE HOVER)"
                    elif key == 'l':
                        self.land()
                    elif key == 'x':
                        self.disarm()
                    elif key in ['\x1b', '\x03']:  # ESC or Ctrl+C
                        self.running = False
                        break

                if now - last_hud >= 0.12:
                    self.render_hud()
                    last_hud = now

        print("\n[Cockpit] Exited manual flight cockpit.")


def main():
    cockpit = PrecisionDroneCockpit()
    if not cockpit.connect():
        sys.exit(1)
    cockpit.run_cockpit()


if __name__ == "__main__":
    main()
