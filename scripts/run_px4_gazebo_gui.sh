#!/usr/bin/env bash
# ==============================================================================
# INFYNEX Window 1: Native Gazebo Harmonic GUI + PX4 SITL (x500_mono_cam)
# World: Realistic Concrete Bridge Infrastructure with 12 Defect Decals & Site Buildings
# ==============================================================================
set -e

echo "=== [Window 1] Configuring X11 Display & GPU Passthrough ==="
xhost +local:root >/dev/null 2>&1 || true
xhost +local:docker >/dev/null 2>&1 || true

export DISPLAY=${DISPLAY:-:0}
echo "Using DISPLAY: $DISPLAY"

echo "=== [Window 1] Launching Gazebo Harmonic + PX4 SITL (Bridge Infrastructure World) ==="
echo "Loading real concrete bridge structure, crack & spalling decals, and surrounding buildings."
echo "Drone loaded on helipad at (0, -6.5, 0.25) facing inspection facade."
echo "MAVLink listening on UDP 14550 (QGroundControl) and UDP 14540 (360 Flight API)."
echo "=========================================================================="

docker run -i --rm \
  --name infynex_px4_gui \
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
  -v "$PWD/simulation/gazebo/models:/opt/PX4-Autopilot/Tools/simulation/gz/models/infynex_models:ro" \
  -v "$PWD/simulation/gazebo/models/x500_mono_cam:/opt/PX4-Autopilot/Tools/simulation/gz/models/x500_mono_cam:ro" \
  -v "$PWD/simulation/gazebo/models/mono_cam:/opt/PX4-Autopilot/Tools/simulation/gz/models/mono_cam:ro" \
  -v "$PWD/simulation/gazebo/worlds/bridge_inspection.sdf:/opt/PX4-Autopilot/Tools/simulation/gz/worlds/bridge_inspection.sdf:ro" \
  infynex-px4-sitl:jazzy bash -c "
    cd /opt/PX4-Autopilot
    export GZ_SIM_RESOURCE_PATH=/opt/PX4-Autopilot/Tools/simulation/gz/models/infynex_models:/opt/PX4-Autopilot/Tools/simulation/gz/models:/opt/PX4-Autopilot/Tools/simulation/gz/worlds
    export SDF_PATH=/opt/PX4-Autopilot/Tools/simulation/gz/models/infynex_models:/opt/PX4-Autopilot/Tools/simulation/gz/models/infynex_models
    export PX4_GZ_WORLD=bridge_inspection
    export PX4_GZ_MODEL_NAME=x500_mono_cam_0
    make px4_sitl gz_x500_mono_cam
  "
