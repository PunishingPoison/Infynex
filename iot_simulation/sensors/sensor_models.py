"""
INFYNEX ESP32 IoT Node Hardware Emulators
Simulates:
- Node 1: ESP32 + DS18B20 (Concrete Surface Temperature)
- Node 2: ESP32 + DS18B20 (Structural Internal Core Temperature)
- Node 3: ESP32 + BME280 (Ambient Temperature, Relative Humidity, Pressure)
- Node 4: ESP32 + DHT22 (Ambient Temperature and Humidity)

Features:
- Configurable sampling intervals
- Dynamic physical process simulation (solar heating, diurnal fluctuations)
- Realistic sensor noise and drift
- Fault injection: sensor dropouts, out-of-range anomalies, packet drops
- MQTT JSON payloads formatted according to the INFYNEX specification
"""

import json
import math
import random
import time
from typing import Dict, Any, Optional


class BaseSensorNode:
    def __init__(self, node_id: str, sensor_model: str, location: str, sample_interval: float = 1.0):
        self.node_id = node_id
        self.sensor_model = sensor_model
        self.location = location
        self.sample_interval = sample_interval
        self.battery_voltage = 3.30
        self.is_faulty = False
        self.is_offline = False
        self.sim_time_sec = 0.0

    def step_time(self, dt: float):
        self.sim_time_sec += dt
        # Slow battery depletion: ~0.0001V per minute
        self.battery_voltage = max(2.5, self.battery_voltage - (0.0000016 * dt))

    def trigger_fault(self, faulty: bool = True):
        self.is_faulty = faulty

    def set_offline(self, offline: bool = True):
        self.is_offline = offline

    def read(self) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


class DS18B20Node(BaseSensorNode):
    """Dallas DS18B20 1-Wire Digital Temperature Sensor Emulator."""
    def __init__(self, node_id: str, location: str, base_temp: float = 28.5, sample_interval: float = 1.0):
        super().__init__(node_id, "DS18B20", location, sample_interval)
        self.base_temp = base_temp

    def read(self) -> Optional[Dict[str, Any]]:
        if self.is_offline:
            return None

        # Solar heating curve + random Gaussian sensor noise
        diurnal_offset = 3.5 * math.sin(self.sim_time_sec * 0.01)
        noise = random.gauss(0, 0.08)
        temp_c = round(self.base_temp + diurnal_offset + noise, 2)

        status = "normal"
        if self.is_faulty:
            # Emulate sensor fault: return error sentinel or extreme temperature
            temp_c = 999.9 if random.random() < 0.5 else -55.0
            status = "sensor_error"
        elif self.battery_voltage < 2.7:
            status = "low_battery"

        return {
            "node_id": self.node_id,
            "sensor_model": self.sensor_model,
            "location": self.location,
            "temperature_c": temp_c,
            "battery_voltage": round(self.battery_voltage, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "status": status
        }


class BME280Node(BaseSensorNode):
    """Bosch Sensortec BME280 Combined Temp, Humidity, and Pressure Sensor."""
    def __init__(self, node_id: str, location: str, sample_interval: float = 1.0):
        super().__init__(node_id, "BME280", location, sample_interval)
        self.base_temp = 27.0
        self.base_humidity = 65.0
        self.base_pressure = 1013.25

    def read(self) -> Optional[Dict[str, Any]]:
        if self.is_offline:
            return None

        temp_c = round(self.base_temp + 2.0 * math.sin(self.sim_time_sec * 0.01) + random.gauss(0, 0.05), 2)
        humidity = round(max(10.0, min(100.0, self.base_humidity - (temp_c - self.base_temp) * 2.0 + random.gauss(0, 0.3))), 1)
        pressure = round(self.base_pressure + 1.5 * math.cos(self.sim_time_sec * 0.005) + random.gauss(0, 0.1), 2)

        status = "normal"
        if self.is_faulty:
            humidity = -1.0
            status = "sensor_error"
        elif self.battery_voltage < 2.7:
            status = "low_battery"

        return {
            "node_id": self.node_id,
            "sensor_model": self.sensor_model,
            "location": self.location,
            "temperature_c": temp_c,
            "humidity_percent": humidity,
            "pressure_hpa": pressure,
            "battery_voltage": round(self.battery_voltage, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "status": status
        }


class DHT22Node(BaseSensorNode):
    """Aosong DHT22 / AM2302 Capacitive Humidity and NTC Temperature Sensor."""
    def __init__(self, node_id: str, location: str, sample_interval: float = 2.0):
        super().__init__(node_id, "DHT22", location, sample_interval)
        self.base_temp = 26.8
        self.base_humidity = 66.5

    def read(self) -> Optional[Dict[str, Any]]:
        if self.is_offline:
            return None

        temp_c = round(self.base_temp + 1.8 * math.sin(self.sim_time_sec * 0.01) + random.gauss(0, 0.1), 1)
        humidity = round(max(0.0, min(100.0, self.base_humidity + random.gauss(0, 0.5))), 1)

        status = "normal"
        if self.is_faulty:
            temp_c = 0.0
            humidity = 0.0
            status = "sensor_error"
        elif self.battery_voltage < 2.7:
            status = "low_battery"

        return {
            "node_id": self.node_id,
            "sensor_model": self.sensor_model,
            "location": self.location,
            "temperature_c": temp_c,
            "humidity_percent": humidity,
            "battery_voltage": round(self.battery_voltage, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
            "status": status
        }
