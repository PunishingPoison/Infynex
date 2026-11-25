#!/usr/bin/env bash
# ==============================================================================
# INFYNEX Window 3: Live Camera Feed in Native OpenCV Window with PyTorch AI
# ==============================================================================
set -e

echo "=== [Window 3] Bridging Gazebo /camera to ROS 2 and Launching Native OpenCV Viewer with PyTorch AI ==="
export DISPLAY=${DISPLAY:-:0}
xhost +local:root >/dev/null 2>&1 || true

docker run -i --rm \
  --name infynex_camera_gui \
  --network host \
  --ipc host \
  --privileged \
  -e DISPLAY="$DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -e QT_X11_NO_MITSHM=1 \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  --device /dev/nvidia0 --device /dev/nvidiactl --device /dev/nvidia-uvm \
  -v /usr/lib/x86_64-linux-gnu/libcuda.so.595.99.02:/usr/lib/x86_64-linux-gnu/libcuda.so.1:ro \
  -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.595.99.02:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro \
  -v "$PWD/simulation/docker/py312_cuda_packages:/opt/cuda_packages:ro" \
  -v "$PWD/simulation/docker/py312_torch_packages:/usr/local/lib/python3.12/dist-packages:ro" \
  -e PYTHONPATH="/workspace:/opt/cuda_packages:/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/dist-packages:/opt/ros/jazzy/lib/python3.12/site-packages" \
  -v "$PWD":/workspace \
  -w /workspace \
  infynex-px4-sitl:jazzy bash -c "
    source /opt/ros/jazzy/setup.bash

    echo '[Bridge] Starting ros_gz_bridge for /camera...'
    ros2 run ros_gz_bridge parameter_bridge /camera@sensor_msgs/msg/Image@gz.msgs.Image &
    BRIDGE_PID=\$!

    sleep 1

    echo '[Viewer] Launching native OpenCV GUI window with PyTorch AI detection...'
    python3 scripts/view_camera_opencv.py /camera

    kill \$BRIDGE_PID 2>/dev/null || true
  "
