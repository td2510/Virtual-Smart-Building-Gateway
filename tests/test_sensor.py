"""
Unit tests for Virtual Sensor (Member 1).
Tests the SensorSimulator class and telemetry message format.
Run: python -m pytest tests/test_sensor.py -v

These tests do NOT require MQTT broker — they test the simulator logic directly.
"""

import sys
import os
import json
import importlib

# We need to import sensor.py but it uses module-level env vars and MQTT.
# So we test the SensorSimulator class by importing only what we need.
# Add virtual_sensor to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "virtual_sensor"))


# Helper: Import SensorSimulator without running the module
def get_simulator_class():
    """Import SensorSimulator from sensor.py."""
    # Set env vars before importing to avoid issues
    os.environ.setdefault("MQTT_BROKER", "localhost")
    os.environ.setdefault("ROOM_ID", "room-01")
    os.environ.setdefault("DEVICE_ID", "sensor-room-01")

    import sensor
    return sensor.SensorSimulator


# Tests for SensorSimulator
class TestSensorSimulator:

    def setup_method(self):
        SimClass = get_simulator_class()
        self.simulator = SimClass()

    def test_initial_values(self):
        """Simulator should start with reasonable initial values."""
        assert 20.0 <= self.simulator.temperature <= 30.0
        assert 40.0 <= self.simulator.humidity <= 80.0
        assert 50.0 <= self.simulator.light_lux <= 800.0
        assert 400.0 <= self.simulator.co2_ppm <= 1000.0
        assert isinstance(self.simulator.occupancy, bool)
        assert self.simulator.cycle_count == 0

    def test_generate_returns_dict(self):
        """generate() should return a dictionary."""
        result = self.simulator.generate()
        assert isinstance(result, dict)

    def test_generate_has_all_required_fields(self):
        """Generated telemetry must have all fields required by shared contract."""
        result = self.simulator.generate()
        required_fields = [
            "device_id", "room_id", "temperature", "humidity",
            "light_lux", "co2_ppm", "occupancy", "timestamp"
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_generate_has_last_seen(self):
        """Generated telemetry should include last_seen field (advanced #4)."""
        result = self.simulator.generate()
        assert "last_seen" in result

    def test_generate_increments_cycle_count(self):
        """Each generate() call should increment the cycle counter."""
        assert self.simulator.cycle_count == 0
        self.simulator.generate()
        assert self.simulator.cycle_count == 1
        self.simulator.generate()
        assert self.simulator.cycle_count == 2

    def test_temperature_type(self):
        """Temperature should be a float."""
        result = self.simulator.generate()
        assert isinstance(result["temperature"], float)

    def test_humidity_type(self):
        """Humidity should be a float."""
        result = self.simulator.generate()
        assert isinstance(result["humidity"], float)

    def test_co2_type(self):
        """CO2 should be a float."""
        result = self.simulator.generate()
        assert isinstance(result["co2_ppm"], float)

    def test_light_type(self):
        """Light lux should be a float."""
        result = self.simulator.generate()
        assert isinstance(result["light_lux"], float)

    def test_occupancy_type(self):
        """Occupancy should be a boolean."""
        result = self.simulator.generate()
        assert isinstance(result["occupancy"], bool)

    def test_drift_stays_in_bounds(self):
        """Values should stay within reasonable bounds after many iterations."""
        for _ in range(100):
            result = self.simulator.generate()
            # Even with anomalies, values should be within extreme bounds
            assert -10.0 <= result["temperature"] <= 50.0
            assert 0.0 <= result["humidity"] <= 100.0
            assert 0.0 <= result["light_lux"] <= 2000.0
            assert 0.0 <= result["co2_ppm"] <= 3000.0

    def test_data_not_identical_over_iterations(self):
        """Data should change over multiple iterations (not static)."""
        readings = [self.simulator.generate() for _ in range(20)]
        temps = [r["temperature"] for r in readings]
        # At least some values should differ (not all same)
        assert len(set(temps)) > 1, "Temperature values are all identical — no drift!"

    def test_message_is_json_serializable(self):
        """Telemetry message should be JSON-serializable."""
        result = self.simulator.generate()
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        assert parsed == result

    def test_timestamp_format(self):
        """Timestamp should be ISO 8601 format."""
        result = self.simulator.generate()
        ts = result["timestamp"]
        assert isinstance(ts, str)
        assert "T" in ts  # ISO 8601 has 'T' separator


# Tests for Telemetry Message Format Compatibility with Gateway
class TestTelemetryFormatCompatibility:
    """Verify sensor output matches what Gateway (M2) expects."""

    def setup_method(self):
        SimClass = get_simulator_class()
        self.simulator = SimClass()

    def test_gateway_required_fields_present(self):
        """
        Gateway's validate_telemetry checks for these fields:
        device_id, room_id, temperature, humidity, light_lux, co2_ppm, occupancy, timestamp
        """
        result = self.simulator.generate()
        gateway_required = [
            "device_id", "room_id", "temperature", "humidity",
            "light_lux", "co2_ppm", "occupancy", "timestamp"
        ]
        for field in gateway_required:
            assert field in result, f"Gateway requires '{field}' but sensor doesn't provide it"

    def test_gateway_type_validation(self):
        """Gateway validates these types: float for numeric, bool for occupancy."""
        result = self.simulator.generate()
        # These should not raise when passed to float()
        float(result["temperature"])
        float(result["humidity"])
        float(result["light_lux"])
        float(result["co2_ppm"])
        # occupancy should be bool
        assert isinstance(result["occupancy"], bool)
