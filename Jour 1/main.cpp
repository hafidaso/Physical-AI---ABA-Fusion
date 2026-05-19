#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>

// WiFi credentials
const char *ssid = "Fibre_inwi_2.4G_D7EB";
const char *password = "CCB071B34340";

// MQTT HiveMQ Cloud

const char *mqttHost = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";
const int mqttPort = 8883;
const char *mqttUser = "hivemq.webclient.1775653497883";
const char *mqttPass = "1B%.CwaP:Kdr2I93k*Ap";

const char *TOPIC_TELEMETRY = "hafida/robot/twin/telemetry";
const char *TOPIC_COMMAND = "hafida/robot/twin/command";
const char *TOPIC_CONFIG = "hafida/robot/twin/config";
const char *TOPIC_LOG = "hafida/robot/twin/log";

// MQTT client setup

WiFiClientSecure secureClient;
PubSubClient mqtt(secureClient);

// PINS - Maker Point Board

#define INFRARED_PIN 4 
#define POT_PIN 35     

#define BUTTON_PIN 34 
#define LED_GREEN 32  
#define LED_RED 33    
#define BUZZER 26    
#define BUTTON1_PIN BUTTON_PIN
#define BUTTON2_PIN 14 

#define LED1_PIN LED_GREEN
#define LED2_PIN LED_RED

#define RELAY1_PIN 25 
#define RELAY2_PIN 27

#define BUZZER_PIN BUZZER

// CONFIGURATION

// DEMO MODE - QUIET ATELIER VERSION
// The potentiometer simulates distance_cm.
// STOP is triggered by distance_cm < threshold or by MQTT/authorized emergency
// command. IR is used as a person/near-object signal for SLOW MODE only.
// Your board showed: hand/object present -> IR=1, no object -> IR=0.
// Therefore IR_ACTIVE_LOW must be false.
#define USE_IR_AS_OBSTACLE false
#define IR_ACTIVE_LOW false
#define USE_INTERNAL_PULLUP_FOR_IR true

// The physical button on GPIO34 can float if there is no external pull-up/down
// resistor. Keep it disabled for a stable demo. Use MQTT/Python RUN/STOP

#define USE_BUTTON_EMERGENCY false

struct Config {
  int distanceThreshold = 15;
  int telemetryInterval = 500;
  bool debugMode = true;
};

Config config;

// VARIABLES

volatile bool emergencyStop = false;
volatile bool systemHealthy = true;

// Buzzer is muted by default because the continuous alarm is noisy during the
// demo. Send BUZZER:ON or BUZZER:UNMUTE by MQTT if you want to enable short
// alert beeps.
volatile bool buzzerEnabled = false;

int infraredValue = 1;
int distanceCm = 50;

String robotState = "NORMAL";
String ledState = "GREEN";
String lastError = "NONE";

unsigned long lastTelemetrySent = 0;
unsigned long lastMqttPing = 0;
unsigned long lastWifiCheck = 0;

// LOGGING SYSTEM

void systemLog(String level, String message) {
  String timestamp = String(millis());
  String logMsg = "[" + timestamp + "] [" + level + "] " + message;

  Serial.println(logMsg);

  if (mqtt.connected() && config.debugMode) {
    mqtt.publish(TOPIC_LOG, logMsg.c_str());
  }
}

// WiFi CONNECTION

void connectWiFi() {
  systemLog("INFO", "Attempting WiFi connection to: " + String(ssid));

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    systemLog("INFO", "WiFi connected! IP: " + WiFi.localIP().toString());
    systemHealthy = true;
  } else {
    systemLog("ERROR", "WiFi connection failed!");
    systemHealthy = false;
  }
}

