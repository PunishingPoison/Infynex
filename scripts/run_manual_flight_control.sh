#!/usr/bin/env bash
# ==============================================================================
# INFYNEX: Manual Interactive Keyboard Drone Flight Cockpit
# ==============================================================================
set -e

echo "======================================================================"
echo "  INFYNEX - Manual Keyboard Drone Cockpit (WASD + Space/Z + Q/E)"
echo "  Connecting to PX4 SITL on MAVLink UDP 14540..."
echo "======================================================================"

docker run -it --rm \
  --network host \
  --ipc host \
  -v "$PWD":/workspace \
  -w /workspace \
  infynex-px4-sitl:jazzy python3 scripts/manual_teleop_keyboard.py
