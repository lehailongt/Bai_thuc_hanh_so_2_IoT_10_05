import json
from datetime import datetime, timezone 
import paho.mqtt.client as mqtt 
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.domain.write_precision import WritePrecision 
from influxdb_client.client.write_api import SYNCHRONOUS 
from paho.mqtt.enums import CallbackAPIVersion  # Thêm dòng này

from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC,
    INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG, INFLUX_BUCKET_RAW
)

# ===== InfluxDB =====
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

REQUIRED_FIELDS = {"temperature", "humidity", "distance_cm"}

def validate(payload: dict) -> bool:
    if not REQUIRED_FIELDS.issubset(payload.keys()):
        return False
    for k in REQUIRED_FIELDS:
        try:
            float(payload[k])
        except (TypeError, ValueError):
            return False
    return True

# ===== MQTT callbacks =====
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected rc={rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"[MQTT] Subscribed: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        if not validate(payload):
            print(f"[SKIP] Invalid payload: {payload}")
            return

        point = (
            Point("sensor_data")
            .tag("device", "esp32-lab2")
            .field("temperature", float(payload["temperature"]))
            .field("humidity",    float(payload["humidity"]))
            .field("distance_cm", float(payload["distance_cm"]))
            .field("rssi",        int(payload.get("rssi", 0)))
            .field("sequence",    int(payload.get("sequence", 0)))
            .time(datetime.now(timezone.utc), WritePrecision.NS) # Đã sửa
        )
        write_api.write(bucket=INFLUX_BUCKET_RAW, org=INFLUX_ORG, record=point)
        print(f"[OK] {payload}")
    except Exception as e:
        print(f"[ERROR] {e}")

# ===== Main =====
def main():
    # Nếu bạn dùng paho-mqtt bản 2.x, hãy mở comment dòng dưới và xóa dòng client = mqtt.Client...
    client = mqtt.Client(CallbackAPIVersion.VERSION1, client_id="python-collector") 
    # client = mqtt.Client(client_id="python-collector") # Dành cho paho-mqtt 1.6.1
    
    client.on_connect = on_connect
    client.on_message = on_message
    print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}")
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_forever()

if __name__ == "__main__":
    main()