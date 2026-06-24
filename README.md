#  Virtual Smart Building IoT Gateway

Hệ thống giám sát và điều khiển tòa nhà thông minh ảo (Virtual Smart Building) sử dụng IoT Gateway. Hệ thống mô phỏng các cảm biến môi trường, bộ điều khiển thiết bị, rule engine xử lý bất thường, REST API và dashboard Grafana — tất cả triển khai bằng Docker Compose.

##  Kiến trúc hệ thống

```
┌──────────────┐     MQTT Telemetry      ┌──────────────┐     Write       ┌──────────────┐
│  Virtual     │ ────────────────────── │  IoT         │ ───────────── │  InfluxDB    │
│  Sensors     │  building/{room}/       │  Gateway     │                │  (Time-Series│
│  (3 phòng)   │  sensor/telemetry       │  + Rule      │                │   Database)  │
└──────────────┘                         │  Engine      │                └──────┬───────┘
                                         └──────┬───────┘                       │
                                                │                               │ Query
                                    MQTT Command│                               │
                                                                               
┌──────────────┐     MQTT Status         ┌──────────────┐              ┌──────────────┐
│  Virtual     │ ────────────────────── │  building/   │              │  REST API    │
│  Actuators   │  building/{room}/       │  {room}/     │              │  (FastAPI)   │
│  (3 phòng)   │  actuator/status        │  actuator/   │              │  Port 8000   │
└──────────────┘                         │  command     │              └──────────────┘
                                         └──────────────┘
                                                                       ┌──────────────┐
                                                                       │  Grafana     │
                                                                       │  Dashboard   │
                                                                       │  Port 3000   │
                                                                       └──────────────┘
```

### Luồng dữ liệu

1. **Virtual Sensor** đọc dữ liệu mô phỏng (nhiệt độ, độ ẩm, CO2, ánh sáng, occupancy) → publish lên MQTT topic `building/{room_id}/sensor/telemetry`
2. **IoT Gateway** subscribe MQTT, nhận telemetry → validate → normalize → ghi vào InfluxDB (`room_telemetry`)
3. **Rule Engine** đánh giá 4 luật bất thường:
   - Nhiệt độ > 30°C → Bật quạt
   - Nhiệt độ < 27°C → Tắt quạt
   - CO2 > 1200 ppm → Bật alarm
   - Không có người + Ánh sáng > 300 lux → Tắt đèn
4. Nếu phát hiện bất thường → ghi event vào InfluxDB (`gateway_events`) + gửi command qua MQTT
5. **Virtual Actuator** nhận command → áp dụng → publish status lại qua MQTT → Gateway ghi vào InfluxDB (`actuator_status`)
6. **REST API** query InfluxDB để hiển thị dữ liệu và cho phép gửi lệnh điều khiển thủ công
7. **Grafana** hiển thị dashboard realtime từ InfluxDB

---

##  Danh sách Services

| Service | Container Name | Port | Mô tả |
|---|---|---|---|
| Mosquitto | `mosquitto` | 1883, 9001 | MQTT Broker trung tâm |
| InfluxDB | `influxdb` | 8086 | Time-series database |
| Grafana | `grafana` | 3000 | Dashboard giám sát |
| Gateway API | `gateway-api` | 8000 | REST API (FastAPI) |
| IoT Gateway | `iot-gateway` | — | Gateway + Rule Engine |
| Sensor Room 01 | `virtual-sensor-room-01` | — | Cảm biến phòng 01 |
| Sensor Room 02 | `virtual-sensor-room-02` | — | Cảm biến phòng 02 |
| Sensor Room 03 | `virtual-sensor-room-03` | — | Cảm biến phòng 03 |
| Actuator Room 01 | `virtual-actuator-room-01` | — | Thiết bị phòng 01 |
| Actuator Room 02 | `virtual-actuator-room-02` | — | Thiết bị phòng 02 |
| Actuator Room 03 | `virtual-actuator-room-03` | — | Thiết bị phòng 03 |

---

## ️ Environment Variables

Tất cả service đều đọc cấu hình từ environment variables, **không hard-code** trong source code.

### Cấu hình chung

| Biến | Giá trị mặc định | Mô tả | Service sử dụng |
|---|---|---|---|
| `MQTT_BROKER` | `mosquitto` | Hostname của MQTT broker | Sensor, Actuator, Gateway, API |
| `MQTT_PORT` | `1883` | Port của MQTT broker | Sensor, Actuator, Gateway, API |

