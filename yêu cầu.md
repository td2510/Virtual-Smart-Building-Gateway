7. Thiết kế MQTT topic
Nhóm cần thiết kế topic hierarchy rõ ràng. Gợi ý:
7.1. Topic cho telemetry thô từ sensor
building/room-01/sensor/telemetry
building/room-02/sensor/telemetry
building/room-03/sensor/telemetry
7.2. Topic cho lệnh điều khiển actuator
building/room-01/actuator/command
building/room-02/actuator/command
building/room-03/actuator/command
7.3. Topic cho trạng thái actuator
building/room-01/actuator/status
building/room-02/actuator/status
building/room-03/actuator/status
7.4. Topic cho dữ liệu gateway đã chuẩn hóa
building/room-01/gateway/normalized
building/room-02/gateway/normalized
building/room-03/gateway/normalized
7.5. Topic cho event bất thường
building/room-01/gateway/event
building/room-02/gateway/event
building/room-03/gateway/event
8. Message format yêu cầu
8.1. Telemetry message từ sensor
Mỗi virtual sensor phải publish message JSON có dạng tối thiểu:
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
8.2. Command message từ gateway đến actuator
Gateway gửi lệnh điều khiển xuống actuator bằng MQTT:
{
"room_id": "room-01",
"target": "fan",
"action": "on",
"reason": "temperature_high",
"timestamp": "2026-06-10T10:00:05Z"
}
Các action tối thiểu:
• on
• off
Các target tối thiểu:
• fan
• light
• alarm

8.3. Status message từ actuator
Sau khi nhận lệnh, actuator phải publish lại trạng thái:
{
"device_id": "actuator-room-01",
"room_id": "room-01",
"fan": "on",
"light": "off",
"alarm": "off",
"last_command_reason": "temperature_high",
"timestamp": "2026-06-10T10:00:06Z"
}
8.4. Event message từ gateway
Khi phát hiện bất thường, gateway phải sinh event:
{
"room_id": "room-01",
"event_type": "temperature_high",
"severity": "warning",
"value": 32.5,
"threshold": 30.0,
"action_taken": "fan_on",
"timestamp": "2026-06-10T10:00:05Z"
}
9. Yêu cầu lập trình
9.1. Virtual Sensor
Nhóm cần lập trình virtual sensor bằng Python.
Yêu cầu:
1. Đọc cấu hình từ environment variables, ví dụ ROOM_ID, DEVICE_ID,
MQTT_BROKER, PUBLISH_INTERVAL.
2. Sinh dữ liệu môi trường theo thời gian.
3. Dữ liệu phải có biến động hợp lý, không chỉ random hoàn toàn độc lập.
4. Có cơ chế sinh tình huống bất thường theo xác suất hoặc theo chu kỳ, ví dụ nhiệt
độ tăng cao hoặc CO2 vượt ngưỡng.
5. Publish message JSON lên topic tương ứng của từng phòng.
Gợi ý: sinh viên có thể mô phỏng xu hướng bằng cách lưu giá trị trước đó và thay đổi
nhẹ ở mỗi chu kỳ.

9.2. Virtual Actuator
Nhóm cần lập trình virtual actuator bằng Python.
Yêu cầu:
1. Subscribe topic command của phòng tương ứng.
2. Parse command JSON.
3. Cập nhật trạng thái nội bộ của fan, light, alarm.
4. Publish lại trạng thái lên topic status.
5. Ghi log khi nhận lệnh hợp lệ hoặc lệnh sai định dạng.
9.3. Virtual IoT Gateway
Đây là thành phần quan trọng nhất của mini-project.
Gateway phải thực hiện các chức năng sau:
1. Subscribe dữ liệu telemetry từ tất cả các phòng.
2. Validate message: kiểm tra room_id, device_id, timestamp và các field dữ liệu.
3. Chuẩn hóa message thành format thống nhất.
4. Lưu trạng thái mới nhất của từng phòng.
5. Ghi dữ liệu telemetry vào InfluxDB.
6. Phát hiện bất thường bằng rule engine.
7. Sinh event khi có bất thường.
8. Ghi event vào InfluxDB.
9. Publish event lên MQTT topic.
10. Gửi command đến actuator nếu cần.
9.4. Rule Engine
Gateway phải có ít nhất 4 luật xử lý:
1. Nếu temperature > 30, bật quạt.
2. Nếu temperature < 27, tắt quạt.
3. Nếu co2_ppm > 1200, bật alarm.
4. Nếu occupancy = false và light_lux > 300, tắt đèn.
Nhóm có thể bổ sung luật khác, ví dụ:
• Nếu độ ẩm quá cao, sinh cảnh báo.

