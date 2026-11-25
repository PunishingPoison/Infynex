# INFYNEX Installation and Setup Guide

## System Prerequisites
- **Host OS**: Ubuntu 26.04 LTS (x86_64)
- **CPU**: Multi-core Intel/AMD processor
- **GPU**: NVIDIA RTX 3050 (Driver >= 550 / 595.99)
- **RAM**: Minimum 16 GB
- **Disk**: 30+ GB free storage
- **Docker**: Version 24+ with Docker Compose v2+

## Architecture Decision: Ubuntu 24.04 Container for PX4 SITL
Because official PX4 SITL and ROS 2 Jazzy development toolchains are certified on Ubuntu 24.04 (Noble Numbat), the robotics simulation stack runs inside an optimized Ubuntu 24.04 container. Host Ubuntu 26.04 runs the AI inference engine, IoT emulators, backend, database, and dashboard natively.

## Step-by-Step Installation

### 1. Verify Docker and GPU Configuration
Verify that current user can run docker without root:
```bash
docker ps
```
Verify NVIDIA driver on host:
```bash
nvidia-smi
```

### 2. Configure Environment Variables
Copy the default environment template:
```bash
cp .env.example .env
```

### 3. Build the Simulation Docker Image
```bash
docker build -t infynex-px4-sitl:jazzy -f simulation/docker/px4.Dockerfile simulation/docker/
```

### 4. Start Infrastructure Services via Docker Compose
```bash
docker compose up -d mosquitto postgres timescaledb
```

### 5. Start Backend and Dashboard
Backend:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Dashboard:
```bash
cd dashboard
npm install
npm run dev
```
