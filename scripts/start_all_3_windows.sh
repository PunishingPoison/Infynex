#!/usr/bin/env bash
# ==============================================================================
# INFYNEX: Launch All 3 Native Windows Simultaneously
# Window 1: Native Gazebo Harmonic GUI + PX4 SITL (x500_mono_cam)
# Window 2: Native QGroundControl (AppRun / GCS connected over UDP 14550)
# Window 3: Native OpenCV Window (Real 1280x720 RGB stream via ros_gz_bridge)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================================"
echo "  INFYNEX - Multi-Window Native Robotics Simulation Launcher"
echo "======================================================================"

# 1. Authorize local X11 connections
echo "[Display] Enabling X11 access for local containers..."
xhost +local:root >/dev/null 2>&1 || true
xhost +local:docker >/dev/null 2>&1 || true
export DISPLAY=${DISPLAY:-:0}

# Trap to kill all background processes on Ctrl+C
cleanup() {
    echo -e "\n[Shutdown] Stopping all 3 native windows..."
    docker stop infynex_px4_gui infynex_qgc_gui infynex_camera_gui 2>/dev/null || true
    kill $(jobs -p) 2>/dev/null || true
    echo "[Shutdown] All simulation windows closed."
}
trap cleanup EXIT INT TERM

# 2. Launch Window 1: Gazebo Harmonic GUI + PX4 SITL
echo -e "\n--> Launching Window 1: Gazebo Harmonic 3D World & Physics (PX4 SITL)..."
bash scripts/run_px4_gazebo_gui.sh &
PID_PX4=$!

echo "[Startup] Waiting 5 seconds for Gazebo & PX4 MAVLink port 14550 to initialize..."
sleep 5

# 3. Launch Window 2: QGroundControl
echo -e "\n--> Launching Window 2: Native QGroundControl GCS..."
bash scripts/run_qgroundcontrol.sh &
PID_QGC=$!

sleep 2

# 4. Launch Window 3: Live Camera Feed in Native OpenCV Window
echo -e "\n--> Launching Window 3: Live RGB Camera Stream via ros_gz_bridge..."
bash scripts/run_opencv_camera_view.sh &
PID_CAM=$!

echo -e "\n======================================================================"
echo "  All 3 Native Windows are now active on your desktop!"
echo "  - Window 1: Gazebo Harmonic GUI showing x500_mono_cam quadcopter"
echo "  - Window 2: QGroundControl connected to PX4 SITL over UDP 14550"
echo "  - Window 3: OpenCV window streaming real live Gazebo RGB camera frames"
echo "======================================================================"
echo "Press Ctrl+C to stop the entire native simulation stack."

wait