// MQTT CALLBACK

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) {
    msg += (char)payload[i];
  }
  msg.trim();

  String topicStr = String(topic);
  systemLog("MQTT_RX", topicStr + " -> " + msg);

  // Command handling
  if (topicStr == TOPIC_COMMAND) {
    if (msg == "STOP") {
      emergencyStop = true;
      systemLog("WARN", "Emergency STOP received");
    } else if (msg == "RUN") {
      emergencyStop = false;
      systemLog("INFO", "RUN command received");
    } else if (msg == "RELAY1:ON") {
      digitalWrite(RELAY1_PIN, HIGH);
      systemLog("INFO", "Relay 1 ON");
    } else if (msg == "RELAY1:OFF") {
      digitalWrite(RELAY1_PIN, LOW);
      systemLog("INFO", "Relay 1 OFF");
    } else if (msg == "RELAY2:ON") {
      digitalWrite(RELAY2_PIN, HIGH);
      systemLog("INFO", "Relay 2 ON");
    } else if (msg == "RELAY2:OFF") {
      digitalWrite(RELAY2_PIN, LOW);
      systemLog("INFO", "Relay 2 OFF");
    } else if (msg == "BUZZER:ON" || msg == "BUZZER:UNMUTE") {
      buzzerEnabled = true;
      systemLog("INFO", "Buzzer alerts enabled");
    } else if (msg == "BUZZER:OFF" || msg == "BUZZER:MUTE") {
      buzzerEnabled = false;
      digitalWrite(BUZZER_PIN, LOW);
      systemLog("INFO", "Buzzer muted");
    } else if (msg.startsWith("DEBUG:")) {
      config.debugMode = (msg.substring(6) == "ON");
      systemLog("INFO",
                "Debug mode: " + String(config.debugMode ? "ON" : "OFF"));
    }
  }

  // Config handling
  else if (topicStr == TOPIC_CONFIG) {
    if (msg == "RESET") {
      systemLog("WARN", "System reset triggered!");
      delay(500);
      ESP.restart();
    }
  }
}

// MQTT CONNECT

void connectMQTT() {
  static int retryCount = 0;

  if (mqtt.connected())
    return;

  if (WiFi.status() != WL_CONNECTED) {
    systemLog("ERROR", "WiFi not connected, cannot connect MQTT");
    return;
  }

  Serial.print("Connecting MQTT...");
  String clientId = "ESP32-robot-" + String(random(10000, 99999));

  if (mqtt.connect(clientId.c_str(), mqttUser, mqttPass)) {
    systemLog("INFO", "MQTT connected! Client: " + clientId);
    mqtt.subscribe(TOPIC_COMMAND);
    mqtt.subscribe(TOPIC_CONFIG);
    retryCount = 0;
  } else {
    retryCount++;
    systemLog("ERROR", "MQTT failed (attempt " + String(retryCount) +
                           "), rc=" + String(mqtt.state()));

    if (retryCount > 5) {
      systemHealthy = false;
      systemLog("CRITICAL", "MQTT connection failed after 5 attempts!");
    }
  }
}

// RELAY CONTROL

bool shortBeep(unsigned long onMs, unsigned long cycleMs) {
  if (!buzzerEnabled)
    return false;
  return (millis() % cycleMs) < onMs;
}

void setRelays() {
  bool buzzerShouldBeOn = false;

  if (robotState == "STOP" || emergencyStop) {
    // Safety stop: actuators OFF.
    digitalWrite(RELAY1_PIN, LOW);
    digitalWrite(RELAY2_PIN, LOW);

    // Quiet demo: only a short beep if buzzerEnabled is true.
    buzzerShouldBeOn = shortBeep(120, 1800);
  } else if (robotState == "WARNING") {
    // Warning is not a full stop. Keep relays ON so the virtual robot can still
    // move slowly.
    digitalWrite(RELAY1_PIN, HIGH);
    digitalWrite(RELAY2_PIN, HIGH);

    // Very short warning beep if buzzerEnabled is true.
    buzzerShouldBeOn = shortBeep(80, 1500);
  } else {
    digitalWrite(RELAY1_PIN, HIGH);
    digitalWrite(RELAY2_PIN, HIGH);
    buzzerShouldBeOn = false;
  }

  digitalWrite(BUZZER_PIN, buzzerShouldBeOn ? HIGH : LOW);
}

// SENSOR TASK

