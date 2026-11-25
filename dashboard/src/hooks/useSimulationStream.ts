import { useState, useEffect, useRef } from 'react';

export interface DefectAlert {
  damage_id: string;
  category: string;
  label?: string;
  severity: string;
  confidence: number;
  position: { x: number; y: number; z: number };
  surface?: string;
  frame?: string;
  annotated?: string;
}

export interface TelemetryData {
  drone: {
    x: number;
    y: number;
    z: number;
    yaw: number;
    battery: number;
    status: string;
    waypoint: string;
    activeFrame: string;
    rawFrame: string;
    flaggedDefect: DefectAlert | null;
  };
  sensors: Record<string, {
    node_id: string;
    temperature_c?: number;
    humidity_percent?: number;
    pressure_hpa?: number;
    status: string;
  }>;
  damages: Array<DefectAlert>;
  network: {
    scenario: string;
    latency_ms: number;
    jitter_ms: number;
    packet_loss_percent: number;
    throughput_mbps: number;
    pdr?: number;
  };
  connected: boolean;
  startMission: () => Promise<void>;
  stopMission: () => Promise<void>;
}

export function useSimulationStream(wsUrl: string = "ws://localhost:8000/ws") {
  const [data, setData] = useState<TelemetryData>({
    drone: {
      x: 0.0,
      y: 0.0,
      z: 0.05,
      yaw: 0.0,
      battery: 100.0,
      status: "STANDBY_DISARMED",
      waypoint: "Helipad Pad (Ready)",
      activeFrame: "http://localhost:8000/data/detections/annotated_W3.jpg",
      rawFrame: "http://localhost:8000/data/captured_images/frame_inspect_W3.jpg",
      flaggedDefect: null
    },
    sensors: {
      "ESP32_001": { node_id: "ESP32_001", temperature_c: 31.2, status: "normal" },
      "ESP32_002": { node_id: "ESP32_002", temperature_c: 26.8, status: "normal" },
      "ESP32_003": { node_id: "ESP32_003", temperature_c: 28.5, humidity_percent: 65.4, pressure_hpa: 1013.2, status: "normal" },
      "ESP32_004": { node_id: "ESP32_004", temperature_c: 27.9, humidity_percent: 66.0, status: "normal" }
    },
    damages: [
      { damage_id: "CRACK_001", category: "crack", severity: "severe", confidence: 0.952, position: { x: 4.74, y: -1.15, z: 2.54 }, surface: "Station W3 (Front Wall)" },
      { damage_id: "SPALL_001", category: "spalling", severity: "critical", confidence: 0.861, position: { x: 4.74, y: 0.20, z: 3.20 }, surface: "Station W4 (Center Pier)" },
      { damage_id: "CRACK_002", category: "crack", severity: "moderate", confidence: 0.760, position: { x: 4.74, y: 1.75, z: 3.15 }, surface: "Station W5 (Overhead Beam)" }
    ],
    network: {
      scenario: "good_signal",
      latency_ms: 10.4,
      jitter_ms: 1.2,
      packet_loss_percent: 0.0,
      throughput_mbps: 498.5,
      pdr: 100.0
    },
    connected: false,
    startMission: async () => {},
    stopMission: async () => {}
  });

  const wsRef = useRef<WebSocket | null>(null);

  const startMission = async () => {
    try {
      await fetch("http://localhost:8000/api/v1/missions/start", { method: "POST" });
    } catch (e) {
      console.error("Failed to start mission via API:", e);
    }
  };

  const stopMission = async () => {
    try {
      await fetch("http://localhost:8000/api/v1/missions/stop", { method: "POST" });
    } catch (e) {
      console.error("Failed to stop mission via API:", e);
    }
  };

  useEffect(() => {
    let reconnectTimeout: any;

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setData(prev => ({ ...prev, connected: true }));
        };

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "drone_telemetry") {
              const d = msg.data;
              const activeFrameUrl = d.active_frame ? `http://localhost:8000${d.active_frame}` : undefined;
              const rawFrameUrl = d.raw_frame ? `http://localhost:8000${d.raw_frame}` : undefined;

              setData(prev => ({
                ...prev,
                drone: {
                  x: d.position?.x ?? prev.drone.x,
                  y: d.position?.y ?? prev.drone.y,
                  z: d.position?.z ?? prev.drone.z,
                  yaw: d.yaw ?? prev.drone.yaw,
                  battery: d.battery_percent ?? prev.drone.battery,
                  status: d.flight_status ?? prev.drone.status,
                  waypoint: d.waypoint ?? prev.drone.waypoint,
                  activeFrame: activeFrameUrl ?? prev.drone.activeFrame,
                  rawFrame: rawFrameUrl ?? prev.drone.rawFrame,
                  flaggedDefect: d.flagged_defect ?? prev.drone.flaggedDefect
                }
              }));
            } else if (msg.type === "sensor_reading") {
              const s = msg.data;
              setData(prev => ({
                ...prev,
                sensors: { ...prev.sensors, [s.node_id]: s }
              }));
            } else if (msg.type === "damage_detection") {
              const det = msg.data;
              setData(prev => {
                const exists = prev.damages.some(d => d.damage_id === det.damage_id);
                return {
                  ...prev,
                  drone: {
                    ...prev.drone,
                    flaggedDefect: det
                  },
                  damages: exists ? prev.damages : [...prev.damages, det]
                };
              });
            } else if (msg.type === "network_metrics") {
              setData(prev => ({
                ...prev,
                network: msg.data
              }));
            }
          } catch (e) {
            console.error("Failed to parse WS payload:", e);
          }
        };

        ws.onclose = () => {
          setData(prev => ({ ...prev, connected: false }));
          reconnectTimeout = setTimeout(connect, 2000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch (err) {
        reconnectTimeout = setTimeout(connect, 2000);
      }
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [wsUrl]);

  return {
    ...data,
    startMission,
    stopMission
  };
}
