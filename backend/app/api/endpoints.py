"""
INFYNEX REST API Endpoints
Provides structured endpoints for missions, live telemetry, damages, sensor health, and 5G network metrics.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import time
import os
from app.services.report_generator import InspectionReportGenerator

router = APIRouter()


class MissionCreateRequest(BaseModel):
    name: str
    target_structure: str = "Bridge Pier Facade A"
    scenario: str = "normal_inspection"


@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "INFYNEX Simulation Backend",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "version": "1.0.0"
    }


@router.get("/missions")
def list_missions():
    return [
        {
            "id": "m-001-preview",
            "name": "Pier 4 Structural Crack & Spall Inspection",
            "target_structure": "Bridge Pier Facade A",
            "status": "completed",
            "start_time": "2026-11-24T10:00:00Z",
            "end_time": "2026-11-24T10:14:32Z",
            "total_waypoints": 9,
            "detected_damages_count": 3
        }
    ]


@router.post("/missions")
def create_mission(request: MissionCreateRequest):
    mission_id = f"m-{int(time.time())}"
    return {
        "id": mission_id,
        "name": request.name,
        "target_structure": request.target_structure,
        "scenario": request.scenario,
        "status": "scheduled",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@router.get("/drone/live")
def get_drone_live():
    from app.main import mqtt_service
    return mqtt_service.latest_drone_telemetry


@router.get("/sensors/live")
def get_sensors_live():
    from app.main import mqtt_service
    return mqtt_service.latest_sensor_readings


@router.get("/damages")
@router.get("/detections")
def list_damages():
    from app.main import mqtt_service
    return mqtt_service.detected_damages


@router.post("/detections")
def add_damage_detection(payload: Dict[str, Any]):
    from app.main import mqtt_service, ws_hub
    from app.services.mqtt_service import asyncio_broadcast
    mqtt_service.detected_damages.append(payload)
    mqtt_service.db.record_damage_detection(payload)
    if ws_hub:
        asyncio_broadcast(ws_hub, {"type": "damage_detection", "data": payload})
    return {"status": "recorded", "damage_id": payload.get("damage_id")}


@router.get("/telemetry/history")
def get_telemetry_history(limit: int = 50):
    from app.main import mqtt_service
    return mqtt_service.db.get_latest_telemetry(limit=limit)


@router.get("/sensors/history")
def get_sensors_history(limit: int = 50):
    from app.main import mqtt_service
    return mqtt_service.db.get_latest_sensors(limit=limit)


@router.get("/detections/history")
def get_detections_history():
    from app.main import mqtt_service
    return mqtt_service.db.get_all_damages()


@router.get("/network/metrics")
def get_network_metrics():
    from app.main import mqtt_service
    return mqtt_service.latest_network_metrics


@router.post("/network/scenario")
def set_network_scenario(scenario_name: str):
    from app.main import mqtt_service
    profiles = {
        "good_signal": {"latency_ms": 10.0, "jitter_ms": 1.0, "packet_loss_percent": 0.0, "throughput_mbps": 200.0},
        "distance_degradation": {"latency_ms": 45.0, "jitter_ms": 8.0, "packet_loss_percent": 1.5, "throughput_mbps": 35.0},
        "congestion": {"latency_ms": 120.0, "jitter_ms": 25.0, "packet_loss_percent": 6.0, "throughput_mbps": 8.0},
        "handover": {"latency_ms": 22.0, "jitter_ms": 3.0, "packet_loss_percent": 0.5, "throughput_mbps": 95.0}
    }
    if scenario_name not in profiles:
        raise HTTPException(status_code=400, detail=f"Unknown scenario. Available: {list(profiles.keys())}")

    p = profiles[scenario_name]
    p["scenario"] = scenario_name
    mqtt_service.latest_network_metrics = p
    return {"status": "applied", "scenario": scenario_name, "profile": p}


@router.post("/reports/generate")
def generate_report(mission_id: str = "MISSION_001"):
    from app.main import mqtt_service, mission_runner
    output_dir = "/app/data" if os.path.exists("/app/data") else os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    rep_gen = InspectionReportGenerator(output_dir=output_dir)

    all_damages = [
        {"damage_id": "CRACK_001", "category": "crack", "severity": "severe", "confidence": 0.965, "position": {"x": 4.74, "y": -1.15, "z": 2.54}, "surface": "North Face: Front Wall Pier"},
        {"damage_id": "SPALL_001", "category": "spalling", "severity": "critical", "confidence": 0.955, "position": {"x": 4.74, "y": 0.20, "z": 3.20}, "surface": "East Flank: Corner Column (Exposed Rebar)"},
        {"damage_id": "CRACK_002", "category": "crack", "severity": "severe", "confidence": 0.942, "position": {"x": 5.20, "y": 0.05, "z": 3.50}, "surface": "South Face: Rear Abutment Wall"},
        {"damage_id": "CRACK_003", "category": "crack", "severity": "moderate", "confidence": 0.890, "position": {"x": 4.50, "y": -1.80, "z": 3.00}, "surface": "West Flank: Left Support Column"},
        {"damage_id": "SPALL_002", "category": "spalling", "severity": "high", "confidence": 0.915, "position": {"x": 4.50, "y": 1.20, "z": 4.75}, "surface": "Top Girder: Cantilever Joint & Flange"}
    ]

    pdf_path = rep_gen.generate_pdf(
        mission_id=mission_id,
        structure_name="Bridge Pier Asset A (360° Circumferential Survey)",
        damages=all_damages,
        sensor_stats={
            "esp1_temp": mqtt_service.latest_sensor_readings.get("ESP32_001", {}).get("temperature_c", 31.2),
            "esp2_temp": mqtt_service.latest_sensor_readings.get("ESP32_002", {}).get("temperature_c", 26.8),
            "esp3_temp": mqtt_service.latest_sensor_readings.get("ESP32_003", {}).get("temperature_c", 28.5),
            "esp3_hum": mqtt_service.latest_sensor_readings.get("ESP32_003", {}).get("humidity_percent", 65.4),
            "esp3_press": mqtt_service.latest_sensor_readings.get("ESP32_003", {}).get("pressure_hpa", 1013.2),
            "esp4_temp": mqtt_service.latest_sensor_readings.get("ESP32_004", {}).get("temperature_c", 27.9),
            "esp4_hum": mqtt_service.latest_sensor_readings.get("ESP32_004", {}).get("humidity_percent", 66.0),
        },
        network_stats={
            "latency_ms": 11.2,
            "jitter_ms": 1.3,
            "throughput_mbps": 498.5,
            "pdr": 100.0
        },
        flight_stats={
            "model": "PX4 SITL x500 (360° Orbital Survey)",
            "altitude_m": 3.0,
            "duration_sec": 185,
            "waypoints_count": 9,
            "battery_start_pct": 100,
            "battery_end_pct": 82
        }
    )
    return {
        "status": "generated",
        "file_path": pdf_path,
        "filename": os.path.basename(pdf_path),
        "mission_id": mission_id
    }


@router.get("/reports/download")
def download_report(filename: str = "INFYNEX_Inspection_Report_MISSION_001.pdf"):
    possible_paths = [
        os.path.join("/app/data", filename),
        os.path.join("data", filename),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data", filename))
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="application/pdf", filename=filename)
    raise HTTPException(status_code=404, detail=f"Report PDF '{filename}' not found")


@router.post("/missions/start")
async def start_flight_mission():
    from app.main import mission_runner
    return mission_runner.start_mission_async()


@router.post("/missions/stop")
async def stop_flight_mission():
    from app.main import mission_runner
    return mission_runner.stop_mission()


@router.get("/camera/status")
def get_camera_status():
    from app.main import mission_runner
    return {
        "status": "STREAMING",
        "fps": 30,
        "resolution": "1280x720",
        "waypoint": mission_runner.current_waypoint,
        "active_frame": mission_runner.active_frame_path,
        "active_annotated": mission_runner.active_annotated_path,
        "active_defect": mission_runner.active_defect
    }


@router.get("/camera/frame")
def get_camera_frame(annotated: bool = True):
    from app.main import mission_runner
    rel_path = mission_runner.active_annotated_path if annotated else mission_runner.active_frame_path
    clean_rel = rel_path.lstrip("/data/").lstrip("/")
    possible_paths = [
        os.path.join("/app/data", clean_rel),
        os.path.join("data", clean_rel),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data", clean_rel))
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="Camera frame not found")


@router.get("/camera/stream")
def get_camera_stream():
    from app.main import video_streamer, mission_runner
    return StreamingResponse(
        video_streamer.generate_mjpeg_stream(mission_runner),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/ai/model_specs")
def get_ai_model_specs():
    from app.main import video_streamer
    return video_streamer.detector.get_model_specs()
