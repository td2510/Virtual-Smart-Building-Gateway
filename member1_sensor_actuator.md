# ‍ THÀNH VIÊN 1: Virtual Sensor + Virtual Actuator + Topic Design

##  Tổng quan

| Mục | Chi tiết |
|---|---|
| **Scope** | `virtual_sensor/`, `virtual_actuator/`, `docs/topic-design.md`, `tests/test_anomaly_publish.py` |
| **Ngôn ngữ** | Python 3.11+ |
| **Thư viện chính** | `paho-mqtt` |
| **Thời gian ước lượng** | 3–4 ngày |

> [!NOTE]
> File này bao gồm cả các **yêu cầu nâng cao (Section 19)** để cộng điểm khuyến khích.

---

##  Checklist task theo thứ tự

### Phần bắt buộc

| # | Task | Thời gian | Trạng thái |
|---|---|---|---|
| 1 | Đọc hiểu shared contracts (topic, message format, env vars) | 30 phút | `[ ]` |
| 2 | Viết `docs/topic-design.md` | 1 giờ | `[ ]` |
| 3 | Lập trình `virtual_sensor/sensor.py` | 3–4 giờ | `[ ]` |
| 4 | Viết `virtual_sensor/requirements.txt` | 10 phút | `[ ]` |
| 5 | Viết `virtual_sensor/Dockerfile` | 15 phút | `[ ]` |
| 6 | Test sensor độc lập với Mosquitto local | 1 giờ | `[ ]` |
| 7 | Lập trình `virtual_actuator/actuator.py` | 2–3 giờ | `[ ]` |
| 8 | Viết `virtual_actuator/requirements.txt` | 10 phút | `[ ]` |
| 9 | Viết `virtual_actuator/Dockerfile` | 15 phút | `[ ]` |
| 10 | Test actuator độc lập với Mosquitto local | 1 giờ | `[ ]` |
| 11 | Test kết hợp sensor + actuator (không cần gateway) | 1 giờ | `[ ]` |
| 12 | Review code, thêm comments, cleanup | 1 giờ | `[ ]` |

###  Phần nâng cao (cộng điểm khuyến khích)

| # | Task nâng cao | Yêu cầu số | Thời gian | Trạng thái |
|---|---|---|---|---|
| A1 | Thêm `last_seen` timestamp vào telemetry để gateway phát hiện sensor offline | #4 | 30 phút | `[ ]` |
| A2 | Thêm cơ chế mô phỏng mất kết nối MQTT và tự reconnect trong sensor | #10 | 1–2 giờ | `[ ]` |
| A3 | Viết script `tests/test_anomaly_publish.py` tự động publish dữ liệu bất thường để kiểm thử | #9 | 1–2 giờ | `[ ]` |

---

##  QUY ƯỚC BẮT BUỘC (SHARED CONTRACTS)

### MQTT Topics mà bạn sẽ dùng

| Topic | Ai publish | Ai subscribe |
|---|---|---|
| `building/{room_id}/sensor/telemetry` | **Sensor (bạn)** | Gateway (TV2) |
| `building/{room_id}/actuator/command` | Gateway (TV2) | **Actuator (bạn)** |
| `building/{room_id}/actuator/status` | **Actuator (bạn)** | Gateway (TV2) |

> `room_id` ∈ {`room-01`, `room-02`, `room-03`}

### Environment Variables cần đọc

**Sensor:**
- `MQTT_BROKER` (default: `mosquitto`)
- `MQTT_PORT` (default: `1883`)
- `ROOM_ID` (vd: `room-01`)
- `DEVICE_ID` (vd: `sensor-room-01`)
- `PUBLISH_INTERVAL` (default: `5`, đơn vị giây)

**Actuator:**
- `MQTT_BROKER` (default: `mosquitto`)
- `MQTT_PORT` (default: `1883`)
- `ROOM_ID` (vd: `room-01`)
- `DEVICE_ID` (vd: `actuator-room-01`)

---

##  Code Skeleton

### 1. `virtual_sensor/sensor.py`

