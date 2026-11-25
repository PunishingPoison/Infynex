#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "  INFYNEX - Environment Setup and Verification Script"
echo "  Ubuntu 26.04 Host | Ubuntu 24.04 Simulation Container"
echo "=========================================================="

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"

# 1. Check Docker Availability
echo "[Setup] Checking Docker and Docker Compose..."
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed or not in PATH."
    exit 1
fi
echo "✓ Docker: $(docker --version)"
echo "✓ Docker Compose: $(docker compose version)"

# 2. Check NVIDIA GPU
echo "[Setup] Checking GPU and NVIDIA drivers..."
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1)
    echo "✓ GPU Detected: ${GPU_NAME} (Driver: ${DRIVER_VER})"
else
    echo "⚠ Warning: nvidia-smi not found. Simulation will use CPU/Mesa software rendering."
fi

# 3. Create Required Runtime Directories
echo "[Setup] Ensuring data directories exist..."
mkdir -p data/captured_images data/detections data/sensor_logs data/telemetry data/network_logs

# 4. Copy Environment Template if not exists
if [ ! -f .env ]; then
    echo "[Setup] Creating .env from .env.example..."
    cp .env.example .env
fi

# 5. Build Simulation Docker Container
echo "[Setup] Building PX4 SITL & ROS 2 Jazzy container..."
docker build -t infynex-px4-sitl:jazzy -f simulation/docker/px4.Dockerfile simulation/docker/

echo "=========================================================="
echo "  INFYNEX Setup Completed Successfully!"
echo "=========================================================="
