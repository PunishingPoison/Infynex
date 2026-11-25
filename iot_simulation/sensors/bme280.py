#!/usr/bin/env python3
"""
INFYNEX BME280 Combined Environmental Sensor Node
Simulates ambient temperature, relative humidity, and barometric pressure.
"""

import math
import random
from typing import Dict, Any
from iot_simulation.sensors.base_node import BaseSensorNode

class BME280Node(BaseSensorNode):
    def __init__(
        self,
        node_id: str,
        location: str,
        base_temp_c: float = 26.0,
        base_humidity_pct: float = 62.0,
        base_pressure_hpa: float = 1013.25,
        sample_interval_sec: float = 1.0,
        broker_host: str = "localhost",
        broker_port: int = 1883
    ):
        super().__init__(
            node_id=node_id,
            sensor_type="BME280",
            location=location,
            sample_interval_sec=sample_interval_sec,
            broker_host=broker_host,
            broker_port=broker_port
        )
        self.base_temp_c = base_temp_c
        self.base_humidity_pct = base_humidity_pct
        self.base_pressure_hpa = base_pressure_hpa

    def read_raw(self) -> Dict[str, Any]:
        temp_osc = 3.2 * math.sin(self.sim_time_sec * 0.015)
        temp_c = self.base_temp_c + temp_osc + random.gauss(0, 0.04)

        # Humidity inverse correlation to ambient temperature
        humidity = self.base_humidity_pct - (temp_osc * 1.8) + random.gauss(0, 0.25)
        humidity = max(15.0, min(99.0, humidity))

        # Barometric micro-fluctuations
        pressure = self.base_pressure_hpa + 1.2 * math.cos(self.sim_time_sec * 0.005) + random.gauss(0, 0.08)

        status = "normal"

        if self.fault_mode == "drift":
            temp_c += self.drift_offset
            humidity = max(0.0, min(100.0, humidity + self.drift_offset * 1.5))
            status = "warning"
        elif self.fault_mode == "spike":
            humidity = 98.5
            temp_c += 18.0
            status = "critical"
        elif self.battery_voltage < 2.6:
            status = "low_battery"

        return {
            "temperature_c": round(temp_c, 2),
            "humidity_pct": round(humidity, 1),
            "pressure_hpa": round(pressure, 2),
            "status": status
        }