```python
"""
Virtual Sensor for Smart Building IoT System.
Simulates environmental sensors for a room in a smart building.
Publishes telemetry data to MQTT broker periodically.
"""

import os
import json
import time
import random
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# Configuration from environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ROOM_ID = os.getenv("ROOM_ID", "room-01")
DEVICE_ID = os.getenv("DEVICE_ID", f"sensor-{ROOM_ID}")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

# MQTT topic
TELEMETRY_TOPIC = f"building/{ROOM_ID}/sensor/telemetry"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(DEVICE_ID)


# Sensor Data Simulator
class SensorSimulator:
    """
    Simulates environmental sensor data with realistic trends.
    Values change gradually (not pure random) by keeping previous state.
    Has a mechanism to inject anomalies (~10% probability).
    """

    def __init__(self):
        # Initial values (reasonable defaults)
        self.temperature = 26.0   # °C
        self.humidity = 60.0      # %
        self.light_lux = 400.0    # lux
        self.co2_ppm = 600.0      # ppm
        self.occupancy = True
        self.cycle_count = 0

    def _drift(self, current: float, min_val: float, max_val: float,
               step: float = 0.5) -> float:
        """
        Apply a small random drift to the current value.
        Keeps the value within [min_val, max_val].
        """
        delta = random.uniform(-step, step)
        new_val = current + delta
        return max(min_val, min(max_val, round(new_val, 2)))

    def _maybe_anomaly(self) -> bool:
        """Return True ~10% of the time to trigger an anomaly."""
        return random.random() < 0.10

    def generate(self) -> dict:
        """
        Generate the next telemetry reading.
        Occasionally injects anomalies (high temp, high CO2, etc.).
        """
        self.cycle_count += 1

        # --- Normal drift ---
        self.temperature = self._drift(self.temperature, 20.0, 28.0, step=0.3)
        self.humidity = self._drift(self.humidity, 40.0, 80.0, step=1.0)
        self.light_lux = self._drift(self.light_lux, 50.0, 800.0, step=20.0)
        self.co2_ppm = self._drift(self.co2_ppm, 400.0, 1000.0, step=15.0)

        # Occupancy changes less frequently
        if random.random() < 0.05:
            self.occupancy = not self.occupancy

        # --- Anomaly injection (~10% chance) ---
        if self._maybe_anomaly():
            anomaly_type = random.choice([
                "temperature_high", "co2_high", "humidity_high"
            ])
            if anomaly_type == "temperature_high":
                self.temperature = round(random.uniform(31.0, 38.0), 2)
                logger.warning(f" ANOMALY: temperature spike → {self.temperature}°C")
            elif anomaly_type == "co2_high":
                self.co2_ppm = round(random.uniform(1250.0, 2000.0), 2)
                logger.warning(f" ANOMALY: CO2 spike → {self.co2_ppm} ppm")
            elif anomaly_type == "humidity_high":
                self.humidity = round(random.uniform(85.0, 98.0), 2)
                logger.warning(f" ANOMALY: humidity spike → {self.humidity}%")

        # --- Build telemetry message ---
        message = {
            "device_id": DEVICE_ID,
            "room_id": ROOM_ID,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "light_lux": self.light_lux,
            "co2_ppm": self.co2_ppm,
            "occupancy": self.occupancy,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return message


# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f" Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        logger.error(f" Failed to connect, return code: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    logger.warning(f"️ Disconnected from MQTT broker (rc={rc}). Reconnecting...")


# Main loop
def main():
    logger.info(f"Starting Virtual Sensor: {DEVICE_ID} for {ROOM_ID}")
    logger.info(f"Publishing to topic: {TELEMETRY_TOPIC}")
    logger.info(f"Publish interval: {PUBLISH_INTERVAL}s")

    # Create MQTT client
    client = mqtt.Client(
        client_id=DEVICE_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Connect with retry
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            logger.error(f"Connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

    client.loop_start()

    # Sensor simulator
    simulator = SensorSimulator()

    try:
        while True:
            telemetry = simulator.generate()
            payload = json.dumps(telemetry)

            result = client.publish(TELEMETRY_TOPIC, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f" Published: temp={telemetry['temperature']}, "
                           f"humidity={telemetry['humidity']}, "
                           f"co2={telemetry['co2_ppm']}, "
                           f"light={telemetry['light_lux']}, "
                           f"occupancy={telemetry['occupancy']}")
            else:
                logger.error(f"Publish failed with rc={result.rc}")

            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down sensor...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
```

