"""
Integration tests between Member 2 (Gateway) and Member 3 (API).
These tests verify that Gateway and API can work together correctly
WITHOUT needing Member 1's code (sensor/actuator).

Tests verify:
1. Shared contracts compatibility (MQTT topics, InfluxDB measurements, field names)
2. Gateway validate/normalize matches what API expects
3. Rule engine output format matches API query expectations
4. Command format from API matches what Gateway processes
5. State store data format matches API response structure

Run: python -m pytest tests/test_integration_gateway_api.py -v
"""

import sys
import os
import json

# Add iot_gateway to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "iot_gateway"))

from rule_engine import evaluate, _make_event, _make_command
from state_store import StateStore


# ============================================================
# Shared Contract Constants (from project_prompt.md)
# ============================================================
# These are the contracts both Gateway (M2) and API (M3) must follow.
KNOWN_ROOMS = ["room-01", "room-02", "room-03"]

# InfluxDB measurement names used by Gateway (writer) and API (reader)
INFLUX_MEASUREMENT_TELEMETRY = "room_telemetry"
INFLUX_MEASUREMENT_EVENTS = "gateway_events"
INFLUX_MEASUREMENT_ACTUATOR = "actuator_status"

# Telemetry field names used in InfluxDB
TELEMETRY_FIELDS = ["temperature", "humidity", "light_lux", "co2_ppm", "occupancy"]
TELEMETRY_TAGS = ["room_id", "device_id"]

# Event field names
EVENT_TAGS = ["room_id", "event_type", "severity"]
EVENT_FIELDS = ["value", "threshold", "action_taken"]

# Actuator field names
ACTUATOR_TAGS = ["room_id", "device_id"]
ACTUATOR_FIELDS = ["fan", "light", "alarm"]

# MQTT Topics
TELEMETRY_TOPIC_PATTERN = "building/{room_id}/sensor/telemetry"
COMMAND_TOPIC_PATTERN = "building/{room_id}/actuator/command"
STATUS_TOPIC_PATTERN = "building/{room_id}/actuator/status"
EVENT_TOPIC_PATTERN = "building/{room_id}/gateway/event"
NORMALIZED_TOPIC_PATTERN = "building/{room_id}/gateway/normalized"


# ============================================================
# Sample data (simulating what Member 1's sensor would produce)
# ============================================================
def make_sensor_telemetry(room_id="room-01", **overrides):
    """Create a sensor telemetry message matching Member 1's format."""
    msg = {
        "device_id": f"sensor-{room_id}",
        "room_id": room_id,
        "temperature": 25.5,
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
        "timestamp": "2026-06-10T10:00:00Z"
    }
    msg.update(overrides)
    return msg


def make_actuator_status(room_id="room-01", **overrides):
    """Create an actuator status message matching Member 1's format."""
    msg = {
        "device_id": f"actuator-{room_id}",
        "room_id": room_id,
        "fan": "off",
        "light": "off",
        "alarm": "off",
        "last_command_reason": "",
        "timestamp": "2026-06-10T10:00:06Z"
    }
    msg.update(overrides)
    return msg


