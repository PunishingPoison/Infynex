#!/usr/bin/env python3
"""
INFYNEX DS18B20 1-Wire Digital Temperature Sensor Node
Simulates structural concrete thermal dynamics with concrete thermal mass damping.
"""

import math
import random
from typing import Dict, Any
from iot_simulation.sensors.base_node import BaseSensorNode

class DS18B20Node(BaseSensorNode):
    def __init__(
        self,
        node_id: str,
        location: str,
        base_temp_c: float = 24.5,
        sample_interval_sec: float = 1.0,
        broker_host: str = "localhost",
        broker_port: int = 1883
    ):
        super().__init__(
            node_id=node_id,
            sensor_type="DS18B20",
            location=location,
            sample_interval_sec=sample_interval_sec,
            broker_host=broker_host,
            broker_port=broker_port
        )
        self.base_temp_c = base_temp_c

    def read_raw(self) -> Dict[str, Any]:
        # High thermal mass concrete oscillation (period ~ 600s in sim)
        thermal_oscillation = 2.8 * math.sin(self.sim_time_sec * 0.01)
        noise = random.gauss(0, 0.05)
        temp_c = self.base_temp_c + thermal_oscillation + noise

        status = "normal"

        if self.fault_mode == "drift":
            temp_c += self.drift_offset
            status = "warning" if abs(self.drift_offset) < 10.0 else "critical"
        elif self.fault_mode == "spike":
            temp_c += 45.0
            status = "critical"
        elif self.battery_voltage < 2.6:
            status = "low_battery"

        return {
            "temperature_c": round(temp_c, 2),
            "status": status
        }