### Sensor

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `ROOM_ID` | `room-01` | ID phòng mà sensor thuộc về |
| `DEVICE_ID` | `sensor-{ROOM_ID}` | ID thiết bị sensor |
| `PUBLISH_INTERVAL` | `5` | Chu kỳ gửi dữ liệu (giây) |

### Actuator

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `ROOM_ID` | `room-01` | ID phòng mà actuator thuộc về |
| `DEVICE_ID` | `actuator-{ROOM_ID}` | ID thiết bị actuator |

### Gateway & API

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `INFLUXDB_URL` | `http://influxdb:8086` | URL của InfluxDB |
| `INFLUXDB_TOKEN` | `my-super-secret-token` | Token xác thực InfluxDB |
| `INFLUXDB_ORG` | `iot-org` | Organization trong InfluxDB |
| `INFLUXDB_BUCKET` | `smart-building` | Bucket lưu dữ liệu |

### InfluxDB

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `INFLUXDB_USERNAME` | `admin` | Username InfluxDB |
| `INFLUXDB_PASSWORD` | `admin12345` | Password InfluxDB |

### Grafana

| Biến | Giá trị mặc định | Mô tả |
|---|---|---|
| `GRAFANA_USER` | `admin` | Username Grafana |
| `GRAFANA_PASSWORD` | `admin` | Password Grafana |

> **Tùy chỉnh**: Copy file `.env.example` thành `.env` trong thư mục `api/` và chỉnh sửa giá trị theo nhu cầu:
> ```bash
> cd api
> cp .env.example .env
> # Sửa file .env theo ý muốn
> ```

---

##  Cách chạy hệ thống

### Yêu cầu

- **Docker** (>= 20.0) và **Docker Compose** (>= 2.0)
- Đảm bảo các port sau **chưa bị chiếm**: `1883`, `8086`, `3000`, `8000`, `9001`

### Khởi động toàn bộ hệ thống

```bash
cd api
docker compose up -d --build
```

### Kiểm tra trạng thái các container

```bash
docker compose ps
```

Output mong đợi — tất cả services ở trạng thái `Up`:

```
NAME                        STATUS
mosquitto                   Up
influxdb                    Up
grafana                     Up
gateway-api                 Up
iot-gateway                 Up
virtual-sensor-room-01      Up
virtual-sensor-room-02      Up
virtual-sensor-room-03      Up
virtual-actuator-room-01    Up
virtual-actuator-room-02    Up
virtual-actuator-room-03    Up
```

### Dừng hệ thống

```bash
docker compose down
```

### Dừng hệ thống + xóa dữ liệu

```bash
docker compose down -v
```

> Cờ `-v` sẽ xóa toàn bộ Docker volumes (InfluxDB data, Mosquitto data, Grafana data).

### Rebuild sau khi sửa code

```bash
docker compose up -d --build
```

---

##  Cách kiểm tra Log

### Xem log tất cả services

```bash
docker compose logs -f
```

### Xem log IoT Gateway (Rule Engine)

```bash
docker compose logs -f iot-gateway
```

Log gateway sẽ hiển thị:
- ` Telemetry from room-01: temp=...` — Nhận dữ liệu
- ` Event: temperature_high in room-01` — Phát hiện bất thường
- ` Command sent to room-01: fan=on` — Gửi lệnh điều khiển

### Xem log REST API

```bash
docker compose logs -f gateway-api
```

### Xem log Sensors

```bash
docker compose logs -f virtual-sensor-room-01
docker compose logs -f virtual-sensor-room-02
docker compose logs -f virtual-sensor-room-03
```

### Xem log Actuators

```bash
docker compose logs -f virtual-actuator-room-01
```

### Xem log MQTT Broker

```bash
docker compose logs -f mosquitto
```

---

##  Cách truy cập Grafana, InfluxDB và REST API

### Grafana Dashboard

- **URL**: http://localhost:3000
- **Username**: `admin`
- **Password**: `admin`
- Datasource InfluxDB đã được tự động provisioning

### InfluxDB UI

- **URL**: http://localhost:8086
- **Username**: `admin`
- **Password**: `admin12345`
- **Organization**: `iot-org`
- **Bucket**: `smart-building`

