# ‍ THÀNH VIÊN 2: Virtual IoT Gateway + Rule Engine + InfluxDB

##  Tổng quan

| Mục | Chi tiết |
|---|---|
| **Scope** | `iot_gateway/` (gateway.py, rule_engine.py, state_store.py, thresholds.py), `tests/test_rule_engine.py` |
| **Ngôn ngữ** | Python 3.11+ |
| **Thư viện chính** | `paho-mqtt`, `influxdb-client` |
| **Thời gian ước lượng** | 4–5 ngày |

> [!IMPORTANT]
> Đây là thành phần **quan trọng nhất** của hệ thống (chiếm 2.4/10 điểm cho gateway + rule engine). Cần thiết kế cẩn thận và test kỹ.

> [!NOTE]
> File này bao gồm cả các **yêu cầu nâng cao (Section 19)** để cộng điểm khuyến khích.

---

##  Checklist task theo thứ tự

### Phần bắt buộc

| # | Task | Thời gian | Trạng thái |
|---|---|---|---|
| 1 | Đọc hiểu shared contracts (topic, message format, env vars, rules) | 30 phút | `[ ]` |
| 2 | Lập trình `iot_gateway/state_store.py` | 1–2 giờ | `[ ]` |
| 3 | Lập trình `iot_gateway/rule_engine.py` (4 luật bắt buộc) | 2–3 giờ | `[ ]` |
| 4 | Lập trình `iot_gateway/gateway.py` — phần MQTT subscribe/publish | 2–3 giờ | `[ ]` |
| 5 | Thêm validate & normalize message vào gateway | 1–2 giờ | `[ ]` |
| 6 | Tích hợp InfluxDB writer vào gateway | 2–3 giờ | `[ ]` |
| 7 | Viết `iot_gateway/requirements.txt` | 10 phút | `[ ]` |
| 8 | Viết `iot_gateway/Dockerfile` | 15 phút | `[ ]` |
| 9 | Test gateway với mosquitto_pub giả lập sensor | 1–2 giờ | `[ ]` |
| 10 | Test ghi dữ liệu vào InfluxDB | 1 giờ | `[ ]` |
| 11 | Test rule engine phát hiện bất thường | 1 giờ | `[ ]` |
| 12 | Review code, thêm comments, cleanup | 1 giờ | `[ ]` |

###  Phần nâng cao (cộng điểm khuyến khích)

| # | Task nâng cao | Yêu cầu số | Thời gian | Trạng thái |
|---|---|---|---|---|
| A1 | Thêm cơ chế phát hiện sensor offline (kiểm tra `last_seen` định kỳ) | #4 | 2–3 giờ | `[ ]` |
| A2 | Thêm cơ chế actuator acknowledgement timeout | #5 | 2–3 giờ | `[ ]` |
| A3 | Viết `iot_gateway/thresholds.py` — thưởng xuựen động (hỗ trợ TV3 thay đổi qua API) | #6 | 1–2 giờ | `[ ]` |
| A4 | Viết unit test `tests/test_rule_engine.py` | #8 | 2–3 giờ | `[ ]` |

---

##  QUY ƯỚC BẮT BUỘC (SHARED CONTRACTS)

### MQTT Topics mà bạn sẽ dùng

| Topic | Vai trò |
|---|---|
| `building/+/sensor/telemetry` | **Subscribe** (nhận telemetry từ tất cả phòng) |
| `building/+/actuator/status` | **Subscribe** (nhận trạng thái actuator) |
| `building/{room_id}/actuator/command` | **Publish** (gửi lệnh điều khiển) |
| `building/{room_id}/gateway/normalized` | **Publish** (dữ liệu đã chuẩn hóa) |
| `building/{room_id}/gateway/event` | **Publish** (event bất thường) |

### 4 Luật Rule Engine BẮT BUỘC

| # | Điều kiện | Hành động | Event type |
|---|---|---|---|
| 1 | `temperature > 30` | Bật quạt (fan ON) | `temperature_high` |
| 2 | `temperature < 27` | Tắt quạt (fan OFF) | `temperature_low` |
| 3 | `co2_ppm > 1200` | Bật alarm (alarm ON) | `co2_high` |
| 4 | `occupancy == false` AND `light_lux > 300` | Tắt đèn (light OFF) | `unnecessary_light` |

