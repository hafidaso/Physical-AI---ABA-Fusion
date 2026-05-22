#include <Adafruit_BME280.h>
#include <Arduino.h>
#include <NextMPU6050.h>
#include <PubSubClient.h>
#include <TM1637Display.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <math.h>

/*
  PROJET FINAL - SEMAINE 1
  SMART ROBOT SAFETY CONTROLLER + MQTT DIGITAL TWIN
  By : Hafida Belayd

  Carte : Maker Point Beginner Kit + ESP32

  Architecture locale :
  Capteurs -> Lecture -> Filtrage -> Validation -> Decision
            -> Sorties -> Telemetrie MQTT

  Architecture connectee :
  ESP32 -> WiFi -> HiveMQ Cloud -> Pygame -> ABA Fusion -> Google Sheets

  Etats :
  1 = NORMAL
  2 = WARNING
  3 = STOP / DANGER
  F = FAULT

  Capteurs utilises :
  - IR : detection d'obstacle
  - Potentiometre : simulation de la vitesse
  - MPU6050 : detection de choc
  - Bouton STOP : arret physique
  - BME280 : humidite transmise en telemetrie

  Important :
  - La securite locale continue meme sans WiFi ni MQTT.
  - L'humidite est mesuree et transmise, mais ne change pas
    l'etat du robot tant qu'une regle metier n'est pas definie.
  - Une commande distante peut demander STOP.
  - Une commande distante ne force jamais le relais ON en cas de danger local.
*/

// 1. WIFI / MQTT - REMPLIR LOCALEMENT, NE PAS PUBLIER SUR GITHUB

const char *ssid = "Fibre_inwi_2.4G_D7EB";
const char *password = "CCB071B34340";

const char *mqttHost = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";
const int mqttPort = 8883;
const char *mqttUser = "hivemq.webclient.1775653497883";
const char *mqttPass = "1B%.CwaP:Kdr2I93k*Ap";

const char *TOPIC_TELEMETRY = "hafida/robot/twin/telemetry";
const char *TOPIC_COMMAND = "hafida/robot/twin/command";

const char *DEVICE_ID = "hafida-smart-robot-safety";

// 2. PINS - MAKER POINT BEGINNER KIT

// Entrees
const int PIN_IR = 4;
const int PIN_POT = 35;         // Potentiometre externe : X5 / GPIO35 (ADC1)
const int PIN_STOP_BUTTON = 34;

// LEDs
const int PIN_LED_GREEN = 32;
const int PIN_LED_RED = 33;
const int PIN_LED_ORANGE = 19; // LED orange externe : X13 / GPIO19

// Sorties
const int PIN_BUZZER = 26;
const int PIN_RELAY_1 = 23;
const int PIN_RELAY_2 = 27;

// Afficheur 7 segments TM1637
const int PIN_DISPLAY_DIO = 5;
const int PIN_DISPLAY_CLK = 18;

// Bus I2C partage : MPU6050 + BME280
const int PIN_I2C_SDA = 21;
const int PIN_I2C_SCL = 22;

// 3. CONFIGURATION FONCTIONNELLE

const bool ENABLE_IR_WARNING = true;
const bool ENABLE_POT_WARNING = true;
const bool ENABLE_BUTTON_STOP = true;
const bool ENABLE_SHOCK_STOP = true;

// IR teste : IR = 1 signifie obstacle detecte.
const int IR_OBSTACLE_LEVEL = HIGH;

// BTN2 : non appuye = HIGH, appuye = LOW.
const int STOP_ACTIVE_LEVEL = LOW;

// Le potentiometre simule la vitesse du robot.
const int POT_SPEED_WARNING_THRESHOLD = 3000;

// Seuil initial du choc, a calibrer apres les tests.
const float SHOCK_DELTA_THRESHOLD = 0.80;

// Inverser seulement si les relais physiques reagissent a l'envers.
const int RELAY_ON_LEVEL = HIGH;
const int RELAY_OFF_LEVEL = LOW;