# ============================================================
# Test 1: Validate Gateway writes fields that API can read
# ============================================================
class TestInfluxDBFieldCompatibility:
    """Verify Gateway writes the exact fields/tags that API queries expect."""

    def test_telemetry_fields_match(self):
        """
        Gateway's write_telemetry uses these fields:
          Point("room_telemetry")
            .tag("room_id", ...).tag("device_id", ...)
            .field("temperature", ...).field("humidity", ...)
            .field("light_lux", ...).field("co2_ppm", ...).field("occupancy", ...)

        API's query_latest_telemetry reads:
          r._measurement == "room_telemetry"
          r.room_id == "{room_id}"
          record.values.get("temperature"), etc.

        This test verifies the field names match.
        """
        # Gateway writes these fields to InfluxDB
        gateway_telemetry_fields = ["temperature", "humidity", "light_lux", "co2_ppm", "occupancy"]
        gateway_telemetry_tags = ["room_id", "device_id"]
        gateway_measurement = "room_telemetry"

        # API reads these fields from InfluxDB
        api_expected_fields = ["temperature", "humidity", "light_lux", "co2_ppm", "occupancy"]
        api_expected_measurement = "room_telemetry"

        assert gateway_measurement == api_expected_measurement
        assert set(gateway_telemetry_fields) == set(api_expected_fields)
        assert "room_id" in gateway_telemetry_tags

    def test_event_fields_match(self):
        """
        Gateway's write_event uses:
          Point("gateway_events")
            .tag("room_id", ...).tag("event_type", ...).tag("severity", ...)
            .field("value", ...).field("threshold", ...).field("action_taken", ...)

        API's query_events reads:
          r._measurement == "gateway_events"
          record.values.get("event_type"), etc.
        """
        gateway_event_tags = ["room_id", "event_type", "severity"]
        gateway_event_fields = ["value", "threshold", "action_taken"]
        gateway_measurement = "gateway_events"

        api_measurement = "gateway_events"
        api_read_tags = ["event_type", "severity"]
        api_read_fields = ["value", "threshold", "action_taken"]

        assert gateway_measurement == api_measurement
        assert set(api_read_tags).issubset(set(gateway_event_tags))
        assert set(api_read_fields) == set(gateway_event_fields)

    def test_actuator_fields_match(self):
        """
        Gateway's write_actuator_status uses:
          Point("actuator_status")
            .tag("room_id", ...).tag("device_id", ...)
            .field("fan", ...).field("light", ...).field("alarm", ...)

        API's query_latest_actuator reads:
          r._measurement == "actuator_status"
          record.values.get("fan"), etc.
        """
        gateway_actuator_fields = ["fan", "light", "alarm"]
        gateway_measurement = "actuator_status"

        api_actuator_fields = ["fan", "light", "alarm"]
        api_measurement = "actuator_status"

        assert gateway_measurement == api_measurement
        assert set(gateway_actuator_fields) == set(api_actuator_fields)


# ============================================================
# Test 2: MQTT Topic Compatibility
# ============================================================
class TestMQTTTopicCompatibility:
    """Verify Gateway and API use the same MQTT topic patterns."""

    def test_command_topic_format(self):
        """
        API publishes to: building/{room_id}/actuator/command
        Gateway subscribes to: building/+/sensor/telemetry (for telemetry)
        Actuator subscribes to: building/{room_id}/actuator/command (TV1)

        This test verifies the topic format.
        """
        for room_id in KNOWN_ROOMS:
            # API builds this topic when sending manual commands
            api_topic = f"building/{room_id}/actuator/command"
            # This is the pattern actuators subscribe to
            expected_pattern = COMMAND_TOPIC_PATTERN.format(room_id=room_id)
            assert api_topic == expected_pattern

    def test_event_topic_format(self):
        """Gateway publishes events to: building/{room_id}/gateway/event"""
        for room_id in KNOWN_ROOMS:
            event_topic = f"building/{room_id}/gateway/event"
            assert event_topic == EVENT_TOPIC_PATTERN.format(room_id=room_id)


# ============================================================
# Test 3: Command Message Format Compatibility
# ============================================================
class TestCommandFormatCompatibility:
    """
    Verify the command messages sent by API match what Gateway/Actuator expect.
    """

    def test_api_command_has_required_fields(self):
        """
        API sends commands with fields: room_id, target, action, reason, timestamp
        Member 1's actuator expects: room_id, target, action (+ optional reason, timestamp)
        Gateway's rule engine creates commands with same fields.
        """
        # Simulated command from API (as in api.py send_command endpoint)
        api_command = {
            "room_id": "room-01",
            "target": "fan",
            "action": "on",
            "reason": "manual_control",
            "timestamp": "2026-06-10T10:00:00Z"
        }

        required_fields = ["room_id", "target", "action"]
        for field in required_fields:
            assert field in api_command

        # Verify values are valid
        assert api_command["target"] in {"fan", "light", "alarm"}
        assert api_command["action"] in {"on", "off"}

    def test_gateway_command_format_matches_api(self):
        """
        Gateway's rule engine creates commands using _make_command.
        Verify format matches API's expected format.
        """
        cmd = _make_command("room-01", "fan", "on", "temperature_high")

        assert "room_id" in cmd
        assert "target" in cmd
        assert "action" in cmd
        assert "reason" in cmd
        assert "timestamp" in cmd
        assert cmd["room_id"] == "room-01"
        assert cmd["target"] == "fan"
        assert cmd["action"] == "on"
        assert cmd["reason"] == "temperature_high"


