# Mapping Yêu Cầu - Virtual Smart Building

Dưới đây là bảng phân tích và mapping chi tiết từng yêu cầu trong file `yêu cầu.md` tới các dòng code thực tế trong dự án, kèm theo cách kiểm tra (test) từng chức năng.

## 7. Thiết kế MQTT Topic & 8. Message Format
**Nơi thực hiện:**
- **Sensor Telemetry (7.1 & 8.1):** Code publish nằm ở [virtual_sensor/sensor.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/virtual_sensor/sensor.py) hàm `publish_telemetry()`. Format đúng chuẩn JSON với `device_id`, `room_id`, `temperature`...
- **Command (7.2 & 8.2):** Code publish nằm ở [iot_gateway/gateway.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/gateway.py) hàm `handle_telemetry()`. Gửi lệnh với `target` (fan/light/alarm), `action` (on/off), `reason`.
- **Status (7.3 & 8.3):** Code subscribe/publish nằm ở [virtual_actuator/actuator.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/virtual_actuator/actuator.py) hàm `publish_status()` và `on_message()`.
- **Normalized & Event (7.4, 7.5, 8.4):** Code publish nằm ở [iot_gateway/gateway.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/gateway.py) (publish ra MQTT) và [iot_gateway/rule_engine.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/rule_engine.py) (hàm `_make_event` tạo format JSON).

**Cách test:** 
Mở terminal và subscribe lắng nghe mọi topic để xem format thực tế đang chạy:
```bash
docker compose exec mosquitto mosquitto_sub -u admin -P admin12345 -t "building/#" -v
```

---

## 9.1. Virtual Sensor
**Nơi thực hiện:** Toàn bộ logic nằm tại [virtual_sensor/sensor.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/virtual_sensor/sensor.py).
- Đọc biến môi trường bằng `os.getenv()`.
- Biến động dữ liệu (`random walk`) được thực hiện trong hàm `generate_telemetry()` với việc cộng trừ một lượng nhỏ `random.uniform()` từ giá trị cũ.
- Bất thường ngẫu nhiên: Xác suất `0.05` (5%) nhiệt độ/CO2 sẽ tăng đột biến (dòng logic `if random.random() < 0.05`).

**Cách test:**
```bash
docker compose logs -f virtual-sensor-room-01
# Theo dõi log sẽ thấy thỉnh thoảng có cảnh báo "⚠️  Simulating anomaly..."
```

---

## 9.2. Virtual Actuator
**Nơi thực hiện:** [virtual_actuator/actuator.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/virtual_actuator/actuator.py)
- Subscribe `building/{ROOM_ID}/actuator/command` trong `on_connect()`.
- Cập nhật state (fan, light, alarm) và gọi `publish_status()` bên trong hàm `on_message()`.

**Cách test:**
Sử dụng API để gửi lệnh điều khiển và xem log Actuator.
```bash
curl -X POST http://localhost:8000/rooms/room-01/command \
     -H "Content-Type: application/json" -d '{"target":"fan","action":"on","reason":"manual_test"}'
docker compose logs virtual-actuator-room-01
```

---

## 9.3. Virtual IoT Gateway
**Nơi thực hiện:** Trái tim của hệ thống nằm tại [iot_gateway/gateway.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/gateway.py).
- Validate & Normalize: Hàm `validate_telemetry()` và `normalize_telemetry()`.
- Ghi InfluxDB: Các hàm `write_telemetry`, `write_event`, `write_actuator_status`.
- Đánh giá rules: Gọi hàm `evaluate()` từ module `rule_engine`.

**Cách test:**
Xem toàn bộ flow (nhận -> xử lý -> ghi DB -> báo event) bằng lệnh:
```bash
docker compose logs -f iot-gateway
```

---

## 9.4. Rule Engine
**Nơi thực hiện:** [iot_gateway/rule_engine.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/rule_engine.py)
- Code thực hiện chính xác 4 luật cơ bản được định nghĩa qua các hàm `rule_temperature_high`, `rule_temperature_low`, `rule_co2_high`, `rule_unnecessary_light`.
- Nó kiểm tra state hiện tại của actuator (truyền vào qua `actuator_state`) để đảm bảo không gửi lệnh Bật Quạt nếu Quạt đã Bật.

