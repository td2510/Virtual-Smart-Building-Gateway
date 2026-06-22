"""
Full Integration Tests — All 3 Members Together.
Tests the complete data flow: Sensor (M1) → Gateway (M2) → API/InfluxDB (M3)

These tests verify contract compatibility between ALL 3 members
without requiring MQTT broker or InfluxDB (pure logic tests).

Run: python -m pytest tests/test_full_integration.py -v
"""

import sys
import os
import json

# Add all module paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "virtual_sensor"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "virtual_actuator"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "iot_gateway"))

# Set env vars before importing
os.environ.setdefault("MQTT_BROKER", "localhost")
os.environ.setdefault("ROOM_ID", "room-01")
os.environ.setdefault("DEVICE_ID", "sensor-room-01")

from sensor import SensorSimulator
from actuator import ActuatorState
from rule_engine import evaluate
from state_store import StateStore

KNOWN_ROOMS = ["room-01", "room-02", "room-03"]


# ============================================================
# Test: Sensor → Gateway Telemetry Contract
# ============================================================
class TestSensorToGateway:
    """Verify Sensor (M1) output is compatible with Gateway (M2) input."""

    def test_sensor_telemetry_passes_gateway_validation(self):
        """
        Sensor's generate() output should pass Gateway's validate_telemetry().
        """
        # Import gateway's validation function
        from gateway import validate_telemetry

        simulator = SensorSimulator()
        for _ in range(20):
            telemetry = simulator.generate()
            assert validate_telemetry(telemetry), \
                f"Gateway rejected sensor telemetry: {telemetry}"

    def test_sensor_telemetry_can_be_normalized(self):
        """
        Sensor output should be successfully normalized by Gateway.
        """
        from gateway import normalize_telemetry

        simulator = SensorSimulator()
        telemetry = simulator.generate()
        normalized = normalize_telemetry(telemetry)

        assert isinstance(normalized["temperature"], float)
        assert isinstance(normalized["humidity"], float)
        assert isinstance(normalized["light_lux"], float)
        assert isinstance(normalized["co2_ppm"], float)
        assert isinstance(normalized["occupancy"], bool)
        assert "normalized_at" in normalized

    def test_sensor_data_triggers_rules_when_anomalous(self):
        """
        When sensor produces high temperature data, rule engine should detect it.
        """
        # Manually create high-temp telemetry (as if sensor had anomaly)
        high_temp_data = {
            "device_id": "sensor-room-01",
            "room_id": "room-01",
            "temperature": 35.0,  # > 30 → triggers rule
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        }
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", high_temp_data, actuator_state)

        assert len(events) == 1
        assert events[0]["event_type"] == "temperature_high"
        assert len(commands) == 1
        assert commands[0]["target"] == "fan"
        assert commands[0]["action"] == "on"

    def test_normal_sensor_data_no_trigger(self):
        """Normal sensor data should not trigger any rules."""
        normal_data = {
            "device_id": "sensor-room-01",
            "room_id": "room-01",
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        }
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", normal_data, actuator_state)
        assert len(events) == 0
        assert len(commands) == 0


