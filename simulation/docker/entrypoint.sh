#!/bin/bash
set -e

# Source ROS 2 setup
source /opt/ros/jazzy/setup.bash

echo "=========================================================="
echo "  INFYNEX - PX4 SITL & Gazebo Harmonic Simulation Service"
echo "  ROS 2: Jazzy | Gazebo: Harmonic | Model: x500"
echo "=========================================================="

MODE="${1:-headless}"

if [ "$MODE" = "headless" ]; then
    echo "[INFYNEX] Launching PX4 SITL with Gazebo Harmonic (HEADLESS mode)..."
    export HEADLESS=1
    cd /opt/PX4-Autopilot
    exec make px4_sitl gz_x500

elif [ "$MODE" = "gui" ]; then
    echo "[INFYNEX] Launching PX4 SITL with Gazebo Harmonic (GUI mode)..."
    export HEADLESS=0
    cd /opt/PX4-Autopilot
    exec make px4_sitl gz_x500

elif [ "$MODE" = "test-flight" ]; then
    echo "[INFYNEX] Launching Gazebo Harmonic and PX4 SITL for flight verification..."
    export HEADLESS=1
    export GZ_SIM_RESOURCE_PATH="/opt/PX4-Autopilot/Tools/simulation/gz/models:/opt/PX4-Autopilot/Tools/simulation/gz/worlds"
    
    # Start Gazebo Harmonic headless server
    echo "[INFYNEX] Starting Gazebo Harmonic server..."
    gz sim -s -r /opt/PX4-Autopilot/Tools/simulation/gz/worlds/default.sdf > /tmp/gz_sim.log 2>&1 &
    GZ_PID=$!

    # Wait for Gazebo service to become ready
    echo "[INFYNEX] Waiting for Gazebo world to load..."
    for i in {1..20}; do
        if gz service -l 2>/dev/null | grep -q "/world/default/create"; then
            echo "[INFYNEX] Gazebo ready after ${i}s"
            break
        fi
        sleep 1
    done

    # Start Micro-XRCE-DDS Agent
    echo "[INFYNEX] Starting Micro-XRCE-DDS Agent on UDP:8888..."
    MicroXRCEAgent udp4 -p 8888 > /tmp/micro_xrce.log 2>&1 &
    XRCE_PID=$!

    # Start PX4 SITL
    echo "[INFYNEX] Starting PX4 SITL firmware with Gazebo Harmonic integration..."
    cd /opt/PX4-Autopilot/build/px4_sitl_default
    rm -f parameters.bson*
    export PX4_SIM_MODEL=gz_x500
    export PX4_GZ_WORLD=default
    export PX4_GZ_MODEL=x500
    ./bin/px4 etc -s etc/init.d-posix/rcS > /tmp/px4_sitl.log 2>&1 &
    PX4_PID=$!
    echo "[INFYNEX] PX4 SITL started with PID: $PX4_PID"

    # Wait for PX4 MAVLink port to initialize
    echo "[INFYNEX] Waiting for PX4 MAVLink telemetry stream..."
    for i in {1..20}; do
        if ss -u -a -n 2>/dev/null | grep -E -q ":14540|:14580"; then
            echo "[INFYNEX] MAVLink telemetry ready after ${i}s"
            break
        fi
        sleep 1
    done
    sleep 2

    if [ -f /workspace/ros2_ws/install/setup.bash ]; then
        source /workspace/ros2_ws/install/setup.bash
    fi

    # Run flight verification test
    if [ -f /workspace/simulation/drone/verify_phase1_baseline.py ]; then
        python3 /workspace/simulation/drone/verify_phase1_baseline.py
        TEST_EXIT=$?
    else
        python3 /workspace/simulation/drone/test_flight.py
        TEST_EXIT=$?
    fi

    echo "[INFYNEX] Test completed with exit code: $TEST_EXIT"
    kill -9 $PX4_PID $GZ_PID $XRCE_PID 2>/dev/null || true
    exit $TEST_EXIT

elif [ "$MODE" = "agent" ]; then
    echo "[INFYNEX] Starting Micro-XRCE-DDS Agent..."
    exec MicroXRCEAgent udp4 -p 8888

else
    echo "[INFYNEX] Executing custom command: $@"
    exec "$@"
fi
