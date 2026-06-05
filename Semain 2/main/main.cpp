#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h> // Changed to WiFiClientSecure for HiveMQ Cloud
#include <Wire.h>

// --- Configuration Wi-Fi ---
const char *ssid = "x";
const char *password = "12345678900";

// --- Configuration MQTT (HiveMQ Cloud) ---
const char *mqttHost = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";
const int mqttPort = 8883;
const char *mqttUser = "hivemq.webclient.1775653497883";
const char *mqttPass = "1B%.CwaP:Kdr2I93k*Ap";

// MQTT Topics
const char *mqttTopicControl = "robot/control";
const char *mqttTopicDistance = "robot/distance";
const char *mqttTopicAngle = "robot/angle";
const char *mqttTopicTwin = "hafida/robot/twin/telemetry"; // For JSON telemetry

WiFiClientSecure espClient;
PubSubClient client(espClient);

// --- State Variables ---
String currentCommand = "STOP";
int robotSpeed = 150;
int robotTurnSpeed = 255;

// --- Precise Turn Variables ---
bool isTurningPrecise = false;
float turnTargetHeading = 0.0;
String turnDirection = "";

// --- Capteur de distance HC-SR04 ---
const int TRIG_PIN = 33;
const int ECHO_PIN = 34;
const float SAFETY_STOP_CM = 20.0;
float latestDistance = -1.0;
unsigned long lastDistanceTime = 0;
const unsigned long DISTANCE_INTERVAL = 60;

bool obstacleDetected = false;
bool bypassObstacle = false;
int obstacleCounter = 0;

unsigned long lastMqttPublishTime = 0;
const unsigned long MQTT_PUBLISH_INTERVAL = 250;

// --- Configuration MPU6050 (Motion Tracking) ---
Adafruit_MPU6050 mpu;
bool mpuFound = false;
float yaw = 0.0;
float targetHeading = 0.0;
float gyroBiasZ = 0.0;
unsigned long lastGyroTime = 0;
unsigned long stopStartTime = 0;
const float Kp = 3.5;

// Variable global pour traquer les erreurs I2C
int consecutiveI2CErrors = 0;

// --- Configuration des Moteurs (Pins ESP32) ---
const int PWMB1 = 25;
const int BIN2_1 = 26;
const int BIN1_1 = 27; // M1 (Gauche Avant)
const int PWMA3 = 13;
const int AIN2_3 = 14;
const int AIN1_3 = 19; // M3 (Gauche Arrière)
const int PWMB2 = 16;
const int BIN2_2 = 17;
const int BIN1_2 = 18; // M2 (Droite Arrière)
const int PWMA4 = 32;
const int AIN2_4 = 4;
const int AIN1_4 = 23; // M4 (Droite Avant)

// Logique inverseurs moteurs (Chassis direction calibration)
const bool INVERT_M1 = true;
const bool INVERT_M2 = true;
const bool INVERT_M3 = true;
const bool INVERT_M4 = true;

// --- Détecter si un obstacle est trop proche ---
bool isObstacleTooClose() {
  if (bypassObstacle)
    return false;
  return obstacleDetected;
}

// --- Contrôle Individuel des Moteurs ---
void setMotor(int motorIndex, int speed) {
  bool dir = (speed >= 0) ? HIGH : LOW;
  int pwmValue = constrain(abs(speed), 0, 255);

  if (motorIndex == 1) {
    bool actualDir = INVERT_M1 ? !dir : dir;
    digitalWrite(BIN1_1, actualDir);
    digitalWrite(BIN2_1, !actualDir);
    analogWrite(PWMB1, pwmValue);
  } else if (motorIndex == 2) {
    bool actualDir = INVERT_M2 ? !dir : dir;
    digitalWrite(BIN1_2, actualDir);
    digitalWrite(BIN2_2, !actualDir);
    analogWrite(PWMB2, pwmValue);
  } else if (motorIndex == 3) {
    bool actualDir = INVERT_M3 ? !dir : dir;
    digitalWrite(AIN1_3, actualDir);
    digitalWrite(AIN2_3, !actualDir);
    analogWrite(PWMA3, pwmValue);
  } else if (motorIndex == 4) {
    bool actualDir = INVERT_M4 ? !dir : dir;
    digitalWrite(AIN1_4, actualDir);
    digitalWrite(AIN2_4, !actualDir);
    analogWrite(PWMA4, pwmValue);
  }
}

