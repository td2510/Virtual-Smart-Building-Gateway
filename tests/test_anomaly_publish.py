"""
Test script: Automatically publish anomaly data to test the gateway rule engine.
Usage: python tests/test_anomaly_publish.py --broker localhost --room room-01 --scenario all

This script publishes various anomaly scenarios to MQTT to verify
that the gateway rule engine detects and responds correctly.
Can be run standalone against a live Mosquitto + Gateway setup.
"""

import argparse
import json
import time
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

# --- Anomaly Scenarios ---
SCENARIOS = {
    "temperature_high": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 35.0,     # > 30 → triggers fan ON
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
    },
    "co2_high": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 25.0,
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 1500.0,       # > 1200 → triggers alarm ON
        "occupancy": True,
    },
    "unnecessary_light": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 25.0,
        "humidity": 60.0,
        "light_lux": 600.0,      # > 300 AND occupancy=false → triggers light OFF
        "co2_ppm": 800.0,
        "occupancy": False,
    },
    "temperature_low": {
        "device_id": "sensor-room-01",
        "room_id": "room-01",
        "temperature": 22.0,     # < 27 → triggers fan OFF
        "humidity": 60.0,
        "light_lux": 400.0,
        "co2_ppm": 800.0,
        "occupancy": True,
    },
}


def publish_scenario(broker: str, room_id: str, scenario_name: str, port: int = 1883):
    """Publish a single anomaly scenario to MQTT."""
    if scenario_name not in SCENARIOS:
        print(f"❌ Unknown scenario: {scenario_name}")
        return

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(broker, port)
    client.loop_start()

    data = SCENARIOS[scenario_name].copy()
    data["room_id"] = room_id
    data["device_id"] = f"sensor-{room_id}"
    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    data["last_seen"] = datetime.now(timezone.utc).isoformat()

    topic = f"building/{room_id}/sensor/telemetry"
    payload = json.dumps(data)

    result = client.publish(topic, payload, qos=1)
    result.wait_for_publish()
    print(f"✅ Published [{scenario_name}] to {topic}")
    print(f"   Payload: {payload}")

    client.loop_stop()
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Anomaly Test Publisher")
    parser.add_argument("--broker", default="localhost",
                        help="MQTT broker hostname")
    parser.add_argument("--port", type=int, default=1883,
                        help="MQTT broker port")
    parser.add_argument("--room", default="room-01",
                        help="Room ID to publish to")
    parser.add_argument("--scenario", default="all",
                        choices=list(SCENARIOS.keys()) + ["all"],
                        help="Which scenario to publish (or 'all')")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Interval between scenarios in seconds")
    args = parser.parse_args()

    print(f"🔧 Anomaly Test Publisher")
    print(f"   Broker: {args.broker}:{args.port}")
    print(f"   Room: {args.room}")
    print(f"   Scenario: {args.scenario}")
    print()

    if args.scenario == "all":
        for name in SCENARIOS:
            print(f"\n--- Testing scenario: {name} ---")
            publish_scenario(args.broker, args.room, name, args.port)
            time.sleep(args.interval)
        print(f"\n✅ All {len(SCENARIOS)} scenarios published!")
    else:
        publish_scenario(args.broker, args.room, args.scenario, args.port)


if __name__ == "__main__":
    main()