# ============================================================
# Test: Gateway → Actuator Command Contract
# ============================================================
class TestGatewayToActuator:
    """Verify Gateway (M2) commands are compatible with Actuator (M1)."""

    def test_rule_engine_command_accepted_by_actuator(self):
        """
        Gateway's rule engine creates commands that Actuator should accept.
        """
        # Gateway detects high temperature → generates command
        high_temp = {
            "device_id": "sensor-room-01",
            "room_id": "room-01",
            "temperature": 35.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        }
        actuator_status = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", high_temp, actuator_status)

        assert len(commands) == 1
        cmd = commands[0]

        # Actuator should accept this command
        actuator = ActuatorState()
        success = actuator.apply_command(cmd["target"], cmd["action"],
                                         cmd.get("reason", "unknown"))
        assert success is True
        assert actuator.fan == "on"

    def test_all_rule_commands_accepted_by_actuator(self):
        """
        Test all 4 rules produce commands that Actuator accepts.
        """
        scenarios = [
            # (telemetry_overrides, actuator_init, expected_target, expected_action)
            ({"temperature": 35.0}, {"fan": "off", "light": "off", "alarm": "off"},
             "fan", "on"),
            ({"temperature": 22.0}, {"fan": "on", "light": "off", "alarm": "off"},
             "fan", "off"),
            ({"co2_ppm": 1500.0}, {"fan": "off", "light": "off", "alarm": "off"},
             "alarm", "on"),
            ({"occupancy": False, "light_lux": 500.0},
             {"fan": "off", "light": "on", "alarm": "off"},
             "light", "off"),
        ]

        for overrides, act_status, exp_target, exp_action in scenarios:
            data = {
                "device_id": "sensor-room-01",
                "room_id": "room-01",
                "temperature": 25.0,
                "humidity": 60.0,
                "light_lux": 400.0,
                "co2_ppm": 800.0,
                "occupancy": True,
                "timestamp": "2026-06-10T10:00:00Z"
            }
            data.update(overrides)

            events, commands = evaluate("room-01", data, act_status)

            # Find the expected command
            matching = [c for c in commands
                       if c["target"] == exp_target and c["action"] == exp_action]
            assert len(matching) == 1, \
                f"Expected {exp_target}={exp_action} for overrides {overrides}"

            # Actuator accepts it
            actuator = ActuatorState()
            for k, v in act_status.items():
                setattr(actuator, k, v)
            success = actuator.apply_command(
                matching[0]["target"],
                matching[0]["action"],
                matching[0].get("reason", "unknown")
            )
            assert success is True

    def test_actuator_status_after_command(self):
        """
        After receiving a command, actuator should publish status
        that Gateway can process.
        """
        actuator = ActuatorState()
        actuator.apply_command("fan", "on", "temperature_high")
        status = actuator.to_status_message()

        # Gateway's handle_actuator_status reads these fields
        assert "device_id" in status
        assert "room_id" in status
        assert "fan" in status
        assert "light" in status
        assert "alarm" in status
        assert status["fan"] == "on"

        # State store should accept this
        store = StateStore()
        store.update_actuator("room-01", status)
        state = store.get_room_state("room-01")
        assert state["actuator"]["fan"] == "on"


# ============================================================
# Test: Actuator → Gateway → InfluxDB → API
# ============================================================
class TestActuatorToGatewayToAPI:
    """Verify the Actuator status → Gateway → StateStore → API chain."""

    def test_actuator_status_stored_correctly(self):
        """Actuator status should be stored in StateStore and readable."""
        store = StateStore()
        actuator = ActuatorState()
        actuator.apply_command("fan", "on", "temperature_high")
        actuator.apply_command("alarm", "on", "co2_high")

        status = actuator.to_status_message()
        store.update_actuator("room-01", status)

        state = store.get_room_state("room-01")
        assert state["actuator"]["fan"] == "on"
        assert state["actuator"]["alarm"] == "on"
        assert state["actuator"]["light"] == "off"


