# Prompt: Lập kế hoạch chia việc song song cho 3 người — Virtual Smart Building Gateway

> Copy toàn bộ prompt bên dưới và dán vào AI assistant (ChatGPT, Gemini, Claude,...) để sinh ra kế hoạch chi tiết cho nhóm.

---

##  PROMPT

```
Tôi cần bạn lập kế hoạch triển khai chi tiết cho mini-project "Virtual Smart Building Gateway" — một hệ thống IoT ảo hóa hoàn chỉnh chạy bằng Docker Compose. Hệ thống mô phỏng smart building với ít nhất 3 phòng (room-01, room-02, room-03), mỗi phòng có virtual sensor và virtual actuator, kết nối qua MQTT broker (Mosquitto), xử lý bởi virtual IoT gateway, lưu trữ vào InfluxDB, hiển thị trên Grafana dashboard, và cung cấp REST API.

---

## PHẦN A — QUY ƯỚC CHUNG (SHARED CONTRACTS)

Trước khi chia việc, hãy xác định rõ các quy ước chung mà CẢ 3 THÀNH VIÊN đều phải tuân theo để có thể code song song mà không phụ thuộc nhau:

### A1. Cấu trúc thư mục project
smart-building-iot-gateway/
├── docker-compose.yml
├── README.md
├── .env.example
├── mosquitto/
│   └── config/
│       └── mosquitto.conf
├── virtual_sensor/
│   ├── sensor.py
│   ├── requirements.txt
│   └── Dockerfile
├── virtual_actuator/
│   ├── actuator.py
│   ├── requirements.txt
│   └── Dockerfile
├── iot_gateway/
│   ├── gateway.py
│   ├── rule_engine.py
│   ├── state_store.py
│   ├── requirements.txt
│   └── Dockerfile
├── gateway_api/
│   ├── api.py
│   ├── requirements.txt
│   └── Dockerfile
├── grafana/
│   └── provisioning/ (datasource + dashboard JSON nếu có)
├── docs/
│   ├── architecture.png
│   └── topic-design.md
└── screenshots/

### A2. MQTT Topic Hierarchy (BẮT BUỘC tuân theo)
- Telemetry (sensor → gateway):  `building/{room_id}/sensor/telemetry`
- Command (gateway → actuator):  `building/{room_id}/actuator/command`
- Status (actuator → gateway):   `building/{room_id}/actuator/status`
- Normalized (gateway publish):  `building/{room_id}/gateway/normalized`
- Event (gateway publish):       `building/{room_id}/gateway/event`

Trong đó room_id ∈ {room-01, room-02, room-03}.

### A3. Message Format (JSON) — BẮT BUỘC tuân theo

**Telemetry message (sensor publish):**
```json
{
  "device_id": "sensor-room-01",
  "room_id": "room-01",
  "temperature": 29.5,
  "humidity": 73.2,
  "light_lux": 380.0,
  "co2_ppm": 950.0,
  "occupancy": true,
  "timestamp": "2026-06-10T10:00:00Z"
}
```

**Command message (gateway → actuator):**
```json
{
  "room_id": "room-01",
  "target": "fan",        // fan | light | alarm
  "action": "on",         // on | off
  "reason": "temperature_high",
  "timestamp": "2026-06-10T10:00:05Z"
}
```

**Status message (actuator → gateway):**
```json
{
  "device_id": "actuator-room-01",
  "room_id": "room-01",
  "fan": "on",
  "light": "off",
  "alarm": "off",
  "last_command_reason": "temperature_high",
  "timestamp": "2026-06-10T10:00:06Z"
}
```

**Event message (gateway publish):**
```json
{
  "room_id": "room-01",
  "event_type": "temperature_high",
  "severity": "warning",
  "value": 32.5,
  "threshold": 30.0,
  "action_taken": "fan_on",
  "timestamp": "2026-06-10T10:00:05Z"
}
```

### A4. Environment Variables chung
Tất cả service đều đọc cấu hình từ environment variables, KHÔNG hard-code:
- `MQTT_BROKER=mosquitto`
- `MQTT_PORT=1883`
- `ROOM_ID=room-01` (cho sensor/actuator)
- `DEVICE_ID=sensor-room-01` hoặc `actuator-room-01`
- `PUBLISH_INTERVAL=5` (giây, cho sensor)
- `INFLUXDB_URL=http://influxdb:8086`
- `INFLUXDB_TOKEN=my-super-secret-token`
- `INFLUXDB_ORG=iot-org`
- `INFLUXDB_BUCKET=smart-building`