### 2. `virtual_actuator/actuator.py`

```python
"""
Virtual Actuator for Smart Building IoT System.
Simulates actuators (fan, light, alarm) for a room in a smart building.
Receives commands via MQTT and publishes status updates.
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
        """Generate a status message dictionary."""
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
```

### 3. `virtual_sensor/requirements.txt`

```
paho-mqtt>=2.0.0
```

### 4. `virtual_actuator/requirements.txt`

```
paho-mqtt>=2.0.0
```

### 5. `virtual_sensor/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sensor.py .

CMD ["python", "-u", "sensor.py"]
```

### 6. `virtual_actuator/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY actuator.py .

CMD ["python", "-u", "actuator.py"]
```

### 7. `docs/topic-design.md`

```markdown
# MQTT Topic Design — Smart Building IoT Gateway

## Topic Hierarchy

| Topic Pattern | Direction | Description |
|---|---|---|
| `building/{room_id}/sensor/telemetry` | Sensor → Gateway | Raw telemetry data from sensors |
| `building/{room_id}/actuator/command` | Gateway → Actuator | Control commands to actuators |
| `building/{room_id}/actuator/status` | Actuator → Gateway | Current state of actuators |
| `building/{room_id}/gateway/normalized` | Gateway → (subscribers) | Normalized/cleaned data |
| `building/{room_id}/gateway/event` | Gateway → (subscribers) | Anomaly events detected |

## Room IDs
- `room-01`
- `room-02`
- `room-03`

## Message Formats

(Insert the 4 JSON schemas from shared contracts here)

## Wildcard Subscriptions
- Gateway subscribes to `building/+/sensor/telemetry` to receive all rooms.
- Gateway subscribes to `building/+/actuator/status` to track actuator state.
```

---

##  Hướng dẫn Test Độc Lập

Bạn có thể test mà **KHÔNG cần** code của TV2 và TV3. Chỉ cần một Mosquitto broker.

### Bước 1: Chạy Mosquitto local (bằng Docker)

```bash
docker run -d --name mosquitto -p 1883:1883 eclipse-mosquitto:2 \
  sh -c 'echo -e "listener 1883\nallow_anonymous true" > /mosquitto/config/mosquitto.conf && mosquitto -c /mosquitto/config/mosquitto.conf'
```

### Bước 2: Test Virtual Sensor

```bash
# Terminal 1 — Chạy subscriber để xem sensor data
mosquitto_sub -h localhost -t "building/room-01/sensor/telemetry" -v

# Terminal 2 — Chạy sensor
cd virtual_sensor
pip install -r requirements.txt
MQTT_BROKER=localhost ROOM_ID=room-01 DEVICE_ID=sensor-room-01 PUBLISH_INTERVAL=3 python sensor.py
```

**Kiểm tra:**
-  Terminal 1 nhận được JSON message mỗi 3 giây
-  Dữ liệu có biến động nhẹ (không random hoàn toàn)
-  Thỉnh thoảng (~10%) có spike bất thường
-  JSON format đúng shared contract

### Bước 3: Test Virtual Actuator

```bash
# Terminal 1 — Chạy actuator
cd virtual_actuator
pip install -r requirements.txt
MQTT_BROKER=localhost ROOM_ID=room-01 DEVICE_ID=actuator-room-01 python actuator.py

# Terminal 2 — Xem actuator status
mosquitto_sub -h localhost -t "building/room-01/actuator/status" -v

# Terminal 3 — Gửi command giả lập (đóng vai Gateway)
mosquitto_pub -h localhost -t "building/room-01/actuator/command" \
  -m '{"room_id":"room-01","target":"fan","action":"on","reason":"temperature_high","timestamp":"2026-06-10T10:00:00Z"}'