• Nếu sensor không gửi dữ liệu trong một khoảng thời gian, sinh event
sensor_offline.
• Nếu actuator không phản hồi sau khi nhận command, sinh event
actuator_no_response.
9.5. REST API
Nhóm cần xây dựng REST API đơn giản, có thể dùng FastAPI.
API tối thiểu cần có các endpoint sau:
GET /health
GET /rooms
GET /rooms/{room_id}/state
GET /rooms/{room_id}/events
POST /rooms/{room_id}/command
Ý nghĩa:
• GET /health: kiểm tra API còn chạy hay không.
• GET /rooms: trả về danh sách phòng.
• GET /rooms/{room_id}/state: trả về trạng thái mới nhất của một phòng.
• GET /rooms/{room_id}/events: trả về các event gần nhất.
• POST /rooms/{room_id}/command:gửilệnhđiều khiển thủ công đến actuator.
Ví dụ body của API gửi lệnh thủ công:
{
"target": "fan",
"action": "on",
"reason": "manual_control"
}
API có thể giao tiếp với gateway bằng một trong hai cách:
1. API publish command trực tiếp lên MQTT.
2. API đọc/ghi trạng thái thông qua một file, Redis, hoặc một cơ chế lưu trữ đơn giản
do nhóm tự thiết kế.
Nhóm phải giải thích rõ lựa chọn thiết kế trong báo cáo.
10. Yêu cầu lưu trữ InfluxDB
Nhóm cần lưu ít nhất 3 loại dữ liệu vào InfluxDB:
1. Telemetry data: dữ liệu sensor sau khi chuẩn hóa.
2. Event data: các event bất thường do gateway sinh ra.
3. Actuator status: trạng thái fan, light, alarm của từng phòng.

Gợi ý measurement:
• room_telemetry
• gateway_events
• actuator_status
Các tag nên có:
• room_id
• device_id
• event_type
• severity
Các field nên có:
• temperature
• humidity
• light_lux
• co2_ppm
• occupancy
• fan
• light
• alarm
11. Yêu cầu Grafana Dashboard
Dashboard Grafana phải có ít nhất các panel sau:
1. Nhiệt độ theo thời gian cho từng phòng.
2. CO2 theo thời gian cho từng phòng.
3. Độ ẩm theo thời gian cho từng phòng.
4. Trạng thái fan/light/alarm theo từng phòng.
5. Số lượng event bất thường theo thời gian.
6. Bảng event gần nhất, gồm room_id, event_type, severity, action_taken.
Dashboard cần thể hiện được mối liên hệ giữa dữ liệu sensor, event gateway và trạng
thái actuator.
Ví dụ: khi nhiệt độ phòng 1 vượt ngưỡng, dashboard cần cho thấy nhiệt độ tăng, event
temperature_high xuất hiện và trạng thái fan chuyển sang on.

12. Yêu cầu Docker và ảo hóa
Toàn bộ hệ thống phải chạy bằng Docker Compose.
12.1. Dockerfile
Các service do nhóm tự lập trình phải có Dockerfile riêng:
• virtual_sensor/Dockerfile
• virtual_actuator/Dockerfile
• iot_gateway/Dockerfile
• gateway_api/Dockerfile
12.2. Environment variables
Không hard-code các thông số triển khai trong source code. Các service cần đọc cấu hình
từ environment variables.
Ví dụ:
• MQTT_BROKER
• MQTT_PORT
• ROOM_ID
• DEVICE_ID
• PUBLISH_INTERVAL
• INFLUXDB_URL
• INFLUXDB_TOKEN
• INFLUXDB_ORG
• INFLUXDB_BUCKET
12.3. Network
Các service phải giao tiếp với nhau qua Docker Compose network.
Trong container, không dùng localhost để gọi service khác. Ví dụ:
MQTT_BROKER=mosquitto
INFLUXDB_URL=http://influxdb:8086
12.4. Volume
Nhóm phải dùng Docker volume cho:
• InfluxDB data.
• Grafana data.
Khuyến khích dùng volume hoặc bind mount cho Mosquitto config.

19. Yêu cầu nâng cao để cộng điểm khuyến khích
Nhóm có thể thực hiện thêm một số chức năng nâng cao:
1. Cấu hình username/password cho Mosquitto MQTT broker.
2. Dùng file .env để quản lý cấu hình.
3. Thêm health check cho các service trong Docker Compose.
4. Thêm cơ chế phát hiện sensor offline.
5. Thêm cơ chế actuator acknowledgement timeout.
6. Thêm API endpoint để thay đổi threshold của rule engine.
7. Thêm Grafana alert rule.
8. Thêm unit test cho rule engine.
9. Thêm script tự động publish dữ liệu bất thường để kiểm thử.
10. Mô phỏng mất kết nối MQTT và cơ chế reconnect.