### REST API (FastAPI)

- **URL**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

#### Các endpoint chính

| Method | Endpoint | Mô tả |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/rooms` | Danh sách phòng |
| `GET` | `/rooms/{room_id}/state` | Telemetry + Actuator state của phòng |
| `GET` | `/rooms/{room_id}/events` | Các sự kiện bất thường |
| `POST` | `/rooms/{room_id}/command` | Gửi lệnh điều khiển thủ công |

#### Ví dụ query API

```bash
# Kiểm tra hệ thống
curl http://localhost:8000/health

# Xem danh sách phòng
curl http://localhost:8000/rooms

# Xem telemetry + actuator state phòng 01
curl http://localhost:8000/rooms/room-01/state

# Xem events bất thường phòng 01
curl http://localhost:8000/rooms/room-01/events
```

---

##  Cách gửi lệnh điều khiển thủ công

### Qua REST API

```bash
# Bật quạt phòng 01
curl -X POST http://localhost:8000/rooms/room-01/command \
  -H "Content-Type: application/json" \
  -d '{"target": "fan", "action": "on", "reason": "manual_control"}'

# Tắt đèn phòng 02
curl -X POST http://localhost:8000/rooms/room-02/command \
  -H "Content-Type: application/json" \
  -d '{"target": "light", "action": "off", "reason": "manual_control"}'

# Bật alarm phòng 03
curl -X POST http://localhost:8000/rooms/room-03/command \
  -H "Content-Type: application/json" \
  -d '{"target": "alarm", "action": "on", "reason": "manual_test"}'
```

### Qua MQTT trực tiếp (mosquitto_pub)

```bash
# Bật quạt phòng 01
mosquitto_pub -h localhost -t "building/room-01/actuator/command" \
  -m '{"room_id":"room-01","target":"fan","action":"on","reason":"manual_control","timestamp":"2026-06-10T10:00:00Z"}'

# Tắt đèn phòng 02
mosquitto_pub -h localhost -t "building/room-02/actuator/command" \
  -m '{"room_id":"room-02","target":"light","action":"off","reason":"manual_control","timestamp":"2026-06-10T10:00:00Z"}'

# Subscribe để xem actuator phản hồi
mosquitto_sub -h localhost -t "building/+/actuator/status" -v
```

### Qua Script test anomaly

```bash
# Publish tất cả scenarios bất thường
python tests/test_anomaly_publish.py --broker localhost --room room-01 --scenario all

# Publish chỉ scenario nhiệt độ cao
python tests/test_anomaly_publish.py --broker localhost --room room-01 --scenario temperature_high
```

---

##  Chạy Tests

```bash
# Chạy tất cả tests (không cần Docker)
python -m pytest tests/ -v

