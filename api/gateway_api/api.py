"""
REST API for Smart Building IoT Gateway.
Provides endpoints to query room states and send manual commands.
Built with FastAPI.
"""

# ============================================================
# 📋 CHECKLIST TÍCH HỢP — Những chỗ CẦN KIỂM TRA sau khi nhận code TV1 + TV2
# ============================================================
# ⚠️ [1] KNOWN_ROOMS  : Phải khớp với ROOM_ID TV1 khai báo trong sensor/actuator
# ⚠️ [2] MQTT topics  : Phải khớp với topic TV1 subscribe (building/{room_id}/actuator/command)
# ⚠️ [3] Measurement  : Phải khớp với tên TV2 dùng khi ghi vào InfluxDB
# ⚠️ [4] Field names  : Phải khớp với tên fields TV2 ghi vào InfluxDB
# ⚠️ [5] MQTT auth    : Nếu TV2 bật auth, cần thêm username_pw_set() vào mqtt_client
# ============================================================

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient

# ============================================================
# Đọc cấu hình từ environment variables
# ============================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "iot-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "smart-building")

# ⚠️ TODO [SYNC TV1] — Checklist item #1
# Danh sách phòng PHẢI KHỚP với ROOM_ID mà TV1 cấu hình trong sensor và actuator.
# Kiểm tra: docker-compose.yml của TV1 → env var ROOM_ID của mỗi container sensor/actuator
# Nếu TV1 dùng tên khác (vd: "room_01" thay vì "room-01") → sửa list này
KNOWN_ROOMS = ["room-01", "room-02", "room-03"]

# Cấu hình logging để dễ debug
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gateway-api")

# ============================================================
# Khởi tạo FastAPI app
# ============================================================
app = FastAPI(
    title="Smart Building IoT Gateway API",
    description="REST API for querying room states and sending manual commands",
    version="1.0.0"
)

# ============================================================
# Pydantic Models — Định nghĩa cấu trúc dữ liệu request/response
# ============================================================
class CommandRequest(BaseModel):
    target: str    # fan | light | alarm
    action: str    # on | off
    reason: str = "manual_control"


class HealthResponse(BaseModel):
    status: str
    timestamp: str


# ============================================================
# MQTT Client — chỉ dùng để PUBLISH lệnh điều khiển
# ============================================================
# ⚠️ TODO [SYNC TV2] — Checklist item #5
# Nếu TV2 cấu hình Mosquitto có username/password (nâng cao),
# cần bổ sung 2 dòng sau TRƯỚC khi gọi mqtt_client.connect():
#
#   MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
#   MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
#   if MQTT_USERNAME:
#       mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
#
# Và thêm vào .env: MQTT_USERNAME=iotuser, MQTT_PASSWORD=iotpass
mqtt_client = mqtt.Client(
    client_id="gateway-api",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
)