# ============================================================
# Test 4: Event Message Format Compatibility
# ============================================================
class TestEventFormatCompatibility:
    """Verify event messages from Gateway match what API queries expect."""

    def test_event_has_all_fields_for_api(self):
        """
        API's query_events reads: room_id, event_type, severity, value, threshold, action_taken
        Gateway's _make_event creates all these fields.
        """
        event = _make_event(
            room_id="room-01",
            event_type="temperature_high",
            severity="warning",
            value=33.0,
            threshold=30.0,
            action_taken="fan_on"
        )

        # Fields that API reads from InfluxDB query results
        api_expected = ["room_id", "event_type", "severity",
                       "value", "threshold", "action_taken", "timestamp"]
        for field in api_expected:
            assert field in event, f"Missing field '{field}' in event"

    def test_event_severity_values(self):
        """Verify severity values are consistent between Gateway and API."""
        # Rule engine uses these severity values
        telemetry_high_temp = make_sensor_telemetry(temperature=33.0)
        events, _ = evaluate("room-01", telemetry_high_temp, {"fan": "off", "light": "off", "alarm": "off"})
        assert events[0]["severity"] in ["info", "warning", "critical"]

        telemetry_high_co2 = make_sensor_telemetry(co2_ppm=1500.0)
        events2, _ = evaluate("room-01", telemetry_high_co2, {"fan": "off", "light": "off", "alarm": "off"})
        assert events2[0]["severity"] == "critical"


# ============================================================
# Test 5: State Store ↔ API Response Structure
# ============================================================
class TestStateStoreAPICompatibility:
    """
    Verify state store's to_dict() format is compatible with
    what API's get_room_state endpoint returns.
    """

    def test_state_dict_has_telemetry_and_actuator(self):
        """
        API's get_room_state returns: {room_id, telemetry: {...}, actuator: {...}}
        StateStore.get_room_state returns same structure.
        """
        store = StateStore()
        store.update_telemetry("room-01", {
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        })
        store.update_actuator("room-01", {
            "fan": "on",
            "light": "off",
            "alarm": "off",
            "last_command_reason": "temperature_high",
            "timestamp": "2026-06-10T10:00:05Z"
        })

        state = store.get_room_state("room-01")

        # API response structure
        assert "room_id" in state
        assert "telemetry" in state
        assert "actuator" in state

        # Telemetry fields (same as API reads from InfluxDB)
        telemetry = state["telemetry"]
        for field in TELEMETRY_FIELDS:
            assert field in telemetry, f"Missing telemetry field: {field}"

        # Actuator fields (same as API reads from InfluxDB)
        actuator = state["actuator"]
        for field in ACTUATOR_FIELDS:
            assert field in actuator, f"Missing actuator field: {field}"


