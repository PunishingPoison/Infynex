"""
Unit Tests for INFYNEX ESP32 IoT Node Simulation
"""

import unittest
from iot_simulation.sensors.sensor_models import DS18B20Node, BME280Node, DHT22Node


class TestIotSensors(unittest.TestCase):
    def test_ds18b20_readings(self):
        node = DS18B20Node("ESP32_001", "pillar_1", base_temp=28.0)
        reading = node.read()
        self.assertIsNotNone(reading)
        self.assertEqual(reading["node_id"], "ESP32_001")
        self.assertIn("temperature_c", reading)
        self.assertGreaterEqual(reading["temperature_c"], 20.0)
        self.assertLessEqual(reading["temperature_c"], 40.0)
        self.assertEqual(reading["status"], "normal")

    def test_bme280_readings(self):
        node = BME280Node("ESP32_003", "foundation")
        reading = node.read()
        self.assertIsNotNone(reading)
        self.assertEqual(reading["sensor_model"], "BME280")
        self.assertIn("humidity_percent", reading)
        self.assertIn("pressure_hpa", reading)
        self.assertGreater(reading["pressure_hpa"], 950.0)

    def test_sensor_fault_injection(self):
        node = DS18B20Node("ESP32_002", "core", base_temp=25.0)
        node.trigger_fault(True)
        reading = node.read()
        self.assertEqual(reading["status"], "sensor_error")

    def test_sensor_offline(self):
        node = DHT22Node("ESP32_004", "deck")
        node.set_offline(True)
        reading = node.read()
        self.assertIsNone(reading)


if __name__ == "__main__":
    unittest.main()
