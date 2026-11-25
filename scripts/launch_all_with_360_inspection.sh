#!/usr/bin/env bash
# ==============================================================================
# INFYNEX: All-in-One Autonomous Inspection Mission Launcher
# 1. Authorizes X11 Display & Cleans up old sessions
# 2. Launches Window 1: Native Gazebo Harmonic GUI + PX4 SITL (x500_mono_cam)
# 3. Launches Window 2: Native QGroundControl GCS (UDP 14550)
# 4. Launches Window 3: Live OpenCV 30 FPS Camera Viewer with PyTorch CUDA AI
# 5. Executes the Autonomous 360-Degree Defect Inspection Flight
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "======================================================================"
echo "  INFYNEX - All-in-One Autonomous Infrastructure Inspection Launcher"
echo "======================================================================"

# 1. Clean up old containers, sockets, and orphaned shared memory
echo "[1/5] Resetting environment and configuring X11 display authorization..."
docker rm -f infynex_px4_gui infynex_camera_gui infynex_qgc_gui 2>/dev/null || true
pkill -9 -f "QGroundControl|ros_gz_bridge|view_camera_opencv|fly_360_inspection|manual_teleop" 2>/dev/null || true
for id in $(ipcs -m 2>/dev/null | awk '$6 == 0 {print $2}'); do ipcrm -m "$id" 2>/dev/null || true; done
rm -rf /tmp/qtsingleapp* /tmp/runtime-ubuntu 2>/dev/null || true

# Authorize X11 Display for Docker
xhost +local:root >/dev/null 2>&1 || true
xhost +local:docker >/dev/null 2>&1 || true
xhost + >/dev/null 2>&1 || true
export DISPLAY=${DISPLAY:-:0}

# Trap to cleanly terminate all windows on Ctrl+C
cleanup() {
    echo -e "\n[Shutdown] Stopping all simulation windows and containers..."
    docker rm -f infynex_px4_gui infynex_camera_gui infynex_qgc_gui 2>/dev/null || true
    pkill -9 -f "QGroundControl|ros_gz_bridge|view_camera_opencv|fly_360_inspection" 2>/dev/null || true
    kill $(jobs -p) 2>/dev/null || true
    echo "[Shutdown] All INFYNEX simulation processes stopped cleanly."
}
trap cleanup EXIT INT TERM

# 2. Launch Window 1: Gazebo Harmonic GUI + PX4 SITL
echo -e "\n--> [2/5] Launching Window 1: Gazebo Harmonic 3D World & PX4 SITL..."
bash scripts/run_px4_gazebo_gui.sh &
PID_PX4=$!

# Wait for Gazebo Harmonic & PX4 to initialize simulation world and open MAVLink
echo "[Startup] Waiting 12 seconds for Gazebo physics & PX4 SITL MAVLink to initialize..."
sleep 12

# 3. Launch Window 2: Native QGroundControl GCS
echo -e "\n--> [3/5] Launching Window 2: Native QGroundControl GCS..."
bash scripts/run_qgroundcontrol.sh &
PID_QGC=$!

sleep 3

# 4. Launch Window 3: Real Live Camera Feed with PyTorch CUDA AI Damage Segmentation
echo -e "\n--> [4/5] Launching Window 3: Live RGB Camera Stream with PyTorch AI Viewer..."
bash scripts/run_opencv_camera_view.sh &
PID_CAM=$!

echo "[Startup] Waiting 6 seconds for ROS 2 camera bridge & AI models to warm up on RTX 3050..."
sleep 6

# 5. Launch the Autonomous 360-Degree Defect Inspection Flight
echo -e "\n======================================================================"
echo "--> [5/5] Executing Autonomous 360-Degree Defect Inspection Tour..."
echo "======================================================================"
bash scripts/start_360_inspection_flight.sh

echo -e "\n======================================================================"
echo "  ✓ 360-DEGREE DEFECT INSPECTION COMPLETED SUCCESSFULLY!"
echo "  All 3 native windows (Gazebo Sim, QGroundControl, OpenCV AI Viewer)"
echo "  remain open for post-flight inspection review."
echo "  Press Ctrl+C in this terminal when you wish to close the simulation."
echo "======================================================================"

# Wait for user to exit with Ctrl+C
wait