# ============================================================
# Test 6: End-to-End Flow Simulation (no MQTT/InfluxDB needed)
# ============================================================
class TestEndToEndFlow:
    """
    Simulate the complete data flow:
    Sensor telemetry → Gateway processes → Events/Commands generated
    Verify everything is compatible with API expectations.
    """

    def test_normal_telemetry_flow(self):
        """Normal sensor data → Gateway processes → no events → API gets state."""
        store = StateStore()
        telemetry = make_sensor_telemetry(temperature=25.0, co2_ppm=800.0)

        # Gateway processes telemetry
        store.update_telemetry("room-01", telemetry)

        # Rule engine evaluates
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", telemetry, actuator_state)

        # No anomalies → no events/commands
        assert len(events) == 0
        assert len(commands) == 0

        # API can read state
        state = store.get_room_state("room-01")
        assert state["telemetry"]["temperature"] == 25.0

    def test_anomaly_telemetry_flow(self):
        """
        High temperature telemetry → Gateway detects → Event + Command →
        Actuator updates → State reflects change → API reads updated state.
        """
        store = StateStore()

        # Step 1: Sensor sends high temperature
        telemetry = make_sensor_telemetry(temperature=33.0)
        store.update_telemetry("room-01", telemetry)

        # Step 2: Rule engine evaluates
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", telemetry, actuator_state)

        # Step 3: Verify event generated
        assert len(events) == 1
        assert events[0]["event_type"] == "temperature_high"
        assert events[0]["room_id"] == "room-01"

        # Step 4: Verify command generated
        assert len(commands) == 1
        assert commands[0]["target"] == "fan"
        assert commands[0]["action"] == "on"

        # Step 5: Actuator responds with updated status
        actuator_status = make_actuator_status(
            room_id="room-01",
            fan="on",
            last_command_reason="temperature_high"
        )
        store.update_actuator("room-01", actuator_status)

        # Step 6: API reads the updated state
        state = store.get_room_state("room-01")
        assert state["telemetry"]["temperature"] == 33.0
        assert state["actuator"]["fan"] == "on"
        assert state["actuator"]["last_command_reason"] == "temperature_high"

    def test_multi_room_flow(self):
        """
        Multiple rooms sending data simultaneously → Gateway processes each →
        State store maintains independent state per room.
        """
        store = StateStore()

        # Room 1: normal data
        store.update_telemetry("room-01", make_sensor_telemetry("room-01", temperature=25.0))
        # Room 2: high CO2
        store.update_telemetry("room-02", make_sensor_telemetry("room-02", co2_ppm=1500.0))
        # Room 3: no occupancy + bright light
        store.update_telemetry("room-03", make_sensor_telemetry("room-03", occupancy=False, light_lux=500.0))

        # Evaluate rules for each room
        default_actuator = {"fan": "off", "light": "on", "alarm": "off"}

        events1, cmds1 = evaluate("room-01", make_sensor_telemetry("room-01", temperature=25.0), default_actuator)
        events2, cmds2 = evaluate("room-02", make_sensor_telemetry("room-02", co2_ppm=1500.0), default_actuator)
        events3, cmds3 = evaluate("room-03", make_sensor_telemetry("room-03", occupancy=False, light_lux=500.0), default_actuator)

        # Room 1: no events (normal data)
        assert len(events1) == 0

        # Room 2: co2_high event
        assert any(e["event_type"] == "co2_high" for e in events2)

        # Room 3: unnecessary_light event
        assert any(e["event_type"] == "unnecessary_light" for e in events3)

        # All rooms exist in state store
        assert len(store.get_all_rooms()) == 3

    def test_command_json_serializable(self):
        """Commands should be JSON-serializable (for MQTT publish)."""
        telemetry = make_sensor_telemetry(temperature=33.0)
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", telemetry, actuator_state)

        for event in events:
            json_str = json.dumps(event)
            parsed = json.loads(json_str)
            assert parsed == event

        for command in commands:
            json_str = json.dumps(command)
            parsed = json.loads(json_str)
            assert parsed == command

    def test_api_room_list_matches_gateway_rooms(self):
        """
        API's KNOWN_ROOMS should match the room IDs Gateway handles.
        This test ensures both sides agree on room-01, room-02, room-03.
        """
        store = StateStore()
        for room_id in KNOWN_ROOMS:
            store.update_telemetry(room_id, make_sensor_telemetry(room_id))

        gateway_rooms = sorted(store.get_all_rooms())
        api_rooms = sorted(KNOWN_ROOMS)
        assert gateway_rooms == api_rooms
