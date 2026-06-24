# ‍ THÀNH VIÊN 3: REST API + Docker Compose + Grafana + README

##  Tổng quan

| Mục | Chi tiết |
|---|---|
| **Scope** | `gateway_api/`, `docker-compose.yml`, `mosquitto/`, `grafana/`, `README.md`, `.env`, `.env.example` |
| **Ngôn ngữ** | Python 3.11+ |
| **Thư viện chính** | `fastapi`, `uvicorn`, `paho-mqtt`, `influxdb-client` |
| **Thời gian ước lượng** | 4–5 ngày |

> [!NOTE]
> Thành viên 3 đóng vai trò **"người tích hợp"** — viết docker-compose.yml để gom tất cả service, cấu hình Grafana dashboard, và viết README cho cả nhóm. Cần phối hợp sớm với TV1 và TV2 về service names và env vars.

> [!NOTE]
> File này bao gồm cả các **yêu cầu nâng cao (Section 19)** để cộng điểm khuyến khích.

---

##  Checklist task theo thứ tự

### Phần bắt buộc

| # | Task | Thời gian | Trạng thái |
|---|---|---|---|
| 1 | Đọc hiểu shared contracts (topic, message format, env vars) | 30 phút | `[ ]` |
| 2 | Viết `docker-compose.yml` hoàn chỉnh | 2–3 giờ | `[ ]` |
| 3 | Viết `.env.example` + `.env` | 15 phút | `[ ]` |
| 4 | Viết `mosquitto/config/mosquitto.conf` | 15 phút | `[ ]` |
| 5 | Lập trình `gateway_api/api.py` (FastAPI) | 3–4 giờ | `[ ]` |
| 6 | Viết `gateway_api/requirements.txt` | 10 phút | `[ ]` |
| 7 | Viết `gateway_api/Dockerfile` | 15 phút | `[ ]` |
| 8 | Test API độc lập với mosquitto_pub + InfluxDB | 1–2 giờ | `[ ]` |
| 9 | Cấu hình Grafana datasource provisioning | 1 giờ | `[ ]` |
| 10 | Tạo Grafana dashboard JSON (6 panels) | 2–3 giờ | `[ ]` |
| 11 | Viết `README.md` chi tiết | 1–2 giờ | `[ ]` |
| 12 | Test toàn bộ stack bằng docker compose up | 1–2 giờ | `[ ]` |

###  Phần nâng cao (cộng điểm khuyến khích)

| # | Task nâng cao | Yêu cầu số | Thời gian | Trạng thái |
|---|---|---|---|---|
| A1 | Cấu hình username/password cho Mosquitto MQTT broker | #1 | 1 giờ | `[ ]` |
| A2 | Thêm `healthcheck` cho tất cả service trong `docker-compose.yml` | #3 | 1–2 giờ | `[ ]` |
| A3 | Thêm endpoint `GET /config/thresholds` và `PUT /config/thresholds` vào API | #6 | 1–2 giờ | `[ ]` |
| A4 | Thêm Grafana alert rule cho nhiệt độ và CO2 | #7 | 1–2 giờ | `[ ]` |


---

##  QUY ƯỚC BẮT BUỘC (SHARED CONTRACTS)

### REST API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/rooms` | Danh sách phòng |
| GET | `/rooms/{room_id}/state` | Trạng thái mới nhất của phòng |
| GET | `/rooms/{room_id}/events` | Events gần nhất |
| POST | `/rooms/{room_id}/command` | Gửi lệnh thủ công đến actuator |

### Command body (POST):
```json
{
  "target": "fan",
  "action": "on",
  "reason": "manual_control"
}
```

### Environment Variables cho API:
- `MQTT_BROKER=mosquitto`
- `MQTT_PORT=1883`
- `INFLUXDB_URL=http://influxdb:8086`
- `INFLUXDB_TOKEN=my-super-secret-token`
- `INFLUXDB_ORG=iot-org`
- `INFLUXDB_BUCKET=smart-building`

---

##  Code Skeleton

### 1. `gateway_api/api.py`

