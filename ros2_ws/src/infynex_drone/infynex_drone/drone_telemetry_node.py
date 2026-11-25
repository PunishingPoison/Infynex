"""
INFYNEX Drone Telemetry ROS 2 Node (pymavlink implementation)
Subscribes to PX4 MAVLink telemetry and publishes to ROS 2 topics:
- /infynex/drone/position (geometry_msgs/PointStamped)
- /infynex/drone/battery (sensor_msgs/BatteryState)
- /infynex/drone/status (std_msgs/String)
"""

import threading
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from pymavlink import mavutil


class DroneTelemetryNode(Node):
    def __init__(self):
        super().__init__('drone_telemetry_node')
        self.declare_parameter('mavlink_address', 'udpin:0.0.0.0:14540')
        self.mavlink_address = self.get_parameter('mavlink_address').value

        self.pos_pub = self.create_publisher(PointStamped, '/infynex/drone/position', 10)
        self.battery_pub = self.create_publisher(BatteryState, '/infynex/drone/battery', 10)
        self.status_pub = self.create_publisher(String, '/infynex/drone/status', 10)

        self.master = None
        self.running = True
        self.thread = threading.Thread(target=self._telemetry_worker, daemon=True)
        self.thread.start()

    def _telemetry_worker(self):
        self.get_logger().info(f"Connecting to PX4 MAVLink telemetry on {self.mavlink_address}...")
        try:
            self.master = mavutil.mavlink_connection(self.mavlink_address)
            self.master.wait_heartbeat(timeout=30)
            self.get_logger().info("✓ Connected to PX4 SITL Telemetry Stream!")
        except Exception as e:
            self.get_logger().error(f"Failed to connect to MAVLink telemetry: {e}")
            return

        while self.running:
            try:
                msg = self.master.recv_match(blocking=True, timeout=0.5)
                if not msg:
                    continue

                msg_type = msg.get_type()
                if msg_type == 'GLOBAL_POSITION_INT':
                    pt = PointStamped()
                    pt.header.stamp = self.get_clock().now().to_msg()
                    pt.header.frame_id = "map"
                    pt.point.x = msg.lat / 1e7
                    pt.point.y = msg.lon / 1e7
                    pt.point.z = msg.relative_alt / 1000.0
                    self.pos_pub.publish(pt)

                elif msg_type == 'SYS_STATUS':
                    bat = BatteryState()
                    bat.header.stamp = self.get_clock().now().to_msg()
                    bat.voltage = msg.voltage_battery / 1000.0 if msg.voltage_battery > 0 else 16.8
                    bat.percentage = float(msg.battery_remaining) if msg.battery_remaining >= 0 else 98.0
                    self.battery_pub.publish(bat)

                elif msg_type == 'HEARTBEAT':
                    is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    status_msg = String()
                    status_msg.data = f"ARMED" if is_armed else "DISARMED"
                    self.status_pub.publish(status_msg)

            except Exception as e:
                time.sleep(0.1)

    def destroy_node(self):
        self.running = False
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DroneTelemetryNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