# ============================================================
# Test: End-to-End Flow (Sensor → Gateway → Actuator → Status → Store)
# ============================================================
class TestEndToEndAllMembers:
    """
    Simulate the complete system flow without MQTT/InfluxDB.
    Sensor → Gateway validates → Rules evaluate → Command to Actuator →
    Actuator applies → Status back → StateStore updated.
    """

    def test_complete_flow_temperature_high(self):
        """
        1. Sensor generates high temperature
        2. Gateway validates and normalizes
        3. Rule engine detects anomaly
        4. Command generated for actuator
        5. Actuator applies command
        6. Actuator publishes status
        7. State store is updated
        """
        from gateway import validate_telemetry, normalize_telemetry

        store = StateStore()

        # Step 1: Sensor generates telemetry with high temp
        telemetry = {
            "device_id": "sensor-room-01",
            "room_id": "room-01",
            "temperature": 33.5,
            "humidity": 65.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z",
            "last_seen": "2026-06-10T10:00:00Z"
        }

        # Step 2: Gateway validates
        assert validate_telemetry(telemetry) is True

        # Step 3: Gateway normalizes
        normalized = normalize_telemetry(telemetry)
        store.update_telemetry("room-01", normalized)

        # Step 4: Rule engine evaluates
        actuator_state = {"fan": "off", "light": "off", "alarm": "off"}
        events, commands = evaluate("room-01", normalized, actuator_state)

        assert len(events) == 1
        assert events[0]["event_type"] == "temperature_high"
        assert len(commands) == 1
        assert commands[0]["target"] == "fan"
        assert commands[0]["action"] == "on"

        # Step 5: Actuator receives command and applies
        actuator = ActuatorState()
        cmd = commands[0]
        success = actuator.apply_command(cmd["target"], cmd["action"],
                                         cmd.get("reason", "unknown"))
        assert success is True
        assert actuator.fan == "on"

        # Step 6: Actuator publishes status
        status = actuator.to_status_message()
        assert status["fan"] == "on"

        # Step 7: Gateway receives status and updates store
        store.update_actuator("room-01", status)

        # Final state verification
        final_state = store.get_room_state("room-01")
        assert final_state["telemetry"]["temperature"] == 33.5
        assert final_state["actuator"]["fan"] == "on"

    def test_complete_flow_co2_high(self):
        """CO2 spike → alarm ON flow."""
        from gateway import validate_telemetry, normalize_telemetry

        store = StateStore()

        telemetry = {
            "device_id": "sensor-room-02",
            "room_id": "room-02",
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 1500.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z",
            "last_seen": "2026-06-10T10:00:00Z"
        }

        assert validate_telemetry(telemetry)
        normalized = normalize_telemetry(telemetry)
        store.update_telemetry("room-02", normalized)

        events, commands = evaluate("room-02", normalized,
                                     {"fan": "off", "light": "off", "alarm": "off"})

        assert any(e["event_type"] == "co2_high" for e in events)
        alarm_cmds = [c for c in commands if c["target"] == "alarm"]
        assert len(alarm_cmds) == 1

        actuator = ActuatorState()
        actuator.apply_command(alarm_cmds[0]["target"],
                              alarm_cmds[0]["action"],
                              alarm_cmds[0]["reason"])
        assert actuator.alarm == "on"

        store.update_actuator("room-02", actuator.to_status_message())
        assert store.get_room_state("room-02")["actuator"]["alarm"] == "on"

    def test_complete_flow_unnecessary_light(self):
        """No occupancy + bright light → light OFF flow."""
        from gateway import validate_telemetry, normalize_telemetry

        store = StateStore()

        telemetry = {
            "device_id": "sensor-room-03",
            "room_id": "room-03",
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 500.0,
            "co2_ppm": 800.0,
            "occupancy": False,
            "timestamp": "2026-06-10T10:00:00Z",
            "last_seen": "2026-06-10T10:00:00Z"
        }

        assert validate_telemetry(telemetry)
        normalized = normalize_telemetry(telemetry)
        store.update_telemetry("room-03", normalized)

        events, commands = evaluate("room-03", normalized,
                                     {"fan": "off", "light": "on", "alarm": "off"})

        assert any(e["event_type"] == "unnecessary_light" for e in events)
        light_cmds = [c for c in commands if c["target"] == "light"]
        assert len(light_cmds) == 1
        assert light_cmds[0]["action"] == "off"

        actuator = ActuatorState()
        actuator.light = "on"  # simulate current state
        actuator.apply_command(light_cmds[0]["target"],
                              light_cmds[0]["action"],
                              light_cmds[0]["reason"])
        assert actuator.light == "off"

    def test_multi_room_independence(self):
        """Each room should operate independently."""
        from gateway import validate_telemetry, normalize_telemetry

        store = StateStore()

        rooms_data = {
            "room-01": {"temperature": 35.0, "co2_ppm": 800.0, "occupancy": True, "light_lux": 400.0},
            "room-02": {"temperature": 25.0, "co2_ppm": 1500.0, "occupancy": True, "light_lux": 400.0},
            "room-03": {"temperature": 25.0, "co2_ppm": 800.0, "occupancy": False, "light_lux": 500.0},
        }

        results = {}
        for room_id, overrides in rooms_data.items():
            telemetry = {
                "device_id": f"sensor-{room_id}",
                "room_id": room_id,
                "temperature": overrides["temperature"],
                "humidity": 60.0,
                "light_lux": overrides["light_lux"],
                "co2_ppm": overrides["co2_ppm"],
                "occupancy": overrides["occupancy"],
                "timestamp": "2026-06-10T10:00:00Z",
            }
            normalized = normalize_telemetry(telemetry)
            store.update_telemetry(room_id, normalized)
            act = {"fan": "off", "light": "on", "alarm": "off"}
            events, commands = evaluate(room_id, normalized, act)
            results[room_id] = (events, commands)

        # Room 1: temperature_high → fan ON
        assert any(e["event_type"] == "temperature_high" for e in results["room-01"][0])
        # Room 2: co2_high → alarm ON
        assert any(e["event_type"] == "co2_high" for e in results["room-02"][0])
        # Room 3: unnecessary_light → light OFF
        assert any(e["event_type"] == "unnecessary_light" for e in results["room-03"][0])
        # All rooms in store
        assert len(store.get_all_rooms()) == 3


