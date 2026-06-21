FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway.py .
COPY rule_engine.py .
COPY state_store.py .

CMD ["python", "-u", "gateway.py"]
