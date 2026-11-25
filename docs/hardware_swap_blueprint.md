# INFYNEX Physical Hardware Migration Blueprint
**Digital Simulation to Physical Drone, Raspberry Pi 5, ESP32 Fleet & 5G Modem Integration**

---

## 1. Executive Summary & Zero-Code-Change Architecture

INFYNEX was architected from inception around a strict boundary separation between the **Field Plane** (Sensors, Cameras, Drone Autopilot) and the **Edge/Cloud Processing Plane** (PyTorch AI Engine, 3D Mesh Localizer, TimescaleDB, and Web Dashboard).

Because all communications adhere to standardized, platform-agnostic wire protocols (**MicroXRCE-DDS**, **RTSP/MJPEG H.264**, **MQTT v3.1.1**, and **REST/WebSocket APIs**), **not a single line of downstream edge processing, AI inference, or dashboard code needs to be modified** when replacing simulated components with physical hardware.

```
       [ PHYSICAL FIELD PLANE ]                     [ 5G SA NETWORK ]              [ EDGE / CLOUD PLANE ]
 ┌──────────────────────────────────┐             ┌──────────────────┐           ┌────────────────────────┐
 │ Holybro Pixhawk 6C Autopilot     │             │                  │           │ NVIDIA Jetson Orin /   │
 │ (Telem1 -> RPi 5 MicroXRCEAgent) ├─────────┐   │ Quectel RM500Q   │           │ RTX Industrial PC      │
 ├──────────────────────────────────┤         │   │ 5G M.2 Modem     │           │                        │
 │ Raspberry Pi 5 + Sony IMX708 Cam │         ├──►│ (APN: infynex.sa)├──────────►│ • PyTorch AI Engine    │
 │ (Hardware H.264 RTSP Server)     │         │   │ IP: 10.45.0.2    │           │ • 3D Mesh Ray-Caster   │
 ├──────────────────────────────────┤         │   │                  │           │ • TimescaleDB Cluster  │
 │ 4x Physical ESP32-S3 Nodes       │         │   └──────────────────┘           │ • Mosquitto Broker     │
 │ (DS18B20, BME280, DHT22)         ├─────────┘                                  │ • FastAPI & WebSockets │
 └──────────────────────────────────┘                                            │ • Three.js Digital Twin│
                                                                                 └────────────────────────┘
```

---

## 2. Component-by-Component Hardware Replacement Guide

### Subsystem 1: PX4 Autopilot Hardware Swap
| Simulation Component | Physical Drop-in Replacement |
| :--- | :--- |
| `px4-sitl` Docker Container | Holybro Pixhawk 6C / CUAV v6X Flight Controller |
| Simulated Gazebo Physics | Hexacopter / Quadcopter Airframe with Carbon Fiber Props |
| Simulated MAVLink Bridge | Hardware Serial Telem1 port connected to Raspberry Pi 5 UART (`/dev/ttyAMA0`) |

#### Migration Steps:
1. Flash **PX4 Autopilot Firmware v1.15.x** onto the Pixhawk using QGroundControl.
2. In PX4 Parameters, configure:
   - `UXRCE_DDS_CFG = 101` (Telem 1)
   - `SER_TEL1_BAUD = 921600`
   - `EKF2_AID_MASK = 1` (GPS Positioning enabled)
3. On the Raspberry Pi 5 companion computer, start the MicroXRCEAgent client:
   ```bash
   MicroXRCEAgent serial --dev /dev/ttyAMA0 -b 921600
   ```
4. PX4 uORB topics (`/fmu/out/vehicle_odometry`, `/fmu/in/trajectory_setpoint`) will immediately appear on the ROS 2 bus identically to SITL.

---

### Subsystem 2: Camera Payload Hardware Swap
| Simulation Component | Physical Drop-in Replacement |
| :--- | :--- |
| Gazebo Harmonic RGB Sensor (`1280x720@30FPS`) | Sony IMX708 (Raspberry Pi Camera Module 3) or FLIR Blackfly S USB3 |
| Virtual ROS-Gz Bridge | `libcamera-vid` hardware-accelerated H.264 RTSP server |

