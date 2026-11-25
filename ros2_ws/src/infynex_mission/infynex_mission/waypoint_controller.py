#!/usr/bin/env python3
"""
INFYNEX Waypoint Controller & Manual Override Node
Executes W1-W9 circumferential inspection flight around bridge superstructure.
Preempts autonomous offboard path if manual override is triggered on /infynex/mission/override.
"""

import time
import yaml
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String


class WaypointController(Node):
    def __init__(self):
        super().__init__('waypoint_controller')
        self.declare_parameter('use_sim_time', True)
        self.declare_parameter('mission_file', '/workspace/simulation/scenarios/mission_facade_scan.yaml')
        self.mission_file = self.get_parameter('mission_file').value

        self.setpoint_pub = self.create_publisher(PoseStamped, '/infynex/drone/setpoint_enu', 10)
        self.active_wp_pub = self.create_publisher(String, '/infynex/mission/active_waypoint', 10)

        # Manual override listener
        self.create_subscription(String, '/infynex/mission/override', self._override_cb, 10)

        self.manual_override_active = False
        self.override_state = "AUTO"
        self.waypoints = []
        self._load_mission()

        self.current_idx = 0
        self.dwell_timer = 0
        self.timer = self.create_timer(1.0, self._step_mission)

    def _load_mission(self):
        try:
            with open(self.mission_file, 'r') as f:
                data = yaml.safe_load(f)
                self.waypoints = data.get('waypoints', [])
                self.get_logger().info(f"✓ WaypointController loaded {len(self.waypoints)} waypoints from {self.mission_file}")
        except Exception as e:
            self.get_logger().error(f"Failed to load mission YAML: {e}")

    def _override_cb(self, msg: String):
        cmd = msg.data.strip().lower()
        self.get_logger().warn(f"🚨 MANUAL OVERRIDE RECEIVED: '{cmd.upper()}'! Preempting offboard mission controller.")
        self.manual_override_active = True
        self.override_state = cmd.upper()

        status_msg = String()
        status_msg.data = f"OVERRIDE_{cmd.upper()}"
        self.active_wp_pub.publish(status_msg)

    def _step_mission(self):
        if self.manual_override_active:
            self.get_logger().info(f"Manual Override in effect: {self.override_state} (Offboard tracking paused).")
            return

        if self.current_idx >= len(self.waypoints):
            self.get_logger().info("✓ Inspection Mission W1-W9 completed successfully.")
            return

        wp = self.waypoints[self.current_idx]
        wp_id = wp.get("id", f"W{self.current_idx+1}")
        pos = wp.get("position_enu", {"x": 0.0, "y": 0.0, "z": 0.0})

        # Publish target ENU setpoint
        sp = PoseStamped()
        sp.header.stamp = self.get_clock().now().to_msg()
        sp.header.frame_id = "world"
        sp.pose.position.x = float(pos.get("x", 0.0))
        sp.pose.position.y = float(pos.get("y", 0.0))
        sp.pose.position.z = float(pos.get("z", 0.0))
        self.setpoint_pub.publish(sp)

        # Broadcast active waypoint name
        wp_msg = String()
        wp_msg.data = f"{wp_id}: {wp.get('name', 'Survey Station')}"
        self.active_wp_pub.publish(wp_msg)

        self.dwell_timer += 1
        if self.dwell_timer >= 4:  # Advance waypoint every 4s
            self.dwell_timer = 0
            self.current_idx += 1
            if self.current_idx < len(self.waypoints):
                next_wp = self.waypoints[self.current_idx]
                self.get_logger().info(f"Advancing -> {next_wp['id']}: {next_wp['name']} [{next_wp['position_enu']}]")


def main(args=None):
    rclpy.init(args=args)
    node = WaypointController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