# Chạy test riêng từng module
python -m pytest tests/test_sensor.py -v          # Test sensor
python -m pytest tests/test_actuator.py -v         # Test actuator
python -m pytest tests/test_rule_engine.py -v      # Test rule engine
python -m pytest tests/test_state_store.py -v      # Test state store
python -m pytest tests/test_integration_gateway_api.py -v  # Test Gateway↔API
python -m pytest tests/test_full_integration.py -v # Test tích hợp 3 thành viên
```

---

##  Cấu trúc thư mục

```
Virtual-Smart-Building-Gateway/
├── virtual_sensor/          # Thành viên 1: Virtual Sensor
│   ├── sensor.py            #   Mô phỏng cảm biến môi trường
│   ├── requirements.txt
│   └── Dockerfile
├── virtual_actuator/        # Thành viên 1: Virtual Actuator
│   ├── actuator.py          #   Mô phỏng thiết bị điều khiển
│   ├── requirements.txt
│   └── Dockerfile
├── iot_gateway/             # Thành viên 2: IoT Gateway + Rule Engine
│   ├── gateway.py           #   Gateway chính: MQTT ↔ InfluxDB
│   ├── rule_engine.py       #   4 luật xử lý bất thường
│   ├── state_store.py       #   Lưu trạng thái realtime mỗi phòng
│   ├── requirements.txt
│   └── Dockerfile
├── api/                     # Thành viên 3: REST API + Docker + Grafana
│   ├── docker-compose.yml   #   Orchestration toàn bộ hệ thống
│   ├── .env.example         #   Template environment variables
│   ├── gateway_api/         #   FastAPI application
│   │   └── api.py
│   └── grafana/             #   Grafana provisioning
│       └── provisioning/
├── mosquitto/               # Cấu hình MQTT Broker
│   └── config/
│       └── mosquitto.conf
├── docs/                    # Tài liệu
│   └── topic-design.md      #   Thiết kế MQTT topic
├── tests/                   # Test suite
│   ├── test_sensor.py       #   Unit test sensor (16 tests)
│   ├── test_actuator.py     #   Unit test actuator (19 tests)
│   ├── test_rule_engine.py  #   Unit test rule engine (21 tests)
│   ├── test_state_store.py  #   Unit test state store (12 tests)
│   ├── test_integration_gateway_api.py  # Gateway↔API (15 tests)
│   ├── test_full_integration.py         # 3-member E2E (19 tests)
│   └── test_anomaly_publish.py          # Script test anomaly
├── .gitignore
└── README.md
```

---

##  MQTT Topics

| Topic | Hướng | Mô tả |
|---|---|---|
| `building/{room_id}/sensor/telemetry` | Sensor → Gateway | Dữ liệu cảm biến |
| `building/{room_id}/actuator/command` | Gateway/API → Actuator | Lệnh điều khiển |
| `building/{room_id}/actuator/status` | Actuator → Gateway | Trạng thái thiết bị |
| `building/{room_id}/gateway/normalized` | Gateway → Subscribers | Dữ liệu đã chuẩn hóa |
| `building/{room_id}/gateway/event` | Gateway → Subscribers | Sự kiện bất thường |

> `room_id` ∈ {`room-01`, `room-02`, `room-03`}

---

##  Các tính năng nâng cao

Hệ thống đã được tích hợp thêm các tính năng nâng cao sau để tăng cường độ tin cậy và linh hoạt.

### 1. Cấu hình bảo mật cho MQTT Broker
- **Mô tả**: Mosquitto Broker không còn cho phép kết nối ẩn danh (anonymous). Tất cả các service đều phải đăng nhập.
- **Cách xem**: Kiểm tra file `api/.env` sẽ thấy `MQTT_USER=admin` và `MQTT_PASSWORD=admin12345`.
- **Cách test**: Thử kết nối MQTT client bất kỳ (như MQTT Explorer) tới `localhost:1883` mà không điền user/password. Broker sẽ lập tức ngắt kết nối.

### 2. Docker Compose Healthchecks
- **Mô tả**: Thay vì chỉ quy định thứ tự khởi động lỏng lẻo, `docker-compose.yml` giờ đây có khai báo `healthcheck` cho `mosquitto`, `influxdb`, `grafana` và `gateway-api`. Các service phụ thuộc (như Sensor, Gateway) sẽ thực sự đợi đến khi Broker và Database "Healthy" mới bắt đầu chạy.
- **Cách xem**: Chạy lệnh `docker ps` và bạn sẽ thấy trạng thái `(healthy)` ở cột STATUS của các container cốt lõi.

### 3. Phát hiện Sensor Offline (Timeout)
- **Mô tả**: IoT Gateway liên tục theo dõi thời gian bản tin cuối cùng từ các phòng. Nếu quá 30 giây không nhận được dữ liệu, nó sẽ tự động phát ra một cảnh báo nguy cấp.
- **Cách test**: 
  1. Tắt một sensor bất kỳ: `docker stop virtual-sensor-room-01`
  2. Chờ 30 giây và kiểm tra log của Gateway: `docker compose logs -f iot-gateway` (sẽ thấy báo lỗi "Sensor offline detected").
  3. Kiểm tra API Event hoặc Grafana để xem cảnh báo được ghi lại.

### 4. Actuator Acknowledgement Timeout
- **Mô tả**: Khi Gateway ra lệnh điều khiển (vd: bật quạt), nó sẽ chờ phản hồi trạng thái từ Actuator đó. Nếu sau 10 giây Actuator không báo cáo đã bật thành công, Gateway sẽ phát ra cảnh báo.
- **Cách test**:
  1. Tắt một actuator: `docker stop virtual-actuator-room-01`
  2. Gửi lệnh qua API: `curl -X POST http://localhost:8000/rooms/room-01/command -H "Content-Type: application/json" -d '{"target":"fan","action":"on"}'`
  3. Chờ 10 giây và quan sát log Gateway để thấy thông báo Timeout.