### InfluxDB Measurements

| Measurement | Tags | Fields |
|---|---|---|
| `room_telemetry` | room_id, device_id | temperature, humidity, light_lux, co2_ppm, occupancy |
| `gateway_events` | room_id, event_type, severity | value, threshold, action_taken |
| `actuator_status` | room_id, device_id | fan, light, alarm |

### Environment Variables

- `MQTT_BROKER=mosquitto`
- `MQTT_PORT=1883`
- `INFLUXDB_URL=http://influxdb:8086`
- `INFLUXDB_TOKEN=my-super-secret-token`
- `INFLUXDB_ORG=iot-org`
- `INFLUXDB_BUCKET=smart-building`

---

##  Code Skeleton

### 1. `iot_gateway/state_store.py`

```python
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
        with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState(room_id)
            self._rooms[room_id].update_telemetry(data)
            logger.debug(f"Updated telemetry for {room_id}")

    def update_actuator(self, room_id: str, data: dict):
        with self._lock:
            if room_id not in self._rooms:
                self._rooms[room_id] = RoomState(room_id)
            self._rooms[room_id].update_actuator(data)
            logger.debug(f"Updated actuator status for {room_id}")

    def get_room_state(self, room_id: str) -> Optional[dict]:
        with self._lock:
            room = self._rooms.get(room_id)
            return room.to_dict() if room else None

    def get_all_rooms(self) -> list[str]:
        with self._lock:
            return list(self._rooms.keys())

    def get_all_states(self) -> dict:
        with self._lock:
            return {rid: room.to_dict() for rid, room in self._rooms.items()}
```

### 2. `iot_gateway/rule_engine.py`

```python
"""
Rule Engine for IoT Gateway.
Evaluates telemetry data against predefined rules.
Returns lists of events and commands to execute.

Designed to be extensible — add new rules by appending to RULES list.
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
    """Helper to create an event message."""
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
    """Helper to create a command message."""
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
```

### 3. `iot_gateway/gateway.py`

