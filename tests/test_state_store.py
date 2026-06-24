"""
Unit tests for the State Store.
Run: python -m pytest tests/test_state_store.py -v

Tests thread-safe state management for room telemetry and actuator status.
"""

import sys
import os

# Add iot_gateway to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "iot_gateway"))

from state_store import StateStore, RoomState


# Tests for RoomState
class TestRoomState:

    def test_initial_state(self):
        """A new room should have None telemetry and off actuators."""
        room = RoomState("room-01")
        assert room.room_id == "room-01"
        assert room.temperature is None
        assert room.humidity is None
        assert room.fan == "off"
        assert room.light == "off"
        assert room.alarm == "off"

    def test_update_telemetry(self):
        """Updating telemetry should set all sensor fields."""
        room = RoomState("room-01")
        data = {
            "temperature": 25.5,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        }
        room.update_telemetry(data)

        assert room.temperature == 25.5
        assert room.humidity == 60.0
        assert room.light_lux == 400.0
        assert room.co2_ppm == 800.0
        assert room.occupancy is True
        assert room.last_telemetry_time == "2026-06-10T10:00:00Z"

    def test_update_actuator(self):
        """Updating actuator should set fan/light/alarm states."""
        room = RoomState("room-01")
        data = {
            "fan": "on",
            "light": "off",
            "alarm": "on",
            "last_command_reason": "temperature_high",
            "timestamp": "2026-06-10T10:00:05Z"
        }
        room.update_actuator(data)

        assert room.fan == "on"
        assert room.light == "off"
        assert room.alarm == "on"
        assert room.last_command_reason == "temperature_high"

    def test_to_dict(self):
        """to_dict should return complete room state."""
        room = RoomState("room-01")
        room.update_telemetry({
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        })
        room.update_actuator({
            "fan": "on",
            "light": "off",
            "alarm": "off",
            "last_command_reason": "temperature_high",
            "timestamp": "2026-06-10T10:00:05Z"
        })

        result = room.to_dict()
        assert result["room_id"] == "room-01"
        assert result["telemetry"]["temperature"] == 25.0
        assert result["actuator"]["fan"] == "on"

    def test_partial_actuator_update(self):
        """Updating only some actuator fields should preserve others."""
        room = RoomState("room-01")
        room.update_actuator({"fan": "on"})
        assert room.fan == "on"
        assert room.light == "off"  # default preserved
        assert room.alarm == "off"  # default preserved


# Tests for StateStore
class TestStateStore:

    def test_empty_store(self):
        """New store should have no rooms."""
        store = StateStore()
        assert store.get_all_rooms() == []
        assert store.get_room_state("room-01") is None

    def test_update_creates_room(self):
        """Updating telemetry for a new room should auto-create it."""
        store = StateStore()
        store.update_telemetry("room-01", {
            "temperature": 25.0,
            "humidity": 60.0,
            "light_lux": 400.0,
            "co2_ppm": 800.0,
            "occupancy": True,
            "timestamp": "2026-06-10T10:00:00Z"
        })

        assert "room-01" in store.get_all_rooms()
        state = store.get_room_state("room-01")
        assert state is not None
        assert state["telemetry"]["temperature"] == 25.0

    def test_multiple_rooms(self):
        """Store should handle multiple rooms independently."""
        store = StateStore()
        store.update_telemetry("room-01", {"temperature": 25.0, "humidity": 60.0,
                                           "light_lux": 400.0, "co2_ppm": 800.0,
                                           "occupancy": True, "timestamp": "t1"})
        store.update_telemetry("room-02", {"temperature": 30.0, "humidity": 70.0,
                                           "light_lux": 500.0, "co2_ppm": 900.0,
                                           "occupancy": False, "timestamp": "t2"})

        rooms = store.get_all_rooms()
        assert len(rooms) == 2
        assert "room-01" in rooms
        assert "room-02" in rooms

        state1 = store.get_room_state("room-01")
        state2 = store.get_room_state("room-02")
        assert state1["telemetry"]["temperature"] == 25.0
        assert state2["telemetry"]["temperature"] == 30.0

    def test_update_actuator_creates_room(self):
        """Updating actuator for a new room should auto-create it."""
        store = StateStore()
        store.update_actuator("room-01", {
            "fan": "on",
            "light": "off",
            "alarm": "off",
            "timestamp": "2026-06-10T10:00:05Z"
        })

        state = store.get_room_state("room-01")
        assert state is not None
        assert state["actuator"]["fan"] == "on"

    def test_get_all_states(self):
        """get_all_states should return dict of all room states."""
        store = StateStore()
        store.update_telemetry("room-01", {"temperature": 25.0, "humidity": 60.0,
                                           "light_lux": 400.0, "co2_ppm": 800.0,
                                           "occupancy": True, "timestamp": "t1"})
        store.update_telemetry("room-02", {"temperature": 30.0, "humidity": 70.0,
                                           "light_lux": 500.0, "co2_ppm": 900.0,
                                           "occupancy": False, "timestamp": "t2"})

        all_states = store.get_all_states()
        assert len(all_states) == 2
        assert "room-01" in all_states
        assert "room-02" in all_states

    def test_nonexistent_room_returns_none(self):
        """Getting state of nonexistent room should return None."""
        store = StateStore()
        assert store.get_room_state("room-99") is None

    def test_overwrite_telemetry(self):
        """Updating telemetry twice should overwrite previous values."""
        store = StateStore()
        store.update_telemetry("room-01", {"temperature": 25.0, "humidity": 60.0,
                                           "light_lux": 400.0, "co2_ppm": 800.0,
                                           "occupancy": True, "timestamp": "t1"})
        store.update_telemetry("room-01", {"temperature": 33.0, "humidity": 70.0,
                                           "light_lux": 500.0, "co2_ppm": 1500.0,
                                           "occupancy": False, "timestamp": "t2"})

        state = store.get_room_state("room-01")
        assert state["telemetry"]["temperature"] == 33.0
        assert state["telemetry"]["co2_ppm"] == 1500.0
        assert state["telemetry"]["occupancy"] is False
