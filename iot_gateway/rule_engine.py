"""
Rule Engine for IoT Gateway.
Evaluates telemetry data against predefined rules.
Returns lists of events and commands to execute.

Designed to be extensible — add new rules by appending to RULES list.

Rules (mandatory):
    1. temperature > 30  → fan ON
    2. temperature < 27  → fan OFF
    3. co2_ppm > 1200    → alarm ON
    4. occupancy == false AND light_lux > 300 → light OFF
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("rule_engine")


class RuleResult:
    """Result of evaluating a single rule."""

    def __init__(self, triggered: bool, event: Optional[dict] = None,
                 command: Optional[dict] = None):
        self.triggered = triggered
        self.event = event
        self.command = command


def _make_event(room_id: str, event_type: str, severity: str,
                value: float, threshold: float, action_taken: str) -> dict:
    """Helper to create an event message following shared contract format."""
    return {
        "room_id": room_id,
        "event_type": event_type,
        "severity": severity,
        "value": value,
        "threshold": threshold,
        "action_taken": action_taken,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def _make_command(room_id: str, target: str, action: str,
                  reason: str) -> dict:
    """Helper to create a command message following shared contract format."""
    return {
        "room_id": room_id,
        "target": target,
        "action": action,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# Rule Definitions

def rule_temperature_high(room_id: str, data: dict,
                          actuator_state: dict) -> RuleResult:
    """Rule 1: If temperature > 30, turn ON fan."""
    temp = data.get("temperature", 0)
    threshold = 30.0

    if temp > threshold:
        # Only trigger if fan is not already ON
        if actuator_state.get("fan") != "on":
            logger.info(f" Rule triggered: temperature_high in {room_id} "
                       f"(value={temp}, threshold={threshold})")
            return RuleResult(
                triggered=True,
                event=_make_event(room_id, "temperature_high", "warning",
                                  temp, threshold, "fan_on"),
                command=_make_command(room_id, "fan", "on",
                                     "temperature_high")
            )
    return RuleResult(triggered=False)


def rule_temperature_low(room_id: str, data: dict,
                         actuator_state: dict) -> RuleResult:
    """Rule 2: If temperature < 27, turn OFF fan."""
    temp = data.get("temperature", 30)
    threshold = 27.0

    if temp < threshold:
        if actuator_state.get("fan") != "off":
            logger.info(f"️ Rule triggered: temperature_low in {room_id} "
                       f"(value={temp}, threshold={threshold})")
            return RuleResult(
                triggered=True,
                event=_make_event(room_id, "temperature_low", "info",
                                  temp, threshold, "fan_off"),
                command=_make_command(room_id, "fan", "off",
                                     "temperature_low")
            )
    return RuleResult(triggered=False)


def rule_co2_high(room_id: str, data: dict,
                  actuator_state: dict) -> RuleResult:
    """Rule 3: If co2_ppm > 1200, turn ON alarm."""
    co2 = data.get("co2_ppm", 0)
    threshold = 1200.0

    if co2 > threshold:
        if actuator_state.get("alarm") != "on":
            logger.warning(f" Rule triggered: co2_high in {room_id} "
                          f"(value={co2}, threshold={threshold})")
            return RuleResult(
                triggered=True,
                event=_make_event(room_id, "co2_high", "critical",
                                  co2, threshold, "alarm_on"),
                command=_make_command(room_id, "alarm", "on", "co2_high")
            )
    return RuleResult(triggered=False)


def rule_unnecessary_light(room_id: str, data: dict,
                           actuator_state: dict) -> RuleResult:
    """Rule 4: If occupancy==false AND light_lux > 300, turn OFF light."""
    occupancy = data.get("occupancy", True)
    light_lux = data.get("light_lux", 0)
    threshold = 300.0

    if not occupancy and light_lux > threshold:
        if actuator_state.get("light") != "off":
            logger.info(f" Rule triggered: unnecessary_light in {room_id} "
                       f"(occupancy=false, light_lux={light_lux})")
            return RuleResult(
                triggered=True,
                event=_make_event(room_id, "unnecessary_light", "info",
                                  light_lux, threshold, "light_off"),
                command=_make_command(room_id, "light", "off",
                                     "unnecessary_light")
            )
    return RuleResult(triggered=False)


# Rules Registry (extensible — just append new functions)
RULES = [
    rule_temperature_high,
    rule_temperature_low,
    rule_co2_high,
    rule_unnecessary_light,
]


# Main evaluation function
def evaluate(room_id: str, telemetry_data: dict,
             actuator_state: dict) -> tuple[list[dict], list[dict]]:
    """
    Evaluate all rules against the given telemetry data.

    Args:
        room_id: The room identifier
        telemetry_data: Latest sensor data for the room
        actuator_state: Current actuator state {"fan": "on/off", ...}

    Returns:
        Tuple of (events_list, commands_list)
    """
    events = []
    commands = []

    for rule_fn in RULES:
        result = rule_fn(room_id, telemetry_data, actuator_state)
        if result.triggered:
            if result.event:
                events.append(result.event)
            if result.command:
                commands.append(result.command)

    return events, commands