```python
"""
REST API for Smart Building IoT Gateway.
Provides endpoints to query room states and send manual commands.
Built with FastAPI.
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "smart-building")

KNOWN_ROOMS = ["room-01", "room-02", "room-03"]

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gateway-api")

# FastAPI App
app = FastAPI(
    title="Smart Building IoT Gateway API",
    description="REST API for querying room states and sending manual commands",
    version="1.0.0"
)

# Pydantic Models
class CommandRequest(BaseModel):
    target: str    # fan | light | alarm
    action: str    # on | off
    reason: str = "manual_control"


class HealthResponse(BaseModel):
    status: str
    timestamp: str


# MQTT Client (for publishing commands)
mqtt_client = mqtt.Client(
    client_id="gateway-api",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)


@app.on_event("startup")
async def startup():
    """Connect to MQTT broker on startup."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info(f" MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.error(f" MQTT connection failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Disconnect MQTT on shutdown."""
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


# InfluxDB Query Helper
def get_influx_client():
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )


def query_latest_telemetry(room_id: str) -> Optional[dict]:
    """Query the latest telemetry data for a room from InfluxDB."""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "room_telemetry")
      |> filter(fn: (r) => r.room_id == "{room_id}")
      |> last()
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''

    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        for table in tables:
            for record in table.records:
                return {
                    "room_id": room_id,
                    "temperature": record.values.get("temperature"),
                    "humidity": record.values.get("humidity"),
                    "light_lux": record.values.get("light_lux"),
                    "co2_ppm": record.values.get("co2_ppm"),
                    "occupancy": record.values.get("occupancy"),
                    "timestamp": str(record.get_time()),
                }
    except Exception as e:
        logger.error(f"InfluxDB query error: {e}")
    finally:
        client.close()

    return None


def query_latest_actuator(room_id: str) -> Optional[dict]:
    """Query the latest actuator status for a room from InfluxDB."""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -1h)
      |> filter(fn: (r) => r._measurement == "actuator_status")
      |> filter(fn: (r) => r.room_id == "{room_id}")
      |> last()
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''

    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        for table in tables:
            for record in table.records:
                return {
                    "room_id": room_id,
                    "fan": record.values.get("fan"),
                    "light": record.values.get("light"),
                    "alarm": record.values.get("alarm"),
                    "timestamp": str(record.get_time()),
                }
    except Exception as e:
        logger.error(f"InfluxDB query error: {e}")
    finally:
        client.close()

    return None


def query_events(room_id: str, limit: int = 20) -> list[dict]:
    """Query recent events for a room from InfluxDB."""
    client = get_influx_client()
    query_api = client.query_api()

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -24h)
      |> filter(fn: (r) => r._measurement == "gateway_events")
      |> filter(fn: (r) => r.room_id == "{room_id}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: {limit})
    '''

    events = []
    try:
        tables = query_api.query(query, org=INFLUXDB_ORG)
        for table in tables:
            for record in table.records:
                events.append({
                    "room_id": room_id,
                    "event_type": record.values.get("event_type", ""),
                    "severity": record.values.get("severity", ""),
                    "value": record.values.get("value"),
                    "threshold": record.values.get("threshold"),
                    "action_taken": record.values.get("action_taken", ""),
                    "timestamp": str(record.get_time()),
                })
    except Exception as e:
        logger.error(f"InfluxDB query error: {e}")
    finally:
        client.close()

    return events


# API Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check if the API is running."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/rooms")
async def list_rooms():
    """Return the list of known rooms."""
    return {
        "rooms": KNOWN_ROOMS,
        "count": len(KNOWN_ROOMS)
    }


@app.get("/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    """Return the latest state of a room (telemetry + actuator)."""
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404,
                          detail=f"Room '{room_id}' not found")

    telemetry = query_latest_telemetry(room_id)
    actuator = query_latest_actuator(room_id)

    return {
        "room_id": room_id,
        "telemetry": telemetry,
        "actuator": actuator
    }


@app.get("/rooms/{room_id}/events")
async def get_room_events(room_id: str, limit: int = 20):
    """Return recent events for a room."""
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404,
                          detail=f"Room '{room_id}' not found")

    events = query_events(room_id, limit)
    return {
        "room_id": room_id,
        "events": events,
        "count": len(events)
    }


@app.post("/rooms/{room_id}/command")
async def send_command(room_id: str, cmd: CommandRequest):
    """Send a manual command to a room's actuator via MQTT."""
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404,
                          detail=f"Room '{room_id}' not found")

    # Validate target and action
    valid_targets = {"fan", "light", "alarm"}
    valid_actions = {"on", "off"}

    if cmd.target not in valid_targets:
        raise HTTPException(status_code=400,
                          detail=f"Invalid target. Must be one of: {valid_targets}")
    if cmd.action not in valid_actions:
        raise HTTPException(status_code=400,
                          detail=f"Invalid action. Must be one of: {valid_actions}")

    # Build command message
    command = {
        "room_id": room_id,
        "target": cmd.target,
        "action": cmd.action,
        "reason": cmd.reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Publish to MQTT
    topic = f"building/{room_id}/actuator/command"
    payload = json.dumps(command)

    result = mqtt_client.publish(topic, payload, qos=1)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logger.info(f" Manual command sent to {room_id}: "
                   f"{cmd.target}={cmd.action}")
        return {
            "status": "command_sent",
            "command": command,
            "topic": topic
        }
    else:
        raise HTTPException(status_code=500,
                          detail="Failed to publish command to MQTT")
```

