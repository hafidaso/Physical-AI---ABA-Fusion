#include <Arduino.h>

#include <WiFi.h>

#include <WiFiClientSecure.h>

#include <PubSubClient.h>

// --- Configuration Wi-Fi ---

const char *ssid = "x";

const char *password = "12345678900";

// --- Configuration MQTT (HiveMQ Cloud) ---

const char *mqttHost = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";

const int mqttPort = 8883;

const char *mqttUser = "hivemq.webclient.1775653497883";

const char *mqttPass = "1B%.CwaP:Kdr2I93k*Ap";

const char *mqttTopic = "robot/control";

WiFiClientSecure espClient;

PubSubClient client(espClient);

String currentCommand = "STOP";
int robotSpeed = 50;
int robotTurnSpeed = 255;

// --- Capteur de distance HC-SR04 ---

const int TRIG_PIN = 33;

const int ECHO_PIN = 34;

// --- Configuration des Moteurs ---

const int PWMB1 = 25;
const int BIN2_1 = 26;
const int BIN1_1 = 27;

const int PWMA3 = 13;
const int AIN2_3 = 14;
const int AIN1_3 = 19;

const int PWMB2 = 16;
const int BIN2_2 = 17;
const int BIN1_2 = 18;

const int PWMA4 = 32;
const int AIN2_4 = 4;
const int AIN1_4 = 23;

// LOGIQUE CORRIGÉE : Kamlin rj3naom True bach l-itijahyt yjiw m9addin m3a
// l-kifay

const bool INVERT_M1 = true; // Gauche Avant

const bool INVERT_M2 = true; // Droite Arrière

const bool INVERT_M3 = true; // Gauche Arrière

const bool INVERT_M4 = true; // Droite Avant

const float SAFETY_STOP_CM = 20.0;

float latestDistance = -1.0;

unsigned long lastDistanceTime = 0;

const unsigned long DISTANCE_INTERVAL = 60;

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

void moveRobot(String command) {

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
}

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

    if (client.connect(clientId.c_str(), mqttUser, mqttPass)) {

      client.subscribe(mqttTopic);

    } else {

      delay(5000);
    }
  }
}

void setup() {

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

  espClient.setInsecure();

  client.setServer(mqttHost, mqttPort);

  client.setCallback(callback);
}

void loop() {

  if (!client.connected()) {
    reconnect();
  }

  client.loop();

  unsigned long now = millis();

  if (now - lastDistanceTime >= DISTANCE_INTERVAL) {

    latestDistance = readDistanceCM();

    lastDistanceTime = now;
  }

  moveRobot(currentCommand);
}