```python
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

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "smart-building")

# MQTT topic patterns
TELEMETRY_TOPIC = "building/+/sensor/telemetry"
ACTUATOR_STATUS_TOPIC = "building/+/actuator/status"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("iot-gateway")

# Global instances
state_store = StateStore()
influx_client = None
write_api = None


# InfluxDB Setup
def init_influxdb():
    """Initialize InfluxDB client with retry."""
    global influx_client, write_api
    while True:
        try:
            influx_client = InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            write_api = influx_client.write_api(write_options=SYNCHRONOUS)
            # Test connection
            influx_client.ping()
            logger.info(f" Connected to InfluxDB at {INFLUXDB_URL}")
            return
        except Exception as e:
            logger.error(f"InfluxDB connection failed: {e}. Retrying in 5s...")
            time.sleep(5)


def write_telemetry(room_id: str, device_id: str, data: dict):
    """Write telemetry data to InfluxDB."""
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
        logger.debug(f" Wrote telemetry for {room_id}")
    except Exception as e:
        logger.error(f"Failed to write telemetry: {e}")


def write_event(event: dict):
    """Write an anomaly event to InfluxDB."""
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
        logger.debug(f" Wrote event: {event['event_type']} for {event['room_id']}")
    except Exception as e:
        logger.error(f"Failed to write event: {e}")


def write_actuator_status(room_id: str, device_id: str, data: dict):
    """Write actuator status to InfluxDB."""
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
        logger.debug(f" Wrote actuator status for {room_id}")
    except Exception as e:
        logger.error(f"Failed to write actuator status: {e}")


# Message Validation & Normalization
REQUIRED_TELEMETRY_FIELDS = [
    "device_id", "room_id", "temperature", "humidity",
    "light_lux", "co2_ppm", "occupancy", "timestamp"
]


def validate_telemetry(data: dict) -> bool:
    """Validate a telemetry message has all required fields."""
    for field in REQUIRED_TELEMETRY_FIELDS:
        if field not in data:
            logger.warning(f"️ Missing field '{field}' in telemetry message")
            return False

    # Validate data types
    try:
        float(data["temperature"])
        float(data["humidity"])
        float(data["light_lux"])
        float(data["co2_ppm"])
        bool(data["occupancy"])
    except (ValueError, TypeError) as e:
        logger.warning(f"️ Invalid data type in telemetry: {e}")
        return False

    return True


def normalize_telemetry(data: dict) -> dict:
    """Normalize telemetry data into a unified format."""
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


# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f" Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(TELEMETRY_TOPIC, qos=1)
        client.subscribe(ACTUATOR_STATUS_TOPIC, qos=1)
        logger.info(f" Subscribed to: {TELEMETRY_TOPIC}")
        logger.info(f" Subscribed to: {ACTUATOR_STATUS_TOPIC}")
    else:
        logger.error(f" Connection failed (rc={rc})")


def on_disconnect(client, userdata, rc, properties=None):
    logger.warning(f"️ Disconnected (rc={rc}). Reconnecting...")


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
        logger.error(f" Invalid JSON on {msg.topic}: {msg.payload}")
    except Exception as e:
        logger.error(f" Error handling message on {msg.topic}: {e}")


def handle_telemetry(client, topic: str, data: dict):
    """Process incoming telemetry from a sensor."""
    room_id = data.get("room_id", "unknown")
    device_id = data.get("device_id", "unknown")

    logger.info(f" Telemetry from {room_id}: temp={data.get('temperature')}, "
               f"co2={data.get('co2_ppm')}, occupancy={data.get('occupancy')}")

    # Step 1: Validate
    if not validate_telemetry(data):
        logger.warning(f"️ Dropping invalid telemetry from {room_id}")
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

    # Step 7: Process events
    for event in events:
        # Write event to InfluxDB
        write_event(event)
        # Publish event to MQTT
        event_topic = f"building/{room_id}/gateway/event"
        client.publish(event_topic, json.dumps(event), qos=1)
        logger.warning(f" Event: {event['event_type']} in {room_id} "
                      f"(severity={event['severity']})")

    # Step 8: Send commands to actuators
    for command in commands:
        cmd_topic = f"building/{room_id}/actuator/command"
        client.publish(cmd_topic, json.dumps(command), qos=1)
        logger.info(f" Command sent to {room_id}: "
                   f"{command['target']}={command['action']} "
                   f"(reason={command['reason']})")


def handle_actuator_status(client, topic: str, data: dict):
    """Process incoming actuator status update."""
    room_id = data.get("room_id", "unknown")
    device_id = data.get("device_id", "unknown")

    logger.info(f" Actuator status from {room_id}: "
               f"fan={data.get('fan')}, light={data.get('light')}, "
               f"alarm={data.get('alarm')}")

    # Update state store
    state_store.update_actuator(room_id, data)

    # Write to InfluxDB
    write_actuator_status(room_id, device_id, data)


# Main
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
```

### 4. `iot_gateway/requirements.txt`

```
paho-mqtt>=2.0.0
influxdb-client>=1.36.0
```

### 5. `iot_gateway/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway.py .
COPY rule_engine.py .
COPY state_store.py .

CMD ["python", "-u", "gateway.py"]
```

---

##  Hướng dẫn Test Độc Lập

Bạn có thể test mà **KHÔNG cần** code của TV1 (sensor/actuator) và TV3 (API). Dùng `mosquitto_pub` giả lập sensor.

### Bước 1: Chạy hạ tầng (Mosquitto + InfluxDB)

```bash
# docker-compose-dev.yml tạm cho dev
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto:2 \
  sh -c 'echo -e "listener 1883\nallow_anonymous true" > /mosquitto/config/mosquitto.conf && mosquitto -c /mosquitto/config/mosquitto.conf'