```

**Kiểm tra:**
-  Actuator log hiển thị nhận command
-  Terminal 2 nhận được status message với `fan: "on"`
-  Gửi command sai format → actuator log lỗi rõ ràng, không crash

### Bước 4: Test kết hợp Sensor + Actuator (không cần Gateway)

```bash
# Chạy cả sensor + actuator cho room-01 cùng lúc
# Dùng mosquitto_pub giả lập gateway gửi command khi thấy temperature cao
```

### Bước 5: Test bằng Docker build

```bash
# Build và test sensor container
cd virtual_sensor
docker build -t virtual-sensor .
docker run --rm -e MQTT_BROKER=host.docker.internal -e ROOM_ID=room-01 -e DEVICE_ID=sensor-room-01 virtual-sensor

# Build và test actuator container
cd virtual_actuator
docker build -t virtual-actuator .
docker run --rm -e MQTT_BROKER=host.docker.internal -e ROOM_ID=room-01 -e DEVICE_ID=actuator-room-01 virtual-actuator
```

---

##  Timeline gợi ý (trong 1 tuần)

| Ngày | Công việc |
|---|---|
| **Ngày 1** | Đọc hiểu đề bài + shared contracts. Viết `docs/topic-design.md`. Setup Mosquitto local. |
| **Ngày 2** | Code `sensor.py` hoàn chỉnh (bao gồm `last_seen` + reconnect logic). Test với mosquitto_sub. |
| **Ngày 3** | Code `actuator.py` hoàn chỉnh. Test với mosquitto_pub. |
| **Ngày 4** | Viết Dockerfile cho cả 2. Test Docker build. Fix bugs. |
| **Ngày 5** |  Viết `test_anomaly_publish.py`. Test kết hợp sensor + actuator. Review code. |
| **Ngày 6–7** | **TÍCH HỢP** với TV2 và TV3. Debug hệ thống. Chụp screenshot. |

---

##  Integration Checklist (khi merge với TV2, TV3)

Khi tích hợp code với cả nhóm, kiểm tra:

**Bắt buộc:**
- [ ] Sensor publish đúng topic `building/{room_id}/sensor/telemetry`
- [ ] Gateway (TV2) nhận được telemetry từ cả 3 phòng
- [ ] Gateway gửi command → Actuator nhận được và xử lý đúng
- [ ] Actuator publish status → Gateway nhận và ghi InfluxDB
- [ ] Message format JSON khớp 100% với shared contracts
- [ ] Tất cả env vars đọc đúng từ docker-compose.yml
- [ ] Container start/stop không có lỗi
- [ ] Log rõ ràng, dễ debug

**Nâng cao:**
- [ ] Field `last_seen` có trong telemetry message → TV2 dùng để phát hiện offline
- [ ] Sensor tự reconnect sau khi mất kết nối MQTT (test bằng cách restart Mosquitto)
- [ ] Script `test_anomaly_publish.py` chạy được và kích hoạt rule engine của TV2

---

##  NÂNG CAO — Code bổ sung

### [Nâng cao #10] Cơ chế mô phỏng mất kết nối + Reconnect

Thêm vào `sensor.py` — thay thế phần `main()` để hỗ trợ reconnect tự động:

```python
# Thêm vào sensor.py — cơ chế reconnect tự động

def on_disconnect(client, userdata, rc, properties=None):
    """Handle MQTT disconnection and trigger reconnect loop."""
    logger.warning(f"️ Disconnected (rc={rc}). Will reconnect in 5s...")
    # paho-mqtt tự động reconnect nếu dùng loop_forever() với reconnect_delay_set

# Trong main(), trước client.connect():
client.reconnect_delay_set(min_delay=1, max_delay=30)  # exponential backoff

# Thay loop_start() + vòng while bằng loop_forever() để auto-reconnect:
# client.loop_forever()  # paho-mqtt tự handle reconnect
```

**Cách test reconnect:**
```bash
# Terminal 1: Chạy sensor
MQTT_BROKER=localhost ROOM_ID=room-01 python sensor.py

