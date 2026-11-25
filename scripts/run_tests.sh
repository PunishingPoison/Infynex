#!/usr/bin/env bash
set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
cd "${PROJECT_ROOT}"

echo "=========================================================="
echo "  Running INFYNEX Automated Verification Suite"
echo "=========================================================="

# 1. Verify PX4 SITL Takeoff, Hover, and Landing
echo "[Test 1/3] Executing Phase 1 Flight Verification..."
docker run --rm \
    --network host \
    -v "${PROJECT_ROOT}:/workspace" \
    infynex-px4-sitl:jazzy test-flight

# 2. Run Subsystem Unit Tests
echo "[Test 2/3] Executing Subsystems Unit Test Suite..."
docker run --rm \
    -v "${PROJECT_ROOT}:/workspace" \
    -w /workspace \
    infynex-px4-sitl:jazzy python3 -m unittest discover -s /workspace/tests/unit -v

# 3. Run End-to-End Integration Scenario Tests (T1 - T10)
echo "[Test 3/3] Executing End-to-End Scenarios Integration Test Suite..."
docker run --rm \
    -v "${PROJECT_ROOT}:/workspace" \
    -w /workspace \
    infynex-px4-sitl:jazzy python3 -m unittest discover -s /workspace/tests/integration -v

echo "=========================================================="
echo "  Verification Suite Completed Successfully!"
echo "=========================================================="
