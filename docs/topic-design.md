# MQTT Topic Design — Smart Building IoT Gateway

## Topic Hierarchy

| Topic Pattern | Direction | Publisher | Subscriber | Description |
|---|---|---|---|---|
| `building/{room_id}/sensor/telemetry` | Sensor → Gateway | Virtual Sensor | IoT Gateway | Raw telemetry data from room sensors |
| `building/{room_id}/actuator/command` | Gateway/API → Actuator | IoT Gateway, REST API | Virtual Actuator | Control commands to actuators |
| `building/{room_id}/actuator/status` | Actuator → Gateway | Virtual Actuator | IoT Gateway | Current state of actuators after command |
| `building/{room_id}/gateway/normalized` | Gateway → Subscribers | IoT Gateway | (any) | Validated and normalized sensor data |
| `building/{room_id}/gateway/event` | Gateway → Subscribers | IoT Gateway | (any) | Anomaly events detected by rule engine |

## Room IDs

- `room-01`
- `room-02`
- `room-03`

## Wildcard Subscriptions

- Gateway subscribes to `building/+/sensor/telemetry` to receive data from **all** rooms
- Gateway subscribes to `building/+/actuator/status` to track actuator state for **all** rooms

## Message Formats

### Telemetry Message (Sensor → Gateway)

```json
{
  "device_id": "sensor-room-01",
  "room_id": "room-01",
  "temperature": 29.5,
  "humidity": 73.2,
  "light_lux": 380.0,
  "co2_ppm": 950.0,
  "occupancy": true,
  "timestamp": "2026-06-10T10:00:00Z",
  "last_seen": "2026-06-10T10:00:00Z"
}
```

### Command Message (Gateway/API → Actuator)

```json
{
  "room_id": "room-01",
  "target": "fan",
  "action": "on",
  "reason": "temperature_high",
  "timestamp": "2026-06-10T10:00:05Z"
}
```

- `target`: `fan` | `light` | `alarm`
- `action`: `on` | `off`

### Status Message (Actuator → Gateway)

```json
{
  "device_id": "actuator-room-01",
  "room_id": "room-01",
  "fan": "on",
  "light": "off",
  "alarm": "off",
  "last_command_reason": "temperature_high",
  "timestamp": "2026-06-10T10:00:06Z"
}
```

### Event Message (Gateway → Subscribers)

```json
{
  "room_id": "room-01",
  "event_type": "temperature_high",
  "severity": "warning",
  "value": 32.5,
  "threshold": 30.0,
  "action_taken": "fan_on",
  "timestamp": "2026-06-10T10:00:05Z"
}
```

- `event_type`: `temperature_high` | `temperature_low` | `co2_high` | `unnecessary_light`
- `severity`: `info` | `warning` | `critical`

## Data Flow

```
Sensor ──publish──► building/{room_id}/sensor/telemetry ──subscribe──► Gateway
                                                                          │
                                                                    ┌─────┴─────┐
                                                                    │           │
                                                              Validate    Evaluate
                                                              Normalize   Rules
                                                                    │           │
                                                                    ▼           ▼
                                                              Write to    Generate
                                                              InfluxDB    Events/Commands
                                                                          │         │
                                                                          ▼         ▼
Gateway ──publish──► building/{room_id}/actuator/command ──subscribe──► Actuator
Actuator ──publish──► building/{room_id}/actuator/status ──subscribe──► Gateway
Gateway ──publish──► building/{room_id}/gateway/event
Gateway ──publish──► building/{room_id}/gateway/normalized
```