### 2. `gateway_api/requirements.txt`

```
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
paho-mqtt>=2.0.0
influxdb-client>=1.36.0
```

### 3. `gateway_api/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py .

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 4. `docker-compose.yml`

```yaml
version: "3.8"

services:
  # MQTT Broker
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: mosquitto
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto/config/mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mosquitto_data:/mosquitto/data
      - mosquitto_log:/mosquitto/log
    restart: unless-stopped

  # InfluxDB
  influxdb:
    image: influxdb:2
    container_name: influxdb
    ports:
      - "8086:8086"
    environment:
      - DOCKER_INFLUXDB_INIT_MODE=setup
      - DOCKER_INFLUXDB_INIT_USERNAME=${INFLUXDB_USERNAME:-admin}
      - DOCKER_INFLUXDB_INIT_PASSWORD=${INFLUXDB_PASSWORD:-admin12345}
      - DOCKER_INFLUXDB_INIT_ORG=${INFLUXDB_ORG:-iot-org}
      - DOCKER_INFLUXDB_INIT_BUCKET=${INFLUXDB_BUCKET:-smart-building}
      - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=${INFLUXDB_TOKEN:-my-super-secret-token}
    volumes:
      - influxdb_data:/var/lib/influxdb2
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - influxdb
    restart: unless-stopped

  # Virtual Sensors (1 per room)
  virtual-sensor-room-01:
    build: ./virtual_sensor
    container_name: virtual-sensor-room-01
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-01
      - DEVICE_ID=sensor-room-01
      - PUBLISH_INTERVAL=${PUBLISH_INTERVAL:-5}
    depends_on:
      - mosquitto
    restart: unless-stopped

  virtual-sensor-room-02:
    build: ./virtual_sensor
    container_name: virtual-sensor-room-02
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-02
      - DEVICE_ID=sensor-room-02
      - PUBLISH_INTERVAL=${PUBLISH_INTERVAL:-5}
    depends_on:
      - mosquitto
    restart: unless-stopped

  virtual-sensor-room-03:
    build: ./virtual_sensor
    container_name: virtual-sensor-room-03
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-03
      - DEVICE_ID=sensor-room-03
      - PUBLISH_INTERVAL=${PUBLISH_INTERVAL:-5}
    depends_on:
      - mosquitto
    restart: unless-stopped

  # Virtual Actuators (1 per room)
  virtual-actuator-room-01:
    build: ./virtual_actuator
    container_name: virtual-actuator-room-01
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-01
      - DEVICE_ID=actuator-room-01
    depends_on:
      - mosquitto
    restart: unless-stopped

  virtual-actuator-room-02:
    build: ./virtual_actuator
    container_name: virtual-actuator-room-02
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-02
      - DEVICE_ID=actuator-room-02
    depends_on:
      - mosquitto
    restart: unless-stopped

  virtual-actuator-room-03:
    build: ./virtual_actuator
    container_name: virtual-actuator-room-03
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - ROOM_ID=room-03
      - DEVICE_ID=actuator-room-03
    depends_on:
      - mosquitto
    restart: unless-stopped

  # IoT Gateway
  iot-gateway:
    build: ./iot_gateway
    container_name: iot-gateway
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-my-super-secret-token}
      - INFLUXDB_ORG=${INFLUXDB_ORG:-iot-org}
      - INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-smart-building}
    depends_on:
      - mosquitto
      - influxdb
    restart: unless-stopped

  # Gateway REST API
  gateway-api:
    build: ./gateway_api
    container_name: gateway-api
    ports:
      - "8000:8000"
    environment:
      - MQTT_BROKER=mosquitto
      - MQTT_PORT=1883
      - INFLUXDB_URL=http://influxdb:8086
      - INFLUXDB_TOKEN=${INFLUXDB_TOKEN:-my-super-secret-token}
      - INFLUXDB_ORG=${INFLUXDB_ORG:-iot-org}
      - INFLUXDB_BUCKET=${INFLUXDB_BUCKET:-smart-building}
    depends_on:
      - mosquitto
      - influxdb
    restart: unless-stopped

# Volumes
volumes:
  mosquitto_data:
  mosquitto_log:
  influxdb_data:
  grafana_data:
```

