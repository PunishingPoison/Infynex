#!/usr/bin/env python3
"""
INFYNEX Flight State Publisher
Subscribes to PX4 VehicleOdometry (NED frame) and publishes standard Gazebo ENU poses.
Converts:
  X_enu = Y_ned
  Y_enu = X_ned
  Z_enu = -Z_ned
Publishes:
  /infynex/drone/odometry_enu (geometry_msgs/PoseStamped)
  /infynex/drone/battery (sensor_msgs/BatteryState)
  /infynex/drone/mission_status (std_msgs/String)
"""

import time
import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from rosgraph_msgs.msg import Clock
from pymavlink import mavutil


class FlightStatePublisher(Node):
    def __init__(self):
        super().__init__('flight_state_publisher')
        self.declare_parameter('use_sim_time', True)
        self.declare_parameter('mavlink_address', 'udpin:0.0.0.0:14540')
        self.mavlink_address = self.get_parameter('mavlink_address').value

        self.pose_pub = self.create_publisher(PoseStamped, '/infynex/drone/odometry_enu', 10)
        self.battery_pub = self.create_publisher(BatteryState, '/infynex/drone/battery', 10)
        self.status_pub = self.create_publisher(String, '/infynex/drone/mission_status', 10)

        # Sim time listener
        self.sim_time_ns = 0
        self.create_subscription(Clock, '/clock', self._clock_cb, 10)

        # MAVLink connection
        self.master = None
        self._init_mavlink()

        self.start_wall_time = time.time()
        self.battery_pct = 100.0
        self.active_waypoint = "W1"

        # 20 Hz update timer
        self.timer = self.create_timer(0.05, self._tick)

    def _clock_cb(self, msg: Clock):
        self.sim_time_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def _init_mavlink(self):
        try:
            self.master = mavutil.mavlink_connection(self.mavlink_address)
            self.get_logger().info(f"Connecting to MAVLink on {self.mavlink_address}...")
        except Exception as e:
            self.get_logger().warn(f"MAVLink init exception: {e}")

    def _tick(self):
        now = self.get_clock().now()
        wall_now_ns = int(time.time() * 1_000_000_000)
        stamp_ns = self.sim_time_ns if self.sim_time_ns > 0 else wall_now_ns

        # Read latest pose if available
        x_enu, y_enu, z_enu = 0.0, -6.5, 0.0
        yaw_deg = 0.0

        if self.master:
            pos = self.master.recv_match(type=['LOCAL_POSITION_NED', 'GLOBAL_POSITION_INT'], blocking=False)
            if pos:
                if pos.get_type() == 'LOCAL_POSITION_NED':
                    # NED to ENU conversion
                    x_enu = float(pos.y)
                    y_enu = float(pos.x)
                    z_enu = float(-pos.z)
                elif pos.get_type() == 'GLOBAL_POSITION_INT':
                    z_enu = float(pos.relative_alt / 1000.0)

            att = self.master.recv_match(type='ATTITUDE', blocking=False)
            if att:
                yaw_deg = math.degrees(att.yaw)

        # Publish PoseStamped in ENU
        pose = PoseStamped()
        pose.header.stamp = now.to_msg()
        pose.header.frame_id = "world"
        pose.pose.position.x = x_enu
        pose.pose.position.y = y_enu
        pose.pose.position.z = z_enu

        # Approximate quaternion from yaw
        cy = math.cos(math.radians(yaw_deg) * 0.5)
        sy = math.sin(math.radians(yaw_deg) * 0.5)
        pose.pose.orientation.w = cy
        pose.pose.orientation.z = sy
        self.pose_pub.publish(pose)

        # Dynamic battery modeling
        elapsed = time.time() - self.start_wall_time
        drain_rate = 0.045 if z_enu > 0.3 else 0.005
        self.battery_pct = max(0.0, 100.0 - (elapsed * drain_rate))

        bat = BatteryState()
        bat.header.stamp = now.to_msg()
        bat.percentage = float(self.battery_pct)
        bat.voltage = float(14.8 * (self.battery_pct / 100.0) + 1.2)
        self.battery_pub.publish(bat)

        # Status
        status = String()
        status.data = f"Waypoint: {self.active_waypoint} | Alt: {z_enu:.2f}m | Bat: {self.battery_pct:.1f}% | SimTime: {stamp_ns}ns"
        self.status_pub.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = FlightStatePublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
