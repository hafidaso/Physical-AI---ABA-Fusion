#include <Arduino.h>
#include <LiquidCrystal_I2C.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>

// --- إعدادات شبكة Wi-Fi و MQTT ---
const char *ssid = "IDS SALE";
const char *password = "IDS@2023";

const char *mqttHost = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";
const int mqttPort = 8883;
const char *mqttUser = "hivemq.webclient.1775653497883";
const char *mqttPass = "1B%.CwaP:Kdr2I93k*Ap";

const char *TOPIC_TELEMETRY = "hafida/robot/twin2/telemetry";
const char *TOPIC_COMMAND = "hafida/robot/twin2/command";
const char *DEVICE_ID = "hafida-smart-robot-safety-2";

WiFiClientSecure espClient;
PubSubClient client(espClient);

// Configuration de l'ecran I2C (SDA=21, SCL=22)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// --- Capteur de distance HC-SR04 ---
const int TRIG_PIN = 33;
const int ECHO_PIN = 34; // Input Only

// --- Pilote moteur 1 ---
const int PWMB1 = 25;
const int BIN2_1 = 26;
const int BIN1_1 = 27;

const int PWMA3 = 13;
const int AIN2_3 = 14;
const int AIN1_3 = 19;

// --- Pilote moteur 2 ---
const int PWMB2 = 16;
const int BIN2_2 = 17;
const int BIN1_2 = 18;

const int PWMA4 = 32;
const int AIN2_4 = 4;
const int AIN1_4 = 23;

// Niveaux de batterie
const int BATTERY_1_LEVEL = 80;
const int BATTERY_2_LEVEL = 100;

int currentM1 = 0, currentM2 = 0, currentM3 = 0, currentM4 = 0;
int lastSpeed = 999;
float lastDistance = -999.0;

// Gestion du timing
unsigned long lastSerialTime = 0;
unsigned long lastReconnectAttempt = 0;
unsigned long lastDistanceTime = 0;
unsigned long lastLcdTime = 0;
unsigned long lastCommandTime = 0; // Watchdog pour surveiller les commandes de Python

// Envoi de la télémétrie très fréquemment (200ms) pour réduire la latence avec le Dashboard 3D
const unsigned long TELEMETRY_INTERVAL = 200;
const unsigned long DISTANCE_INTERVAL = 60;
const unsigned long LCD_INTERVAL = 250;
const unsigned long WATCHDOG_TIMEOUT = 1500; // Si aucun ordre reçu en 1.5s, arrêt d'urgence.
const float SAFETY_STOP_CM = 20.0;
float latestDistance = -1.0;
float lastValidDistance = -1.0;
bool wasObstacle = false;

// Variable pour stocker les données provenant du Serial sans bloquer le processeur
String serialBuffer = "";

void sendTelemetry(float distance);

bool isObstacleTooClose() {
  return latestDistance > 0.0 && latestDistance <= SAFETY_STOP_CM;
}

void setMotor(int motorIndex, int speed) {
  if (speed > 0 && isObstacleTooClose()) {
    speed = 0;
  }

  bool dir = (speed >= 0) ? HIGH : LOW;
  int pwmValue = constrain(abs(speed), 0, 255);

  if (motorIndex == 1) {
    currentM1 = speed;
    digitalWrite(BIN1_1, dir);
    digitalWrite(BIN2_1, !dir);
    analogWrite(PWMB1, pwmValue);
  } else if (motorIndex == 2) {
    currentM2 = speed;
    digitalWrite(BIN1_2, dir);
    digitalWrite(BIN2_2, !dir);
    analogWrite(PWMB2, pwmValue);
  } else if (motorIndex == 3) {
    currentM3 = speed;
    digitalWrite(AIN1_3, dir);
    digitalWrite(AIN2_3, !dir);
    analogWrite(PWMA3, pwmValue);
  } else if (motorIndex == 4) {
    currentM4 = speed;
    digitalWrite(AIN1_4, dir);
    digitalWrite(AIN2_4, !dir);
    analogWrite(PWMA4, pwmValue);
  }
}