void sensorTask(void *parameter) {
  while (true) {
    // Read infrared sensor
    infraredValue = digitalRead(INFRARED_PIN);

    // Read potentiometer for distance simulation
    int analogValue = analogRead(POT_PIN);
    distanceCm = map(analogValue, 0, 4095, 3, 50);

    // State machine
    // Priority: emergency stop > distance obstacle > line warning > normal
    bool distanceObstacle = distanceCm < config.distanceThreshold;

#if USE_IR_AS_OBSTACLE
    bool irObstacle =
        IR_ACTIVE_LOW ? (infraredValue == LOW) : (infraredValue == HIGH);
#else
    bool irObstacle = false;
#endif

    // IR warning logic:
    // If the sensor detects a hand/person/object, the robot does NOT stop.
    // It enters WARNING/SLOW mode.
    // On this board: IR=1 means object/person detected.
    bool personDetected =
        IR_ACTIVE_LOW ? (infraredValue == LOW) : (infraredValue == HIGH);

    if (emergencyStop) {
      robotState = "STOP";
      ledState = "RED";
      lastError = "EMERGENCY_STOP";
    } else if (distanceObstacle) {
      robotState = "STOP";
      ledState = "RED";
      lastError = "DISTANCE_OBSTACLE";
    } else if (irObstacle) {
      robotState = "STOP";
      ledState = "RED";
      lastError = "IR_OBSTACLE_DETECTED";
    } else if (personDetected) {
      robotState = "WARNING";
      ledState = "YELLOW";
      lastError = "PERSON_DETECTED_SLOW_MODE";
    } else {
      robotState = "NORMAL";
      ledState = "GREEN";
      lastError = "NONE";
    }

    static unsigned long lastSensorDebug = 0;
    if (config.debugMode && millis() - lastSensorDebug > 1000) {
      Serial.println("SENSOR_DEBUG: IR=" + String(infraredValue) +
                     " | person_detected=" + String(personDetected ? "YES" : "NO") +
                     " | distance_cm=" + String(distanceCm) +
                     " | state=" + robotState + " | error=" + lastError);
      lastSensorDebug = millis();
    }

    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// ACTUATOR TASK (LEDs + Relays)

void actuatorTask(void *parameter) {
  unsigned long lastBlink = 0;
  bool blinkState = false;

  while (true) {
    // LED Control with blinking for warnings
    if (robotState == "STOP") {
      digitalWrite(LED1_PIN, LOW);
      digitalWrite(LED2_PIN, HIGH);
    } else if (robotState == "WARNING") {
      digitalWrite(LED1_PIN, LOW);

      if (millis() - lastBlink > 250) {
        blinkState = !blinkState;
        lastBlink = millis();
      }
      digitalWrite(LED2_PIN, blinkState ? HIGH : LOW);
    } else {
      digitalWrite(LED1_PIN, HIGH);
      digitalWrite(LED2_PIN, LOW);
    }

    // Control relays
    setRelays();

    vTaskDelay(20 / portTICK_PERIOD_MS);
  }
}

// BUTTON TASK

void buttonTask(void *parameter) {
  int lastState1 = HIGH;
  int lastState2 = HIGH;
  unsigned long lastPressTime = 0;

  while (true) {
#if USE_BUTTON_EMERGENCY
    int currentState1 = digitalRead(BUTTON1_PIN);
    int currentState2 = digitalRead(BUTTON2_PIN);

    // Debouncing for Button 1
    if (lastState1 == HIGH && currentState1 == LOW &&
        (millis() - lastPressTime) > 200) {
      emergencyStop = !emergencyStop;
      systemLog("INFO", emergencyStop ? "EMERGENCY_STOP_ACTIVATED"
                                      : "EMERGENCY_STOP_RELEASED");
      lastPressTime = millis();
    }

    // Handle Button 2 (optional)
    if (lastState2 == HIGH && currentState2 == LOW &&
        (millis() - lastPressTime) > 200) {
      systemLog("INFO", "Button 2 pressed");
      lastPressTime = millis();
    }

    lastState1 = currentState1;
    lastState2 = currentState2;
    vTaskDelay(10 / portTICK_PERIOD_MS);
#else
    // Physical emergency button disabled for stable demo.
    // Use MQTT/Python commands STOP and RUN instead.
    vTaskDelay(500 / portTICK_PERIOD_MS);
#endif
  }
}

// TELEMETRY TASK

void telemetryTask(void *parameter) {
  while (true) {
    // Reconnect if needed
    if (!mqtt.connected()) {
      connectMQTT();
    }
    mqtt.loop();

    unsigned long currentTime = millis();

    if (currentTime - lastTelemetrySent >= config.telemetryInterval) {
      // Build telemetry JSON
      String payload = "{";
      payload += "\"time_ms\":" + String(currentTime) + ",";
      payload += "\"infrared_value\":" + String(infraredValue) + ",";
      payload += "\"distance_cm\":" + String(distanceCm) + ",";
      payload += "\"state\":\"" + robotState + "\",";
      payload += "\"led\":\"" + ledState + "\",";
      payload += "\"relay1_status\":" +
                 String(digitalRead(RELAY1_PIN) ? "true" : "false") + ",";
      payload += "\"relay2_status\":" +
                 String(digitalRead(RELAY2_PIN) ? "true" : "false") + ",";
      payload += "\"buzzer_status\":" +
                 String(digitalRead(BUZZER_PIN) ? "true" : "false") + ",";
      payload +=
          "\"system_healthy\":" + String(systemHealthy ? "true" : "false") +
          ",";
      payload += "\"last_error\":\"" + lastError + "\"";
      payload += "}";

      if (mqtt.connected()) {
        mqtt.publish(TOPIC_TELEMETRY, payload.c_str());
      }

      if (config.debugMode) {
        Serial.println("TELEMETRY: " + payload);
      }

      lastTelemetrySent = currentTime;
    }

    vTaskDelay(100 / portTICK_PERIOD_MS);
  }
}

// SYSTEM HEALTH MONITOR TASK

void monitorTask(void *parameter) {
  while (true) {
    unsigned long currentTime = millis();

    // Check WiFi connection every 30 seconds
    if (currentTime - lastWifiCheck > 30000) {
      if (WiFi.status() != WL_CONNECTED) {
        systemLog("WARN", "WiFi disconnected, attempting reconnect...");
        connectWiFi();
      }
      lastWifiCheck = currentTime;
    }

    // Check MQTT connection
    if (!mqtt.connected() && currentTime - lastMqttPing > 10000) {
      connectMQTT();
      lastMqttPing = currentTime;
    }

    vTaskDelay(1000 / portTICK_PERIOD_MS);
  }
}

// SETUP

void setup() {
  Serial.begin(9600);
  delay(1000);

  systemLog("INFO", "=== HAFIDA ROBOT MAKER POINT INITIALIZATION ===");
  systemLog("INFO", "Firmware Version: 2.0 Maker Point Edition");

// PIN CONFIGURATION
#if USE_INTERNAL_PULLUP_FOR_IR
  pinMode(INFRARED_PIN, INPUT_PULLUP);
#else
  pinMode(INFRARED_PIN, INPUT);
#endif
  pinMode(POT_PIN, INPUT);
  pinMode(BUTTON1_PIN, INPUT);
  pinMode(BUTTON2_PIN, INPUT_PULLUP);

  pinMode(LED1_PIN, OUTPUT);
  pinMode(LED2_PIN, OUTPUT);

  pinMode(RELAY1_PIN, OUTPUT);
  pinMode(RELAY2_PIN, OUTPUT);

  pinMode(BUZZER_PIN, OUTPUT);

  // Turn off all outputs initially
  digitalWrite(LED1_PIN, LOW);
  digitalWrite(LED2_PIN, LOW);
  digitalWrite(RELAY1_PIN, LOW);
  digitalWrite(RELAY2_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  // WiFi & MQTT
  connectWiFi();

  secureClient.setInsecure();
  mqtt.setServer(mqttHost, mqttPort);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(512);

  systemLog("INFO", "MQTT configured");

  // RTOS TASKS
  xTaskCreate(sensorTask, "sensorTask", 4096, NULL, 3, NULL);
  xTaskCreate(actuatorTask, "actuatorTask", 3072, NULL, 2, NULL);
  xTaskCreate(buttonTask, "buttonTask", 2048, NULL, 3, NULL);
  xTaskCreate(telemetryTask, "telemetryTask", 4096, NULL, 2, NULL);
  xTaskCreate(monitorTask, "monitorTask", 3072, NULL, 1, NULL);

  systemLog("INFO", "All tasks created successfully");
  systemLog("INFO", "=== SYSTEM READY ===");
}

void loop() {
  // Main work is handled by FreeRTOS tasks.
  vTaskDelay(100 / portTICK_PERIOD_MS);
}