// Temporisations
const unsigned long MQTT_TELEMETRY_INTERVAL_MS = 1000;
const unsigned long WARNING_BEEP_PERIOD = 1500;
const unsigned long WARNING_BEEP_DURATION = 100;
const unsigned long FAULT_BLINK_PERIOD = 500;
const unsigned long WIFI_RETRY_INTERVAL_MS = 10000;
const unsigned long MQTT_RETRY_INTERVAL_MS = 5000;

// 4. OBJETS

TM1637Display display(PIN_DISPLAY_CLK, PIN_DISPLAY_DIO);
NextMPU6050 mpu;
Adafruit_BME280 bme;

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

// 5. ETATS DU SYSTEME

enum class SystemState { NORMAL = 1, WARNING = 2, STOP_DANGER = 3, FAULT = 4 };

SystemState currentState = SystemState::FAULT;
const char *decisionReason = "BOOT";

// STOP distant recu par MQTT : reste actif jusqu'a RELEASE_STOP.
bool remoteEmergencyStop = false;
bool statusPublishRequested = false;

// 6. DONNEES CAPTEURS

struct SensorData {
  int irRaw = 0;
  bool stopPressed = false;

  int potRaw = 0;
  int potFiltered = 0;

  float accelX = 0.0;
  float accelY = 0.0;
  float accelZ = 0.0;
  float accelerationMagnitude = 0.0;
  float shockDeltaRaw = 0.0;
  float shockDeltaFiltered = 0.0;

  float humidityPct = NAN;

  bool mpuAvailable = false;
  bool bmeAvailable = false;
};

SensorData sensors;

// 7. VARIABLES TEMPORELLES ET FILTRAGE

unsigned long lastTelemetryPublishTime = 0;
unsigned long lastFaultBlinkTime = 0;
unsigned long lastWiFiAttemptTime = 0;
unsigned long lastMqttAttemptTime = 0;

bool faultBlinkState = false;
bool filterInitialized = false;
bool wifiConnectedAnnounced = false;

float filteredPot = 0.0;
float filteredShock = 0.0;

// 8. FONCTIONS UTILITAIRES

const char *stateToString(SystemState state) {
  switch (state) {
  case SystemState::NORMAL:
    return "NORMAL";
  case SystemState::WARNING:
    return "WARNING";
  case SystemState::STOP_DANGER:
    return "STOP";
  case SystemState::FAULT:
    return "FAULT";
  default:
    return "UNKNOWN";
  }
}