void applySafetyStop() {
  bool currentlyClose = isObstacleTooClose();

  if (currentlyClose && !wasObstacle) {
    sendTelemetry(latestDistance);
    lastSerialTime = millis();
    wasObstacle = true;
  } else if (!currentlyClose && wasObstacle) {
    sendTelemetry(latestDistance);
    lastSerialTime = millis();
    wasObstacle = false;
  }

  if (!currentlyClose) {
    return;
  }

  if (currentM1 > 0 || currentM2 > 0 || currentM3 > 0 || currentM4 > 0) {
    Serial.print("!!! EMERGENCY STOP: Distance = ");
    Serial.print(latestDistance);
    Serial.println(" cm !!!");
  }

  if (currentM1 > 0)
    setMotor(1, 0);
  if (currentM2 > 0)
    setMotor(2, 0);
  if (currentM3 > 0)
    setMotor(3, 0);
  if (currentM4 > 0)
    setMotor(4, 0);
}

void updateLCD(int speed, float distance, int battery) {
  if (speed != lastSpeed || abs(distance - lastDistance) > 0.5) {
    char line1[17];
    char line2[17];
    sprintf(line1, "Spd:%-4d Bat:%d%%  ", speed, battery);
    sprintf(line2, "Dist: %-5.1f cm  ", distance);

    lcd.setCursor(0, 0);
    lcd.print(line1);
    lcd.setCursor(0, 1);
    lcd.print(line2);

    lastSpeed = speed;
    lastDistance = distance;
  }
}

void mqttCallback(char *topic, byte *payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  message.trim();

  Serial.print("[MQTT RX] ");
  Serial.print(topic);
  Serial.print(" -> ");
  Serial.println(message);

  if (message.startsWith("{")) {
    return;
  }

  int m1 = 0, m2 = 0, m3 = 0, m4 = 0;
  if (sscanf(message.c_str(), "%d,%d,%d,%d", &m1, &m2, &m3, &m4) == 4) {
    setMotor(1, m1);
    setMotor(2, m2);
    setMotor(3, m3);
    setMotor(4, m4);
    lastCommandTime = millis(); // Reset du Watchdog
    Serial.printf("[CMD] Motors -> M1:%d M2:%d M3:%d M4:%d\n", m1, m2, m3, m4);
  }
}

// Fonction de connexion non bloquante (Non-blocking WiFi & MQTT)
void connectToWiFiAndMQTT() {
  // 1. Si le WiFi n'est pas connecté, on quitte immédiatement et on laisse l'ESP32 tenter de se connecter en arrière-plan
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  // 2. Si le WiFi est connecté mais que le MQTT est déconnecté, on tente de se connecter au serveur
  if (WiFi.status() == WL_CONNECTED && !client.connected()) {
    if (client.connect(DEVICE_ID, mqttUser, mqttPass)) {
      client.subscribe(TOPIC_COMMAND); // Inscription aux commandes uniquement
      Serial.println("[MQTT] Connecté !");
    } else {
      Serial.print("[MQTT] Échec, code erreur: ");
      Serial.println(client.state());
    }
  }
}

float readDistanceCM() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    // 10000us couvrent environ 1.7 mètres. C'est amplement suffisant pour l'évitement de collision (20cm)
    // et cela évite de bloquer la boucle `loop()` trop longtemps, ce qui accélére la réception MQTT.
    long duration = pulseIn(ECHO_PIN, HIGH, 10000);
    if (duration > 0) {
      float distance = (duration * 0.0343) / 2.0;
      lastValidDistance = distance;
      return distance;
    }
    delayMicroseconds(200);
  }

  // Si aucun écho ne revient, on considère que la voie est libre et qu'il n'y a pas d'obstacle devant le capteur.
  lastValidDistance = 999.0;
  return 999.0;
}

void sendTelemetry(float distance) {
  Serial.println("--- AGV TELEMETRY ---");
  if (distance < 0) {
    Serial.println("Distance: 0 cm (Hors de portée awla mochkil)");
  } else {
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");
  }
  Serial.printf("Motors   | M1: %d | M2: %d | M3: %d | M4: %d\n", currentM1,
                currentM2, currentM3, currentM4);
  Serial.printf("Battery  | BAT1: %d%% | BAT2: %d%%\n", BATTERY_1_LEVEL,
                BATTERY_2_LEVEL);
  Serial.println("---------------------\n");

  if (client.connected()) {
    char mqttPayload[200];
    snprintf(mqttPayload, sizeof(mqttPayload),
             "{\"device\":\"%s\",\"distance\":%.1f,\"motors\":[%d,%d,%d,%d],"
             "\"battery\":[%d,%d]}",
             DEVICE_ID, (distance < 0 ? 0.0 : distance), currentM1, currentM2,
             currentM3, currentM4, BATTERY_1_LEVEL, BATTERY_2_LEVEL);

    client.publish(TOPIC_TELEMETRY, mqttPayload);
  }
}

