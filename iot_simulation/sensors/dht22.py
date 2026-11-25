#!/usr/bin/env python3
"""
INFYNEX DHT22 Digital Temperature & Humidity Sensor Node
Simulates deck surface ambient humidity and temperature monitoring.
"""

import math
import random
from typing import Dict, Any
from iot_simulation.sensors.base_node import BaseSensorNode

class DHT22Node(BaseSensorNode):
    def __init__(
        self,
        node_id: str,
        location: str,
        base_temp_c: float = 27.5,
        base_humidity_pct: float = 58.0,
        sample_interval_sec: float = 2.0,
        broker_host: str = "localhost",
        broker_port: int = 1883
    ):
        super().__init__(
            node_id=node_id,
            sensor_type="DHT22",
            location=location,
            sample_interval_sec=sample_interval_sec,
            broker_host=broker_host,
            broker_port=broker_port
        )
        self.base_temp_c = base_temp_c
        self.base_humidity_pct = base_humidity_pct

    def read_raw(self) -> Dict[str, Any]:
        temp_osc = 2.5 * math.sin(self.sim_time_sec * 0.012)
        temp_c = self.base_temp_c + temp_osc + random.gauss(0, 0.1)

        humidity = self.base_humidity_pct - (temp_osc * 1.4) + random.gauss(0, 0.4)
        humidity = max(10.0, min(95.0, humidity))

        status = "normal"

        if self.fault_mode == "drift":
            temp_c += self.drift_offset
            status = "warning"
        elif self.fault_mode == "spike":
            temp_c += 22.0
            status = "critical"
        elif self.battery_voltage < 2.6:
            status = "low_battery"

        return {
            "temperature_c": round(temp_c, 2),
            "humidity_pct": round(humidity, 1),
            "status": status
        }
