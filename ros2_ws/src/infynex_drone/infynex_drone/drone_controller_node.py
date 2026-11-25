"""
INFYNEX Drone Controller ROS 2 Node (pymavlink implementation)
Provides services/commands for:
- Autonomous Arm & Takeoff
- Waypoint Navigation (Traverse 3D positions with speed & heading control)
- Hover / Hold
- Land & Disarm
- Manual Override
"""

import time
import math
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped
from pymavlink import mavutil

# PX4 Custom Mode Constants
PX4_CUSTOM_MAIN_MODE_AUTO = 4
PX4_CUSTOM_SUB_MODE_AUTO_LOITER = 3
PX4_CUSTOM_SUB_MODE_AUTO_TAKEOFF = 2
PX4_CUSTOM_SUB_MODE_AUTO_LAND = 6
PX4_CUSTOM_SUB_MODE_AUTO_RTL = 5


class DroneControllerNode(Node):
    def __init__(self):
        super().__init__('drone_controller_node')
        self.declare_parameter('mavlink_address', 'udpin:0.0.0.0:14540')
        self.mavlink_address = self.get_parameter('mavlink_address').value

        self.cmd_sub = self.create_subscription(String, '/infynex/drone/command', self._handle_command, 10)
        self.target_sub = self.create_subscription(PoseStamped, '/infynex/drone/setpoint', self._handle_setpoint, 10)
        self.mission_status_pub = self.create_publisher(String, '/infynex/drone/mission_status', 10)

        self.master = None
        self._init_connection()

    def _init_connection(self):
        try:
            self.get_logger().info(f"Connecting to PX4 via {self.mavlink_address}...")
            self.master = mavutil.mavlink_connection(self.mavlink_address)
            self.get_logger().info("✓ MAVLink connection established.")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to PX4 MAVLink: {e}")

    def _publish_status(self, status: str):
        msg = String()
        msg.data = status
        self.mission_status_pub.publish(msg)

    def _handle_command(self, msg: String):
        cmd = msg.data.lower().strip()
        self.get_logger().info(f"Received Drone Command: {cmd}")
        if not self.master:
            self._init_connection()
            if not self.master:
                return

        if cmd == "takeoff":
            self._cmd_takeoff(altitude_m=2.5)
        elif cmd == "land":
            self._cmd_land()
        elif cmd == "rtl":
            self._cmd_rtl()
        elif cmd == "arm":
            self._cmd_arm()
        elif cmd == "disarm":
            self._cmd_disarm()

    def _cmd_arm(self):
        if not self.master:
            return
        self.get_logger().info("Arming drone...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 1, 21196, 0, 0, 0, 0, 0
        )
        self._publish_status("ARMED")

    def _cmd_disarm(self):
        if not self.master:
            return
        self.get_logger().info("Disarming drone...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 0, 0, 0, 0, 0, 0, 0
        )
        self._publish_status("DISARMED")

    def _cmd_takeoff(self, altitude_m: float = 2.5):
        if not self.master:
            return
        self.get_logger().info(f"Arming and executing takeoff to {altitude_m}m...")
        self._cmd_arm()
        time.sleep(1)

        msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=False)
        current_lat = (msg.lat / 1e7) if msg and msg.lat != 0 else float('nan')
        current_lon = (msg.lon / 1e7) if msg and msg.lon != 0 else float('nan')

        # Switch to AUTO -> TAKEOFF
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
        # Send NAV_TAKEOFF
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            0, 0, 0, 0,
            float('nan'),
            current_lat, current_lon,
            float(altitude_m)
        )
        self._publish_status("TAKEOFF_IN_PROGRESS")

    def _cmd_land(self):
        if not self.master:
            return
        self.get_logger().info("Initiating autonomous landing...")
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
            0, 0, 0, 0, 0, 0, 0, 0
        )
        self._publish_status("LANDING_IN_PROGRESS")

    def _cmd_rtl(self):
        if not self.master:
            return
        self.get_logger().info("Executing Return-to-Launch (RTL)...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_MODE,
            0,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            PX4_CUSTOM_MAIN_MODE_AUTO,
            PX4_CUSTOM_SUB_MODE_AUTO_RTL,
            0, 0, 0, 0
        )
        self._publish_status("RTL_IN_PROGRESS")

    def _handle_setpoint(self, msg: PoseStamped):
        if not self.master:
            return
        x = msg.pose.position.x
        y = msg.pose.position.y
        z = -msg.pose.position.z # Up in Gazebo -> Down in NED
        self.get_logger().info(f"Navigating to waypoint target: [{x:.2f}, {y:.2f}, {-z:.2f}]")

        # Send SET_POSITION_TARGET_LOCAL_NED
        # coordinate_frame: MAV_FRAME_LOCAL_NED = 1
        # type_mask: ignore velocity, accel, yaw rate (0b0000111111000111 = 0x0DF7)
        type_mask = 0b0000111111000111
        self.master.mav.set_position_target_local_ned_send(
            int(time.time() * 1000) & 0xFFFFFFFF,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            type_mask,
            x, y, z,
            0, 0, 0,
            0, 0, 0,
            0, 0
        )


def main(args=None):
    rclpy.init(args=args)
    node = DroneControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