// --- Réinitialisation HARDWARE forcée du bus I2C ---
void recoverI2CBus() {
  Serial.println("[⚠️] Hardware I2C Lock détecté ! Lancement d'une récupération "
                 "agressive...");

  Wire.end();
  delay(10);

  pinMode(21, OUTPUT); // SDA
  pinMode(22, OUTPUT); // SCL
  digitalWrite(21, HIGH);

  for (int i = 0; i < 16; i++) {
    digitalWrite(22, LOW);
    delayMicroseconds(10);
    digitalWrite(22, HIGH);
    delayMicroseconds(10);
  }

  digitalWrite(21, LOW);
  delayMicroseconds(10);
  digitalWrite(22, HIGH);
  delayMicroseconds(10);
  digitalWrite(21, HIGH);
  delayMicroseconds(10);

  Wire.begin(21, 22);
  Wire.setClock(100000);

  if (mpu.begin(0x69)) {
    Serial.println("[+] MPU6050 récupéré avec succès !");
    mpuFound = true;
  } else {
    Serial.println("[-] Récupération échouée. Mode Safe actif.");
    mpuFound = false;
  }
}

// --- Calcul de l'Angle Yaw (MPU6050) ---
void updateYaw() {
  if (!mpuFound)
    return;

  sensors_event_t a, g, temp;
  bool success = mpu.getEvent(&a, &g, &temp);

  unsigned long now = millis();
  float dt = (now - lastGyroTime) / 1000.0;
  lastGyroTime = now;

  if (!success) {
    consecutiveI2CErrors++;
    if (consecutiveI2CErrors > 5) {
      recoverI2CBus();
      consecutiveI2CErrors = 0;
    }
    return;
  } else {
    consecutiveI2CErrors = 0;
  }

  // --- BACKGROUND AUTO-CALIBRATION ---
  if (currentCommand == "STOP" && !isTurningPrecise) {
    if (stopStartTime == 0) {
      stopStartTime = now;
    } else if (now - stopStartTime > 800) {
      gyroBiasZ = (gyroBiasZ * 0.98) + (g.gyro.z * 0.02);
    }
  } else {
    stopStartTime = 0;
  }

  float gyroZ = (g.gyro.z - gyroBiasZ) * (180.0 / M_PI);
  if (abs(gyroZ) > 0.15) {
    yaw += gyroZ * dt;
  }
}

// --- Calibrer le MPU6050 ---
void calibrateGyro() {
  if (!mpuFound)
    return;
  float sum = 0;
  int samples = 200;
  for (int i = 0; i < samples; i++) {
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    sum += g.gyro.z;
    delay(10);
  }
  gyroBiasZ = sum / samples;
}

