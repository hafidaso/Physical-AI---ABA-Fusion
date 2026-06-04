#include <Arduino.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <Wire.h>

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

LiquidCrystal_I2C lcd(0x27, 16, 2);

const char *TOPIC_TELEMETRY = "hafida/robot/twin2/telemetry";
const char *DEVICE_ID = "hafida-smart-robot-safety-2";

byte heart[8] = {
  0b00000,
  0b01010,
  0b11111,
  0b11111,
  0b11111,
  0b01110,
  0b00100,
  0b00000
};
byte battery[8] = {
  0b01110,
  0b11111,
  0b10001,
  0b10001,
  0b11111,
  0b11111,
  0b11111,
  0b11111
};
byte robot[8] = {
  0b00000,
  0b01010,
  0b11111,
  0b01110,
  0b11111,
  0b10101,
  0b01010,
  0b00000
};
byte hazard[8] = {
  0b00100,
  0b01110,
  0b01110,
  0b11011,
  0b11011,
  0b11111,
  0b11111,
  0b00000
};

String currentCommand = "STOP";
int robotSpeed = 50;
int robotTurnSpeed = 255;

int currentM1 = 0, currentM2 = 0, currentM3 = 0, currentM4 = 0;
int lastSpeed = 999;
float lastDistance = -999.0;

const int BATTERY_1_LEVEL = 80;
const int BATTERY_2_LEVEL = 100;

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
float lastValidDistance = -1.0;
bool wasObstacle = false;

unsigned long lastDistanceTime = 0;
unsigned long lastSerialTime = 0;
unsigned long lastLcdTime = 0;

const unsigned long DISTANCE_INTERVAL = 60;
const unsigned long TELEMETRY_INTERVAL = 200;
const unsigned long LCD_INTERVAL = 250;

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

    bool actualDir = INVERT_M1 ? !dir : dir;

    digitalWrite(BIN1_1, actualDir);
    digitalWrite(BIN2_1, !actualDir);
    analogWrite(PWMB1, pwmValue);

  } else if (motorIndex == 2) {
    currentM2 = speed;

    bool actualDir = INVERT_M2 ? !dir : dir;

    digitalWrite(BIN1_2, actualDir);
    digitalWrite(BIN2_2, !actualDir);
    analogWrite(PWMB2, pwmValue);

  } else if (motorIndex == 3) {
    currentM3 = speed;

    bool actualDir = INVERT_M3 ? !dir : dir;

    digitalWrite(AIN1_3, actualDir);
    digitalWrite(AIN2_3, !actualDir);
    analogWrite(PWMA3, pwmValue);

  } else if (motorIndex == 4) {
    currentM4 = speed;

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
  for (int i = 0; i < 2; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 10000);
    if (duration > 0) {
      float distance = (duration * 0.0343) / 2.0;
      lastValidDistance = distance;
      return distance;
    }
    delayMicroseconds(200);
  }
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

  if (currentM1 > 0) setMotor(1, 0);
  if (currentM2 > 0) setMotor(2, 0);
  if (currentM3 > 0) setMotor(3, 0);
  if (currentM4 > 0) setMotor(4, 0);
}

void updateLCD(int speed, float distance, int batteryVal) {
  char line1[17];
  char line2[17];

  char statusChar = ' ';
  if (isObstacleTooClose()) {
    statusChar = (millis() / 250 % 2 == 0) ? (char)3 : ' '; // Blinking warning icon
  } else {
    statusChar = (millis() / 500 % 2 == 0) ? (char)0 : ' '; // Heartbeat blink icon
  }

  // Formatting Line 1: [RobotIcon] Spd:XXXX [BatteryIcon]XXX%
  sprintf(line1, "%c Spd:%-4d %c%3d%%", (char)2, speed, (char)1, batteryVal);

  // Formatting Line 2: [Heart/Warning] Dist: X cm
  if (distance > 900.0) {
    sprintf(line2, "%c Dist: CLEAR    ", statusChar);
  } else {
    sprintf(line2, "%c Dist: %-5.1f cm  ", statusChar, distance);
  }

  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
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
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();

  // Create custom character sets
  lcd.createChar(0, heart);
  lcd.createChar(1, battery);
  lcd.createChar(2, robot);
  lcd.createChar(3, hazard);

  // Booting animation sequence
  lcd.setCursor(0, 0);
  lcd.print("Booting AGV OS ");
  lcd.write(2); // robot icon
  for (int i = 0; i < 16; i++) {
    lcd.setCursor(i, 1);
    lcd.write(255); // Solid block loading bar segment
    delay(60);
  }
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Active! ");
  lcd.write(0); // heart icon
  delay(500);
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
    applySafetyStop();
    lastDistanceTime = now;
  }

  if (now - lastSerialTime >= TELEMETRY_INTERVAL) {
    sendTelemetry(latestDistance);
    lastSerialTime = now;
  }

  if (now - lastLcdTime >= LCD_INTERVAL) {
    int activeSpeed = 0;
    if (currentCommand == "FORWARD" || currentCommand == "BACKWARD") {
      activeSpeed = robotSpeed;
    } else if (currentCommand == "LEFT" || currentCommand == "RIGHT") {
      activeSpeed = robotTurnSpeed;
    }
    updateLCD(activeSpeed, latestDistance, BATTERY_1_LEVEL);
    lastLcdTime = now;
  }

  moveRobot(currentCommand);
}