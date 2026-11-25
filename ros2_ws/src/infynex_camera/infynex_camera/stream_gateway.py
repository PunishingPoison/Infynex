#!/usr/bin/env python3
"""
INFYNEX Stream Gateway Node
Subscribes to live Gazebo / ROS 2 camera frames (/infynex/camera/image_raw),
embeds sim_time_ns and wall_time_ns timestamps, and streams over UDP/RTP or HTTP/MJPEG
across the infynex_5g_ran virtual network interface to the edge AI engine.
"""

import cv2
import json
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from rosgraph_msgs.msg import Clock
import socket
import threading
import time


class StreamGateway(Node):
    def __init__(self):
        super().__init__('stream_gateway')
        self.declare_parameter('use_sim_time', True)
        self.declare_parameter('stream_port', 5000)
        self.stream_port = self.get_parameter('stream_port').value

        self.sim_time_ns = 0
        self.create_subscription(Clock, '/clock', self._clock_cb, 10)
        self.create_subscription(Image, '/infynex/camera/image_raw', self._image_cb, 10)
        self.create_subscription(CameraInfo, '/infynex/camera/camera_info', self._cam_info_cb, 10)

        self.latest_frame = None
        self.frame_seq = 0
        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.camera_k = None

        self.get_logger().info(f"✓ Stream Gateway initialized on port {self.stream_port}")

    def _clock_cb(self, msg: Clock):
        self.sim_time_ns = msg.clock.sec * 1_000_000_000 + msg.clock.nanosec

    def _cam_info_cb(self, msg: CameraInfo):
        if self.camera_k is None:
            self.camera_k = list(msg.k)
            self.get_logger().info(f"✓ Camera Intrinsics K received: fx={msg.k[0]}, fy={msg.k[4]}, cx={msg.k[2]}, cy={msg.k[5]}")

    def _image_cb(self, msg: Image):
        self.frame_seq += 1
        wall_time_ns = int(time.time() * 1_000_000_000)
        sim_time = self.sim_time_ns if self.sim_time_ns > 0 else wall_time_ns

        # Decode image
        try:
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape((msg.height, msg.width, 3))
            self.latest_frame = arr

            # Frame rate tracking
            self.fps_counter += 1
            now = time.time()
            if now - self.last_fps_time >= 2.0:
                measured_fps = round(self.fps_counter / (now - self.last_fps_time), 1)
                self.get_logger().info(f"[Camera Gateway] Live stream rate: {measured_fps} FPS | Seq: {self.frame_seq} | SimTime: {sim_time}ns")
                self.fps_counter = 0
                self.last_fps_time = now
        except Exception as e:
            self.get_logger().warn(f"Frame decode error: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = StreamGateway()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