### A5. Rule Engine — 4 luật BẮT BUỘC
1. Nếu `temperature > 30` → bật quạt (fan ON)
2. Nếu `temperature < 27` → tắt quạt (fan OFF)
3. Nếu `co2_ppm > 1200` → bật alarm (alarm ON)
4. Nếu `occupancy == false` VÀ `light_lux > 300` → tắt đèn (light OFF)

### A6. InfluxDB Measurements
- `room_telemetry`: tags=[room_id, device_id], fields=[temperature, humidity, light_lux, co2_ppm, occupancy]
- `gateway_events`: tags=[room_id, event_type, severity], fields=[value, threshold, action_taken]
- `actuator_status`: tags=[room_id, device_id], fields=[fan, light, alarm]

### A7. Docker service names (trong docker-compose.yml)
mosquitto, virtual-sensor-room-01, virtual-sensor-room-02, virtual-sensor-room-03, virtual-actuator-room-01, virtual-actuator-room-02, virtual-actuator-room-03, iot-gateway, influxdb, grafana, gateway-api

---

## PHẦN B — PHÂN CÔNG SONG SONG CHO 3 THÀNH VIÊN

### ‍ THÀNH VIÊN 1: Virtual Sensor + Virtual Actuator + Thiết kế topic/message

**Scope:** Toàn bộ folder `virtual_sensor/` và `virtual_actuator/`, file `docs/topic-design.md`

**Nhiệm vụ cụ thể:**
1. Lập trình `virtual_sensor/sensor.py`:
   - Đọc cấu hình từ env vars (ROOM_ID, DEVICE_ID, MQTT_BROKER, PUBLISH_INTERVAL)
   - Sinh dữ liệu môi trường có xu hướng (không random hoàn toàn — lưu giá trị trước đó, thay đổi nhẹ mỗi chu kỳ)
   - Có cơ chế sinh bất thường theo xác suất (~10%) hoặc theo chu kỳ
   - Publish JSON lên topic `building/{room_id}/sensor/telemetry`
2. Lập trình `virtual_actuator/actuator.py`:
   - Subscribe topic `building/{room_id}/actuator/command`
   - Parse command JSON, cập nhật trạng thái nội bộ (fan, light, alarm)
   - Publish trạng thái mới lên `building/{room_id}/actuator/status`
   - Log rõ ràng khi nhận lệnh hợp lệ hoặc sai format
3. Viết Dockerfile cho cả 2 service
4. Viết `requirements.txt` cho cả 2 service
5. Viết `docs/topic-design.md` mô tả topic hierarchy và message format

**Deliverables:** `virtual_sensor/`, `virtual_actuator/`, `docs/topic-design.md`
**Có thể test độc lập:** Dùng Mosquitto local + mosquitto_sub/mosquitto_pub để verify

---

### ‍ THÀNH VIÊN 2: Virtual IoT Gateway + Rule Engine + InfluxDB

**Scope:** Toàn bộ folder `iot_gateway/`

**Nhiệm vụ cụ thể:**
1. Lập trình `iot_gateway/gateway.py`:
   - Subscribe `building/+/sensor/telemetry` (wildcard cho tất cả phòng)
   - Validate message: kiểm tra room_id, device_id, timestamp và các field dữ liệu
   - Chuẩn hóa message thành format thống nhất
   - Lưu trạng thái mới nhất của từng phòng (trong memory hoặc state_store)
   - Ghi telemetry data vào InfluxDB (measurement: `room_telemetry`)
   - Gọi rule engine để kiểm tra bất thường
   - Sinh event message khi có bất thường, ghi vào InfluxDB (`gateway_events`) và publish lên MQTT
   - Gửi command đến actuator qua MQTT khi cần
   - Subscribe `building/+/actuator/status` và ghi trạng thái actuator vào InfluxDB (`actuator_status`)
2. Lập trình `iot_gateway/rule_engine.py`:
   - Implement 4 luật bắt buộc (xem phần A5)
   - Thiết kế dạng extensible (dễ thêm luật mới)
   - Trả về danh sách events và commands cần thực hiện
3. Lập trình `iot_gateway/state_store.py`:
   - Lưu trạng thái mới nhất của từng phòng (latest telemetry + actuator status)
   - Cung cấp API nội bộ để gateway_api có thể truy vấn (nếu cần chia sẻ state)