# Terminal 2: Dừng Mosquitto để giả lập mất kết nối
docker stop mosquitto
# Quan sát sensor log → thấy "Disconnected" và retry

# Khởi động lại Mosquitto
docker start mosquitto
# Quan sát sensor log → thấy "Connected" và tiếp tục publish
```

---

### [Nâng cao #4] Thêm `last_seen` vào Telemetry

Gateway (TV2) cần timestamp để phát hiện sensor offline. Thêm field này vào message:

```python
# Trong SensorSimulator.generate() — đã có timestamp, đổi tên thành last_seen
message = {
    "device_id": DEVICE_ID,
    "room_id": ROOM_ID,
    "temperature": self.temperature,
    "humidity": self.humidity,
    "light_lux": self.light_lux,
    "co2_ppm": self.co2_ppm,
    "occupancy": self.occupancy,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "last_seen": datetime.now(timezone.utc).isoformat()  # ← thêm field này
}
```

---

### [Nâng cao #9] Script `tests/test_anomaly_publish.py`

Script này publish dữ liệu bất thường để kiểm thử gateway mà không cần chờ sensor tự sinh anomaly.

```python
"""
Test script: Automatically publish anomaly data to test the gateway rule engine.
Usage: python test_anomaly_publish.py --broker localhost --room room-01 --scenario all
"""

import argparse
import json
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# --- Scenarios ---
SCENARIOS = {
    "temperature_high": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 35.0,     # > 30 → triggers fan ON
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
    },
    "co2_high": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 25.0,
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 1500.0,       # > 1200 → triggers alarm ON
        "occupancy": True,
    },
    "unnecessary_light": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 25.0,
        "humidity": 60.0,
        "light_lux": 600.0,      # > 300 AND occupancy=false → triggers light OFF
        "co2_ppm": 800.0,
        "occupancy": False,
    },
    "temperature_low": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 22.0,     # < 27 → triggers fan OFF
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
    },
}


def publish_scenario(broker: str, room_id: str, scenario_name: str, port: int = 1883):
    """Publish a single anomaly scenario to MQTT."""
    if scenario_name not in SCENARIOS:
        print(f" Unknown scenario: {scenario_name}")
        return

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker, port)
    client.loop_start()

    data = SCENARIOS[scenario_name].copy()
    data["room_id"] = room_id
    data["device_id"] = f"sensor-{room_id}"
    data["timestamp"] = datetime.now(timezone.utc).isoformat()

    topic = f"building/{room_id}/sensor/telemetry"
    payload = json.dumps(data)

    result = client.publish(topic, payload, qos=1)
    result.wait_for_publish()
    print(f" Published [{scenario_name}] to {topic}")
    print(f"   Payload: {payload}")

    client.loop_stop()
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Anomaly Test Publisher")
    parser.add_argument("--broker", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--room", default="room-01")
    parser.add_argument("--scenario", default="all",
                        choices=list(SCENARIOS.keys()) + ["all"],
                        help="Which scenario to publish (or 'all')")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Interval between scenarios (seconds)")
    args = parser.parse_args()

    if args.scenario == "all":
        for name in SCENARIOS:
            print(f"\n--- Testing scenario: {name} ---")
            publish_scenario(args.broker, args.room, name, args.port)
            time.sleep(args.interval)
    else:
        publish_scenario(args.broker, args.room, args.scenario, args.port)


if __name__ == "__main__":
    main()
```

**Cách chạy:**
```bash
# Cài đặt
pip install paho-mqtt

# Chạy tất cả scenarios
python tests/test_anomaly_publish.py --broker localhost --room room-01 --scenario all

# Chạy một scenario cụ thể
python tests/test_anomaly_publish.py --broker localhost --room room-02 --scenario co2_high

# Chạy cho tất cả 3 phòng
for room in room-01 room-02 room-03; do
  python tests/test_anomaly_publish.py --broker localhost --room $room --scenario temperature_high
done
```

**Kiểm tra:**
-  Sau khi chạy script, gateway (TV2) phải log event tương ứng
-  Command được gửi đến actuator topic
-  InfluxDB có event data trong `gateway_events`