// --- Direction Globale ---
void moveRobot(String command) {

  // High-Level Safety Stop
  if (command == "FORWARD" && isObstacleTooClose()) {
    command = "STOP";
    static unsigned long lastLog = 0;
    if (millis() - lastLog > 1500) {
      Serial.println("[🚨 SAFETY STOP] FORWARD bloqué par obstacle. Recul et "
                     "rotations restent actifs !");
      lastLog = millis();
    }
  }

  if (!mpuFound) { // Fallback sans gyroscope
    if (command == "FORWARD") {
      setMotor(1, robotSpeed);
      setMotor(2, robotSpeed);
      setMotor(3, robotSpeed);
      setMotor(4, robotSpeed);
    } else if (command == "BACKWARD") {
      setMotor(1, -robotSpeed);
      setMotor(2, -robotSpeed);
      setMotor(3, -robotSpeed);
      setMotor(4, -robotSpeed);
    } else if (command == "LEFT") {
      setMotor(1, -robotTurnSpeed);
      setMotor(2, robotTurnSpeed);
      setMotor(3, -robotTurnSpeed);
      setMotor(4, robotTurnSpeed);
    } else if (command == "RIGHT") {
      setMotor(1, robotTurnSpeed);
      setMotor(2, -robotTurnSpeed);
      setMotor(3, robotTurnSpeed);
      setMotor(4, -robotTurnSpeed);
    } else {
      setMotor(1, 0);
      setMotor(2, 0);
      setMotor(3, 0);
      setMotor(4, 0);
    }
    return;
  }

  if (isTurningPrecise) {
    if (command == "FORWARD" || command == "BACKWARD" || command == "LEFT" ||
        command == "RIGHT") {
      isTurningPrecise = false;
      stopStartTime = 0;
    }
  }

  // Déclenchement des rotations automatiques précises
  if (!isTurningPrecise) {
    if (command == "TURN_90_L") {
      isTurningPrecise = true;
      yaw = 0.0;
      turnTargetHeading = 90.0;
      turnDirection = "LEFT";
    } else if (command == "TURN_90_R") {
      isTurningPrecise = true;
      yaw = 0.0;
      turnTargetHeading = -90.0;
      turnDirection = "RIGHT";
    } else if (command == "TURN_180") {
      isTurningPrecise = true;
      yaw = 0.0;
      turnTargetHeading = 180.0;
      turnDirection = "LEFT";
    }
  }

  // Asservissement de rotation
  if (isTurningPrecise) {
    float error = turnTargetHeading - yaw;
    if (abs(error) <= 1.5) {
      isTurningPrecise = false;
      currentCommand = "STOP";
      targetHeading = turnTargetHeading;
      setMotor(1, 0);
      setMotor(2, 0);
      setMotor(3, 0);
      setMotor(4, 0);
      return;
    }
    int dynamicTurnSpeed =
        constrain((int)(abs(error) * 4.0), 85, robotTurnSpeed);
    if (turnDirection == "LEFT") {
      setMotor(1, -dynamicTurnSpeed);
      setMotor(2, dynamicTurnSpeed);
      setMotor(3, -dynamicTurnSpeed);
      setMotor(4, dynamicTurnSpeed);
    } else {
      setMotor(1, dynamicTurnSpeed);
      setMotor(2, -dynamicTurnSpeed);
      setMotor(3, dynamicTurnSpeed);
      setMotor(4, -dynamicTurnSpeed);
    }
    return;
  }

  // Mode normal avec stabilisation Gyro
  float headingError = targetHeading - yaw;
  int correction = (int)(headingError * Kp);
  correction = constrain(correction, -100, 100);

  if (command == "FORWARD") {
    setMotor(1, robotSpeed - correction);
    setMotor(2, robotSpeed + correction);
    setMotor(3, robotSpeed - correction);
    setMotor(4, robotSpeed + correction);
  } else if (command == "BACKWARD") {
    setMotor(1, -robotSpeed - correction);
    setMotor(2, -robotSpeed + correction);
    setMotor(3, -robotSpeed - correction);
    setMotor(4, -robotSpeed + correction);
  } else if (command == "LEFT") {
    setMotor(1, -robotTurnSpeed);
    setMotor(2, robotTurnSpeed);
    setMotor(3, -robotTurnSpeed);
    setMotor(4, robotTurnSpeed);
    targetHeading = yaw;
  } else if (command == "RIGHT") {
    setMotor(1, robotTurnSpeed);
    setMotor(2, -robotTurnSpeed);
    setMotor(3, robotTurnSpeed);
    setMotor(4, -robotTurnSpeed);
    targetHeading = yaw;
  } else {
    setMotor(1, 0);
    setMotor(2, 0);
    setMotor(3, 0);
    setMotor(4, 0);
    targetHeading = yaw;
  }
}

