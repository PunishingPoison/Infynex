# INFYNEX API and Communication Specification

## 1. ROS 2 Topics

| Topic | Type | Source | Purpose |
| :--- | :--- | :--- | :--- |
| `/fmu/out/vehicle_odometry` | `px4_msgs/msg/VehicleOdometry` | PX4 SITL | Drone position, orientation, velocity |
| `/fmu/out/vehicle_status` | `px4_msgs/msg/VehicleStatus` | PX4 SITL | Arming state, flight mode, nav state |
| `/fmu/in/trajectory_setpoint` | `px4_msgs/msg/TrajectorySetpoint` | Mission Controller | Waypoint target coordinates & yaw |
| `/fmu/in/offboard_control_mode`| `px4_msgs/msg/OffboardControlMode` | Mission Controller | Offboard heartbeat |
| `/fmu/in/vehicle_command` | `px4_msgs/msg/VehicleCommand` | Mission Controller | Arm, disarm, takeoff, land commands |
| `/infynex/camera/image_raw` | `sensor_msgs/msg/Image` | Gazebo RGB Camera | High-resolution camera feed (1280x720) |
| `/infynex/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Gazebo RGB Camera | Optical intrinsic parameters |
| `/infynex/drone/telemetry` | `infynex_msgs/msg/DroneTelemetry` | Bridge Node | Consolidated drone state |
| `/infynex/inspection/detections`| `infynex_msgs/msg/DamageDetection`| AI Engine | Real-time defect bounding boxes & coordinates |

## 2. MQTT Topic Hierarchy

All sensor telemetry uses standard JSON payloads with ISO-8601 UTC timestamps.

### Topic Structure
- `infynex/sensors/{node_id}/telemetry`: Periodic sensor readings
- `infynex/sensors/{node_id}/status`: Node connectivity heartbeat (`online`, `offline`, `fault`)
- `infynex/sensors/command/{node_id}`: Over-the-air sampling rate configuration

### Payload Examples

#### Temperature Node (DS18B20)
```json
{
  "node_id": "ESP32_001",
  "sensor_model": "DS18B20",
  "location": "front_wall_pillar_1",
  "temperature_c": 31.45,
  "timestamp": "2026-11-24T10:30:00.125Z",
  "battery_voltage": 3.28,
  "status": "normal"
}
```

#### Environmental Node (BME280)
```json
{
  "node_id": "ESP32_003",
  "sensor_model": "BME280",
  "location": "foundation_anchor_south",
  "temperature_c": 29.80,
  "humidity_percent": 68.4,
  "pressure_hpa": 1012.35,
  "timestamp": "2026-11-24T10:30:00.150Z",
  "battery_voltage": 3.30,
  "status": "normal"
}
```

## 3. Backend REST & WebSocket Endpoints

### REST Endpoints
- `GET /api/v1/health`: Service health check.
- `GET /api/v1/missions`: List all historical and active inspection missions.
- `POST /api/v1/missions`: Create a new inspection mission.
- `GET /api/v1/missions/{mission_id}`: Detailed mission telemetry and detections.
- `POST /api/v1/missions/{mission_id}/start`: Start drone inspection flight.
- `POST /api/v1/missions/{mission_id}/abort`: Emergency RTL / Land.
- `GET /api/v1/damages`: Query all detected structural damages with filters.
- `GET /api/v1/sensors/live`: Latest readings from all active ESP32 nodes.
- `GET /api/v1/network/metrics`: Real-time 5G network performance metrics.
- `POST /api/v1/network/scenario`: Set active 5G emulation profile.
- `GET /api/v1/reports/{mission_id}/pdf`: Generate and download PDF report.

### WebSocket Feeds
- `ws://{host}:8000/ws/telemetry`: High-frequency drone position, orientation, battery, and speed.
- `ws://{host}:8000/ws/sensors`: Multi-node IoT sensor stream.
- `ws://{host}:8000/ws/detections`: Instant notification of new AI damage findings with 3D coordinate pins.
- `ws://{host}:8000/ws/network`: Live 5G latency, throughput, and packet loss stream.