#### Migration Steps:
1. Connect the camera ribbon to the RPi 5 CSI-2 port.
2. Launch the low-latency RTSP stream server:
   ```bash
   libcamera-vid -t 0 --inline --width 1280 --height 720 --framerate 30 --codec h264 --listen -o rtsp://0.0.0.0:8554/live
   ```
3. Update the Edge AI container environment variable:
   ```bash
   CAMERA_STREAM_URL=rtsp://10.45.0.2:8554/live
   ```

---

### Subsystem 3: Physical ESP32 IoT Sensor Fleet
| Simulation Component | Physical Drop-in Replacement | Wiring & Pins |
| :--- | :--- | :--- |
| `ESP32_001` (DS18B20) | ESP32-WROOM-32D + DS18B20 Waterproof Probe | GPIO 4 (with 4.7kΩ pull-up resistor to 3.3V) |
| `ESP32_002` (DS18B20) | ESP32-WROOM-32D + DS18B20 Core Probe | GPIO 4 (with 4.7kΩ pull-up resistor to 3.3V) |
| `ESP32_003` (BME280) | ESP32-WROOM-32D + Bosch BME280 Breakout | I2C: SDA -> GPIO 21, SCL -> GPIO 22 |
| `ESP32_004` (DHT22) | ESP32-WROOM-32D + DHT22 / AM2302 Sensor | GPIO 14 (with 10kΩ pull-up to 3.3V) |

#### ESP-IDF / Arduino C++ Firmware Template:
```cpp
#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "INFYNEX_FIELD_AP";
const char* password = "FieldSecurityPass";
const char* mqtt_server = "10.45.0.1"; // Edge Mosquitto IP
const char* node_id = "ESP32_001";

WiFiClient espClient;
PubSubClient client(espClient);

void setup_mqtt() {
  client.setServer(mqtt_server, 1883);
  String lwtTopic = "infynex/sensors/" + String(node_id) + "/status";
  String lwtPayload = "{\"node_id\":\"" + String(node_id) + "\",\"status\":\"offline\",\"reason\":\"unexpected_disconnect\"}";
  
  while (!client.connected()) {
    // Connect with Last Will and Testament configured
    if (client.connect(node_id, lwtTopic.c_str(), 1, true, lwtPayload.c_str())) {
      String birthTopic = "infynex/sensors/" + String(node_id) + "/status";
      client.publish(birthTopic.c_str(), "{\"status\":\"online\"}", true);
    } else {
      delay(2000);
    }
  }
}
```

---

### Subsystem 4: 5G NR Cellular Modem Integration
| Simulation Component | Physical Drop-in Replacement |
| :--- | :--- |
| `ns-3 / 5G-LENA` & `tc netem` | Quectel RM500Q-AE / RM520N-GL 5G NR M.2 Sub-6GHz Module |
| Virtual Bridge Network | Commercial / Private 5G Standalone (SA) SIM Card |

#### Migration Steps:
1. Insert the 5G M.2 Modem into a USB 3.0 HAT on the Raspberry Pi 5.
2. Verify modem discovery:
   ```bash
   lsusb | grep Quectel
   qmicli -d /dev/cdc-wdm0 --dms-get-operating-mode
   ```
3. Connect to the 5G Standalone network with QMI Network Manager:
   ```bash
   qmicli -d /dev/cdc-wdm0 --wds-start-network="apn='infynex.sa',ip-type=4" --client-no-release-cid
   udhcpc -i wwan0
   ```
4. Verify sub-15ms 5G latency to the Edge server:
   ```bash
   ping -c 5 10.45.0.1
   ```

---

### Subsystem 5: Edge Processing & AI Inference Hardware
| Simulation Component | Production Edge Replacement |
| :--- | :--- |
| Backend Container on RTX 3050 Laptop | NVIDIA Jetson Orin Nano (8GB) / Orin NX (16GB) Industrial Box |

#### Inference Optimization on Hardware:
Export the PyTorch weights `best.pt` directly to **TensorRT FP16 engine** for 12ms inference:
```bash
trtexec --onnx=damage_segmentor.onnx --saveEngine=damage_segmentor_fp16.engine --fp16
```