**Cách test:**
Chỉnh nhiệt độ môi trường cao lên thông qua API (Rule linh hoạt) để xem Quạt tự động bật:
```bash
curl -X PUT http://localhost:8000/rules -H "Content-Type: application/json" -d '{"temperature_high": 25.0}'
# Chờ vài giây, Gateway sẽ thấy nhiệt độ hiện tại (VD 26 độ) vượt ngưỡng mới 25, nó sẽ kích hoạt Rule 1 bật quạt.
```

---

## 9.5. REST API
**Nơi thực hiện:** [api/gateway_api/api.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/api/gateway_api/api.py)
- FastAPI với cấu trúc rõ ràng. 
- API giao tiếp với Gateway qua cách **(1) Publish command trực tiếp lên MQTT** (`mqtt_client.publish()`) và đọc state bằng cách **Query trực tiếp từ InfluxDB** (hàm `query_latest_telemetry` và `query_events`).

**Cách test:**
Truy cập giao diện Swagger UI có sẵn: [http://localhost:8000/docs](http://localhost:8000/docs) và bấm **Try it out** ở bất kỳ endpoint nào.

---

## 10. Lưu trữ InfluxDB & 11. Grafana Dashboard
**Nơi thực hiện:**
- Code ghi InfluxDB (Tag/Field): Xem các hàm `write_xxx` ở `gateway.py` (vd: `Point("room_telemetry").tag("room_id", room_id)...`).
- Cấu hình Dashboard tự động: [api/grafana/provisioning/dashboards/smart_building.json](file:///d:/workspace/Virtual-Smart-Building-Gateway/api/grafana/provisioning/dashboards/smart_building.json).

**Cách test:**
- Truy cập InfluxDB (http://localhost:8086), đăng nhập `admin`/`admin12345`, vào **Data Explorer** để xem các measurement `room_telemetry`, `actuator_status`, `gateway_events`.
- Truy cập Grafana (http://localhost:3000), đăng nhập `admin`/`admin`, mở **Smart Building Dashboard** để xem biểu đồ realtime.

---

## 12. Docker và Ảo hóa
**Nơi thực hiện:**
- Dockerfile: Đã tạo sẵn trong 4 thư mục (`virtual_sensor`, `virtual_actuator`, `iot_gateway`, `gateway_api`).
- Compose & Biến môi trường: Tồn tại trong [api/docker-compose.yml](file:///d:/workspace/Virtual-Smart-Building-Gateway/api/docker-compose.yml) và `.env`. Mạng nội bộ là `api_default`. Không dùng localhost trong config (vd `MQTT_BROKER=mosquitto`).
- Volumes: Được khai báo ở cuối `docker-compose.yml` (`influxdb_data`, `grafana_data`, `mosquitto_data`, `mosquitto_log`).

**Cách test:**
```bash
# Kiểm tra các network và volume đang tồn tại
docker network ls
docker volume ls
```

---

## 19. Yêu cầu nâng cao (Khuyến khích)
**Nơi thực hiện:**
1. **User/Pass Mosquitto**: Cấu hình tại `mosquitto/config/mosquitto.conf` (`allow_anonymous false`, `password_file`) và file `passwd` sinh tự động. Các service dùng `.env` để lấy `MQTT_USER` và gọi `client.username_pw_set()`.
2. **File `.env`**: Được load bởi docker-compose.
3. **Healthcheck**: Xem khối `healthcheck` của `mosquitto`, `influxdb`, `grafana` trong `docker-compose.yml`. Khối `depends_on` được setup `condition: service_healthy`.
4. **Sensor Offline**: [iot_gateway/gateway.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/gateway.py). Có bộ đếm giờ `last_seen` trong vòng lặp `while True`. Test bằng lệnh `docker stop virtual-sensor-room-01` và chờ 30 giây.
5. **Actuator Timeout**: [iot_gateway/gateway.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/iot_gateway/gateway.py). Có biến `pending_commands` chờ 10s. Test bằng lệnh `docker stop virtual-actuator-room-01` rồi gửi lệnh qua POST API.
6. **API Thay đổi Threshold**: Endpoint `PUT /rules` trong [api/gateway_api/api.py](file:///d:/workspace/Virtual-Smart-Building-Gateway/api/gateway_api/api.py). Publish tới topic `building/gateway/config`, Gateway hứng được cập nhật vào biến `THRESHOLDS` tại `rule_engine.py`.
7. **Grafana Alert Rule**: Xem file [api/grafana/provisioning/alerting/rules.yml](file:///d:/workspace/Virtual-Smart-Building-Gateway/api/grafana/provisioning/alerting/rules.yml). Quét `gateway_events` mỗi 1 phút để báo động.
