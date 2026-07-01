Mở terminal và subscribe lắng nghe mọi topic để xem format thực tế đang chạy:
docker compose exec mosquitto mosquitto\_sub -u admin -P admin12345 -t "building/#" -v





Virtual Sensor:
docker compose logs -f virtual-sensor-room-01





Rule Engine:
curl -X PUT http://localhost:8000/rules -H "Content-Type: application/json" -d '{"temperature\_high": 25.0}'

# Chờ vài giây, Gateway sẽ thấy nhiệt độ hiện tại (VD 26 độ) vượt ngưỡng mới 25, nó sẽ kích hoạt Rule 1 bật quạt.







Xem các thông số cảm biến (nhiệt độ, độ ẩm, CO2...) của phòng 01:
from(bucket: "smart-building")
|> range(start: -1h)
|> filter(fn: (r) => r.\_measurement == "room\_telemetry")
|> filter(fn: (r) => r.room\_id == "room-01")
|> aggregateWindow(every: 10s, fn: mean, createEmpty: false)
|> yield(name: "telemetry")

Xem trạng thái Actuator (1 là bật, 0 là tắt nếu bạn quy đổi, hoặc xem raw):
from(bucket: "smart-building")
|> range(start: -1h)
|> filter(fn: (r) => r.\_measurement == "actuator\_status")
|> yield(name: "actuator\_status")

Xem các sự kiện/cảnh báo:
from(bucket: "smart-building")
|> range(start: -24h)
|> filter(fn: (r) => r.\_measurement == "gateway\_events")
|> yield(name: "events")



Kiểm tra xem API có đang sống hay không:

bash
curl http://localhost:8000/health
Lấy danh sách các phòng đang có trong hệ thống:

bash
curl http://localhost:8000/rooms
Xem trạng thái hiện tại (cảm biến + thiết bị) của phòng 01:

bash
curl http://localhost:8000/rooms/room-01/state
Xem lịch sử cảnh báo bất thường của phòng 02:

bash
curl http://localhost:8000/rooms/room-02/events
Gửi lệnh bật quạt cho phòng 01:

bash
curl -X POST http://localhost:8000/rooms/room-01/command -H "Content-Type: application/json" -d "{"target": "fan", "action": "on", "reason": "manual\_test"}"
(Note: Vì bạn dùng Windows PowerShell, tôi đã bọc JSON bằng dấu ngoặc kép " và escape (thêm ) bên trong để PowerShell không báo lỗi syntax).

Gửi lệnh bật còi báo động (alarm) cho phòng 03:

bash
curl -X POST http://localhost:8000/rooms/room-03/command -H "Content-Type: application/json" -d "{"target": "alarm", "action": "on", "reason": "security\_breach"}"