docker run -d --name influxdb -p 8086:8086 \
  -e DOCKER_INFLUXDB_INIT_MODE=setup \
  -e DOCKER_INFLUXDB_INIT_USERNAME=admin \
  -e DOCKER_INFLUXDB_INIT_PASSWORD=admin12345 \
  -e DOCKER_INFLUXDB_INIT_ORG=iot-org \
  -e DOCKER_INFLUXDB_INIT_BUCKET=smart-building \
  -e DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-token \
  influxdb:2
```

### Bước 2: Chạy Gateway

```bash
cd iot_gateway
pip install -r requirements.txt

MQTT_BROKER=localhost \
INFLUXDB_URL=http://localhost:8086 \
INFLUXDB_TOKEN=my-super-secret-token \
INFLUXDB_ORG=iot-org \
INFLUXDB_BUCKET=smart-building \
python gateway.py
```

### Bước 3: Giả lập sensor bằng mosquitto_pub

```bash
# Telemetry bình thường (temperature=25, trong ngưỡng an toàn)
mosquitto_pub -h localhost -t "building/room-01/sensor/telemetry" \
  -m '{"device_id":"sensor-room-01","room_id":"room-01","temperature":25.5,"humidity":60.0,"light_lux":400.0,"co2_ppm":800.0,"occupancy":true,"timestamp":"2026-06-10T10:00:00Z"}'

# Telemetry bất thường (temperature=33, sẽ trigger rule 1)
mosquitto_pub -h localhost -t "building/room-01/sensor/telemetry" \
  -m '{"device_id":"sensor-room-01","room_id":"room-01","temperature":33.0,"humidity":60.0,"light_lux":400.0,"co2_ppm":800.0,"occupancy":true,"timestamp":"2026-06-10T10:01:00Z"}'

# CO2 cao (co2=1500, sẽ trigger rule 3)
mosquitto_pub -h localhost -t "building/room-02/sensor/telemetry" \
  -m '{"device_id":"sensor-room-02","room_id":"room-02","temperature":25.0,"humidity":60.0,"light_lux":400.0,"co2_ppm":1500.0,"occupancy":true,"timestamp":"2026-06-10T10:02:00Z"}'

# Không có người + ánh sáng mạnh (trigger rule 4)
mosquitto_pub -h localhost -t "building/room-03/sensor/telemetry" \
  -m '{"device_id":"sensor-room-03","room_id":"room-03","temperature":25.0,"humidity":60.0,"light_lux":500.0,"co2_ppm":600.0,"occupancy":false,"timestamp":"2026-06-10T10:03:00Z"}'
```

### Bước 4: Verify

```bash
# Xem gateway có gửi command không
mosquitto_sub -h localhost -t "building/+/actuator/command" -v

# Xem gateway có gửi event không
mosquitto_sub -h localhost -t "building/+/gateway/event" -v

# Xem dữ liệu trong InfluxDB (truy cập http://localhost:8086)
# Login: admin / admin12345
# Vào Data Explorer → query measurement room_telemetry, gateway_events
```

**Kiểm tra:**
-  Gateway log hiển thị nhận telemetry
-  Khi temperature > 30: có event `temperature_high` và command `fan ON`
-  Khi co2 > 1200: có event `co2_high` và command `alarm ON`
-  InfluxDB có dữ liệu trong 3 measurements
-  Message sai format → gateway log warning, không crash

### Bước 5: Giả lập actuator status

```bash
mosquitto_pub -h localhost -t "building/room-01/actuator/status" \
  -m '{"device_id":"actuator-room-01","room_id":"room-01","fan":"on","light":"off","alarm":"off","last_command_reason":"temperature_high","timestamp":"2026-06-10T10:00:06Z"}'