### 5. `mosquitto/config/mosquitto.conf`

```
# Mosquitto MQTT Broker Configuration
# Smart Building IoT Gateway

# Default listener
listener 1883

# Allow anonymous connections (dev environment)
allow_anonymous true

# WebSocket listener (optional)
listener 9001
protocol websockets

# Persistence
persistence true
persistence_location /mosquitto/data/

# Logging
log_dest stdout
log_type all
connection_messages true
```

### 6. `.env.example`

```env
# Smart Building IoT Gateway - Environment Variables
# Copy this file to .env and modify as needed:
#   cp .env.example .env

# --- MQTT ---
MQTT_BROKER=mosquitto
MQTT_PORT=1883

# --- Sensor ---
PUBLISH_INTERVAL=5

# --- InfluxDB ---
INFLUXDB_URL=http://influxdb:8086
INFLUXDB_USERNAME=admin
INFLUXDB_PASSWORD=admin12345
INFLUXDB_ORG=iot-org
INFLUXDB_BUCKET=smart-building
INFLUXDB_TOKEN=my-super-secret-token

# --- Grafana ---
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
```

### 7. `grafana/provisioning/datasources/influxdb.yml`

```yaml
apiVersion: 1

datasources:
  - name: InfluxDB
    type: influxdb
    access: proxy
    url: http://influxdb:8086
    jsonData:
      version: Flux
      organization: iot-org
      defaultBucket: smart-building
    secureJsonData:
      token: my-super-secret-token
    isDefault: true
    editable: true
```

### 8. `grafana/provisioning/dashboards/dashboard.yml`

```yaml
apiVersion: 1

providers:
  - name: "Smart Building"
    orgId: 1
    folder: ""
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /etc/grafana/provisioning/dashboards/json
      foldersFromFilesStructure: false
```

> [!TIP]
> **Grafana Dashboard JSON**: Tạo file `grafana/provisioning/dashboards/json/smart-building.json` chứa dashboard JSON. Cách tạo:
> 1. Chạy Grafana trước (docker compose up grafana influxdb)
> 2. Đăng nhập http://localhost:3000 (admin/admin)
> 3. Tạo dashboard thủ công với 6 panels
> 4. Export dashboard JSON → lưu vào file trên

### Dashboard cần 6 panels:

| # | Panel | Query (Flux) |
|---|---|---|
| 1 | **Nhiệt độ theo phòng** | `from(bucket:"smart-building") \|> range(start: -1h) \|> filter(fn:(r) => r._measurement == "room_telemetry" and r._field == "temperature")` |
| 2 | **CO2 theo phòng** | `...r._field == "co2_ppm"...` |
| 3 | **Độ ẩm theo phòng** | `...r._field == "humidity"...` |
| 4 | **Trạng thái actuator** | `from(bucket:"smart-building") \|> range(start: -1h) \|> filter(fn:(r) => r._measurement == "actuator_status")` |
| 5 | **Event count** | `from(bucket:"smart-building") \|> range(start: -1h) \|> filter(fn:(r) => r._measurement == "gateway_events") \|> count()` |
| 6 | **Bảng events gần nhất** | `from(bucket:"smart-building") \|> range(start: -24h) \|> filter(fn:(r) => r._measurement == "gateway_events") \|> last()` |

---

### 9. `README.md` (Template)

