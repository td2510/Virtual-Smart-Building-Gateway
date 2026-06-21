"""
Unit tests for the Rule Engine.
Run: python -m pytest tests/test_rule_engine.py -v

Tests all 4 mandatory rules:
  1. temperature > 30 → fan ON
  2. temperature < 27 → fan OFF
  3. co2_ppm > 1200   → alarm ON
  4. occupancy == false AND light_lux > 300 → light OFF
"""

import sys
import os

# Add iot_gateway to Python path so we can import rule_engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "iot_gateway"))

from rule_engine import evaluate


def make_telemetry(**kwargs) -> dict:
    """Create a minimal telemetry dict with given overrides."""
    defaults = {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 25.0,
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
        "timestamp": "2026-06-10T10:00:00Z"
    }
    defaults.update(kwargs)
    return defaults


def make_actuator(fan="off", light="off", alarm="off") -> dict:
    """Create an actuator state dict."""
    return {"fan": fan, "light": light, "alarm": alarm}


# ============================================================
# Tests for Rule 1: temperature_high → fan ON
# ============================================================
class TestRule1TemperatureHigh:

    def test_high_temp_triggers_fan_on(self):
        """Temperature > 30 with fan OFF should trigger fan ON command."""
        data = make_telemetry(temperature=33.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)

        assert len(events) == 1
        assert events[0]["event_type"] == "temperature_high"
        assert events[0]["severity"] == "warning"
        assert events[0]["value"] == 33.0
        assert events[0]["threshold"] == 30.0
        assert events[0]["action_taken"] == "fan_on"
        assert len(commands) == 1
        assert commands[0]["target"] == "fan"
        assert commands[0]["action"] == "on"
        assert commands[0]["reason"] == "temperature_high"

    def test_high_temp_no_command_if_fan_already_on(self):
        """Temperature > 30 with fan already ON should NOT trigger command."""
        data = make_telemetry(temperature=35.0)
        actuator = make_actuator(fan="on")  # fan already on
        events, commands = evaluate("room-01", data, actuator)
        assert len(commands) == 0

    def test_normal_temp_no_trigger(self):
        """Temperature within normal range should NOT trigger temperature_high."""
        data = make_telemetry(temperature=28.0)
        actuator = make_actuator()
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "temperature_high" for e in events)

    def test_boundary_temp_30_no_trigger(self):
        """Temperature exactly 30 should NOT trigger (rule is > 30, not >=)."""
        data = make_telemetry(temperature=30.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "temperature_high" for e in events)

    def test_temp_just_above_30_triggers(self):
        """Temperature 30.1 should trigger fan ON."""
        data = make_telemetry(temperature=30.1)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)
        temp_events = [e for e in events if e["event_type"] == "temperature_high"]
        assert len(temp_events) == 1


# ============================================================
# Tests for Rule 2: temperature_low → fan OFF
# ============================================================
class TestRule2TemperatureLow:

    def test_low_temp_triggers_fan_off(self):
        """Temperature < 27 with fan ON should trigger fan OFF command."""
        data = make_telemetry(temperature=22.0)
        actuator = make_actuator(fan="on")
        events, commands = evaluate("room-01", data, actuator)

        fan_off_cmds = [c for c in commands if c["target"] == "fan" and c["action"] == "off"]
        assert len(fan_off_cmds) == 1
        fan_off_events = [e for e in events if e["event_type"] == "temperature_low"]
        assert len(fan_off_events) == 1
        assert fan_off_events[0]["severity"] == "info"

    def test_low_temp_no_command_if_fan_already_off(self):
        """Temperature < 27 with fan already OFF should NOT trigger command."""
        data = make_telemetry(temperature=22.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)
        fan_off_cmds = [c for c in commands if c["target"] == "fan"]
        assert len(fan_off_cmds) == 0

    def test_boundary_temp_27_no_trigger(self):
        """Temperature exactly 27 should NOT trigger (rule is < 27, not <=)."""
        data = make_telemetry(temperature=27.0)
        actuator = make_actuator(fan="on")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "temperature_low" for e in events)


# ============================================================
# Tests for Rule 3: co2_high → alarm ON
# ============================================================
class TestRule3Co2High:

    def test_high_co2_triggers_alarm(self):
        """CO2 > 1200 with alarm OFF should trigger alarm ON command."""
        data = make_telemetry(co2_ppm=1500.0)
        actuator = make_actuator(alarm="off")
        events, commands = evaluate("room-01", data, actuator)

        alarm_cmds = [c for c in commands if c["target"] == "alarm" and c["action"] == "on"]
        assert len(alarm_cmds) == 1
        co2_events = [e for e in events if e["event_type"] == "co2_high"]
        assert len(co2_events) == 1
        assert co2_events[0]["severity"] == "critical"
        assert co2_events[0]["value"] == 1500.0
        assert co2_events[0]["threshold"] == 1200.0

    def test_borderline_co2_no_trigger(self):
        """CO2 exactly at 1200 should NOT trigger (rule is > 1200, not >=)."""
        data = make_telemetry(co2_ppm=1200.0)
        actuator = make_actuator()
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "co2_high" for e in events)

    def test_high_co2_no_command_if_alarm_already_on(self):
        """CO2 > 1200 with alarm already ON should NOT trigger command."""
        data = make_telemetry(co2_ppm=1500.0)
        actuator = make_actuator(alarm="on")
        events, commands = evaluate("room-01", data, actuator)
        alarm_cmds = [c for c in commands if c["target"] == "alarm"]
        assert len(alarm_cmds) == 0


