# INFYNEX Verification and Test Plan

## Test Scenarios Matrix

| ID | Test Scenario | Procedure | Expected Outcome | Status |
| :--- | :--- | :--- | :--- | :--- |
| **T1** | **Normal Infrastructure Inspection** | Execute waypoints W1 -> W9 along building structure. | Drone takes off, navigates all waypoints cleanly, lands at origin. | Pending |
| **T2** | **Structure Crack Detection** | Inspect concrete facade with vertical and diagonal cracks. | AI identifies cracks, classifies severity, draws bounding boxes. | Pending |
| **T3** | **Concrete Spalling Detection** | Inspect damaged pillar with exposed concrete spall. | AI detects spall area, outputs confidence >= 0.80, registers 3D point. | Pending |
| **T4** | **Environmental Variation** | Vary ambient temp & humidity in IoT simulation. | Sensor charts on dashboard reflect dynamic environmental shifts. | Pending |
| **T5** | **Sensor Node Disconnection** | Simulate battery depletion / network drop on ESP32_002. | Broker detects timeout, dashboard flags node as `offline`. | Pending |
| **T6** | **High Network Latency (5G)** | Apply 150ms round-trip latency via `tc netem`. | Application logs increased round-trip delay; video buffering handled gracefully. | Pending |
| **T7** | **Packet Loss (5G)** | Apply 5% packet loss on drone-to-edge link. | Telemetry reports packet delivery ratio drop; retry mechanisms validated. | Pending |
| **T8** | **Digital Twin Drone Tracking** | Drone moves along inspection route. | Three.js 3D viewport updates drone position in real-time (< 100ms lag). | Pending |
| **T9** | **Full System Integration** | Run end-to-end mission with all 6 subsystems active. | Data flows seamlessly: Drone -> 5G -> Edge -> AI + IoT -> Dashboard. | Pending |
| **T10**| **Inspection Report Compilation**| Complete mission and trigger PDF export. | PDF contains mission map, damage photos, severity stats, and sensor charts. | Pending |