void setup() {
  Serial.begin(115200);

  espClient.setInsecure();
  client.setServer(mqttHost, mqttPort);
  client.setCallback(mqttCallback);

  // Configuration du KeepAlive pour empêcher le serveur de couper la connexion soudainement
  client.setKeepAlive(60);
  client.setSocketTimeout(1);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("AGV ESP32 Ready");
  delay(1000);
  lcd.clear();

  pinMode(PWMB1, OUTPUT);
  pinMode(BIN2_1, OUTPUT);
  pinMode(BIN1_1, OUTPUT);
  pinMode(AIN1_3, OUTPUT);
  pinMode(AIN2_3, OUTPUT);
  pinMode(PWMA3, OUTPUT);
  pinMode(PWMB2, OUTPUT);
  pinMode(BIN2_2, OUTPUT);
  pinMode(BIN1_2, OUTPUT);
  pinMode(AIN1_4, OUTPUT);
  pinMode(AIN2_4, OUTPUT);
  pinMode(PWMA4, OUTPUT);

  setMotor(1, 0);
  setMotor(2, 0);
  setMotor(3, 0);
  setMotor(4, 0);

  // Forcer la carte à fonctionner uniquement en tant que récepteur (Station)
  WiFi.mode(WIFI_STA);
  // Activer la gestion automatique de la connexion en arrière-plan
  WiFi.setAutoReconnect(true);
  // Empêcher la puce WiFi d'entrer en mode veille
  WiFi.setSleep(false);

  WiFi.begin(ssid, password);
}

void loop() {
  unsigned long now = millis();

  // Watchdog : Sécurité si le script Python crash ou le réseau fige
  if (now - lastCommandTime > WATCHDOG_TIMEOUT) {
    if (currentM1 != 0 || currentM2 != 0 || currentM3 != 0 || currentM4 != 0) {
      Serial.println("!!! WATCHDOG FAILSAFE: Aucun ordre depuis 1.5s. ARRET !!!");
      setMotor(1, 0); setMotor(2, 0); setMotor(3, 0); setMotor(4, 0);
    }
  }

  // Tentative de connexion toutes les 5 secondes en cas de coupure, sans utiliser delay
  if (!client.connected()) {
    // Failsafe : Arrêt immédiat avant de bloquer le microcontrôleur sur la reconnexion
    if (currentM1 != 0 || currentM2 != 0 || currentM3 != 0 || currentM4 != 0) {
      Serial.println("!!! CONNECTION LOST: Arrêt de sécurité !!!");
      setMotor(1, 0); setMotor(2, 0); setMotor(3, 0); setMotor(4, 0);
    }

    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = millis();
      connectToWiFiAndMQTT();
    }
  } else {
    client.loop();
  }

  // Réception des commandes Serial de manière non bloquante (Non-blocking)
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      int m1 = 0, m2 = 0, m3 = 0, m4 = 0;
      if (sscanf(serialBuffer.c_str(), "%d,%d,%d,%d", &m1, &m2, &m3, &m4) ==
          4) {
        setMotor(1, m1);
        setMotor(2, m2);
        setMotor(3, m3);
        setMotor(4, m4);
        lastCommandTime = millis(); // Reset du Watchdog via Serial
      }
      serialBuffer = "";
    } else {
      serialBuffer += c;
    }
  }

  if (now - lastDistanceTime >= DISTANCE_INTERVAL) {
    latestDistance = readDistanceCM();
    applySafetyStop();
    lastDistanceTime = now;
  }

  if (now - lastSerialTime >= TELEMETRY_INTERVAL) {
    sendTelemetry(latestDistance);
    lastSerialTime = now;
  }

  if (now - lastLcdTime >= LCD_INTERVAL) {
    updateLCD(currentM1, latestDistance, BATTERY_1_LEVEL);
    lastLcdTime = now;
  }
}