// --- Lecture du Capteur HC-SR04 ---
float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 10000);
  if (duration > 0)
    return (duration * 0.0343) / 2.0;
  return 999.0;
}

// --- Callback MQTT ---
void callback(char *topic, byte *payload, unsigned int length) {
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  message.trim();

  if (message.startsWith("SPEED:")) {
    int newSpeed = message.substring(6).toInt();
    if (newSpeed >= 0 && newSpeed <= 255) {
      robotSpeed = newSpeed;
    }
  } else if (message == "BYPASS:ON") {
    bypassObstacle = true;
    Serial.println("[🛡️] Obstacle avoidance BYPASSED (Disabled).");
  } else if (message == "BYPASS:OFF") {
    bypassObstacle = false;
    Serial.println("[🛡️] Obstacle avoidance ACTIVATED (Enabled).");
  } else {
    currentCommand = message;
  }
}

void setup_wifi() {
  delay(10);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void reconnect() {
  while (!client.connected()) {
    String clientId = "ESP32Client-" + String(random(0, 0xffff), HEX);
    Serial.println("Tentative de connexion MQTT...");
    if (client.connect(clientId.c_str(), mqttUser, mqttPass)) {
      client.subscribe(mqttTopicControl);
      Serial.println("[+] Connecté à HiveMQ Cloud !");
    } else {
      Serial.print("[-] Erreur de connexion MQTT. Code: ");
      Serial.println(client.state());
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  // Initialisation I2C standard
  Wire.begin(21, 22);
  Wire.setClock(100000);

  if (!mpu.begin(0x69)) {
    Serial.println(
        "[-] MPU6050 non trouvé à l'adresse 0x69! Safe Mode (No IMU).");
    mpuFound = false;
  } else {
    Serial.println("[+] MPU6050 trouvé avec succès à l'adresse 0x69!");
    mpuFound = true;
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
    calibrateGyro();
  }

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
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

  moveRobot("STOP");
  setup_wifi();

  espClient.setInsecure(); // Trust HiveMQ without certificate validation
  client.setServer(mqttHost, mqttPort);
  client.setCallback(callback);
  lastGyroTime = millis();
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  updateYaw();
  unsigned long now = millis();

  // 1. Lecture du capteur de distance
  if (now - lastDistanceTime >= DISTANCE_INTERVAL) {
    latestDistance = readDistanceCM();
    lastDistanceTime = now;

    if (latestDistance >= 3.0 && latestDistance <= SAFETY_STOP_CM) {
      obstacleCounter++;
      if (obstacleCounter >= 3) {
        obstacleDetected = true;
        Serial.printf(
            "[🚨 STOP] Obstacle détecté à %.1f cm ! Arrêt moteurs activé.\n",
            latestDistance);
      }
    } else {
      obstacleCounter = 0;
      obstacleDetected = false;
    }
  }

  if (now - lastMqttPublishTime >= MQTT_PUBLISH_INTERVAL) {
    if (client.connected()) {
      // 1. Publish simple strings for the Frontend (Dashboard)
      String distStr = String(latestDistance, 1);
      client.publish(mqttTopicDistance, distStr.c_str());
      if (mpuFound) {
        String angleStr = String(yaw, 1);
        client.publish(mqttTopicAngle, angleStr.c_str());
      }

      // 2. Publish JSON for the Backend (Digital Twin 3D)
      String jsonPayload =
          "{\"device\":\"hafida-smart-robot-safety-2\",\"distance\":" +
          String(latestDistance, 1);
      if (mpuFound) {
        jsonPayload += ",\"yaw\":" + String(yaw, 1);
      }
      jsonPayload += "}";
      client.publish(mqttTopicTwin, jsonPayload.c_str());
    }
    lastMqttPublishTime = now;
  }

  moveRobot(currentCommand);
}