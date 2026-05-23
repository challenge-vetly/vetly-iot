/*
 * VetlyCollar — Coleira Inteligente Multi-Pet
 * Sprint 1 — Firmware ESP32
 *
 * Bibliotecas necessárias (Wokwi Library Manager):
 *   - PubSubClient
 *   - OneWire
 *   - DallasTemperature
 *   - Adafruit MPU6050
 *   - Adafruit Unified Sensor
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// ---------------- Configurações ----------------
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

const char* MQTT_BROKER = "broker.hivemq.com";
const int   MQTT_PORT   = 1883;

const char* TOPIC_PREFIX = "vetlycollar";

const unsigned long PUBLISH_INTERVAL_MS = 2000;

// ---------------- Pinos ----------------
#define PIN_DS18B20  4
#define PIN_POT      34

// ---------------- Objetos globais ----------------
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

OneWire oneWire(PIN_DS18B20);
DallasTemperature ds18b20(&oneWire);

Adafruit_MPU6050 mpu;
bool mpuOk = false;

// ---------------- Estado dos pets virtuais ----------------
struct VirtualPet {
  const char* id;
  const char* nome;
  float tempBase;
  float bpmBase;
  float atvBase;
  float driftTemp;
  float driftBpm;
  float driftAtv;
  int   driftCounter;
};

VirtualPet pet002 = {"pet002", "Mimi", 38.6f, 180.0f, 0.35f, 0, 0, 0, 0};
VirtualPet pet003 = {"pet003", "Tobi", 39.2f, 220.0f, 0.40f, 0, 0, 0, 0};

unsigned long lastPublish = 0;

// ---------------- Utilidades ----------------
float ruidoGauss(float desvio) {
  float u1 = (random(1, 10000)) / 10000.0f;
  float u2 = (random(1, 10000)) / 10000.0f;
  float z  = sqrt(-2.0f * log(u1)) * cos(2.0f * 3.14159265f * u2);
  return z * desvio;
}

void atualizaDrift(VirtualPet& p) {
  p.driftCounter++;
  if (p.driftCounter >= 30) {
    p.driftCounter = 0;
    p.driftTemp = ruidoGauss(0.15f);
    p.driftBpm  = ruidoGauss(8.0f);
    p.driftAtv  = ruidoGauss(0.05f);
  }
}

// ---------------- Wi-Fi ----------------
void conectaWiFi() {
  Serial.print("[WiFi] Conectando");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("[WiFi] Conectado | IP: ");
  Serial.println(WiFi.localIP());
}

// ---------------- MQTT ----------------
void conectaMQTT() {
  while (!mqtt.connected()) {
    String clientId = "vetlycollar-esp32-";
    clientId += String(millis());

    Serial.print("[MQTT] Conectando ao ");
    Serial.print(MQTT_BROKER);
    Serial.print(" ... ");

    if (mqtt.connect(clientId.c_str())) {
      Serial.println("OK");
      Serial.println("[MQTT] Conectado ao broker.hivemq.com");
    } else {
      Serial.print("falhou rc=");
      Serial.print(mqtt.state());
      Serial.println(" — tentando novamente em 2s");
      delay(2000);
    }
  }
}

void publica(const char* petId, const char* metrica, float valor, int casas = 2) {
  char topic[80];
  char payload[16];
  snprintf(topic, sizeof(topic), "%s/%s/%s", TOPIC_PREFIX, petId, metrica);
  dtostrf(valor, 1, casas, payload);

  mqtt.publish(topic, payload, true);

  Serial.print("[PUB] ");
  Serial.print(topic);
  Serial.print(" ");
  Serial.println(payload);
}

// Publica atividade como JSON (level + steps + mov_ms) — formato esperado pelo dashboard
void publicaAtividade(const char* petId, float indice) {
  int level = 0;
  if (indice > 0.65f)      level = 2;
  else if (indice > 0.25f) level = 1;

  static unsigned long stepsPet001 = 0, stepsPet002 = 0, stepsPet003 = 0;
  static unsigned long movPet001   = 0, movPet002   = 0, movPet003   = 0;

  unsigned long* steps;
  unsigned long* mov;
  if      (strcmp(petId, "pet001") == 0) { steps = &stepsPet001; mov = &movPet001; }
  else if (strcmp(petId, "pet002") == 0) { steps = &stepsPet002; mov = &movPet002; }
  else                                    { steps = &stepsPet003; mov = &movPet003; }

  if (level >= 1) {
    *steps += (level == 2) ? 8 : 3;
    *mov   += PUBLISH_INTERVAL_MS;
  }

  char topic[80];
  char payload[96];
  snprintf(topic, sizeof(topic), "%s/%s/atividade", TOPIC_PREFIX, petId);
  snprintf(payload, sizeof(payload),
           "{\"level\":%d,\"steps\":%lu,\"mov_ms\":%lu,\"idx\":%.2f}",
           level, *steps, *mov, indice);

  mqtt.publish(topic, payload, true);

  Serial.print("[PUB] ");
  Serial.print(topic);
  Serial.print(" ");
  Serial.println(payload);
}

void publicaStatus(const char* petId, float temp, float bpm, float atv) {
  char topic[80];
  char payload[128];
  snprintf(topic, sizeof(topic), "%s/%s/status", TOPIC_PREFIX, petId);
  snprintf(payload, sizeof(payload),
           "{\"temp\":%.2f,\"bpm\":%.0f,\"atv\":%.2f,\"ts\":%lu}",
           temp, bpm, atv, millis());
  mqtt.publish(topic, payload, true);
}

// ---------------- Leituras reais (pet001 / Rex) ----------------
float lerTemperaturaReal() {
  ds18b20.requestTemperatures();
  float t = ds18b20.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C || t < -50.0f) {
    t = 38.4f;
  }
  return t;
}

float lerBpmReal() {
  int raw = analogRead(PIN_POT);
  float bpm = map(raw, 0, 4095, 50, 220);
  return bpm;
}

float lerAtividadeReal() {
  if (!mpuOk) return 0.30f;
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  float mag = sqrt(a.acceleration.x * a.acceleration.x +
                   a.acceleration.y * a.acceleration.y +
                   a.acceleration.z * a.acceleration.z);
  float delta = fabs(mag - 9.81f);
  float idx = delta / 5.0f;
  if (idx > 1.0f) idx = 1.0f;
  if (idx < 0.0f) idx = 0.0f;
  return idx;
}

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("=== VetlyCollar — Firmware ESP32 ===");

  analogReadResolution(12);
  randomSeed(esp_random());

  ds18b20.begin();
  ds18b20.setResolution(11);

  Wire.begin();
  if (mpu.begin()) {
    mpuOk = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println("[MPU6050] OK");
  } else {
    Serial.println("[MPU6050] não detectado — atividade usará fallback");
  }

  conectaWiFi();

  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  conectaMQTT();
}

// ---------------- Loop principal ----------------
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    conectaWiFi();
  }
  if (!mqtt.connected()) {
    conectaMQTT();
  }
  mqtt.loop();

  unsigned long agora = millis();
  if (agora - lastPublish < PUBLISH_INTERVAL_MS) return;
  lastPublish = agora;

  // ----- pet001 (Rex) — sensores reais -----
  float tempRex = lerTemperaturaReal();
  float bpmRex  = lerBpmReal();
  float atvRex  = lerAtividadeReal();

  publica("pet001", "temperatura", tempRex, 1);
  publica("pet001", "bpm",         bpmRex,  0);
  publicaAtividade("pet001", atvRex);
  publicaStatus("pet001", tempRex, bpmRex, atvRex);

  // ----- pet002 (Mimi / gato virtual) -----
  atualizaDrift(pet002);
  float tempMimi = pet002.tempBase + pet002.driftTemp + ruidoGauss(0.08f);
  float bpmMimi  = pet002.bpmBase  + pet002.driftBpm  + ruidoGauss(4.0f);
  float atvMimi  = pet002.atvBase  + pet002.driftAtv  + ruidoGauss(0.03f);
  if (atvMimi < 0) atvMimi = 0; if (atvMimi > 1) atvMimi = 1;

  publica("pet002", "temperatura", tempMimi, 1);
  publica("pet002", "bpm",         bpmMimi,  0);
  publicaAtividade("pet002", atvMimi);
  publicaStatus("pet002", tempMimi, bpmMimi, atvMimi);

  // ----- pet003 (Tobi / coelho virtual) -----
  atualizaDrift(pet003);
  float tempTobi = pet003.tempBase + pet003.driftTemp + ruidoGauss(0.10f);
  float bpmTobi  = pet003.bpmBase  + pet003.driftBpm  + ruidoGauss(6.0f);
  float atvTobi  = pet003.atvBase  + pet003.driftAtv  + ruidoGauss(0.04f);
  if (atvTobi < 0) atvTobi = 0; if (atvTobi > 1) atvTobi = 1;

  publica("pet003", "temperatura", tempTobi, 1);
  publica("pet003", "bpm",         bpmTobi,  0);
  publicaAtividade("pet003", atvTobi);
  publicaStatus("pet003", tempTobi, bpmTobi, atvTobi);
}