```markdown
#  Smart Building IoT Gateway

Hệ thống Virtual IoT Gateway cho Smart Building — mô phỏng việc thu thập dữ liệu
cảm biến, phát hiện bất thường và điều khiển thiết bị qua MQTT.

##  Kiến trúc hệ thống

(Chèn sơ đồ kiến trúc ở đây)

##  Cách chạy

### Yêu cầu
- Docker & Docker Compose

### Bước 1: Clone và cấu hình
\```bash
git clone <repo-url>
cd smart-building-iot-gateway
cp .env.example .env
\```

### Bước 2: Chạy toàn bộ hệ thống
\```bash
docker compose up -d --build
\```

### Bước 3: Kiểm tra trạng thái
\```bash
docker compose ps
\```

##  Truy cập các service

| Service | URL | Credentials |
|---|---|---|
| Grafana Dashboard | http://localhost:3000 | admin / admin |
| InfluxDB UI | http://localhost:8086 | admin / admin12345 |
| REST API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |

##  Kiểm tra log

\```bash
docker compose logs -f iot-gateway
docker compose logs -f gateway-api
docker compose logs -f virtual-sensor-room-01
docker compose logs -f virtual-actuator-room-01
\```

##  REST API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | /health | Health check |
| GET | /rooms | Danh sách phòng |
| GET | /rooms/{room_id}/state | Trạng thái mới nhất |
| GET | /rooms/{room_id}/events | Events gần nhất |
| POST | /rooms/{room_id}/command | Gửi lệnh thủ công |

### Ví dụ gửi lệnh thủ công
\```bash
curl -X POST http://localhost:8000/rooms/room-01/command \
  -H "Content-Type: application/json" \
  -d '{"target":"fan","action":"on","reason":"manual_control"}'
\```

##  Dừng hệ thống
\```bash
docker compose down
\```

##  Troubleshooting

- **Container không start**: Kiểm tra `docker compose logs <service-name>`
- **MQTT không kết nối**: Đảm bảo Mosquitto container running
- **InfluxDB không có data**: Kiểm tra gateway logs, đảm bảo token đúng
- **Grafana không hiện data**: Kiểm tra datasource configuration

##  Phân công

| Thành viên | Nhiệm vụ |
|---|---|
| TV1 | Virtual Sensor, Virtual Actuator, Topic Design |
| TV2 | IoT Gateway, Rule Engine, InfluxDB Writer |
| TV3 | REST API, Docker Compose, Grafana, README |
```

---

##  Hướng dẫn Test Độc Lập

### Bước 1: Chạy hạ tầng

```bash
# Chạy Mosquitto + InfluxDB + Grafana (không cần sensor/actuator/gateway)
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

### Bước 2: Chạy API

```bash
cd gateway_api
pip install -r requirements.txt

MQTT_BROKER=localhost \
INFLUXDB_URL=http://localhost:8086 \
INFLUXDB_TOKEN=my-super-secret-token \
INFLUXDB_ORG=iot-org \
INFLUXDB_BUCKET=smart-building \
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### Bước 3: Test endpoints

```bash
# Health check
curl http://localhost:8000/health

# List rooms
curl http://localhost:8000/rooms

# Room state (sẽ null nếu chưa có data trong InfluxDB)
curl http://localhost:8000/rooms/room-01/state

# Gửi command thủ công
curl -X POST http://localhost:8000/rooms/room-01/command \
  -H "Content-Type: application/json" \
  -d '{"target":"fan","action":"on","reason":"manual_test"}'

# Xem command trên MQTT
mosquitto_sub -h localhost -t "building/+/actuator/command" -v
```

### Bước 4: Giả lập dữ liệu trong InfluxDB