void setRelays(bool enabled) {
  digitalWrite(PIN_RELAY_1, enabled ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
  digitalWrite(PIN_RELAY_2, enabled ? RELAY_ON_LEVEL : RELAY_OFF_LEVEL);
}

bool relayIsEnabled() {
  return currentState == SystemState::NORMAL ||
         currentState == SystemState::WARNING;
}

// 9. AFFICHAGE DE L'ETAT

void displayState(SystemState state) {
  switch (state) {
  case SystemState::NORMAL:
    display.showNumberDec(1, false);
    break;

  case SystemState::WARNING:
    display.showNumberDec(2, false);
    break;

  case SystemState::STOP_DANGER:
    display.showNumberDec(3, false);
    break;

  case SystemState::FAULT: {
    const uint8_t faultDisplay[] = {0x00, 0x00, 0x00,
                                    SEG_A | SEG_F | SEG_G | SEG_E};
    display.setSegments(faultDisplay);
    break;
  }
  }
}

// 10. LECTURE ET FILTRAGE DES CAPTEURS

void lireCapteurs() {
  sensors.irRaw = digitalRead(PIN_IR);
  sensors.potRaw = analogRead(PIN_POT);
  sensors.stopPressed = (digitalRead(PIN_STOP_BUTTON) == STOP_ACTIVE_LEVEL);

  if (sensors.mpuAvailable) {
    sensors.accelX = mpu.getAccelX();
    sensors.accelY = mpu.getAccelY();
    sensors.accelZ = mpu.getAccelZ();

    sensors.accelerationMagnitude =
        sqrt(sensors.accelX * sensors.accelX + sensors.accelY * sensors.accelY +
             sensors.accelZ * sensors.accelZ);

    sensors.shockDeltaRaw = fabs(sensors.accelerationMagnitude - 1.0);
  }

  if (sensors.bmeAvailable) {
    sensors.humidityPct = bme.readHumidity();
  }
}

void filtrerMesures() {
  const float alphaPot = 0.25;
  const float alphaShock = 0.35;

  if (!filterInitialized) {
    filteredPot = sensors.potRaw;
    filteredShock = sensors.shockDeltaRaw;
    filterInitialized = true;
  } else {
    filteredPot = alphaPot * sensors.potRaw + (1.0 - alphaPot) * filteredPot;
    filteredShock =
        alphaShock * sensors.shockDeltaRaw + (1.0 - alphaShock) * filteredShock;
  }

  sensors.potFiltered = (int)filteredPot;
  sensors.shockDeltaFiltered = filteredShock;
}

// 11. VALIDATION ET CONDITIONS DE RISQUE

bool validerMesures() {
  if (!sensors.mpuAvailable) {
    decisionReason = "MPU_NOT_FOUND";
    return false;
  }

  if (isnan(sensors.accelX) || isnan(sensors.accelY) || isnan(sensors.accelZ)) {
    decisionReason = "MPU_INVALID_VALUE";
    return false;
  }

  return true;
}

bool obstacleDetecte() { return sensors.irRaw == IR_OBSTACLE_LEVEL; }

bool vitesseElevee() {
  return sensors.potFiltered >= POT_SPEED_WARNING_THRESHOLD;
}

bool chocFort() { return sensors.shockDeltaFiltered >= SHOCK_DELTA_THRESHOLD; }

// 12. LOGIQUE DE DECISION : FAULT > STOP > WARNING > NORMAL

SystemState deciderEtat() {
  if (!validerMesures()) {
    return SystemState::FAULT;
  }

  if (ENABLE_BUTTON_STOP && sensors.stopPressed) {
    decisionReason = "STOP_BUTTON";
    return SystemState::STOP_DANGER;
  }

  if (ENABLE_SHOCK_STOP && chocFort()) {
    decisionReason = "STRONG_SHOCK";
    return SystemState::STOP_DANGER;
  }

  if (remoteEmergencyStop) {
    decisionReason = "REMOTE_STOP";
    return SystemState::STOP_DANGER;
  }

  if (ENABLE_IR_WARNING && obstacleDetecte()) {
    decisionReason = "IR_OBSTACLE";
    return SystemState::WARNING;
  }

  if (ENABLE_POT_WARNING && vitesseElevee()) {
    decisionReason = "HIGH_SPEED";
    return SystemState::WARNING;
  }

  decisionReason = "ALL_OK";
  return SystemState::NORMAL;
}

// 13. APPLICATION DES SORTIES

void appliquerSorties(SystemState state) {
  unsigned long now = millis();

  switch (state) {
  case SystemState::NORMAL:
    digitalWrite(PIN_LED_GREEN, HIGH);
    digitalWrite(PIN_LED_ORANGE, LOW);
    digitalWrite(PIN_LED_RED, LOW);
    setRelays(true);
    digitalWrite(PIN_BUZZER, LOW);
    displayState(SystemState::NORMAL);
    break;

  case SystemState::WARNING: {
    digitalWrite(PIN_LED_GREEN, LOW);
    digitalWrite(PIN_LED_ORANGE, HIGH);
    digitalWrite(PIN_LED_RED, LOW);
    setRelays(true);

    bool shortBeep = (now % WARNING_BEEP_PERIOD) < WARNING_BEEP_DURATION;
    digitalWrite(PIN_BUZZER, shortBeep ? HIGH : LOW);
    displayState(SystemState::WARNING);
    break;
  }

  case SystemState::STOP_DANGER:
    digitalWrite(PIN_LED_GREEN, LOW);
    digitalWrite(PIN_LED_ORANGE, LOW);
    digitalWrite(PIN_LED_RED, HIGH);
    setRelays(false);
    digitalWrite(PIN_BUZZER, HIGH);
    displayState(SystemState::STOP_DANGER);
    break;

  case SystemState::FAULT:
    digitalWrite(PIN_LED_GREEN, LOW);
    digitalWrite(PIN_LED_ORANGE, LOW);
    setRelays(false);

    if (now - lastFaultBlinkTime >= FAULT_BLINK_PERIOD) {
      lastFaultBlinkTime = now;
      faultBlinkState = !faultBlinkState;
    }

    digitalWrite(PIN_LED_RED, faultBlinkState ? HIGH : LOW);
    digitalWrite(PIN_BUZZER, faultBlinkState ? HIGH : LOW);
    displayState(SystemState::FAULT);
    break;
  }
}

// 14. TELEMETRIE MQTT JSON

void buildTelemetryJson(char *payload, size_t payloadSize) {
  long rssi = (WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0;
  char humidityValue[16];

  if (sensors.bmeAvailable && !isnan(sensors.humidityPct)) {
    snprintf(humidityValue, sizeof(humidityValue), "%.2f", sensors.humidityPct);
  } else {
    snprintf(humidityValue, sizeof(humidityValue), "null");
  }

  snprintf(payload, payloadSize,
           "{\"device\":\"%s\",\"time_ms\":%lu,"
           "\"ir\":%d,\"obstacle\":%s,"
           "\"pot_raw\":%d,\"pot_filtered\":%d,"
           "\"stop_pressed\":%s,"
           "\"ax\":%.2f,\"ay\":%.2f,\"az\":%.2f,"
           "\"shock_delta\":%.2f,"
           "\"humidity_pct\":%s,\"bme_available\":%s,"
           "\"state\":\"%s\",\"reason\":\"%s\","
           "\"relay\":\"%s\",\"remote_stop\":%s,"
           "\"rssi\":%ld}",
           DEVICE_ID, millis(), sensors.irRaw,
           obstacleDetecte() ? "true" : "false", sensors.potRaw,
           sensors.potFiltered, sensors.stopPressed ? "true" : "false",
           sensors.accelX, sensors.accelY, sensors.accelZ,
           sensors.shockDeltaFiltered, humidityValue,
           sensors.bmeAvailable ? "true" : "false", stateToString(currentState),
           decisionReason, relayIsEnabled() ? "ON" : "OFF",
           remoteEmergencyStop ? "true" : "false", rssi);
}

void publishTelemetry() {
  if (!mqtt.connected()) {
    return;
  }

  char payload[640];
  buildTelemetryJson(payload, sizeof(payload));

  Serial.println(payload); 

  if (!mqtt.publish(TOPIC_TELEMETRY, payload)) {
    Serial.println("MQTT_PUBLISH_ERROR,TELEMETRY");
  }
}

// 15. COMMANDES MQTT

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String message;

  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  message.trim();
  message.toUpperCase();

  Serial.print("MQTT_RX,");
  Serial.print(topic);
  Serial.print(",");
  Serial.println(message);

  if (String(topic) != TOPIC_COMMAND) {
    return;
  }

  if (message == "STOP" || message == "EMERGENCY_STOP") {
    remoteEmergencyStop = true;
    Serial.println("REMOTE_COMMAND,STOP_ACCEPTED");
  } else if (message == "RELEASE_STOP" || message == "RESET_STOP") {
    // Retire seulement le STOP distant. Les dangers locaux gardent la priorite.
    remoteEmergencyStop = false;
    Serial.println("REMOTE_COMMAND,REMOTE_STOP_RELEASED");
  } else if (message == "STATUS") {
    statusPublishRequested = true;
  }
}

// 16. WIFI ET MQTT

void startWiFi() {
  WiFi.setHostname("hafida-safety-robot");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  lastWiFiAttemptTime = millis();
  Serial.println("WIFI,CONNECTING");
}

void maintainWiFi() {
  if (WiFi.status() == WL_CONNECTED) {
    if (!wifiConnectedAnnounced) {
      wifiConnectedAnnounced = true;
      Serial.print("WIFI,CONNECTED,IP=");
      Serial.print(WiFi.localIP());
      Serial.print(",RSSI=");
      Serial.println(WiFi.RSSI());
    }
    return;
  }

  wifiConnectedAnnounced = false;
  unsigned long now = millis();

  if (now - lastWiFiAttemptTime >= WIFI_RETRY_INTERVAL_MS) {
    lastWiFiAttemptTime = now;
    Serial.println("WIFI,RETRY");
    WiFi.disconnect();
    WiFi.begin(ssid, password);
  }
}

void connectMQTT() {
  if (WiFi.status() != WL_CONNECTED || mqtt.connected()) {
    return;
  }

  unsigned long now = millis();

  if (now - lastMqttAttemptTime < MQTT_RETRY_INTERVAL_MS) {
    return;
  }

  lastMqttAttemptTime = now;

  uint64_t mac = ESP.getEfuseMac();
  char clientId[48];

  snprintf(clientId, sizeof(clientId), "hafida-robot-%04X%08X",
           (uint16_t)(mac >> 32), (uint32_t)mac);

  Serial.print("MQTT,CONNECTING,CLIENT=");
  Serial.println(clientId);

  if (mqtt.connect(clientId, mqttUser, mqttPass)) {
    Serial.println("MQTT,CONNECTED");
    mqtt.subscribe(TOPIC_COMMAND);
    statusPublishRequested = true;
  } else {
    Serial.print("MQTT,CONNECT_FAILED,STATE=");
    Serial.println(mqtt.state());
  }
}

void maintainMQTT() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (!mqtt.connected()) {
    connectMQTT();
    return;
  }

  mqtt.loop();
}