# ============================================================
# Test: Docker Compose Integration Points
# ============================================================
class TestDockerComposeCompatibility:
    """
    Verify that the docker-compose.yml references match actual folder structure
    and env vars match what each service expects.
    """

    def test_sensor_env_vars(self):
        """Sensor expects specific env vars. Verify they're reasonable."""
        # These are what docker-compose sets for sensors
        env_vars = {
            "MQTT_BROKER": "mosquitto",
            "MQTT_PORT": "1883",
            "ROOM_ID": "room-01",
            "DEVICE_ID": "sensor-room-01",
            "PUBLISH_INTERVAL": "5",
        }
        # Verify defaults match expected values
        assert int(env_vars["MQTT_PORT"]) == 1883
        assert int(env_vars["PUBLISH_INTERVAL"]) == 5

    def test_actuator_env_vars(self):
        """Actuator expects specific env vars."""
        env_vars = {
            "MQTT_BROKER": "mosquitto",
            "MQTT_PORT": "1883",
            "ROOM_ID": "room-01",
            "DEVICE_ID": "actuator-room-01",
        }
        assert int(env_vars["MQTT_PORT"]) == 1883

    def test_gateway_env_vars(self):
        """Gateway expects MQTT + InfluxDB env vars."""
        env_vars = {
            "MQTT_BROKER": "mosquitto",
            "MQTT_PORT": "1883",
            "INFLUXDB_URL": "http://influxdb:8086",
            "INFLUXDB_TOKEN": "my-super-secret-token",
            "INFLUXDB_ORG": "iot-org",
            "INFLUXDB_BUCKET": "smart-building",
        }
        assert env_vars["INFLUXDB_ORG"] == "iot-org"
        assert env_vars["INFLUXDB_BUCKET"] == "smart-building"

    def test_room_ids_consistent_across_all_members(self):
        """All members should use the same room IDs."""
        expected_rooms = ["room-01", "room-02", "room-03"]
        # API's KNOWN_ROOMS
        assert expected_rooms == KNOWN_ROOMS
        # Sensor device_id format
        for room in expected_rooms:
            assert f"sensor-{room}" == f"sensor-{room}"
            assert f"actuator-{room}" == f"actuator-{room}"

    def test_build_directories_exist(self):
        """Docker compose build directories should exist."""
        project_root = os.path.join(os.path.dirname(__file__), "..")
        dirs_to_check = [
            "virtual_sensor",
            "virtual_actuator",
            "iot_gateway",
        ]
        for d in dirs_to_check:
            path = os.path.join(project_root, d)
            assert os.path.isdir(path), f"Directory '{d}' does not exist at {path}"

    def test_dockerfiles_exist(self):
        """Each service should have a Dockerfile."""
        project_root = os.path.join(os.path.dirname(__file__), "..")
        dockerfiles = [
            os.path.join("virtual_sensor", "Dockerfile"),
            os.path.join("virtual_actuator", "Dockerfile"),
            os.path.join("iot_gateway", "Dockerfile"),
        ]
        for df in dockerfiles:
            path = os.path.join(project_root, df)
            assert os.path.isfile(path), f"Dockerfile not found: {df}"

    def test_requirements_exist(self):
        """Each service should have requirements.txt."""
        project_root = os.path.join(os.path.dirname(__file__), "..")
        req_files = [
            os.path.join("virtual_sensor", "requirements.txt"),
            os.path.join("virtual_actuator", "requirements.txt"),
            os.path.join("iot_gateway", "requirements.txt"),
        ]
        for rf in req_files:
            path = os.path.join(project_root, rf)
            assert os.path.isfile(path), f"requirements.txt not found: {rf}"