@app.on_event("startup")
async def startup():
    """Kết nối tới MQTT broker khi API khởi động."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        logger.info(f"✅ MQTT connected to {MQTT_BROKER}:{MQTT_PORT}")
    except Exception as e:
        logger.error(f"❌ MQTT connection failed: {e}")


@app.on_event("shutdown")
async def shutdown():
    """Ngắt kết nối MQTT khi API tắt."""
    mqtt_client.loop_stop()
    mqtt_client.disconnect()


# ============================================================
# InfluxDB Query Helpers
# ============================================================
def get_influx_client():
    """Tạo mới InfluxDB client mỗi lần dùng."""
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )


def query_latest_telemetry(room_id: str) -> Optional[dict]:
    """Lấy bản ghi cảm biến mới nhất của phòng từ InfluxDB."""
    client = get_influx_client()
    query_api = client.query_api()

    # ⚠️ TODO [SYNC TV2] — Checklist item #3
    # Tên measurement "room_telemetry" PHẢI KHỚP với tên TV2 dùng khi write vào InfluxDB.
    # Kiểm tra file iot_gateway/gateway.py của TV2 → tìm dòng write_api.write(...)
    # Ví dụ: nếu TV2 dùng measurement="telemetry" thì sửa "room_telemetry" → "telemetry"
    #
    # ⚠️ TODO [SYNC TV2] — Checklist item #4 (Field names)
    # Tag "room_id" và các field "temperature", "humidity", "light_lux",
    # "co2_ppm", "occupancy" PHẢI KHỚP với tags/fields TV2 ghi vào InfluxDB.
    # Kiểm tra: shared contract trong project_prompt.md → A6. InfluxDB Measurements
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
                    # ⚠️ TODO [SYNC TV2]: Các key dưới đây phải khớp với field name TV2 ghi vào InfluxDB
                    # Nếu TV2 ghi field là "temp" thay vì "temperature" → sửa "temperature" → "temp"
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
    """Lấy trạng thái actuator (fan/light/alarm) mới nhất của phòng."""
    client = get_influx_client()
    query_api = client.query_api()

    # ⚠️ TODO [SYNC TV2] — Checklist item #3
    # Tên measurement "actuator_status" PHẢI KHỚP với tên TV2 ghi vào InfluxDB.
    # TV2 ghi actuator status sau khi nhận status message từ TV1 (actuator).
    # Kiểm tra iot_gateway/gateway.py của TV2 → measurement name khi ghi actuator_status
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
                    # ⚠️ TODO [SYNC TV1 + TV2]: "fan", "light", "alarm" là tên field
                    # TV1 publish trong status message, TV2 đọc và ghi vào InfluxDB.
                    # Kiểm tra actuator.py (TV1) → status message JSON → tên keys
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
    """Lấy danh sách cảnh báo (events) gần nhất của phòng trong 24h."""
    client = get_influx_client()
    query_api = client.query_api()

    # ⚠️ TODO [SYNC TV2] — Checklist item #3
    # Measurement "gateway_events" là do TV2 ghi vào khi rule engine phát hiện bất thường.
    # Kiểm tra iot_gateway/gateway.py (TV2) → measurement name khi ghi event
    # Tag "room_id" và fields "event_type", "severity", "value", "threshold", "action_taken"
    # PHẢI KHỚP với những gì TV2 ghi vào InfluxDB.
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


# ============================================================
# API Endpoints
# ============================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Kiểm tra API có đang chạy không."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat()
    )


@app.get("/rooms")
async def list_rooms():
    """Trả về danh sách các phòng trong hệ thống."""
    return {
        "rooms": KNOWN_ROOMS,
        "count": len(KNOWN_ROOMS)
    }


@app.get("/rooms/{room_id}/state")
async def get_room_state(room_id: str):
    """
    Trả về trạng thái mới nhất của phòng:
    - telemetry: dữ liệu cảm biến (nhiệt độ, độ ẩm, CO2...)
    - actuator: trạng thái thiết bị (fan, light, alarm)
    """
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    telemetry = query_latest_telemetry(room_id)
    actuator = query_latest_actuator(room_id)

    return {
        "room_id": room_id,
        "telemetry": telemetry,
        "actuator": actuator
    }


@app.get("/rooms/{room_id}/events")
async def get_room_events(room_id: str, limit: int = 20):
    """Trả về danh sách cảnh báo gần nhất của phòng."""
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    events = query_events(room_id, limit)
    return {
        "room_id": room_id,
        "events": events,
        "count": len(events)
    }


@app.post("/rooms/{room_id}/command")
async def send_command(room_id: str, cmd: CommandRequest):
    """
    Gửi lệnh điều khiển thủ công đến thiết bị trong phòng qua MQTT.
    Ví dụ: bật quạt, tắt đèn, kích hoạt alarm.
    Topic: building/{room_id}/actuator/command
    """
    if room_id not in KNOWN_ROOMS:
        raise HTTPException(status_code=404, detail=f"Room '{room_id}' not found")

    # Kiểm tra target và action hợp lệ
    valid_targets = {"fan", "light", "alarm"}
    valid_actions = {"on", "off"}

    if cmd.target not in valid_targets:
        raise HTTPException(status_code=400,
                          detail=f"Invalid target. Must be one of: {valid_targets}")
    if cmd.action not in valid_actions:
        raise HTTPException(status_code=400,
                          detail=f"Invalid action. Must be one of: {valid_actions}")

    # ⚠️ TODO [SYNC TV1] — Checklist item #2
    # Format của command JSON dưới đây PHẢI KHỚP với những gì TV1 expect trong actuator.py
    # Kiểm tra actuator.py (TV1) → hàm xử lý message → parse các field nào?
    # Theo Shared Contract (project_prompt.md A3), format chuẩn là:
    # { "room_id", "target": fan|light|alarm, "action": on|off, "reason", "timestamp" }
    command = {
        "room_id": room_id,
        "target": cmd.target,    # ⚠️ TV1 expect key này là "target" hay tên khác?
        "action": cmd.action,    # ⚠️ TV1 expect "on"/"off" hay "true"/"false"?
        "reason": cmd.reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # ⚠️ TODO [SYNC TV1] — Checklist item #2
    # Topic này PHẢI KHỚP với topic TV1 subscribe trong actuator.py
    # Kiểm tra actuator.py (TV1) → client.subscribe(...) → tên topic có đúng format này không?
    # Theo Shared Contract: building/{room_id}/actuator/command
    topic = f"building/{room_id}/actuator/command"
    payload = json.dumps(command)

    result = mqtt_client.publish(topic, payload, qos=1)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        logger.info(f"📤 Manual command sent to {room_id}: {cmd.target}={cmd.action}")
        return {
            "status": "command_sent",
            "command": command,
            "topic": topic
        }
    else:
        raise HTTPException(status_code=500,
                          detail="Failed to publish command to MQTT")