// 17. SETUP

void setup() {
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("===================================================");
  Serial.println(" SMART ROBOT SAFETY CONTROLLER + MQTT DIGITAL TWIN");
  Serial.println("===================================================");

  analogReadResolution(12);

  pinMode(PIN_IR, INPUT_PULLUP);
  pinMode(PIN_POT, INPUT);
  pinMode(PIN_STOP_BUTTON, INPUT);

  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_ORANGE, OUTPUT);
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_RELAY_1, OUTPUT);
  pinMode(PIN_RELAY_2, OUTPUT);

  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_ORANGE, LOW);
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_BUZZER, LOW);
  setRelays(false);

  display.setBrightness(7);
  display.clear();

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);

  sensors.mpuAvailable = mpu.begin();
  Serial.println(sensors.mpuAvailable ? "MPU_STATUS,OK"
                                      : "MPU_STATUS,NOT_FOUND");

  sensors.bmeAvailable = bme.begin(0x76);
  if (!sensors.bmeAvailable) {
    sensors.bmeAvailable = bme.begin(0x77);
  }
  Serial.println(sensors.bmeAvailable ? "BME280_STATUS,OK"
                                      : "BME280_STATUS,NOT_FOUND");

  /*
    Connexion MQTT TLS de test :
    setInsecure() permet une connexion chiffree sans verifier le certificat.
    Pour la version finale, utiliser secureClient.setCACert(...).
  */
  secureClient.setInsecure();

  mqtt.setServer(mqttHost, mqttPort);
  mqtt.setCallback(mqttCallback);
  mqtt.setBufferSize(768);
  mqtt.setKeepAlive(30);

  startWiFi();
}

// 18. LOOP PRINCIPALE

void loop() {
  // La securite locale fonctionne meme sans connexion MQTT.
  lireCapteurs();
  filtrerMesures();
  currentState = deciderEtat();
  appliquerSorties(currentState);

  maintainWiFi();
  maintainMQTT();

  if (mqtt.connected()) {
    unsigned long now = millis();

    if (statusPublishRequested ||
        now - lastTelemetryPublishTime >= MQTT_TELEMETRY_INTERVAL_MS) {
      lastTelemetryPublishTime = now;
      statusPublishRequested = false;
      publishTelemetry();
    }
  }

  delay(20);
}