Dùng InfluxDB UI (http://localhost:8086) hoặc mosquitto_pub + gateway giả lập để tạo data, rồi test GET /rooms/{room_id}/state.

### Bước 5: Test Swagger UI

Truy cập http://localhost:8000/docs để test tất cả endpoints trực quan.

**Kiểm tra:**
-  `GET /health` trả về `{"status": "ok"}`
-  `GET /rooms` trả về 3 rooms
-  `POST .../command` publish message lên MQTT topic đúng
-  `GET .../state` trả về data từ InfluxDB (khi có data)
-  `GET .../events` trả về danh sách events
-  API không crash khi InfluxDB chưa có data

---

##  Timeline gợi ý (trong 1 tuần)

| Ngày | Công việc |
|---|---|
| **Ngày 1** | Đọc hiểu đề bài. Viết `docker-compose.yml` + `.env.example` + `mosquitto.conf`. |
| **Ngày 2** | Code `api.py` — các GET endpoints + InfluxDB query. |
| **Ngày 3** | Code `api.py` — POST command endpoint + MQTT publish. Viết Dockerfile. |
| **Ngày 4** | Cấu hình Grafana provisioning. Tạo 6 dashboard panels. |
| **Ngày 5** | Viết `README.md`. Test API độc lập. Fix bugs. |
| **Ngày 6–7** | **TÍCH HỢP** toàn bộ stack. `docker compose up`. Debug + chụp screenshot. |

---

##  Integration Checklist (khi merge với TV1, TV2)

- [ ] `docker compose up -d --build` chạy không lỗi
- [ ] `docker compose ps` — tất cả container đều running
- [ ] Sensor (TV1) publish data → Gateway (TV2) nhận → InfluxDB có data
- [ ] API query InfluxDB trả về data mới nhất
- [ ] API gửi command → Actuator (TV1) nhận và phản hồi
- [ ] Grafana hiển thị đúng 6 panels với data realtime
- [ ] Env vars trong docker-compose.yml khớp với code của TV1 và TV2
- [ ] Docker volumes hoạt động (restart không mất data)
- [ ] README đủ rõ để chạy lại từ đầu
- [ ] Chụp screenshot cho báo cáo: docker ps, MQTT messages, Grafana, InfluxDB, API


**Nâng cao:**
- [ ] Mosquitto có username/password — tất cả service kết nối được với auth
- [ ] Tất cả service có `healthcheck` — `docker compose ps` hiển thị `healthy`
- [ ] `PUT /config/thresholds` cập nhật threshold trong gateway (TV2) thành công
- [ ] Grafana alert rule sinh cảnh báo khi nhiệt độ > 30 hoặc CO2 > 1200

---

##  NÂNG CAO — Code bổ sung

### [Nâng cao #1] Mosquitto Authentication (username/password)

#### `mosquitto/config/mosquitto.conf` (bản có auth)

```
listener 1883
allow_anonymous false
password_file /mosquitto/config/passwd

listener 9001
protocol websockets
allow_anonymous false
password_file /mosquitto/config/passwd

persistence true
persistence_location /mosquitto/data/
log_dest stdout
```

#### Tạo file password:

```bash
# Chạy trong terminal, không phải trong docker-compose
docker run --rm eclipse-mosquitto:2 sh -c "mosquitto_passwd -b -c /tmp/passwd iotuser iotpass; cat /tmp/passwd" > mosquitto/config/passwd
```

#### Cập nhật `.env.example` và `.env`:

```env
MQTT_USERNAME=iotuser
MQTT_PASSWORD=iotpass
```

#### Cập nhật `docker-compose.yml` — thêm env vars MQTT auth vào tất cả service:

```yaml
environment:
  - MQTT_USERNAME=${MQTT_USERNAME:-iotuser}
  - MQTT_PASSWORD=${MQTT_PASSWORD:-iotpass}
```

#### Code cần thêm vào `sensor.py`, `actuator.py`, `gateway.py`, `api.py` (TV1 + TV2 thực hiện):

```python
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

# Sau khi tạo mqtt.Client():
if MQTT_USERNAME:
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    logger.info(f"MQTT auth enabled for user: {MQTT_USERNAME}")
```

---

### [Nâng cao #3] Health Checks trong Docker Compose

Cập nhật `docker-compose.yml` — thêm `healthcheck` vào các service:

```yaml
  influxdb:
    image: influxdb:2
    healthcheck:
      test: ["CMD", "influx", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  mosquitto:
    image: eclipse-mosquitto:2
    healthcheck:
      test: ["CMD-SHELL", "mosquitto_sub -t '$$SYS/#' -C 1 -i healthcheck -W 3 2>/dev/null; exit 0"]
      interval: 10s
      timeout: 5s
      retries: 3

  grafana:
    image: grafana/grafana:latest
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:3000/api/health -O /dev/null"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 20s

  gateway-api:
    build: ./gateway_api
    healthcheck:
      test: ["CMD-SHELL", "wget -q --tries=1 http://localhost:8000/health -O /dev/null"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
```

Cập nhật `depends_on` để chờ service healthy trước:

```yaml
iot-gateway:
  depends_on:
    mosquitto:
      condition: service_healthy
    influxdb:
      condition: service_healthy
```

---

### [Nâng cao #6] API Endpoint Threshold Dynamic

Thêm vào `api.py` — 2 endpoint GET/PUT để đọc và cập nhật threshold:

```python
import json as _json

THRESHOLD_FILE = os.getenv("THRESHOLD_FILE", "/app/thresholds.json")
DEFAULT_THRESHOLDS = {
    "temperature_high": 30.0,
    "temperature_low": 27.0,
    "co2_high": 1200.0,
    "light_unnecessary": 300.0,
}


class ThresholdUpdate(BaseModel):
    temperature_high: float = None
    temperature_low: float = None
    co2_high: float = None
    light_unnecessary: float = None


@app.get("/config/thresholds")
async def get_thresholds():
    """Return current rule engine thresholds."""
    try:
        if os.path.exists(THRESHOLD_FILE):
            with open(THRESHOLD_FILE) as f:
                return _json.load(f)
        return DEFAULT_THRESHOLDS
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/config/thresholds")
async def update_thresholds(update: ThresholdUpdate):
    """Update rule engine thresholds (shared volume with gateway)."""
    try:
        current = DEFAULT_THRESHOLDS.copy()
        if os.path.exists(THRESHOLD_FILE):
            with open(THRESHOLD_FILE) as f:
                current = _json.load(f)
        updates = update.model_dump(exclude_none=True)
        current.update(updates)
        with open(THRESHOLD_FILE, "w") as f:
            _json.dump(current, f, indent=2)
        logger.info(f"Thresholds updated: {updates}")
        return {"status": "updated", "thresholds": current}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

> **Quan trọng:** Cần shared Docker volume giữa `gateway-api` và `iot-gateway`:
> ```yaml
> volumes:
>   thresholds_data:
>
> iot-gateway:
>   volumes:
>     - thresholds_data:/app
>
> gateway-api:
>   volumes:
>     - thresholds_data:/app
> ```

**Test:**
```bash
curl http://localhost:8000/config/thresholds

curl -X PUT http://localhost:8000/config/thresholds \
  -H "Content-Type: application/json" \
  -d '{"temperature_high": 28.0}'
```

---

### [Nâng cao #7] Grafana Alert Rules

Tạo file `grafana/provisioning/alerting/rules.yml`:

```yaml
apiVersion: 1

groups:
  - orgId: 1
    name: SmartBuilding Alerts
    folder: Smart Building
    interval: 1m
    rules:

      - uid: alert-temperature-high
        title: Temperature High Alert
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: influxdb
            model:
              query: |
                from(bucket: "smart-building")
                  |> range(start: -5m)
                  |> filter(fn: (r) => r._measurement == "room_telemetry" and r._field == "temperature")
                  |> mean()
          - refId: C
            datasourceUid: "-100"
            model:
              conditions:
                - evaluator: {params: [30], type: gt}
                  query: {params: [A]}
                  reducer: {type: last}
                  type: query
              refId: C
              type: classic_conditions
        noDataState: NoData
        execErrState: Error
        for: 2m
        annotations:
          summary: "Nhiet do vuot nguong 30 do C"
        labels:
          severity: warning

      - uid: alert-co2-high
        title: CO2 Level High Alert
        condition: C
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: influxdb
            model:
              query: |
                from(bucket: "smart-building")
                  |> range(start: -5m)
                  |> filter(fn: (r) => r._measurement == "room_telemetry" and r._field == "co2_ppm")
                  |> mean()
          - refId: C
            datasourceUid: "-100"
            model:
              conditions:
                - evaluator: {params: [1200], type: gt}
                  query: {params: [A]}
                  reducer: {type: last}
                  type: query
              refId: C
              type: classic_conditions
        noDataState: NoData
        execErrState: Error
        for: 2m
        annotations:
          summary: "Muc CO2 vuot nguong 1200 ppm"
        labels:
          severity: critical
```

> **Kiểm tra:** Vào Grafana UI → **Alerting → Alert rules → SmartBuilding Alerts**
> Trạng thái sẽ hiển thị `Normal`, `Pending`, hoặc `Firing`.
