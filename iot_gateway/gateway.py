"""
Virtual IoT Gateway for Smart Building.
Central component that:
- Receives telemetry from all room sensors via MQTT
- Validates and normalizes data
- Stores latest state per room
- Evaluates rules to detect anomalies
- Sends commands to actuators
- Writes telemetry, events, and actuator status to InfluxDB
"""

import os
import json
import time
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from rule_engine import evaluate
from state_store import StateStore

# ============================================================
# Configuration from environment variables
# ============================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "smart-building")

# MQTT topic patterns (wildcard subscription for all rooms)
TELEMETRY_TOPIC = "building/+/sensor/telemetry"
ACTUATOR_STATUS_TOPIC = "building/+/actuator/status"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("iot-gateway")

# ============================================================
# Global instances
# ============================================================
state_store = StateStore()
influx_client = None
write_api = None


# ============================================================
# InfluxDB Setup
# ============================================================
def init_influxdb():
    """Initialize InfluxDB client with retry logic."""
    global influx_client, write_api
    while True:
        try:
            influx_client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            write_api = influx_client.write_api(write_options=SYNCHRONOUS)
            # Test connection by pinging
            influx_client.ping()
            logger.info(f"✅ Connected to InfluxDB at {INFLUXDB_URL}")
            return
        except Exception as e:
            logger.error(f"InfluxDB connection failed: {e}. Retrying in 5s...")
            time.sleep(5)


def write_telemetry(room_id: str, device_id: str, data: dict):
    """Write telemetry data to InfluxDB (measurement: room_telemetry)."""
    try:
        point = (
            Point("room_telemetry")
            .tag("room_id", room_id)
            .tag("device_id", device_id)
            .field("temperature", float(data["temperature"]))
            .field("humidity", float(data["humidity"]))
            .field("light_lux", float(data["light_lux"]))
            .field("co2_ppm", float(data["co2_ppm"]))
            .field("occupancy", bool(data["occupancy"]))
        )
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        logger.debug(f"📊 Wrote telemetry for {room_id}")
    except Exception as e:
        logger.error(f"Failed to write telemetry: {e}")


def write_event(event: dict):
    """Write an anomaly event to InfluxDB (measurement: gateway_events)."""
    try:
        point = (
            Point("gateway_events")
            .tag("room_id", event["room_id"])
            .tag("event_type", event["event_type"])
            .tag("severity", event["severity"])
            .field("value", float(event["value"]))
            .field("threshold", float(event["threshold"]))
            .field("action_taken", str(event["action_taken"]))
        )
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        logger.debug(f"📊 Wrote event: {event['event_type']} for {event['room_id']}")
    except Exception as e:
        logger.error(f"Failed to write event: {e}")


def write_actuator_status(room_id: str, device_id: str, data: dict):
    """Write actuator status to InfluxDB (measurement: actuator_status)."""
    try:
        point = (
            Point("actuator_status")
            .tag("room_id", room_id)
            .tag("device_id", device_id)
            .field("fan", str(data.get("fan", "off")))
            .field("light", str(data.get("light", "off")))
            .field("alarm", str(data.get("alarm", "off")))
        )
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        logger.debug(f"📊 Wrote actuator status for {room_id}")
    except Exception as e:
        logger.error(f"Failed to write actuator status: {e}")


# ============================================================
# Message Validation & Normalization
# ============================================================
REQUIRED_TELEMETRY_FIELDS = [
    "device_id", "room_id", "temperature", "humidity",
    "light_lux", "co2_ppm", "occupancy", "timestamp"
]


def validate_telemetry(data: dict) -> bool:
    """Validate a telemetry message has all required fields and correct types."""
    for field in REQUIRED_TELEMETRY_FIELDS:
        if field not in data:
            logger.warning(f"⚠️ Missing field '{field}' in telemetry message")
            return False

    # Validate data types
    try:
        float(data["temperature"])
        float(data["humidity"])
        float(data["light_lux"])
        float(data["co2_ppm"])
        # occupancy should be boolean-like
        if not isinstance(data["occupancy"], bool):
            # Accept 0/1 as boolean
            if data["occupancy"] not in (0, 1, True, False):
                logger.warning(f"⚠️ Invalid occupancy value: {data['occupancy']}")
                return False
    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ Invalid data type in telemetry: {e}")
        return False

    return True


def normalize_telemetry(data: dict) -> dict:
    """Normalize telemetry data into a unified format with consistent types."""
    return {
        "device_id": str(data["device_id"]),
        "room_id": str(data["room_id"]),
        "temperature": round(float(data["temperature"]), 2),
        "humidity": round(float(data["humidity"]), 2),
        "light_lux": round(float(data["light_lux"]), 2),
        "co2_ppm": round(float(data["co2_ppm"]), 2),
        "occupancy": bool(data["occupancy"]),
        "timestamp": data.get("timestamp",
                              datetime.now(timezone.utc).isoformat()),
        "normalized_at": datetime.now(timezone.utc).isoformat()
    }


