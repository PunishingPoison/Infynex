#!/usr/bin/env bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"

echo "=========================================================="
echo "  Starting INFYNEX Digital Simulation Ecosystem"
echo "=========================================================="

MODE="${1:-headless}"

# 1. Start Support Services (Mosquitto MQTT, TimescaleDB, Backend, Dashboard)
echo "[Start] Starting Mosquitto MQTT, TimescaleDB, FastAPI Backend, and React Dashboard..."
docker compose up -d mosquitto timescaledb backend dashboard

# 2. Start PX4 SITL and Gazebo Simulation
echo "[Start] Starting PX4 SITL & Gazebo Harmonic container (${MODE} mode)..."
if [ "$MODE" = "gui" ]; then
    xhost +local:root 2>/dev/null || true
    PX4_HEADLESS=0 docker compose up px4-sitl
else
    PX4_HEADLESS=1 docker compose up -d px4-sitl
    echo "✓ PX4 SITL simulation running in background."
    echo "  Follow logs with: docker logs -f infynex_px4_sitl"
fi