```

-  Gateway ghi actuator_status vào InfluxDB

---

##  Timeline gợi ý (trong 1 tuần)

| Ngày | Công việc |
|---|---|
| **Ngày 1** | Đọc hiểu đề bài + shared contracts. Setup Mosquitto + InfluxDB local. |
| **Ngày 2** | Code `state_store.py` + `rule_engine.py`.  Viết unit test `test_rule_engine.py`. |
| **Ngày 3** | Code `gateway.py` — MQTT subscribe/publish + validate/normalize. |
| **Ngày 4** | Tích hợp InfluxDB writer.  Thêm cơ chế sensor offline detection + actuator ack timeout. |
| **Ngày 5** | Test end-to-end với mosquitto_pub. Viết Dockerfile. Fix bugs. |
| **Ngày 6–7** | **TÍCH HỢP** với TV1 (sensor/actuator) và TV3 (API/Docker). Debug. |

---

##  Integration Checklist (khi merge với TV1, TV3)

**Bắt buộc:**
- [ ] Gateway nhận được telemetry từ sensor thật (TV1) — không chỉ mosquitto_pub
- [ ] Rule engine phát hiện đúng bất thường từ sensor data thật
- [ ] Command gửi đúng topic → Actuator (TV1) nhận và xử lý
- [ ] Actuator status được ghi vào InfluxDB đúng
- [ ] API (TV3) có thể đọc state từ InfluxDB hoặc state_store
- [ ] InfluxDB có đầy đủ 3 measurements với data
- [ ] Grafana (TV3) query được dữ liệu từ InfluxDB
- [ ] Tất cả env vars khớp giữa gateway và docker-compose.yml (TV3)
- [ ] Container chạy ổn định, không crash khi nhận message liên tục

**Nâng cao:**
- [ ] Gateway sinh event `sensor_offline` khi sensor im lặng quá 60 giây
- [ ] Gateway sinh event `actuator_no_response` khi actuator không phản hồi trong 10 giây
- [ ] API endpoint `PUT /config/thresholds` (TV3) cập nhật threshold trong `thresholds.py` thành công
- [ ] Tất cả unit test `test_rule_engine.py` đều pass

---

##  NÂNG CAO — Code bổ sung

### [Nâng cao #4] Phát hiện Sensor Offline

Thêm vào `gateway.py` — background thread kiểm tra sensor nào im lặng quá lâu:

```python
import threading

# Thêm vào config
SENSOR_OFFLINE_TIMEOUT = int(os.getenv("SENSOR_OFFLINE_TIMEOUT", "60"))  # giây

# Trong state_store.py — RoomState cần thêm:
from datetime import datetime, timezone
import time

class SensorOfflineDetector:
    """
    Background thread kiểm tra sensor nào không gửi dữ liệu trong timeout.
    Sinh event sensor_offline và publish lên MQTT.
    """

    def __init__(self, state_store, mqtt_client, timeout_seconds: int = 60):
        self.state_store = state_store
        self.mqtt_client = mqtt_client
        self.timeout = timeout_seconds
        self._running = False
        self._thread = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _run(self):
        import logging
        logger = logging.getLogger("offline_detector")
        while self._running:
            time.sleep(10)  # kiểm tra mỗi 10 giây
            now = datetime.now(timezone.utc)
            for room_id in self.state_store.get_all_rooms():
                state = self.state_store.get_room_state(room_id)
                last_seen_str = state["telemetry"].get("timestamp")
                if not last_seen_str:
                    continue
                try:
                    last_seen = datetime.fromisoformat(
                        last_seen_str.replace("Z", "+00:00")
                    )
                    elapsed = (now - last_seen).total_seconds()
                    if elapsed > self.timeout:
                        event = {
                            "room_id": room_id,
                            "event_type": "sensor_offline",
                            "severity": "critical",
                            "value": elapsed,
                            "threshold": float(self.timeout),
                            "action_taken": "none",
                            "timestamp": now.isoformat()
                        }
                        topic = f"building/{room_id}/gateway/event"
                        self.mqtt_client.publish(topic, json.dumps(event), qos=1)
                        logger.warning(
                            f" SENSOR OFFLINE: {room_id} silent for {elapsed:.0f}s"
                        )
                except Exception as e:
                    logger.error(f"Error checking offline for {room_id}: {e}")

# Trong main() của gateway.py, sau khi connect MQTT:
# detector = SensorOfflineDetector(state_store, client, SENSOR_OFFLINE_TIMEOUT)
# detector.start()
```

---

### [Nâng cao #5] Actuator Acknowledgement Timeout

Theo dõi command đã gửi, nếu actuator không trả lời trong `ACTUATOR_ACK_TIMEOUT` giây → sinh event:

```python
import uuid

