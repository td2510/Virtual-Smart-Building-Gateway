# ⚠️ LƯU Ý QUAN TRỌNG: CHUYỂN GIAO TỪ MÔ PHỎNG SANG CHẠY THẬT

File này giúp bạn phân biệt rõ **đâu là công cụ dùng tạm để test** và **đâu là công việc cần làm khi ráp code thật** với Thành viên 1 và 2.

---

## BẢNG PHÂN BIỆT MÔ PHỎNG VÀ CHẠY THẬT

| Thành phần | Khi bạn Test Độc Lập (Mô Phỏng) | Khi Ráp Code (Chạy Thật) |
|---|---|---|
| **Dữ liệu Cảm biến** | Dùng file `test_mock_data.py` tự viết vào InfluxDB | Cục Gateway của **TV2** sẽ tự động ghi vào InfluxDB |
| **Gửi lệnh Điều khiển** | Dùng lệnh `mosquitto_sub ...` để "đứng hóng" tin nhắn xem có bay ra không | Các Actuator của **TV1** sẽ tự động hứng tin nhắn và phản hồi |
| **Chạy Docker** | Chỉ bật 3 dịch vụ cơ bản: Mosquitto, InfluxDB, API, Grafana | Gõ `docker compose up` sẽ tự động chạy toàn bộ cả Sensor và Actuator |

---

## CÁC BƯỚC DỌN DẸP TRƯỚC KHI RÁP CODE

Khi Thành viên 1 và 2 báo cáo "Xong rồi, ráp code thôi!", bạn hãy thực hiện lần lượt các bước sau để trả hệ thống về trạng thái "sạch tinh khôi":

### Bước 1: Xóa sạch dữ liệu giả (Rất quan trọng)
Dữ liệu do `test_mock_data.py` tạo ra sẽ làm nhiễu dữ liệu thật của TV2. Hãy xóa trắng toàn bộ database bằng lệnh:
```bash
docker compose down -v
```
*(Chữ `-v` sẽ xóa sạch các ổ cứng ảo của InfluxDB và Mosquitto).*

### Bước 2: Phi tang file tạo dữ liệu giả
File `test_mock_data.py` đã hoàn thành sứ mệnh lịch sử của nó. Hãy xóa nó đi để dự án gọn gàng:
```bash
rm gateway_api/test_mock_data.py
```
*(Hoặc click chuột phải vào file chọn Delete).*

### Bước 3: Sửa lại tên thư mục trong `docker-compose.yml` (Nếu cần)
Mở file `docker-compose.yml`, kiểm tra lại phần `build: ./virtual_sensor` và `build: ./iot_gateway`. 
👉 Hãy hỏi TV1 và TV2 xem họ đặt tên thư mục code là gì, và sửa lại cho đúng ở file này (như đã note TODO trong file).

### Bước 4: Khởi động hệ thống thật
Khi mọi thứ đã chuẩn xác, hãy gọi toàn bộ hệ thống dậy:
```bash
docker compose up -d --build
```

Lúc này, toàn bộ quy trình: *Sensor (TV1) -> MQTT -> Gateway (TV2) -> InfluxDB -> API & Grafana (TV3)* sẽ tự động chạy mượt mà!