# ============================================================
# Tests for Rule 4: unnecessary_light
# ============================================================
class TestRule4UnnecessaryLight:

    def test_no_occupancy_bright_triggers_light_off(self):
        """No occupancy + bright light with light ON should trigger light OFF."""
        data = make_telemetry(occupancy=False, light_lux=500.0)
        actuator = make_actuator(light="on")
        events, commands = evaluate("room-01", data, actuator)

        light_off = [c for c in commands if c["target"] == "light" and c["action"] == "off"]
        assert len(light_off) == 1
        light_events = [e for e in events if e["event_type"] == "unnecessary_light"]
        assert len(light_events) == 1
        assert light_events[0]["severity"] == "info"

    def test_occupied_no_trigger(self):
        """Room occupied should NOT trigger light OFF regardless of light level."""
        data = make_telemetry(occupancy=True, light_lux=500.0)
        actuator = make_actuator(light="on")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "unnecessary_light" for e in events)

    def test_no_occupancy_dark_no_trigger(self):
        """No occupancy + dark room should NOT trigger light OFF."""
        data = make_telemetry(occupancy=False, light_lux=100.0)
        actuator = make_actuator(light="off")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "unnecessary_light" for e in events)

    def test_no_occupancy_bright_light_already_off(self):
        """No occupancy + bright but light already OFF should NOT trigger."""
        data = make_telemetry(occupancy=False, light_lux=500.0)
        actuator = make_actuator(light="off")
        events, commands = evaluate("room-01", data, actuator)
        light_cmds = [c for c in commands if c["target"] == "light"]
        assert len(light_cmds) == 0

    def test_borderline_light_300_no_trigger(self):
        """Light exactly at 300 should NOT trigger (rule is > 300, not >=)."""
        data = make_telemetry(occupancy=False, light_lux=300.0)
        actuator = make_actuator(light="on")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "unnecessary_light" for e in events)


# ============================================================
# Tests for multiple rules triggering simultaneously
# ============================================================
class TestMultipleRules:

    def test_multiple_rules_trigger(self):
        """High temp + high CO2 should trigger both fan ON and alarm ON."""
        data = make_telemetry(temperature=35.0, co2_ppm=1500.0)
        actuator = make_actuator(fan="off", alarm="off")
        events, commands = evaluate("room-01", data, actuator)

        # Should have both events
        event_types = [e["event_type"] for e in events]
        assert "temperature_high" in event_types
        assert "co2_high" in event_types

        # Should have both commands
        assert len(commands) == 2
        cmd_targets = [(c["target"], c["action"]) for c in commands]
        assert ("fan", "on") in cmd_targets
        assert ("alarm", "on") in cmd_targets

    def test_no_rules_trigger_normal_data(self):
        """Normal sensor data should trigger NO events or commands."""
        data = make_telemetry(
            temperature=25.0,  # between 27-30
            co2_ppm=800.0,     # < 1200
            occupancy=True,    # occupied
            light_lux=400.0,   # doesn't matter since occupied
        )
        actuator = make_actuator()
        events, commands = evaluate("room-01", data, actuator)
        assert len(events) == 0
        assert len(commands) == 0

    def test_event_message_format(self):
        """Verify event message contains all required fields per shared contract."""
        data = make_telemetry(temperature=33.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)

        assert len(events) == 1
        event = events[0]
        # Check all required fields exist
        required_fields = ["room_id", "event_type", "severity", "value",
                          "threshold", "action_taken", "timestamp"]
        for field in required_fields:
            assert field in event, f"Missing field: {field}"

    def test_command_message_format(self):
        """Verify command message contains all required fields per shared contract."""
        data = make_telemetry(temperature=33.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)

        assert len(commands) == 1
        command = commands[0]
        # Check all required fields exist
        required_fields = ["room_id", "target", "action", "reason", "timestamp"]
        for field in required_fields:
            assert field in command, f"Missing field: {field}"

    def test_different_rooms(self):
        """Rules should work correctly for different room IDs."""
        data = make_telemetry(temperature=33.0)
        actuator = make_actuator(fan="off")

        events1, commands1 = evaluate("room-01", data, actuator)
        events2, commands2 = evaluate("room-02", data, actuator)
        events3, commands3 = evaluate("room-03", data, actuator)

        assert events1[0]["room_id"] == "room-01"
        assert events2[0]["room_id"] == "room-02"
        assert events3[0]["room_id"] == "room-03"
        assert commands1[0]["room_id"] == "room-01"
        assert commands2[0]["room_id"] == "room-02"
        assert commands3[0]["room_id"] == "room-03"