ACTUATOR_ACK_TIMEOUT = int(os.getenv("ACTUATOR_ACK_TIMEOUT", "10"))  # giây

class PendingCommandTracker:
    """
    Theo dõi các command đã gửi đang chờ actuator xác nhận.
    Nếu quá thời gian → sinh event actuator_no_response.
    """

    def __init__(self, timeout_seconds: int = 10):
        self._pending: dict[str, dict] = {}  # {cmd_id: {room_id, target, sent_at}}
        self._lock = threading.Lock()
        self.timeout = timeout_seconds

    def add(self, room_id: str, target: str, action: str) -> str:
        cmd_id = str(uuid.uuid4())[:8]
        with self._lock:
            self._pending[cmd_id] = {
                "room_id": room_id,
                "target": target,
                "action": action,
                "sent_at": time.time()
            }
        return cmd_id

    def acknowledge(self, room_id: str):
        """Mark all pending commands for a room as acknowledged."""
        with self._lock:
            to_remove = [k for k, v in self._pending.items()
                        if v["room_id"] == room_id]
            for k in to_remove:
                del self._pending[k]

    def get_expired(self) -> list[dict]:
        """Return commands that have exceeded the timeout."""
        now = time.time()
        with self._lock:
            expired = [
                v for v in self._pending.values()
                if now - v["sent_at"] > self.timeout
            ]
        return expired

# Trong handle_actuator_status() — khi nhận status từ actuator:
# pending_tracker.acknowledge(room_id)

# Thêm vào SensorOfflineDetector._run() hoặc thread riêng:
# for expired in pending_tracker.get_expired():
#     # sinh event actuator_no_response
```

---

### [Nâng cao #6] Dynamic Thresholds — `iot_gateway/thresholds.py`

Thường xuựen có thể đọc từ file JSON (TV3 sẽ có API để update):

```python
"""
Dynamic thresholds for the Rule Engine.
Thresholds are stored in memory and can be updated via API (TV3).
Can also persist to a JSON file for restart recovery.
"""

import json
import os
import threading
import logging

logger = logging.getLogger("thresholds")

# Default values (from PDF requirements)
DEFAULT_THRESHOLDS = {
    "temperature_high": 30.0,    # fan ON above this
    "temperature_low": 27.0,     # fan OFF below this
    "co2_high": 1200.0,         # alarm ON above this
    "light_unnecessary": 300.0, # light OFF above this (when no occupancy)
    "humidity_high": 80.0,      # bonus rule
}

THRESHOLD_FILE = os.getenv("THRESHOLD_FILE", "/app/thresholds.json")


class ThresholdStore:
    """Thread-safe store for dynamic rule thresholds."""

    def __init__(self):
        self._thresholds = DEFAULT_THRESHOLDS.copy()
        self._lock = threading.Lock()
        self._load_from_file()

    def _load_from_file(self):
        if os.path.exists(THRESHOLD_FILE):
            try:
                with open(THRESHOLD_FILE, "r") as f:
                    saved = json.load(f)
                    self._thresholds.update(saved)
                    logger.info(f"Loaded thresholds from {THRESHOLD_FILE}")
            except Exception as e:
                logger.warning(f"Could not load threshold file: {e}")

    def _save_to_file(self):
        try:
            with open(THRESHOLD_FILE, "w") as f:
                json.dump(self._thresholds, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save threshold file: {e}")

    def get(self, key: str) -> float:
        with self._lock:
            return self._thresholds.get(key, DEFAULT_THRESHOLDS.get(key, 0.0))

    def set(self, key: str, value: float):
        if key not in DEFAULT_THRESHOLDS:
            raise ValueError(f"Unknown threshold key: {key}")
        with self._lock:
            self._thresholds[key] = value
            self._save_to_file()
        logger.info(f"Threshold updated: {key} = {value}")

    def get_all(self) -> dict:
        with self._lock:
            return self._thresholds.copy()


# Singleton instance — dùng trong rule_engine.py
thresholds = ThresholdStore()

# Trong rule_engine.py — thay hard-coded values:
# from thresholds import thresholds
# threshold = thresholds.get("temperature_high")  # thay vì 30.0
```

---

### [Nâng cao #8] Unit Test `tests/test_rule_engine.py`

```python
"""
Unit tests for the Rule Engine.
Run: python -m pytest tests/test_rule_engine.py -v
"""

import sys
import os
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
    return {"fan": fan, "light": light, "alarm": alarm}


# Tests for Rule 1: temperature_high → fan ON
class TestRule1TemperatureHigh:

    def test_high_temp_triggers_fan_on(self):
        data = make_telemetry(temperature=33.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)

        assert len(events) == 1
        assert events[0]["event_type"] == "temperature_high"
        assert events[0]["severity"] == "warning"
        assert len(commands) == 1
        assert commands[0]["target"] == "fan"
        assert commands[0]["action"] == "on"

    def test_high_temp_no_command_if_fan_already_on(self):
        data = make_telemetry(temperature=35.0)
        actuator = make_actuator(fan="on")  # fan already on
        events, commands = evaluate("room-01", data, actuator)
        assert len(commands) == 0

    def test_normal_temp_no_trigger(self):
        data = make_telemetry(temperature=28.0)
        actuator = make_actuator()
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "temperature_high" for e in events)