4. Viết Dockerfile và `requirements.txt`

**Deliverables:** `iot_gateway/`
**Có thể test độc lập:** Dùng mosquitto_pub giả lập sensor data, kiểm tra InfluxDB có dữ liệu

---

### ‍ THÀNH VIÊN 3: REST API + Docker Compose + Grafana Dashboard + README

**Scope:** Folder `gateway_api/`, file `docker-compose.yml`, `mosquitto/`, `grafana/`, `README.md`, `.env.example`

**Nhiệm vụ cụ thể:**
1. Lập trình `gateway_api/api.py` (dùng FastAPI):
   - `GET /health` — health check
   - `GET /rooms` — danh sách phòng
   - `GET /rooms/{room_id}/state` — trạng thái mới nhất (đọc từ InfluxDB hoặc shared state)
   - `GET /rooms/{room_id}/events` — events gần nhất (query InfluxDB)
   - `POST /rooms/{room_id}/command` — gửi lệnh thủ công (publish trực tiếp lên MQTT topic `building/{room_id}/actuator/command`)
2. Viết Dockerfile và `requirements.txt` cho API
3. Viết `docker-compose.yml` hoàn chỉnh:
   - Tất cả services (xem phần A7)
   - Environment variables từ .env
   - Docker volumes cho InfluxDB và Grafana
   - Docker network cho tất cả services
   - Health checks (bonus)
4. Cấu hình `mosquitto/config/mosquitto.conf`
5. Cấu hình Grafana dashboard với ít nhất 6 panels:
   - Nhiệt độ theo thời gian cho từng phòng
   - CO2 theo thời gian cho từng phòng
   - Độ ẩm theo thời gian cho từng phòng
   - Trạng thái fan/light/alarm theo từng phòng
   - Số lượng event bất thường theo thời gian
   - Bảng event gần nhất (room_id, event_type, severity, action_taken)
6. Viết `README.md` chi tiết (mô tả hệ thống, cách chạy, cách kiểm tra, cách truy cập dashboard, troubleshooting)
7. Viết `.env.example`

**Deliverables:** `gateway_api/`, `docker-compose.yml`, `mosquitto/`, `grafana/`, `README.md`, `.env.example`
**Có thể test độc lập:** Dùng mosquitto_pub giả lập data, test API bằng curl/Postman

---

## PHẦN C — YÊU CẦU ĐẦU RA

Hãy sinh ra kế hoạch triển khai chi tiết cho MỖI thành viên, bao gồm:

1. **Checklist task theo thứ tự thực hiện** (mỗi task có ước lượng thời gian)
2. **Code skeleton/template** cho mỗi file chính (sensor.py, actuator.py, gateway.py, rule_engine.py, state_store.py, api.py)
3. **Dockerfile mẫu** cho mỗi service
4. **docker-compose.yml hoàn chỉnh**
5. **Mosquitto config mẫu**
6. **Hướng dẫn test độc lập** cho mỗi thành viên (không cần chờ người khác hoàn thành)
7. **Quy trình tích hợp (integration)** — khi cả 3 merge code lại, cần kiểm tra những gì
8. **Timeline gợi ý** (giả sử có 1 tuần)

Lưu ý:
- Tất cả code bằng Python
- Sử dụng paho-mqtt cho MQTT client
- Sử dụng influxdb-client cho InfluxDB
- Sử dụng FastAPI cho REST API
- Tuân thủ nghiêm ngặt các shared contracts ở Phần A
- Mỗi thành viên phải có thể chạy và test phần của mình ĐỘC LẬP trước khi tích hợp
```

---

> [!TIP]
> **Cách sử dụng prompt này:**
> 1. Copy toàn bộ nội dung trong block ` ``` ` ở trên
> 2. Dán vào ChatGPT / Gemini / Claude
> 3. AI sẽ sinh ra kế hoạch chi tiết với code skeleton, timeline, và hướng dẫn test cho từng người
> 4. Mỗi thành viên lấy phần của mình và bắt đầu code ngay

> [!IMPORTANT]
> **Nguyên tắc song song hóa:** Cả 3 người giao tiếp qua "contracts" (MQTT topics, message format, env vars) đã thống nhất trước. Ai cũng có thể test phần mình bằng cách giả lập input từ mosquitto_pub/mosquitto_sub mà không cần chờ code của người khác.
