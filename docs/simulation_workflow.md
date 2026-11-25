# INFYNEX Simulation Workflow

## End-to-End Mission Workflow

The INFYNEX digital twin executes inspections according to a standardized automated sequence:

```
[Phase 1: Mission Initialization]
        |
        v
[1. Pre-flight Checks: GPS lock, Battery >= 95%, Sensors Active, 5G Uplink OK]
        |
        v
[Phase 2: Autonomous Flight Execution]
        |
        v
[2. Takeoff to 2.5m AGL -> Transition to Offboard Waypoint Mode]
        |
        v
[3. Traverse Inspection Waypoints (W1 -> W8 along Structure Facades)]
        |
        v
[Phase 3: Sensor Data Acquisition & Edge Transmission]
        |
        +---> [RGB Camera captures 1280x720 frames at structural waypoints]
        +---> [Simulated 5G Network introduces latency/jitter/loss constraints]
        +---> [ESP32 Emulators publish structural & ambient metrics via MQTT]
        |
        v
[Phase 4: Real-time Edge AI Inference & Localisation]
        |
        +---> [Preprocess frame: resize, normalize, contrast enhancement]
        +---> [Inference: Detect cracks and spalling with bounding boxes/masks]
        +---> [Localisation: Raycast camera optical ray against 3D facade model]
        +---> [Register Damage ID, Category, Severity, and 3D Coordinates]
        |
        v
[Phase 5: Digital Twin Synchronization & Alerting]
        |
        +---> [FastAPI persists inspection telemetry & detections to TimescaleDB]
        +---> [WebSocket broadcasts drone position, damage markers, and IoT metrics]
        +---> [Three.js Dashboard renders 3D digital twin with interactive pins]
        |
        v
[Phase 6: Mission Conclusion & Report Export]
        |
        v
[4. RTL (Return to Launch) -> Precision Autonomous Landing]
        |
        v
[5. Generate Comprehensive Inspection Report with Damage Analytics (PDF)]
```

## Waypoint Profiles

| Waypoint | X (m) | Y (m) | Z (m) | Yaw (deg) | Inspection Target |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **W1 (Takeoff)** | 0.0 | 0.0 | 2.5 | 0° | Ascend to survey altitude |
| **W2 (Approach)**| 2.0 | 0.0 | 2.5 | 0° | Approach front facade |
| **W3 (Front Wall)**| 4.0 | -2.0 | 3.0 | 90° | Inspect front concrete wall & pillar |
| **W4 (Corner Right)**| 6.0 | 0.0 | 3.0 | 0° | Corner inspection |
| **W5 (Right Wall)**| 6.0 | 3.0 | 3.5 | 270° | Inspect right facade & beam joints |
| **W6 (Rear Wall)** | 4.0 | 5.0 | 3.5 | 180° | Inspect rear surface |
| **W7 (Left Wall)** | 1.0 | 3.0 | 3.0 | 90° | Inspect left facade |
| **W8 (Alignment)** | 1.0 | 0.0 | 2.5 | 0° | Align with home landing zone |
| **W9 (Land)** | 0.0 | 0.0 | 0.0 | 0° | Final touchdown & disarm |
