"""
INFYNEX Mission Coordinator Node
Sequences structural waypoints W1 -> W9 from YAML profile.
Orchestrates:
1. Preflight status checks
2. Takeoff
3. Offboard navigation to inspection stations
4. Optical dwell & camera frame triggers
5. RTL & Touchdown
"""

import time
import yaml
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from geometry_msgs.msg import PoseStamped, PointStamped


class MissionCoordinatorNode(Node):
    def __init__(self):
        super().__init__('mission_coordinator_node')
        self.declare_parameter('scenario_file', '/workspace/simulation/scenarios/normal_inspection.yaml')
        self.scenario_file = self.get_parameter('scenario_file').value

        self.cmd_pub = self.create_publisher(String, '/infynex/drone/command', 10)
        self.setpoint_pub = self.create_publisher(PoseStamped, '/infynex/drone/setpoint', 10)
        self.trigger_pub = self.create_publisher(String, '/infynex/camera/trigger_capture', 10)
        self.mission_status_pub = self.create_publisher(String, '/infynex/mission/status', 10)

        self.waypoints = []
        self._load_mission()
        self.current_wp_idx = 0
        self.timer = self.create_timer(1.0, self._mission_loop)
        self.state = "INIT"
        self.dwell_counter = 0

    def _load_mission(self):
        try:
            with open(self.scenario_file, 'r') as f:
                data = yaml.safe_load(f)
                self.waypoints = data.get('drone', {}).get('waypoints', [])
                self.get_logger().info(f"✓ Loaded {len(self.waypoints)} waypoints from {self.scenario_file}")
        except Exception as e:
            self.get_logger().error(f"Failed to load mission YAML: {e}")

    def _mission_loop(self):
        if self.state == "INIT":
            self.get_logger().info("Mission Coordinator initialized. Ready to execute inspection.")
            self.state = "READY"

        elif self.state == "READY":
            # Command takeoff
            self.get_logger().info("Commanding takeoff...")
            msg = String()
            msg.data = "takeoff"
            self.cmd_pub.publish(msg)
            self.state = "TAKING_OFF"
            self.dwell_counter = 8 # Wait 8 seconds for ascent

        elif self.state == "TAKING_OFF":
            self.dwell_counter -= 1
            if self.dwell_counter <= 0:
                self.state = "TRAVERSING"
                self.current_wp_idx = 1 # W1 takeoff complete, advance to W2

        elif self.state == "TRAVERSING":
            if self.current_wp_idx >= len(self.waypoints):
                self.get_logger().info("All waypoints completed! Commanding RTL/Land.")
                msg = String()
                msg.data = "land"
                self.cmd_pub.publish(msg)
                self.state = "LANDING"
                return

            wp = self.waypoints[self.current_wp_idx]
            self.get_logger().info(f"Advancing to Waypoint {wp['id']} ({wp['action']}) -> [{wp['x']}, {wp['y']}, {wp['z']}]")

            setpoint = PoseStamped()
            setpoint.header.stamp = self.get_clock().now().to_msg()
            setpoint.header.frame_id = "map"
            setpoint.pose.position.x = float(wp['x'])
            setpoint.pose.position.y = float(wp['y'])
            setpoint.pose.position.z = float(wp['z'])
            self.setpoint_pub.publish(setpoint)

            self.state = "DWELLING"
            self.dwell_counter = 5 # 5 seconds travel + dwell

        elif self.state == "DWELLING":
            self.dwell_counter -= 1
            if self.dwell_counter == 2:
                # Trigger inspection image capture at station
                wp = self.waypoints[self.current_wp_idx]
                trigger_msg = String()
                trigger_msg.data = wp['id']
                self.trigger_pub.publish(trigger_msg)
                self.get_logger().info(f"Triggered camera frame capture at {wp['id']}")

            elif self.dwell_counter <= 0:
                self.current_wp_idx += 1
                self.state = "TRAVERSING"

        elif self.state == "LANDING":
            self.get_logger().info("Landing in progress...")
            self.state = "COMPLETED"


def main(args=None):
    rclpy.init(args=args)
    node = MissionCoordinatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
