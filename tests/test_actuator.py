"""
Unit tests for Virtual Actuator (Member 1).
Tests the ActuatorState class and command/status message format.
Run: python -m pytest tests/test_actuator.py -v

These tests do NOT require MQTT broker — they test the ActuatorState logic directly.
"""

import sys
import os
import json

# Add virtual_actuator to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "virtual_actuator"))

# Set env vars before importing
os.environ.setdefault("MQTT_BROKER", "localhost")
os.environ.setdefault("ROOM_ID", "room-01")
os.environ.setdefault("DEVICE_ID", "actuator-room-01")

from actuator import ActuatorState


# Tests for ActuatorState
class TestActuatorState:

    def setup_method(self):
        self.state = ActuatorState()

    def test_initial_state_all_off(self):
        """All actuators should start as OFF."""
        assert self.state.fan == "off"
        assert self.state.light == "off"
        assert self.state.alarm == "off"
        assert self.state.last_command_reason == ""

    def test_apply_fan_on(self):
        """Applying fan ON should set fan to 'on'."""
        result = self.state.apply_command("fan", "on", "temperature_high")
        assert result is True
        assert self.state.fan == "on"
        assert self.state.last_command_reason == "temperature_high"

    def test_apply_fan_off(self):
        """Applying fan OFF should set fan to 'off'."""
        self.state.apply_command("fan", "on", "temperature_high")
        result = self.state.apply_command("fan", "off", "temperature_low")
        assert result is True
        assert self.state.fan == "off"

    def test_apply_light_on(self):
        """Applying light ON should set light to 'on'."""
        result = self.state.apply_command("light", "on", "manual_control")
        assert result is True
        assert self.state.light == "on"

    def test_apply_alarm_on(self):
        """Applying alarm ON should set alarm to 'on'."""
        result = self.state.apply_command("alarm", "on", "co2_high")
        assert result is True
        assert self.state.alarm == "on"

    def test_invalid_target_rejected(self):
        """Invalid target should be rejected."""
        result = self.state.apply_command("heater", "on", "test")
        assert result is False

    def test_invalid_action_rejected(self):
        """Invalid action should be rejected."""
        result = self.state.apply_command("fan", "toggle", "test")
        assert result is False

    def test_apply_same_state(self):
        """Applying same state should still succeed (idempotent)."""
        self.state.apply_command("fan", "on", "reason1")
        result = self.state.apply_command("fan", "on", "reason2")
        assert result is True
        assert self.state.fan == "on"
        assert self.state.last_command_reason == "reason2"

    def test_independent_actuators(self):
        """Changing one actuator should not affect others."""
        self.state.apply_command("fan", "on", "temp_high")
        self.state.apply_command("alarm", "on", "co2_high")
        assert self.state.fan == "on"
        assert self.state.light == "off"  # unchanged
        assert self.state.alarm == "on"


# Tests for Status Message Format
class TestActuatorStatusMessage:

    def setup_method(self):
        self.state = ActuatorState()

    def test_status_message_has_required_fields(self):
        """Status message must have all fields required by shared contract."""
        status = self.state.to_status_message()
        required_fields = [
            "device_id", "room_id", "fan", "light", "alarm",
            "last_command_reason", "timestamp"
        ]
        for field in required_fields:
            assert field in status, f"Missing required field: {field}"

    def test_status_message_reflects_state(self):
        """Status message should reflect the current actuator state."""
        self.state.apply_command("fan", "on", "temperature_high")
        self.state.apply_command("alarm", "on", "co2_high")
        status = self.state.to_status_message()

        assert status["fan"] == "on"
        assert status["light"] == "off"
        assert status["alarm"] == "on"

    def test_status_message_json_serializable(self):
        """Status message should be JSON-serializable."""
        self.state.apply_command("fan", "on", "test")
        status = self.state.to_status_message()
        json_str = json.dumps(status)
        parsed = json.loads(json_str)
        assert parsed["fan"] == "on"

    def test_status_message_room_id(self):
        """Status message should contain correct room_id."""
        status = self.state.to_status_message()
        assert status["room_id"] == "room-01"

    def test_status_message_device_id(self):
        """Status message should contain correct device_id."""
        status = self.state.to_status_message()
        assert status["device_id"] == "actuator-room-01"


# Tests for Command Format Compatibility with Gateway (M2) and API (M3)
class TestCommandCompatibility:
    """Verify that commands from Gateway and API are properly handled."""

    def setup_method(self):
        self.state = ActuatorState()

    def test_gateway_command_format(self):
        """
        Gateway sends commands with: room_id, target, action, reason, timestamp
        Actuator should process this correctly.
        """
        # Simulated command from Gateway's rule engine
        command = {
            "room_id": "room-01",
            "target": "fan",
            "action": "on",
            "reason": "temperature_high",
            "timestamp": "2026-06-10T10:00:05Z"
        }
        result = self.state.apply_command(
            command["target"],
            command["action"],
            command.get("reason", "unknown")
        )
        assert result is True
        assert self.state.fan == "on"

    def test_api_command_format(self):
        """
        API sends commands with: room_id, target, action, reason, timestamp
        Same format as gateway. Verify actuator processes it.
        """
        command = {
            "room_id": "room-01",
            "target": "light",
            "action": "off",
            "reason": "manual_control",
            "timestamp": "2026-06-10T10:00:05Z"
        }
        result = self.state.apply_command(
            command["target"],
            command["action"],
            command.get("reason", "unknown")
        )
        assert result is True
        assert self.state.light == "off"

    def test_status_format_compatible_with_gateway(self):
        """
        Gateway's handle_actuator_status expects: device_id, room_id, fan, light, alarm
        Verify status message contains these.
        """
        self.state.apply_command("fan", "on", "temperature_high")
        status = self.state.to_status_message()

        # Gateway reads these fields
        assert "device_id" in status
        assert "room_id" in status
        assert "fan" in status
        assert "light" in status
        assert "alarm" in status
        assert "timestamp" in status

    def test_all_valid_targets(self):
        """All valid targets (fan, light, alarm) should be accepted."""
        for target in ["fan", "light", "alarm"]:
            state = ActuatorState()
            assert state.apply_command(target, "on", "test") is True
            assert getattr(state, target) == "on"

    def test_all_valid_actions(self):
        """All valid actions (on, off) should be accepted."""
        for action in ["on", "off"]:
            state = ActuatorState()
            assert state.apply_command("fan", action, "test") is True
            assert state.fan == action
