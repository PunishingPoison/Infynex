"""
INFYNEX Camera Capture ROS 2 Node
Subscribes to `/infynex/camera/image_raw`, saves high-resolution inspection frames,
and signals the AI processing pipeline when a structural waypoint frame is registered.
"""

import os
import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String


class CameraCaptureNode(Node):
    def __init__(self):
        super().__init__('camera_capture_node')
        self.declare_parameter('save_dir', '/workspace/data/captured_images')
        self.save_dir = self.get_parameter('save_dir').value
        os.makedirs(self.save_dir, exist_ok=True)

        self.sub_image = self.create_subscription(
            Image,
            '/infynex/camera/image_raw',
            self._handle_image,
            10
        )
        self.sub_trigger = self.create_subscription(
            String,
            '/infynex/camera/trigger_capture',
            self._handle_trigger,
            10
        )
        self.pub_frame_meta = self.create_publisher(
            String,
            '/infynex/camera/frame_captured',
            10
        )

        self.latest_frame = None
        self.frame_count = 0
        self.active_waypoint = "W0"
        self.get_logger().info(f"✓ Camera Capture Node active. Target directory: {self.save_dir}")

    def _handle_image(self, msg: Image):
        # Convert ROS Image message to numpy array (RGB8 or BGR8)
        try:
            dtype = np.uint8
            n_channels = 3
            img_arr = np.frombuffer(msg.data, dtype=dtype).reshape((msg.height, msg.width, n_channels))
            if msg.encoding == 'rgb8':
                self.latest_frame = cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR)
            else:
                self.latest_frame = img_arr
        except Exception as e:
            self.get_logger().warn(f"Failed to decode camera frame: {e}")

    def _handle_trigger(self, msg: String):
        self.active_waypoint = msg.data.strip()
        if self.latest_frame is None:
            self.get_logger().warn("Trigger received but no camera frames received yet.")
            return

        self.frame_count += 1
        filename = f"frame_{self.frame_count:04d}_{self.active_waypoint}.jpg"
        filepath = os.path.join(self.save_dir, filename)
        cv2.imwrite(filepath, self.latest_frame)
        self.get_logger().info(f"✓ Captured inspection frame saved: {filepath}")

        # Broadcast frame metadata
        meta_msg = String()
        meta_msg.data = f"{filename}|{self.active_waypoint}|{time.time():.3f}"
        self.pub_frame_meta.publish(meta_msg)


def main(args=None):
    rclpy.init(args=args)
    node = CameraCaptureNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