# Tests for Rule 2: temperature_low → fan OFF
class TestRule2TemperatureLow:

    def test_low_temp_triggers_fan_off(self):
        data = make_telemetry(temperature=22.0)
        actuator = make_actuator(fan="on")
        events, commands = evaluate("room-01", data, actuator)

        fan_off_cmds = [c for c in commands if c["target"] == "fan" and c["action"] == "off"]
        assert len(fan_off_cmds) == 1

    def test_low_temp_no_command_if_fan_already_off(self):
        data = make_telemetry(temperature=22.0)
        actuator = make_actuator(fan="off")
        events, commands = evaluate("room-01", data, actuator)
        assert len(commands) == 0


# Tests for Rule 3: co2_high → alarm ON
class TestRule3Co2High:

    def test_high_co2_triggers_alarm(self):
        data = make_telemetry(co2_ppm=1500.0)
        actuator = make_actuator(alarm="off")
        events, commands = evaluate("room-01", data, actuator)

        alarm_cmds = [c for c in commands if c["target"] == "alarm" and c["action"] == "on"]
        assert len(alarm_cmds) == 1
        co2_events = [e for e in events if e["event_type"] == "co2_high"]
        assert co2_events[0]["severity"] == "critical"

    def test_borderline_co2_no_trigger(self):
        data = make_telemetry(co2_ppm=1200.0)  # exactly at threshold = no trigger
        actuator = make_actuator()
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "co2_high" for e in events)


# Tests for Rule 4: unnecessary_light
class TestRule4UnnecessaryLight:

    def test_no_occupancy_bright_triggers_light_off(self):
        data = make_telemetry(occupancy=False, light_lux=500.0)
        actuator = make_actuator(light="on")
        events, commands = evaluate("room-01", data, actuator)

        light_off = [c for c in commands if c["target"] == "light" and c["action"] == "off"]
        assert len(light_off) == 1

    def test_occupied_no_trigger(self):
        data = make_telemetry(occupancy=True, light_lux=500.0)
        actuator = make_actuator(light="on")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "unnecessary_light" for e in events)

    def test_no_occupancy_dark_no_trigger(self):
        data = make_telemetry(occupancy=False, light_lux=100.0)  # dark = no issue
        actuator = make_actuator(light="off")
        events, commands = evaluate("room-01", data, actuator)
        assert all(e["event_type"] != "unnecessary_light" for e in events)
```

**Cách chạy:**
```bash
pip install pytest
cd smart-building-iot-gateway
python -m pytest tests/test_rule_engine.py -v
```

**Output mong đợi:**
```
test_rule_engine.py::TestRule1TemperatureHigh::test_high_temp_triggers_fan_on PASSED
test_rule_engine.py::TestRule1TemperatureHigh::test_high_temp_no_command_if_fan_already_on PASSED
...
10 passed in 0.5s
```
