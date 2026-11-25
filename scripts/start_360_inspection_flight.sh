#!/usr/bin/env bash
# ==============================================================================
# INFYNEX: Launch Autonomous 360-Degree Drone Inspection Mission
# ==============================================================================
set -e

echo "======================================================================"
echo "  INFYNEX - Autonomous 360-Degree Infrastructure Inspection Flight"
echo "  Connecting to PX4 SITL on MAVLink UDP 14540..."
echo "======================================================================"

docker run -i --rm \
  --network host \
  --ipc host \
  -v "$PWD":/workspace \
  -w /workspace \
  infynex-px4-sitl:jazzy python3 scripts/fly_360_inspection.py
