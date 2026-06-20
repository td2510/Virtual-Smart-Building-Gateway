# Dùng Python 3.11 phiên bản nhẹ (slim)
FROM python:3.11-slim

# Thư mục làm việc bên trong container
WORKDIR /app

# Copy file requirements trước (để Docker cache lại bước này)
# → Nếu chỉ thay đổi api.py, Docker không cần cài lại thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code chính
COPY api.py .

# Mở port 8000 để bên ngoài truy cập
EXPOSE 8000

# Lệnh khởi động: chạy uvicorn với api.py, lắng nghe mọi địa chỉ
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
