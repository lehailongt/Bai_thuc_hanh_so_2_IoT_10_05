#include <WiFi.h>
#include <PubSubClient.h>
#include <DHTesp.h>
#include <ArduinoJson.h>

// ====== CẤU HÌNH ======
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// Dùng IP LAN của máy tính bạn nếu chạy Mosquitto local (không dùng được trên Wokwi)
// Nếu chạy Wokwi → dùng broker public:
const char* MQTT_SERVER = "broker.hivemq.com";
// const char* MQTT_SERVER = "192.168.1.7"; ?? ip khi máy tính khi gõ lệnh trên cmd: ipconfig
const int   MQTT_PORT   = 1883;
const char* MQTT_TOPIC  = "iot/sensor/data";
const char* CLIENT_ID   = "esp32-lab2-001";

// Nếu chạy Mosquitto local trên máy bạn (mạng LAN):
// const char* MQTT_SERVER = "192.168.1.100";  // ← IP máy tính

// ====== CHÂN CẢM BIẾN ======
const int DHT_PIN  = 15;
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;
const int LED_PIN  = 2;

const unsigned long SEND_INTERVAL_MS = 5000;

WiFiClient    wifiClient;
PubSubClient  mqttClient(wifiClient);
DHTesp        dht;

unsigned long lastSend = 0;
unsigned long sequenceNo = 0;

// ====== KẾT NỐI WIFI ======
void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" connected");
  Serial.print("IP: "); Serial.println(WiFi.localIP());
}

// ====== KẾT NỐI MQTT ======
void connectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Connecting MQTT...");
    if (mqttClient.connect(CLIENT_ID)) {
      Serial.println(" connected");
    } else {
      Serial.printf(" failed rc=%d. Retry 2s\n", mqttClient.state());
      delay(2000);
    }
  }
}

// ====== ĐỌC SIÊU ÂM ======
float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return NAN;
  return duration * 0.0343f / 2.0f;
}

// ====== SETUP ======
void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  dht.setup(DHT_PIN, DHTesp::DHT22);

  connectWiFi();
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setBufferSize(512);
}

// ====== LOOP ======
void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqttClient.connected())        connectMQTT();
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastSend < SEND_INTERVAL_MS) return;
  lastSend = now;

  TempAndHumidity data = dht.getTempAndHumidity();
  float distance = readDistanceCm();

  if (!isfinite(data.temperature) || !isfinite(data.humidity) || !isfinite(distance)) {
    Serial.println("Invalid data — skip");
    return;
  }

  sequenceNo++;

  // Tạo JSON bằng ArduinoJson (an toàn hơn snprintf)
  StaticJsonDocument<256> doc;
  doc["temperature"] = round(data.temperature * 100) / 100.0;
  doc["humidity"]    = round(data.humidity * 100) / 100.0;
  doc["distance_cm"] = round(distance * 100) / 100.0;
  doc["rssi"]        = WiFi.RSSI();
  doc["sequence"]    = sequenceNo;
  doc["uptime_s"]    = millis() / 1000;

  char payload[256];
  serializeJson(doc, payload);

  bool ok = mqttClient.publish(MQTT_TOPIC, payload);
  Serial.printf("Publish %s => %s\n", ok ? "OK" : "FAIL", payload);

  digitalWrite(LED_PIN, HIGH); delay(80);
  digitalWrite(LED_PIN, LOW);
}