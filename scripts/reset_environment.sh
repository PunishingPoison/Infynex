#!/usr/bin/env bash

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"

echo "=========================================================="
echo "  Resetting INFYNEX Simulation Environment"
echo "=========================================================="

# Stop containers
docker compose down -v --remove-orphans

# Clear runtime logs and captured frames
echo "Cleaning runtime data..."
rm -rf data/captured_images/*
rm -rf data/detections/*
rm -rf data/sensor_logs/*
rm -rf data/telemetry/*
rm -rf data/network_logs/*

# Re-touch .gitkeep files
touch data/captured_images/.gitkeep
touch data/detections/.gitkeep
touch data/sensor_logs/.gitkeep
touch data/telemetry/.gitkeep
touch data/network_logs/.gitkeep

echo "✓ Environment successfully reset."
