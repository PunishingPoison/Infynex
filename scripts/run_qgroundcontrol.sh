#!/usr/bin/env bash
# ==============================================================================
# INFYNEX Window 2: Native QGroundControl Ground Control Station
# ==============================================================================
set -e

echo "=== [Window 2] Launching QGroundControl GCS ==="
echo "Connecting to PX4 SITL via MAVLink UDP 14550..."

export DISPLAY=${DISPLAY:-:0}
xhost + >/dev/null 2>&1 || true

# 1. Clean up any previous container or dangling processes
docker rm -f infynex_qgc_gui 2>/dev/null || true
pkill -9 -f /qgc/QGroundControl 2>/dev/null || true

# 2. Clear orphaned Qt/QGC shared memory segments (nattch == 0) from host kernel
for id in $(ipcs -m 2>/dev/null | awk '$6 == 0 {print $2}'); do
  ipcrm -m "$id" 2>/dev/null || true
done
rm -rf /tmp/qtsingleapp* /tmp/runtime-ubuntu 2>/dev/null || true

# 3. Run QGroundControl GUI with display passthrough as non-root user 'ubuntu'
docker run --rm \
  --name infynex_qgc_gui \
  --network host \
  --ipc host \
  --privileged \
  -e DISPLAY="$DISPLAY" \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -e QT_X11_NO_MITSHM=1 \
  -v /home/vcmr/Downloads/squashfs-root:/qgc:ro \
  infynex-px4-sitl:jazzy bash -c "
    exec su - ubuntu -c 'DISPLAY=$DISPLAY /qgc/AppRun'
  "
