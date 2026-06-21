"""
State Store for IoT Gateway.
Maintains the latest state of each room (telemetry + actuator status).
Thread-safe for concurrent access from MQTT callbacks.
"""

import threading
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("state_store")


class RoomState:
    """Represents the latest known state of a room."""

    def __init__(self, room_id: str):
        self.room_id = room_id

        # Latest telemetry
        self.temperature: Optional[float] = None
        self.humidity: Optional[float] = None
        self.light_lux: Optional[float] = None
        self.co2_ppm: Optional[float] = None
        self.occupancy: Optional[bool] = None
        self.last_telemetry_time: Optional[str] = None

        # Latest actuator status
        self.fan: str = "off"
        self.light: str = "off"
        self.alarm: str = "off"
        self.last_command_reason: str = ""
        self.last_actuator_time: Optional[str] = None

    def update_telemetry(self, data: dict):
        """Update room state with new telemetry data."""
        self.temperature = data.get("temperature")
        self.humidity = data.get("humidity")
        self.light_lux = data.get("light_lux")
        self.co2_ppm = data.get("co2_ppm")
        self.occupancy = data.get("occupancy")
        self.last_telemetry_time = data.get("timestamp",
                                            datetime.now(timezone.utc).isoformat())

    def update_actuator(self, data: dict):
        """Update room state with new actuator status."""
        self.fan = data.get("fan", self.fan)
        self.light = data.get("light", self.light)
        self.alarm = data.get("alarm", self.alarm)
        self.last_command_reason = data.get("last_command_reason",
                                            self.last_command_reason)
        self.last_actuator_time = data.get("timestamp",
                                           datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        """Export current state as dictionary."""
        return {
            "room_id": self.room_id,
            "telemetry": {
                "temperature": self.temperature,
                "humidity": self.humidity,
                "light_lux": self.light_lux,
                "co2_ppm": self.co2_ppm,
                "occupancy": self.occupancy,
                "timestamp": self.last_telemetry_time,
            },
            "actuator": {
                "fan": self.fan,
                "light": self.light,
                "alarm": self.alarm,
                "last_command_reason": self.last_command_reason,
                "timestamp": self.last_actuator_time,
            }
        }


class StateStore:
    """
    Thread-safe store for room states.
    Used by both gateway (write) and API (read).
    """

    def __init__(self):
        self._rooms: dict[str, RoomState] = {}
        self._lock = threading.Lock()

    def update_telemetry(self, room_id: str, data: dict):
        """Update telemetry for a room. Creates room if not exists."""
        with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState(room_id)
            self._rooms[room_id].update_telemetry(data)
            logger.debug(f"Updated telemetry for {room_id}")

    def update_actuator(self, room_id: str, data: dict):
        """Update actuator status for a room. Creates room if not exists."""
        with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState(room_id)
            self._rooms[room_id].update_actuator(data)
            logger.debug(f"Updated actuator status for {room_id}")

    def get_room_state(self, room_id: str) -> Optional[dict]:
        """Get the latest state of a room as dictionary."""
        with self._lock:
            room = self._rooms.get(room_id)
            return room.to_dict() if room else None

    def get_all_rooms(self) -> list[str]:
        """Get list of all known room IDs."""
        with self._lock:
            return list(self._rooms.keys())

    def get_all_states(self) -> dict:
        """Get all room states as dictionary."""
        with self._lock:
            return {rid: room.to_dict() for rid, room in self._rooms.items()}
