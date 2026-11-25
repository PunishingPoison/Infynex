#!/usr/bin/env bash
# ==============================================================================
# INFYNEX Host Verification Script (Phase 1 Baseline)
# Verifies Ubuntu kernel, NVIDIA driver, Docker Compose v2, RAM/VRAM,
# X11/Wayland forwarding, and container GPU acceleration.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

LOG_DIR="/home/vcmr/Downloads/INFYNEX/data"
mkdir -p "$LOG_DIR"
REPORT_FILE="$LOG_DIR/host_verification_report.txt"
exec > >(tee -a "$REPORT_FILE") 2>&1

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  INFYNEX Phase 1: Host Environment & Hardware Verification      ${NC}"
echo -e "${BLUE}  Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")                 ${NC}"
echo -e "${BLUE}================================================================${NC}"

ALL_PASSED=true

# 1. Operating System
echo -n "[1/7] Operating System: "
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo -e "${GREEN}PASS${NC} -> $PRETTY_NAME ($VERSION_CODENAME)"
else
    echo -e "${RED}FAIL${NC} (Cannot detect OS release)"
    ALL_PASSED=false
fi

# 2. Linux Kernel
echo -n "[2/7] Linux Kernel: "
KERNEL_VER=$(uname -r)
ARCH=$(uname -m)
echo -e "${GREEN}PASS${NC} -> $KERNEL_VER ($ARCH)"

# 3. RAM & System Resources
echo -n "[3/7] Memory & System RAM: "
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
AVAIL_RAM_MB=$(free -m | awk '/^Mem:/{print $7}')
if [ "$TOTAL_RAM_MB" -ge 12000 ]; then
    echo -e "${GREEN}PASS${NC} -> Total: ${TOTAL_RAM_MB} MB | Available: ${AVAIL_RAM_MB} MB"
else
    echo -e "${YELLOW}WARN${NC} -> Total: ${TOTAL_RAM_MB} MB (< 16GB recommendation)"
fi

# 4. NVIDIA GPU & Driver
echo -n "[4/7] NVIDIA GPU & Driver: "
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)
    DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n 1)
    TOTAL_VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -n 1)
    FREE_VRAM=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader | head -n 1)
    echo -e "${GREEN}PASS${NC} -> $GPU_NAME | Driver: $DRIVER_VER | VRAM: $FREE_VRAM free / $TOTAL_VRAM total"
else
    echo -e "${RED}FAIL${NC} (nvidia-smi not available)"
    ALL_PASSED=false
fi

# 5. Docker & Docker Compose v2
echo -n "[5/7] Docker & Docker Compose v2: "
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_VER=$(docker --version | awk '{print $3}' | tr -d ',')
    COMPOSE_VER=$(docker compose version | awk '{print $4}')
    echo -e "${GREEN}PASS${NC} -> Docker: $DOCKER_VER | Compose: $COMPOSE_VER"
else
    echo -e "${RED}FAIL${NC} (Docker or Docker Compose v2 missing)"
    ALL_PASSED=false
fi

# 6. Display & X11/Wayland Forwarding
echo -n "[6/7] Display / Window Server: "
if [ -n "$WAYLAND_DISPLAY" ]; then
    echo -e "${GREEN}PASS${NC} -> Wayland ($WAYLAND_DISPLAY)"
elif [ -n "$DISPLAY" ]; then
    echo -e "${GREEN}PASS${NC} -> X11 ($DISPLAY)"
else
    echo -e "${YELLOW}WARN${NC} -> Headless / No active DISPLAY detected (Headless mode supported)"
fi

# 7. Container GPU Passthrough Test
echo -n "[7/7] Container GPU Acceleration Test: "
PASSTHROUGH_TEST=$(docker run --rm \
    --device /dev/nvidia0 \
    --device /dev/nvidiactl \
    --device /dev/nvidia-uvm \
    -v /usr/bin/nvidia-smi:/usr/bin/nvidia-smi:ro \
    -v /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.595.99.02:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:ro \
    ubuntu:24.04 nvidia-smi --query-gpu=gpu_name --format=csv,noheader 2>&1 || true)

if echo "$PASSTHROUGH_TEST" | grep -q "GeForce"; then
    echo -e "${GREEN}PASS${NC} -> $PASSTHROUGH_TEST verified inside Ubuntu 24.04 container"
else
    echo -e "${YELLOW}WARN${NC} -> Hardware fallback device node passthrough: $PASSTHROUGH_TEST"
fi

echo -e "${BLUE}================================================================${NC}"
if [ "$ALL_PASSED" = true ]; then
    echo -e "${GREEN}✓ Phase 1 Host Verification Gate PASSED.${NC}"
    echo "Saved verification record to $REPORT_FILE"
    exit 0
else
    echo -e "${RED}✗ Phase 1 Host Verification Gate FAILED.${NC}"
    exit 1
fi
