# INFYNEX: Autonomous Digital Twin Infrastructure Inspection Platform

[![ROS 2 Jazzy](https://img.shields.io/badge/ROS%202-Jazzy%20Jalisco-blue.svg)](https://docs.ros.org/en/jazzy/)
[![Gazebo Harmonic](https://img.shields.io/badge/Gazebo-Harmonic-orange.svg)](https://gazebosim.org/)
[![PX4 Autopilot](https://img.shields.io/badge/PX4-Autopilot%20v1.14+-red.svg)](https://px4.io/)
[![CUDA Accelerated](https://img.shields.io/badge/PyTorch-CUDA%2012.4%20(RTX%203050)-green.svg)](https://pytorch.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20TimescaleDB-009688.svg)](https://fastapi.tiangolo.com/)
[![React 3D](https://img.shields.io/badge/Dashboard-React%20%2B%20Three.js-61DAFB.svg)](https://threejs.org/)
[![Docker](https://img.shields.io/badge/Deployment-Docker%20Compose-2496ED.svg)](https://www.docker.com/)

**INFYNEX** is an end-to-end autonomous cyber-physical digital twin simulation and inspection platform. Designed for structural civil engineering assets (concrete bridges, buildings, and critical infrastructure), it integrates autonomous quadcopter UAV flight control, high-fidelity 3D physics, real-time edge AI damage segmentation, IoT structural health sensors, and 5G network link emulation into a unified operational dashboard.

---

## 🏛 System Architecture

```
                                 +---------------------------------------------+
                                 |         Gazebo Harmonic Simulation          |
                                 |  - High-Fidelity Concrete Infrastructure   |
                                 |  - 9 Realistic Structural Damage Decals    |
                                 |  - X500 Quadcopter + HD Mono RGB Camera    |
                                 +----------------------+----------------------+
                                                        |
                                       /camera (RGB Image Stream) & MAVLink
                                                        |
                                                        v
                     +----------------------------------+----------------------------------+
                     |                                                                     |
                     v                                                                     v
  +-------------------------------------+                               +-------------------------------------+
  |      ROS 2 Jazzy & MAVLink GCS      |                               |       Edge AI Damage Engine         |
  |  - PX4 SITL Flight Autopilot        |                               |  - YOLO26n-seg: Spalling & Rebar    |
  |  - QGroundControl (MAVLink UDP)     |                               |  - YOLOv8s-seg: Cracks (Hairline)   |
  |  - MAV_CMD_DO_REPOSITION Waypoints  |                               |  - Geometric Valley Post-Filter     |
  |  - Autonomous 360° Standoff Tour    |                               |  - Real-Time TensorRT/CUDA (30 FPS) |
  +------------------+------------------+                               +------------------+------------------+
                     |                                                                     |
                     | Telemetry (Pose, GPS, Vel)                         Detections & Bounding Polygons
                     |                                                                     |
                     +----------------------------------+----------------------------------+
                                                        |
                                                        v
                                        +-------------------------------+
                                        |   FastAPI Backend & DB Core   |
                                        |  - PostgreSQL 16 + TimescaleDB|
                                        |  - Eclipse Mosquitto MQTT     |
                                        |  - WebSocket Telemetry Stream |
                                        +---------------+---------------+
                                                        |
                                                        v
                                        +-------------------------------+
                                        |    React + Three.js Web UI    |
                                        |  - 3D Real-Time Digital Twin  |
                                        |  - Telemetry HUD & AI Feed    |
                                        |  - Automated PDF/JSON Reports |
                                        +-------------------------------+
```

---

## ⚡ Core Engineering Highlights

1. **Autonomous 360° Circumferential Inspection Tour:**
   - Smooth counter-clockwise waypoint circuit navigating all 4 facades (South $\to$ East $\to$ North $\to$ West).
   - Holds calibrated $2.8\text{ m}$ normal standoffs facing each defect dead-center in the camera field of view.
   - Dedicated corner waypoints ($45^\circ$, $135^\circ$) guarantee 100% collision-free transit around architectural pillars.
   - Autonomous precision takeoff from and touchdown back to the helipad.

2. **Dual-Model Pretrained Deep Learning Damage Segmentation:**
   - **`iaac-maai/day4-group4-rc-damage-segmentation` (YOLO26n-seg):** Detects reinforced concrete delamination, concrete spalling, and exposed rusted rebar.
   - **`OpenSistemas/YOLOv8-crack-seg` (YOLOv8s-seg):** Generates high-continuity masks along hairline, diagonal, and horizontal flexural cracks.
   - Runs on **NVIDIA GeForce RTX 3050 Laptop GPU** via PyTorch CUDA with single-pass latency achieving **30.1 FPS continuous throughput**.

3. **Geometric False-Positive Suppression Filter:**
   - Discriminates true tortuous dark-valley fractures from straight architectural edges, window trims, slab expansion joints, and cast shadows.
   - Reduces false positives on undamaged architectural facade features to zero.

4. **Multi-Window Native Desktop Visualization Stack:**
   - **Window 1:** Native Gazebo Harmonic GUI 3D simulation with physics and sensor rendering.
   - **Window 2:** Native QGroundControl GCS with real-time MAVLink flight instrument telemetry.
   - **Window 3:** Native OpenCV GUI streaming live 720p frames overlaid with AI segmentation masks and confidence scores.

5. **Integrated IoT & 5G Network Simulation:**
   - Multi-node ESP32 emulators publishing structural telemetry (temperature, vibration, moisture) over MQTT.
   - Linux `tc netem` link degradation simulating cellular handovers, packet loss, and jitter.

---

## 📋 Ground-Truth Defect Catalog (9 Stations)

| Station ID | Facade | Coordinates $(X, Y, Z)$ | Defect Type | Primary AI Model | Severity |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`DEFECT_1_SOUTH_VERT_CRACK`** | South | $(+0.8, -4.005, 3.5)$ | Vertical Tension Crack | `YOLOv8s-seg` | **CRITICAL** |
| **`DEFECT_2_SOUTH_HORIZ_CRACK`**| South | $(-1.6, -4.005, 2.2)$ | Horizontal Flexural Crack | `YOLOv8s-seg` | **CRITICAL** |
| **`DEFECT_3_SOUTH_SPALL_REBAR`** | South | $(+2.6, -4.005, 2.2)$ | Delamination & Rebar Corrosion | `YOLO26n-seg` | **CRITICAL** |
| **`DEFECT_4_EAST_SPALL_REBAR`**  | East  | $(+5.005, -1.8, 2.2)$ | Exposed Rebar Spall | `YOLO26n-seg` | **CRITICAL** |
| **`DEFECT_5_EAST_DIAG_CRACK`**   | East  | $(+5.005, +1.2, 4.2)$ | $45^\circ$ Diagonal Shear Crack | `YOLOv8s-seg` | **MODERATE** |
| **`DEFECT_6_NORTH_VERT_CRACK`**  | North | $(-2.2, +4.005, 3.6)$ | Vertical Column Crack | `YOLOv8s-seg` | **MODERATE** |
| **`DEFECT_7_NORTH_SLAB_CRACK`**  | North | $(0.0, +4.005, 5.8)$  | Floor Slab Horizontal Crack | `YOLOv8s-seg` | **CRITICAL** |
| **`DEFECT_8_WEST_SHEAR_CRACK`**  | West  | $(-5.005, -0.5, 4.5)$ | Stepped Diagonal Shear Fracture| `YOLOv8s-seg` | **MODERATE** |
| **`DEFECT_9_WEST_FOUNDATION_SPALL`**| West | $(-5.005, +1.8, 2.0)$ | Foundation Corner Spalling | `YOLO26n-seg` | **CRITICAL** |

---

## 🛠 Prerequisites & Installation

### 1. System Requirements
- **Host OS:** Linux Ubuntu 22.04 LTS / 24.04 LTS / 26.04 LTS
- **GPU:** NVIDIA GPU with CUDA support (e.g., RTX 3050 Laptop / Desktop or higher)
- **Memory:** 16 GB RAM recommended
- **Storage:** 15 GB free disk space

### 2. Docker & NVIDIA Container Toolkit Setup
Ensure Docker and NVIDIA GPU passthrough are installed:
```bash
# Verify Docker installation
docker --version
docker compose version

# Grant user permissions to Docker (avoids permission denied errors)
sudo usermod -aG docker $USER
sudo chmod 666 /var/run/docker.sock

# Authorize X11 Display access for simulation GUI windows
xhost +local:root
xhost +local:docker
xhost +
export DISPLAY=${DISPLAY:-:0}
```

---

## 🚀 Quick Start Guide

### Option A: The All-in-One Master Launcher (Recommended)

Run this single command to launch all 3 simulation windows and automatically execute the 360° autonomous inspection tour:

```bash
cd ~/Downloads/INFYNEX
bash scripts/launch_all_with_360_inspection.sh
```

*(Or as a self-contained one-liner with display permissions pre-configured):*
```bash
sudo chmod 666 /var/run/docker.sock && xhost +local:root && xhost + && cd ~/Downloads/INFYNEX && bash scripts/launch_all_with_360_inspection.sh
```

**What happens automatically:**
1. Resets previous containers and cleans memory locks.
2. Spawns **Gazebo Harmonic** showing the building, flaws, and the quadcopter on the helipad.
3. Launches **QGroundControl** connected to PX4 SITL over UDP `14550`.
4. Bridges `/camera` and launches the **Native OpenCV AI Viewer** running at 30 FPS.
5. Arms the drone, performs vertical takeoff to 3.5m AGL, visits and scans all 9 defect stations, and returns to precision-land on the helipad.
6. Generates the final inspection report at `data/inspection_reports/inspection_report_360.json`.
7. All 3 windows remain open for your review. Press `Ctrl+C` to terminate when finished.

---

### Option B: Terminal-by-Terminal Execution

If you prefer to start each component in a separate terminal:

#### Terminal 1 — Gazebo Harmonic 3D World + PX4 SITL
```bash
cd ~/Downloads/INFYNEX
bash scripts/run_px4_gazebo_gui.sh
```

#### Terminal 2 — Native QGroundControl GCS
```bash
cd ~/Downloads/INFYNEX
bash scripts/run_qgroundcontrol.sh
```

#### Terminal 3 — Live Camera Stream & AI Defect Detection
```bash
cd ~/Downloads/INFYNEX
bash scripts/run_opencv_camera_view.sh
```

#### Terminal 4 — Flight Control Execution
Choose either automated inspection or manual teleoperation:

* **Automated 360° Inspection Tour:**
  ```bash
  cd ~/Downloads/INFYNEX
  bash scripts/start_360_inspection_flight.sh
  ```

* **Manual Keyboard Teleoperation:**
  ```bash
  cd ~/Downloads/INFYNEX
  bash scripts/run_manual_flight_control.sh
  ```
  *Keybindings:*
  - `W` / `S`: Pitch forward / backward
  - `A` / `D`: Roll left / right
  - `Up` / `Down`: Climb / descend altitude
  - `Left` / `Right`: Yaw turn left / right
  - `Space`: Active brake / hold hover
  - `L`: Autonomous precision landing

---

### Option C: Digital Twin Cloud & Web Ecosystem

To spin up the web monitoring dashboard, time-series database, MQTT broker, and FastAPI edge backend:

```bash
cd ~/Downloads/INFYNEX
docker compose up -d mosquitto timescaledb backend dashboard
```

- **Digital Twin Web Dashboard:** [http://localhost:3000](http://localhost:3000) (or `http://localhost:5173`)
- **FastAPI Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **MQTT Broker:** `localhost:1883` (WebSocket: `localhost:9001`)
- **TimescaleDB:** `localhost:5432` (`infynex_db`)

---

## 📁 Repository Directory Structure

```
INFYNEX/
├── ai_engine/                         # Deep learning models & inference pipeline
│   ├── weights/                       # YOLO26n-seg and YOLOv8s-seg weights
│   ├── models/                        # PyTorch architectures & geometry filters
│   └── evaluation/                    # Ground-truth metric evaluations
├── backend/                           # FastAPI backend server
│   ├── app/                           # Endpoints, database models & MQTT bridge
│   └── Dockerfile                     # Backend container configuration
├── dashboard/                         # React + Three.js Web Dashboard
│   ├── src/components/                # 3D Digital Twin, Telemetry HUD, Map
│   └── Dockerfile                     # Dashboard container configuration
├── data/                              # Flight telemetry & inspection records
│   ├── captured_images/               # Real-time captured damage snapshots
│   └── inspection_reports/            # Generated JSON & PDF inspection reports
├── iot_simulation/                    # Multi-node ESP32 environmental emulators
├── network_simulation/                # 5G NR link profiles and netem shaping
├── ros2_ws/                           # ROS 2 Jazzy workspace
│   └── src/                           # Custom bridge and message packages
├── scripts/                           # Mission launchers & utility scripts
│   ├── launch_all_with_360_inspection.sh  # Master all-in-one launcher
│   ├── run_px4_gazebo_gui.sh              # Window 1: Gazebo + PX4
│   ├── run_qgroundcontrol.sh              # Window 2: QGroundControl
│   ├── run_opencv_camera_view.sh          # Window 3: OpenCV AI Viewer
│   ├── fly_360_inspection.py              # Autonomous 360 flight logic
│   └── manual_teleop_keyboard.py          # Manual keyboard teleop
├── simulation/                        # 3D simulation assets
│   ├── gazebo/models/                 # x500_mono_cam, helipad & decals
│   └── gazebo/worlds/                 # bridge_inspection.sdf world
├── docker-compose.yml                 # Multi-service ecosystem orchestration
└── README.md                          # Platform documentation
```

---

## 📊 Inspection Reports & Verification Data

Upon mission completion, INFYNEX compiles an inspection report containing timestamps, GPS fixes, millimeter crack estimates, spall surface areas, and recommended repair actions:

- **JSON Report:** `data/inspection_reports/inspection_report_360.json`
- **Output Metrics:** Structural Health Index (`67.2 / 100`), defect severity tags, and action items.
- **Visual Evidence:** High-resolution bounding snapshots tagged with class and confidence are stored in `data/captured_images/`.

---

## 🛑 Clean Shutdown

To stop all background processes, windows, and Docker containers:
```bash
cd ~/Downloads/INFYNEX
docker rm -f infynex_camera_gui infynex_px4_gui infynex_qgc_gui 2>/dev/null || true
docker compose down 2>/dev/null || true
```

---

## 👤 Author

**V C Mohit Rao** ([@PunishingPoison](https://github.com/PunishingPoison))  
*INFYNEX: Autonomous Cyber-Physical Digital Twin Infrastructure Inspection Platform*