# ============================================================
# MQTT Callbacks
# ============================================================
def on_connect(client, userdata, flags, rc, properties=None):
    """Handle MQTT connection. Subscribe to telemetry and actuator status topics."""
    if rc == 0:
        logger.info(f"✅ Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        client.subscribe(ACTUATOR_STATUS_TOPIC, qos=1)
        logger.info(f"📥 Subscribed to: {TELEMETRY_TOPIC}")
        logger.info(f"📥 Subscribed to: {ACTUATOR_STATUS_TOPIC}")
    else:
        logger.error(f"❌ Connection failed (rc={rc})")


def on_disconnect(client, userdata, rc, properties=None):
    """Handle MQTT disconnection."""
    logger.warning(f"⚠️ Disconnected (rc={rc}). Reconnecting...")


def on_message(client, userdata, msg):
    """Route incoming messages to the appropriate handler."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        topic = msg.topic

        if "/sensor/telemetry" in topic:
            handle_telemetry(client, topic, payload)
        elif "/actuator/status" in topic:
            handle_actuator_status(client, topic, payload)
        else:
            logger.warning(f"Unknown topic: {topic}")

    except json.JSONDecodeError:
        logger.error(f"❌ Invalid JSON on {msg.topic}: {msg.payload}")
    except Exception as e:
        logger.error(f"❌ Error handling message on {msg.topic}: {e}")


def handle_telemetry(client, topic: str, data: dict):
    """
    Process incoming telemetry from a sensor.
    Pipeline: Validate → Normalize → Store → Write InfluxDB → Publish normalized →
              Evaluate rules → Process events → Send commands
    """
    room_id = data.get("room_id", "unknown")
    device_id = data.get("device_id", "unknown")

    logger.info(f"📩 Telemetry from {room_id}: temp={data.get('temperature')}, "
               f"co2={data.get('co2_ppm')}, occupancy={data.get('occupancy')}")

    # Step 1: Validate
    if not validate_telemetry(data):
        logger.warning(f"⚠️ Dropping invalid telemetry from {room_id}")
        return

    # Step 2: Normalize
    normalized = normalize_telemetry(data)

    # Step 3: Update state store
    state_store.update_telemetry(room_id, normalized)

    # Step 4: Write to InfluxDB
    write_telemetry(room_id, device_id, normalized)

    # Step 5: Publish normalized data
    norm_topic = f"building/{room_id}/gateway/normalized"
    client.publish(norm_topic, json.dumps(normalized), qos=1)

    # Step 6: Evaluate rules
    room_state = state_store.get_room_state(room_id)
    actuator_state = {
        "fan": room_state["actuator"]["fan"] if room_state else "off",
        "light": room_state["actuator"]["light"] if room_state else "off",
        "alarm": room_state["actuator"]["alarm"] if room_state else "off",
    }

    events, commands = evaluate(room_id, normalized, actuator_state)

    # Step 7: Process events — write to InfluxDB and publish to MQTT
    for event in events:
        write_event(event)
        event_topic = f"building/{room_id}/gateway/event"
        client.publish(event_topic, json.dumps(event), qos=1)
        logger.warning(f"🚨 Event: {event['event_type']} in {room_id} "
                      f"(severity={event['severity']})")

    # Step 8: Send commands to actuators via MQTT
    for command in commands:
        cmd_topic = f"building/{room_id}/actuator/command"
        client.publish(cmd_topic, json.dumps(command), qos=1)
        logger.info(f"📤 Command sent to {room_id}: "
                   f"{command['target']}={command['action']} "
                   f"(reason={command['reason']})")


def handle_actuator_status(client, topic: str, data: dict):
    """Process incoming actuator status update. Store and write to InfluxDB."""
    room_id = data.get("room_id", "unknown")
    device_id = data.get("device_id", "unknown")

    logger.info(f"📩 Actuator status from {room_id}: "
               f"fan={data.get('fan')}, light={data.get('light')}, "
               f"alarm={data.get('alarm')}")

    # Update state store
    state_store.update_actuator(room_id, data)

    # Write to InfluxDB
    write_actuator_status(room_id, device_id, data)


# ============================================================
# Main
# ============================================================
def main():
    logger.info("=" * 60)
    logger.info("Starting Virtual IoT Gateway for Smart Building")
    logger.info("=" * 60)

    # Initialize InfluxDB
    init_influxdb()

    # Create MQTT client
    client = mqtt.Client(
        client_id="iot-gateway",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect with retry
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

    logger.info("Gateway is running. Processing messages...")
    client.loop_forever()


if __name__ == "__main__":
    main()