### 5. Cập nhật Rule Engine linh hoạt (Dynamic Rules API)
- **Mô tả**: Trước đây các ngưỡng kích hoạt (vd nhiệt độ > 30) bị gắn cứng vào code. Hiện tại, chúng đã được lưu trong bộ nhớ và Gateway sẽ lắng nghe cập nhật qua MQTT (`building/gateway/config`).
- **Cách test**:
  1. Gửi request PUT để thay đổi ngưỡng:
     ```bash
     curl -X PUT http://localhost:8000/rules \
          -H "Content-Type: application/json" \
          -d '{"temperature_high": 25.0}'
     ```
  2. Ngay lập tức, nếu nhiệt độ phòng hiện tại đang là 26 độ, Gateway sẽ tự động ra lệnh bật Quạt (do vượt ngưỡng mới 25.0). Xem log Gateway để thấy tác dụng.

### 6. Cảnh báo qua Grafana Alerting
- **Mô tả**: Grafana đã được cấu hình tự động (provisioning) một Alert Rule. Cứ mỗi 1 phút, nó sẽ quét bảng `gateway_events` trong InfluxDB. Nếu phát hiện có sự kiện mức độ `critical` (như Sensor Offline hay Actuator Timeout), Grafana sẽ kích hoạt báo động.
- **Cách xem**: Truy cập Grafana (http://localhost:3000), vào menu **Alerting > Alert rules** để xem rule "Critical Gateway Event Detected". Mở bảng điều khiển Dashboard để thấy trạng thái Firing nếu bạn đang test các trường hợp lỗi ở trên.

---

##  Các lỗi thường gặp và cách khắc phục

### 1. Port đã bị chiếm

**Lỗi**: `Bind for 0.0.0.0:1883 failed: port is already allocated`

**Khắc phục**:
```bash
# Kiểm tra process đang dùng port
# Windows:
netstat -ano | findstr :1883
# Linux/Mac:
lsof -i :1883

# Dừng process hoặc đổi port trong docker-compose.yml
```

### 2. Container không start được

**Khắc phục**:
```bash
# Xem log chi tiết
docker compose logs <service-name>

# Rebuild
docker compose up -d --build
```

### 3. Vấn đề phụ thuộc khởi động (Đã được giải quyết)

Hệ thống hiện tại đã sử dụng **Docker Healthcheck**. Do đó, các lỗi như `InfluxDB connection failed` hay `MQTT Connection failed` lúc khởi động sẽ hiếm khi xảy ra vì các Service phụ thuộc luôn kiên nhẫn chờ đến khi Database/Broker thực sự sẵn sàng (Healthy) mới bắt đầu chạy.

### 5. Dữ liệu cũ gây nhiễu

**Khắc phục**:
```bash
# Xóa toàn bộ dữ liệu và restart
cd api
docker compose down -v
docker compose up -d --build
```

### 6. Grafana không hiển thị dữ liệu

**Khắc phục**:
1. Kiểm tra InfluxDB đã có dữ liệu: http://localhost:8086
2. Kiểm tra datasource trong Grafana: Settings → Data Sources
3. Đảm bảo token, org, bucket khớp giữa Grafana và InfluxDB

### 7. API trả về 500 Internal Server Error

**Khắc phục**:
```bash
# Xem log API
docker compose logs -f gateway-api

# Kiểm tra kết nối InfluxDB
curl http://localhost:8086/ping
```

### 8. Sensor không publish được

**Khắc phục**:
```bash
# Subscribe thủ công để kiểm tra
mosquitto_sub -h localhost -t "building/+/sensor/telemetry" -v

# Xem log sensor
docker compose logs -f virtual-sensor-room-01
```

---

##  Các lệnh Docker hữu ích

```bash
# Khởi động hệ thống
cd api
docker compose up -d --build

# Kiểm tra trạng thái
docker compose ps

# Xem log gateway
docker compose logs -f iot-gateway

# Xem log API
docker compose logs -f gateway-api

# Xem log tất cả
docker compose logs -f

# Dừng hệ thống
docker compose down

# Dừng + xóa dữ liệu
docker compose down -v

# Restart một service
docker compose restart iot-gateway

# Xem resource usage
docker compose top
```