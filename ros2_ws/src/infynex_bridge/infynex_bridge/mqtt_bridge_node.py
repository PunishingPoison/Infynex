"""
INFYNEX ROS 2 to MQTT Gateway Bridge Node
Transforms ROS 2 message topics into standardized JSON MQTT payloads
for ingestion by the FastAPI edge processing backend and TimescaleDB.
"""

import json
import time
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
import paho.mqtt.client as mqtt


class Ros2MqttBridgeNode(Node):
    def __init__(self):
        super().__init__('ros2_mqtt_bridge_node')
        self.declare_parameter('mqtt_host', 'localhost')
        self.declare_parameter('mqtt_port', 1883)
        self.mqtt_host = self.get_parameter('mqtt_host').value
        self.mqtt_port = self.get_parameter('mqtt_port').value

        self.mqtt_client = mqtt.Client(client_id="ros2_mqtt_bridge", protocol=mqtt.MQTTv311)
        self._connect_mqtt()

        # ROS 2 Subscriptions
        self.sub_pos = self.create_subscription(PointStamped, '/infynex/drone/position', self._on_pos, 10)
        self.sub_bat = self.create_subscription(BatteryState, '/infynex/drone/battery', self._on_bat, 10)
        self.sub_status = self.create_subscription(String, '/infynex/drone/status', self._on_status, 10)
        self.sub_damage = self.create_subscription(String, '/infynex/inspection/detections', self._on_damage, 10)

        self.latest_telemetry = {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "battery": 100.0,
            "status": "DISARMED"
        }

        # Periodic telemetry publishing timer (10 Hz)
        self.timer = self.create_timer(0.1, self._publish_telemetry)

    def _connect_mqtt(self):
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            self.get_logger().info(f"✓ ROS 2 Bridge connected to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            self.get_logger().warn(f"MQTT connection failed: {e}. Retrying in background...")

    def _on_pos(self, msg: PointStamped):
        self.latest_telemetry["x"] = round(msg.point.x, 3)
        self.latest_telemetry["y"] = round(msg.point.y, 3)
        self.latest_telemetry["z"] = round(msg.point.z, 3)

    def _on_bat(self, msg: BatteryState):
        self.latest_telemetry["battery"] = round(msg.percentage, 1)

    def _on_status(self, msg: String):
        self.latest_telemetry["status"] = msg.data

    def _on_damage(self, msg: String):
        # Directly pass detection payload to MQTT
        self.mqtt_client.publish("infynex/inspection/detections", msg.data)

    def _publish_telemetry(self):
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "drone_id": "DRONE_X500_01",
            "position": {
                "x": self.latest_telemetry["x"],
                "y": self.latest_telemetry["y"],
                "z": self.latest_telemetry["z"]
            },
            "battery_percent": self.latest_telemetry["battery"],
            "flight_status": self.latest_telemetry["status"]
        }
        self.mqtt_client.publish("infynex/drone/telemetry", json.dumps(payload))


def main(args=None):
    rclpy.init(args=args)
    node = Ros2MqttBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client.loop_stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
