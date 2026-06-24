"""
Virtual Actuator for Smart Building IoT System.
Simulates actuators (fan, light, alarm) for a room in a smart building.
Receives commands via MQTT and publishes status updates.

Features:
- Validates incoming command messages (target, action, room_id)
- Maintains internal state (fan, light, alarm)
- Publishes status updates after each command
- Logs clearly for both valid and invalid commands
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# Configuration from environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ROOM_ID = os.getenv("ROOM_ID", "room-01")
DEVICE_ID = os.getenv("DEVICE_ID", f"actuator-{ROOM_ID}")

# MQTT topics
COMMAND_TOPIC = f"building/{ROOM_ID}/actuator/command"
STATUS_TOPIC = f"building/{ROOM_ID}/actuator/status"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(DEVICE_ID)


# Actuator State Manager
class ActuatorState:
    """Manages the internal state of actuator devices (fan, light, alarm)."""

    VALID_TARGETS = {"fan", "light", "alarm"}
    VALID_ACTIONS = {"on", "off"}

    def __init__(self):
        self.fan = "off"
        self.light = "off"
        self.alarm = "off"
        self.last_command_reason = ""

    def apply_command(self, target: str, action: str, reason: str) -> bool:
        """
        Apply a command to the actuator.
        Returns True if the command was valid and applied, False otherwise.
        """
        if target not in self.VALID_TARGETS:
            logger.error(f" Invalid target: '{target}'. "
                        f"Valid: {self.VALID_TARGETS}")
            return False

        if action not in self.VALID_ACTIONS:
            logger.error(f" Invalid action: '{action}'. "
                        f"Valid: {self.VALID_ACTIONS}")
            return False

        old_value = getattr(self, target)
        setattr(self, target, action)
        self.last_command_reason = reason

        if old_value != action:
            logger.info(f" {target.upper()}: {old_value} → {action} "
                       f"(reason: {reason})")
        else:
            logger.info(f"ℹ️ {target.upper()} already {action} "
                       f"(reason: {reason})")

        return True

    def to_status_message(self) -> dict:
        """Generate a status message dictionary matching shared contract."""
        return {
            "device_id": DEVICE_ID,
            "room_id": ROOM_ID,
            "fan": self.fan,
            "light": self.light,
            "alarm": self.alarm,
            "last_command_reason": self.last_command_reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# Global state
actuator_state = ActuatorState()


# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f" Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe to command topic
        client.subscribe(COMMAND_TOPIC, qos=1)
        logger.info(f" Subscribed to: {COMMAND_TOPIC}")
    else:
        logger.error(f" Failed to connect, return code: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    logger.warning(f"️ Disconnected (rc={rc}). Will auto-reconnect.")


def on_message(client, userdata, msg):
    """Handle incoming command messages."""
    try:
        payload = msg.payload.decode("utf-8")
        logger.info(f" Received command on {msg.topic}: {payload}")

        command = json.loads(payload)

        # Validate required fields
        required_fields = ["room_id", "target", "action"]
        for field in required_fields:
            if field not in command:
                logger.error(f" Missing required field: '{field}' in command")
                return

        # Validate room_id matches
        if command["room_id"] != ROOM_ID:
            logger.warning(f"️ Command for {command['room_id']}, "
                          f"but I am {ROOM_ID}. Ignoring.")
            return

        # Apply the command
        target = command["target"]
        action = command["action"]
        reason = command.get("reason", "unknown")

        success = actuator_state.apply_command(target, action, reason)

        if success:
            # Publish updated status
            status = actuator_state.to_status_message()
            status_payload = json.dumps(status)
            client.publish(STATUS_TOPIC, status_payload, qos=1)
            logger.info(f" Published status to {STATUS_TOPIC}")

    except json.JSONDecodeError:
        logger.error(f" Invalid JSON received: {msg.payload}")
    except Exception as e:
        logger.error(f" Error processing command: {e}")


# Main
def main():
    logger.info(f"Starting Virtual Actuator: {DEVICE_ID} for {ROOM_ID}")
    logger.info(f"Listening on topic: {COMMAND_TOPIC}")
    logger.info(f"Publishing status to: {STATUS_TOPIC}")

    client = mqtt.Client(
        client_id=DEVICE_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Auto-reconnect with exponential backoff
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # Connect with retry
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            logger.error(f"Connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

    # Block forever, processing MQTT messages
    logger.info("Actuator is running. Waiting for commands...")
    client.loop_forever()


if __name__ == "__main__":
    main()
