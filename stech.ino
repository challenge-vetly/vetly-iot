/**
 * =============================================================================
 *  ClivoVET — Coleira Inteligente Multi-Pet | Sprint 1
 *  Disruptive Architectures: IoT, IoB & Generative AI
 * =============================================================================
 *
 *  Sensores reais conectados ao ESP32 (representam o pet001 / Rex):
 *    DS18B20  (GPIO 4)         → Temperatura corporal
 *    Potenciômetro (GPIO 34)   → BPM simulado
 *    MPU6050  (I²C 21/22)      → Acelerômetro p/ índice de atividade
 *
 *  Pet002 (Mimi/gato) e pet003 (Tobi/coelho) têm leituras simuladas em
 *  software, como se fossem outros dispositivos do mesmo cliente.
 *
 *  Tópicos por pet:
 *    clivovet/<petId>/temperatura
 *    clivovet/<petId>/bpm
 *    clivovet/<petId>/atividade   (JSON: estado, passos, magnitude)
 *    clivovet/<petId>/status      (JSON agregado)
 * =============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

// -----------------------------------------------------------------------------
// CONFIG
// -----------------------------------------------------------------------------
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";
const char* MQTT_BROKER   = "broker.hivemq.com";
const int   MQTT_PORT     = 1883;

const int PIN_DS18B20 = 4;
const int PIN_POT     = 34;
const unsigned long PUBLISH_INTERVAL_MS = 2000;

// -----------------------------------------------------------------------------
// MODELO DE PET
// -----------------------------------------------------------------------------
struct PetState {
  const char* id;
  const char* species;
  bool isReal;

  // Para pets virtuais — bases e ruído
  float tempBase;
  float tempJitter;
  int   bpmBase;
  int   bpmJitter;
  float tempDrift;
  int   bpmDrift;

  // Atividade — comum aos dois tipos
  int   passos;            // contador acumulado
  unsigned long tMovTotal; // ms acumulado em movimento
  unsigned long lastTickMs;
  int   activityLevel;     // 0=repouso, 1=ativo, 2=intenso
  float activityMag;       // magnitude usada pra classificar (g)

  // Perfil de comportamento p/ pets virtuais
  // (probabilidade base de estar em movimento)
  float baseActivity;
};

PetState pets[] = {
  // id        spp      real   tBase  tJit  bBase bJit  tD bD  passos tMov last lvl mag baseAct
  { "pet001",  "cao",    true,  0,    0,    0,    0,    0, 0,  0,    0,   0,   0,  0,   0.55f }, // Rex (real)
  { "pet002",  "gato",   false, 38.5, 0.25, 175,  18,   0, 0,  0,    0,   0,   0,  0,   0.35f }, // Mimi (mais quieta)
  { "pet003",  "coelho", false, 39.2, 0.30, 220,  25,   0, 0,  0,    0,   0,   0,  0,   0.65f }, // Tobi (hiperativo)
};
const int NUM_PETS = sizeof(pets) / sizeof(pets[0]);

// -----------------------------------------------------------------------------
// OBJETOS GLOBAIS
// -----------------------------------------------------------------------------
WiFiClient   wifiClient;
PubSubClient mqttClient(wifiClient);
OneWire oneWire(PIN_DS18B20);
DallasTemperature tempSensor(&oneWire);
Adafruit_MPU6050 mpu;
bool mpuOk = false;

unsigned long lastPublishMs = 0;
unsigned int  publishCount  = 0;

// -----------------------------------------------------------------------------
// SETUP
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(100);
  Serial.println();
  Serial.println(F("====================================================="));
  Serial.println(F(" ClivoVET — Central Multi-Pet com Atividade"));
  Serial.println(F("====================================================="));

  analogReadResolution(12);
  randomSeed(analogRead(PIN_POT) ^ esp_random());

  // Sensor de temperatura
  tempSensor.begin();
  Serial.print(F("Sensores DS18B20: "));
  Serial.println(tempSensor.getDeviceCount());

  // MPU6050 via I²C
  Wire.begin(21, 22);  // SDA=21, SCL=22
  if (mpu.begin()) {
    mpuOk = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    Serial.println(F("MPU6050: OK"));
  } else {
    Serial.println(F("[WARN] MPU6050 não detectado — pet001 usará atividade simulada."));
  }

  Serial.print(F("Pets monitorados: "));
  Serial.println(NUM_PETS);

  connectWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(256);

  // Inicializa tick de atividade
  unsigned long now = millis();
  for (int i = 0; i < NUM_PETS; i++) pets[i].lastTickMs = now;
}

// -----------------------------------------------------------------------------
// LOOP
// -----------------------------------------------------------------------------
void loop() {
  if (!mqttClient.connected()) connectMqtt();
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastPublishMs >= PUBLISH_INTERVAL_MS) {
    lastPublishMs = now;
    publishAllPets();
    publishCount++;
  }
}

// -----------------------------------------------------------------------------
// GERAÇÃO DE LEITURAS — TEMP/BPM
// -----------------------------------------------------------------------------
float gaussianNoise() {
  float r = (random(0, 1000) + random(0, 1000) + random(0, 1000)) / 3000.0f;
  return (r - 0.5f) * 2.0f;
}

void atualizarDrift(PetState &p) {
  if (publishCount % 30 == 0) {
    p.tempDrift = (random(-10, 11) / 100.0f);
    p.bpmDrift  = random(-8, 9);
  }
}

float gerarTempVirtual(PetState &p) {
  return p.tempBase + p.tempDrift + gaussianNoise() * p.tempJitter;
}

int gerarBpmVirtual(PetState &p) {
  int raw = p.bpmBase + p.bpmDrift + (int)(gaussianNoise() * p.bpmJitter);
  if (raw < 20)  raw = 20;
  if (raw > 450) raw = 450;
  return raw;
}

bool lerSensoresReais(float &tempOut, int &bpmOut) {
  tempSensor.requestTemperatures();
  float t = tempSensor.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) return false;
  int raw = analogRead(PIN_POT);
  tempOut = t;
  bpmOut  = map(raw, 0, 4095, 30, 450);
  return true;
}

// -----------------------------------------------------------------------------
// ATIVIDADE FÍSICA
// -----------------------------------------------------------------------------

// Lê o MPU6050 e devolve a "magnitude líquida" da aceleração em g,
// removendo a componente gravitacional (1g) — quanto resta é movimento.
float lerMagnitudeMPU() {
  if (!mpuOk) return -1.0f;
  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);
  // Aceleração em m/s². Magnitude total:
  float magMs2 = sqrt(a.acceleration.x * a.acceleration.x +
                     a.acceleration.y * a.acceleration.y +
                     a.acceleration.z * a.acceleration.z);
  float magG = magMs2 / 9.80665f;          // converte pra g
  float liquido = fabs(magG - 1.0f);       // remove gravidade
  return liquido;
}

// Classifica nível a partir da magnitude líquida (g)
//   < 0.15g  → repouso
//   < 0.50g  → ativo
//   ≥ 0.50g  → intenso
int classificarNivelDe(float magG) {
  if (magG < 0.15f) return 0;
  if (magG < 0.50f) return 1;
  return 2;
}

// Atualiza atividade de UM pet. Pet real usa o MPU; virtuais usam um
// modelo probabilístico com "personalidade" diferente por animal.
void atualizarAtividade(PetState &p) {
  unsigned long now = millis();
  unsigned long dt  = now - p.lastTickMs;
  p.lastTickMs = now;

  float magG;
  if (p.isReal && mpuOk) {
    magG = lerMagnitudeMPU();
  } else {
    // Pets virtuais — sorteio ponderado pelo "baseActivity"
    // baseActivity ~ probabilidade de estar em movimento neste tick
    float r = random(0, 1000) / 1000.0f;
    if (r < p.baseActivity * 0.30f) {
      magG = 0.6f + gaussianNoise() * 0.15f;   // intenso esporádico
    } else if (r < p.baseActivity) {
      magG = 0.25f + gaussianNoise() * 0.08f;  // ativo
    } else {
      magG = 0.05f + fabs(gaussianNoise()) * 0.05f; // repouso
    }
    if (magG < 0) magG = 0;
  }

  p.activityMag   = magG;
  p.activityLevel = classificarNivelDe(magG);

  // Acumula tempo em movimento (níveis 1 e 2)
  if (p.activityLevel >= 1) p.tMovTotal += dt;

  // Conta passos (heurística simples: cada "pico" de atividade vira ~1-3 passos)
  // No nível 2, mais passos por ciclo; no nível 1, menos.
  if (p.activityLevel == 2) p.passos += 2 + random(0, 2);
  else if (p.activityLevel == 1) p.passos += random(0, 2);
}

const char* nomeNivel(int n) {
  switch (n) {
    case 0: return "repouso";
    case 1: return "ativo";
    case 2: return "intenso";
    default: return "?";
  }
}

// -----------------------------------------------------------------------------
// PUBLICAÇÃO MQTT
// -----------------------------------------------------------------------------
void publishPet(PetState &p) {
  float tempC = 0.0f;
  int   bpm   = 0;

  if (p.isReal) {
    if (!lerSensoresReais(tempC, bpm)) {
      Serial.print(F("[WARN] "));
      Serial.print(p.id);
      Serial.println(F(": leitura real descartada."));
      return;
    }
  } else {
    atualizarDrift(p);
    tempC = gerarTempVirtual(p);
    bpm   = gerarBpmVirtual(p);
  }

  atualizarAtividade(p);

  // Tópicos
  char topicTemp[48], topicBpm[48], topicAct[48], topicStatus[48];
  snprintf(topicTemp,   sizeof(topicTemp),   "clivovet/%s/temperatura", p.id);
  snprintf(topicBpm,    sizeof(topicBpm),    "clivovet/%s/bpm",         p.id);
  snprintf(topicAct,    sizeof(topicAct),    "clivovet/%s/atividade",   p.id);
  snprintf(topicStatus, sizeof(topicStatus), "clivovet/%s/status",      p.id);

  char tempBuf[8], bpmBuf[8];
  dtostrf(tempC, 4, 2, tempBuf);
  itoa(bpm, bpmBuf, 10);

  mqttClient.publish(topicTemp, tempBuf, true);
  mqttClient.publish(topicBpm,  bpmBuf,  true);

  // Atividade — payload JSON
  char actBuf[160];
  char magBuf[10];
  dtostrf(p.activityMag, 4, 2, magBuf);
  snprintf(actBuf, sizeof(actBuf),
           "{\"level\":%d,\"label\":\"%s\",\"mag\":%s,\"steps\":%d,\"mov_ms\":%lu}",
           p.activityLevel, nomeNivel(p.activityLevel), magBuf, p.passos, p.tMovTotal);
  mqttClient.publish(topicAct, actBuf, true);

  // Status agregado
  char jsonBuf[220];
  snprintf(jsonBuf, sizeof(jsonBuf),
           "{\"id\":\"%s\",\"species\":\"%s\",\"temp\":%s,\"bpm\":%s,\"activity\":\"%s\",\"steps\":%d,\"src\":\"%s\",\"ts\":%lu}",
           p.id, p.species, tempBuf, bpmBuf, nomeNivel(p.activityLevel),
           p.passos, p.isReal ? "sensor" : "sim", millis() / 1000);
  mqttClient.publish(topicStatus, jsonBuf, true);

  Serial.print(F("[PUB] "));
  Serial.print(p.id);
  Serial.print(F(" t="));  Serial.print(tempBuf);
  Serial.print(F(" b="));  Serial.print(bpmBuf);
  Serial.print(F(" act=")); Serial.print(nomeNivel(p.activityLevel));
  Serial.print(F(" steps="));Serial.println(p.passos);
}

void publishAllPets() {
  for (int i = 0; i < NUM_PETS; i++) publishPet(pets[i]);
}

// -----------------------------------------------------------------------------
// CONEXÕES
// -----------------------------------------------------------------------------
void connectWiFi() {
  Serial.print(F("Wi-Fi "));
  Serial.print(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print('.'); }
  Serial.println();
  Serial.print(F("IP: "));
  Serial.println(WiFi.localIP());
}

void connectMqtt() {
  while (!mqttClient.connected()) {
    Serial.print(F("MQTT... "));
    String clientId = "clivovet-hub-" + String(millis());
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(F("OK"));
    } else {
      Serial.print(F("rc="));
      Serial.println(mqttClient.state());
      delay(2000);
    }
  }
}