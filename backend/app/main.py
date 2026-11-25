"""
INFYNEX Central FastAPI Application Server
Provides REST endpoints and high-throughput WebSockets for the React digital twin dashboard.
Integrates live MQTT telemetry from drone and ESP32 sensor networks.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.endpoints import router as api_router
from app.services.mqtt_service import MqttBridgeService
from app.services.mission_runner import MissionFlightSimulator
from app.services.video_streamer import DroneCameraVideoStreamer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Backend] %(message)s")


class WebSocketHub:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)


ws_hub = WebSocketHub()
mqtt_service = MqttBridgeService(ws_hub=ws_hub)
mission_runner = MissionFlightSimulator(ws_hub=ws_hub, mqtt_service=mqtt_service)
video_streamer = DroneCameraVideoStreamer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start MQTT background ingestion
    logging.info("Starting INFYNEX backend services...")
    ws_hub.loop = asyncio.get_running_loop()
    mqtt_service.start()
    yield
    # Shutdown
    logging.info("Shutting down INFYNEX backend services...")
    mqtt_service.stop()


app = FastAPI(
    title="INFYNEX Digital Simulation API",
    version="1.0.0",
    description="Backend API and WebSocket real-time telemetry streaming for the INFYNEX drone inspection digital twin.",
    lifespan=lifespan
)

# Enable CORS for local React / Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

data_path = "/app/data" if os.path.exists("/app/data") else os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
if os.path.exists(data_path):
    app.mount("/data", StaticFiles(directory=data_path), name="data")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_hub.connect(websocket)
    try:
        while True:
            # Keep socket open and receive any client control commands
            data = await websocket.receive_text()
            logging.debug(f"Received WS message: {data}")
    except WebSocketDisconnect:
        ws_hub.disconnect(websocket)
    except Exception as e:
        logging.warning(f"WebSocket connection error: {e}")
        ws_hub.disconnect(websocket)
