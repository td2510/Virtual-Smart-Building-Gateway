#  Smart Building IoT Gateway

Hệ thống Virtual IoT Gateway cho Smart Building — mô phỏng thu thập dữ liệu cảm biến,
phát hiện bất thường và điều khiển thiết bị qua MQTT.

##  Kiến trúc hệ thống

```
[Virtual Sensor x3] ──MQTT telemetry── [Mosquitto Broker]
                                               │
                                    ┌──────────┴──────────┐
                                                          
                             [IoT Gateway]          [Gateway API]
                             (Rule Engine)          (REST API)
                                    │                      │
                                    └──────────┬───────────┘
                                               
                                         [InfluxDB]
                                               │
                                               
                                          [Grafana]
```

##  Cách chạy

### Yêu cầu
- Docker & Docker Compose

### Bước 1: Clone và cấu hình
```bash
git clone <repo-url>
cd smart-building-iot-gateway
cp .env.example .env
```

### Bước 2: Chạy toàn bộ hệ thống
```bash
docker compose up -d --build
```

### Bước 3: Kiểm tra trạng thái
```bash
docker compose ps
```

##  Truy cập các service

| Service | URL | Thông tin đăng nhập |
|---|---|---|
| Grafana Dashboard | http://localhost:3000 | admin / admin |
| InfluxDB UI | http://localhost:8086 | admin / admin12345 |
| REST API | http://localhost:8000 | — |
| API Docs (Swagger) | http://localhost:8000/docs | — |

##  Kiểm tra log

```bash
docker compose logs -f iot-gateway
docker compose logs -f gateway-api
docker compose logs -f virtual-sensor-room-01
docker compose logs -f virtual-actuator-room-01
```

##  REST API Endpoints

| Method | Endpoint | Mô tả |
|---|---|---|
| GET | /health | Health check |
| GET | /rooms | Danh sách phòng |
| GET | /rooms/{room_id}/state | Trạng thái mới nhất |
| GET | /rooms/{room_id}/events | Events gần nhất |
| POST | /rooms/{room_id}/command | Gửi lệnh thủ công |

### Ví dụ gửi lệnh thủ công
```bash
curl -X POST http://localhost:8000/rooms/room-01/command \
  -H "Content-Type: application/json" \
  -d '{"target":"fan","action":"on","reason":"manual_control"}'
```

##  Dừng hệ thống
```bash
docker compose down
```

##  Troubleshooting

- **Container không start**: Kiểm tra `docker compose logs <service-name>`
- **MQTT không kết nối**: Đảm bảo Mosquitto container đang running
- **InfluxDB không có data**: Kiểm tra gateway logs, đảm bảo token đúng
- **Grafana không hiện data**: Kiểm tra datasource configuration tại http://localhost:3000/connections/datasources

##  Phân công

| Thành viên | Nhiệm vụ |
|---|---|
| TV1 | Virtual Sensor, Virtual Actuator, Topic Design |
| TV2 | IoT Gateway, Rule Engine, InfluxDB Writer |
| TV3 | REST API, Docker Compose, Grafana, README |
