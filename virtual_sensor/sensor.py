"""
Virtual Sensor for Smart Building IoT System.
Simulates environmental sensors for a room in a smart building.
Publishes telemetry data to MQTT broker periodically.

Features:
- Realistic data trends (values drift gradually, not pure random)
- Anomaly injection (~10% probability) for temperature, CO2, humidity spikes
- Configurable via environment variables
- Auto-reconnect on MQTT disconnection
- last_seen field for offline detection by gateway
"""

import os
import json
import time
import random
import logging
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# Configuration from environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ROOM_ID = os.getenv("ROOM_ID", "room-01")
DEVICE_ID = os.getenv("DEVICE_ID", f"sensor-{ROOM_ID}")
PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))

# MQTT topic
TELEMETRY_TOPIC = f"building/{ROOM_ID}/sensor/telemetry"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(DEVICE_ID)


# Sensor Data Simulator
class SensorSimulator:
    """
    Simulates environmental sensor data with realistic trends.
    Values change gradually (not pure random) by keeping previous state.
    Has a mechanism to inject anomalies (~10% probability).
    """

    def __init__(self):
        # Initial values (reasonable defaults)
        self.temperature = 26.0   # °C
        self.humidity = 60.0      # %
        self.light_lux = 400.0    # lux
        self.co2_ppm = 600.0      # ppm
        self.occupancy = True
        self.cycle_count = 0

    def _drift(self, current: float, min_val: float, max_val: float,
               step: float = 0.5) -> float:
        """
        Apply a small random drift to the current value.
        Keeps the value within [min_val, max_val].
        """
        delta = random.uniform(-step, step)
        new_val = current + delta
        return max(min_val, min(max_val, round(new_val, 2)))

    def _maybe_anomaly(self) -> bool:
        """Return True ~10% of the time to trigger an anomaly."""
        return random.random() < 0.10

    def generate(self) -> dict:
        """
        Generate the next telemetry reading.
        Occasionally injects anomalies (high temp, high CO2, etc.).
        """
        self.cycle_count += 1

        # --- Normal drift ---
        self.temperature = self._drift(self.temperature, 20.0, 28.0, step=0.3)
        self.humidity = self._drift(self.humidity, 40.0, 80.0, step=1.0)
        self.light_lux = self._drift(self.light_lux, 50.0, 800.0, step=20.0)
        self.co2_ppm = self._drift(self.co2_ppm, 400.0, 1000.0, step=15.0)

        # Occupancy changes less frequently
        if random.random() < 0.05:
            self.occupancy = not self.occupancy

        # --- Anomaly injection (~10% chance) ---
        if self._maybe_anomaly():
            anomaly_type = random.choice([
                "temperature_high", "co2_high", "humidity_high"
            ])
            if anomaly_type == "temperature_high":
                self.temperature = round(random.uniform(31.0, 38.0), 2)
                logger.warning(f" ANOMALY: temperature spike → {self.temperature}°C")
            elif anomaly_type == "co2_high":
                self.co2_ppm = round(random.uniform(1250.0, 2000.0), 2)
                logger.warning(f" ANOMALY: CO2 spike → {self.co2_ppm} ppm")
            elif anomaly_type == "humidity_high":
                self.humidity = round(random.uniform(85.0, 98.0), 2)
                logger.warning(f" ANOMALY: humidity spike → {self.humidity}%")

        # --- Build telemetry message ---
        now = datetime.now(timezone.utc).isoformat()
        message = {
            "device_id": DEVICE_ID,
            "room_id": ROOM_ID,
            "temperature": self.temperature,
            "humidity": self.humidity,
            "light_lux": self.light_lux,
            "co2_ppm": self.co2_ppm,
            "occupancy": self.occupancy,
            "timestamp": now,
            "last_seen": now  # For gateway offline detection (advanced #4)
        }
        return message


# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f" Connected to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        logger.error(f" Failed to connect, return code: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    logger.warning(f"️ Disconnected from MQTT broker (rc={rc}). Will reconnect...")


# Main loop
def main():
    logger.info(f"Starting Virtual Sensor: {DEVICE_ID} for {ROOM_ID}")
    logger.info(f"Publishing to topic: {TELEMETRY_TOPIC}")
    logger.info(f"Publish interval: {PUBLISH_INTERVAL}s")

    # Create MQTT client
    client = mqtt.Client(
        client_id=DEVICE_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    # Auto-reconnect with exponential backoff (advanced #10)
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # Connect with retry
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            logger.error(f"Connection failed: {e}. Retrying in 5s...")
            time.sleep(5)

    client.loop_start()

    # Sensor simulator
    simulator = SensorSimulator()

    try:
        while True:
            telemetry = simulator.generate()
            payload = json.dumps(telemetry)

            result = client.publish(TELEMETRY_TOPIC, payload, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f" Published: temp={telemetry['temperature']}, "
                           f"humidity={telemetry['humidity']}, "
                           f"co2={telemetry['co2_ppm']}, "
                           f"light={telemetry['light_lux']}, "
                           f"occupancy={telemetry['occupancy']}")
            else:
                logger.error(f"Publish failed with rc={result.rc}")

            time.sleep(PUBLISH_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Shutting down sensor...")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
