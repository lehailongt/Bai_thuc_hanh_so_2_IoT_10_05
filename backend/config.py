# Cấu hình chung toàn hệ thống

# MQTT
# MQTT_BROKER = "localhost"        # Nếu muốn nghe từ HiveMQ: "broker.hivemq.com"
MQTT_BROKER = "broker.hivemq.com"        # Nếu muốn nghe từ HiveMQ: "broker.hivemq.com"
MQTT_PORT   = 1883
MQTT_TOPIC  = "iot/sensor/data"

# InfluxDB
INFLUX_URL    = "http://localhost:8086"
# INFLUX_TOKEN  = "my-super-secret-token-12345"
INFLUX_TOKEN  = "xPNe4UYkOqfCIDgR44KQMM4hQ7-w_wDqQ6FJkbnUYjrpsJ9BgoFIe272_OTScTMdQWWnlN5IxvqIOwxECL3LRg=="
INFLUX_ORG    = "iot_org"
INFLUX_BUCKET_RAW       = "iot_raw"
INFLUX_BUCKET_PROCESSED = "iot_processed"