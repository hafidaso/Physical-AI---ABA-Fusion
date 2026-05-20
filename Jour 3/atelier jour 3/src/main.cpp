#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

/*
  Atelier Jour 3 - Physical AI
  By : Hafida Belayd
  Acquisition multi-capteurs avec FreeRTOS

  Capteurs utilisés :
  - BME280 : température, humidité, pression via I2C
  - Potentiomètre : signal analogique contrôlable via ADC
  - Capteur infrarouge : obstacle via GPIO digital

  Sorties :
  - LED verte : système OK
  - LED rouge : alerte
  - Buzzer : alerte sonore
*/

//  Pins 

const int PIN_POT = 25;          // ADC / Potentiomètre
const int PIN_IR = 4;           // GPIO digital / Capteur infrarouge

const int LED_GREEN_PIN = 33;    // LED OK
const int LED_RED_PIN = 32;      // LED Alerte
const int BUZZER_PIN = 26;       // Buzzer

//  Seuils 

const float TEMP_THRESHOLD = 23.0;     // Seuil température
const int POT_THRESHOLD = 3000;        // Seuil potentiomètre

// Dans notre cas : IR = 0 sans obstacle, IR = 1 avec obstacle
const int IR_OBSTACLE_STATE = HIGH;

//  Capteur BME280 

Adafruit_BME280 capteur;
bool bmeDetecte = false;

//  Mutex 

SemaphoreHandle_t dataMutex;

//  Structure des données 

struct SensorData {
  bool bmeOK;

  float temperature;
  float humidite;
  float pression;

  int potRaw;
  int potFiltered;
  float potVoltage;

  int irState;

  unsigned long lastBmeMs;
  unsigned long lastPotMs;
  unsigned long lastIrMs;
};

SensorData data = {
  false,
  0.0,
  0.0,
  0.0,
  0,
  0,
  0.0,
  0,
  0,
  0,
  0
};

//  Prototypes des Tasks 

void taskLireBME280(void *pvParameters);
void taskLirePotentiometre(void *pvParameters);
void taskLireIRSensor(void *pvParameters);
void taskSupervision(void *pvParameters);

//  Fonction de filtrage ADC 

int readAverageADC(int pin, int samples = 5) {
  long somme = 0;

  for (int i = 0; i < samples; i++) {
    somme += analogRead(pin);
    vTaskDelay(pdMS_TO_TICKS(2));
  }

  return somme / samples;
}

//  Setup 

void setup() {
  Serial.begin(115200);
  Wire.begin();

  analogReadResolution(12);

  pinMode(PIN_POT, INPUT);
  pinMode(PIN_IR, INPUT_PULLUP);

  pinMode(LED_GREEN_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LED_GREEN_PIN, LOW);
  digitalWrite(LED_RED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  Serial.println("--- Atelier Jour 3 : Acquisition multi-capteurs ---");

  // Initialisation du BME280
  if (capteur.begin(0x76) || capteur.begin(0x77)) {
    bmeDetecte = true;
    data.bmeOK = true;
    Serial.println("BME280 détecté avec succès.");
  } else {
    bmeDetecte = false;
    data.bmeOK = false;
    Serial.println("Erreur : BME280 introuvable.");
  }

  // Création du Mutex
  dataMutex = xSemaphoreCreateMutex();

  if (dataMutex == NULL) {
    Serial.println("Erreur : Mutex non créé !");
    while (true);
  }

  Serial.println("Fréquences cibles :");
  Serial.println("BME280         : 1 Hz");
  Serial.println("Potentiomètre  : 10 Hz");
  Serial.println("IR sensor      : 20 Hz");
  Serial.println("Supervision    : 5 Hz");
  Serial.println("-------");

  // Task 1 : lecture BME280
  xTaskCreatePinnedToCore(
    taskLireBME280,
    "Lecture BME280",
    4096,
    NULL,
    1,
    NULL,
    1
  );

  // Task 2 : lecture Potentiomètre
  xTaskCreatePinnedToCore(
    taskLirePotentiometre,
    "Lecture Potentiometre",
    2048,
    NULL,
    1,
    NULL,
    1
  );

  // Task 3 : lecture IR sensor
  xTaskCreatePinnedToCore(
    taskLireIRSensor,
    "Lecture IR",
    2048,
    NULL,
    1,
    NULL,
    1
  );

  // Task 4 : supervision, alerte et journalisation
  xTaskCreatePinnedToCore(
    taskSupervision,
    "Supervision",
    4096,
    NULL,
    1,
    NULL,
    1
  );
}

//  Loop 

void loop() {
  // Vide, car tout le travail est géré par les Tasks FreeRTOS
}

//  TASK 1 : Lecture BME280 

void taskLireBME280(void *pvParameters) {
  while (true) {
    if (bmeDetecte) {
      float t = capteur.readTemperature();
      float h = capteur.readHumidity();
      float p = capteur.readPressure() / 100.0F;

      if (!isnan(t) && !isnan(h) && !isnan(p)) {
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
          data.temperature = t;
          data.humidite = h;
          data.pression = p;
          data.bmeOK = true;
          data.lastBmeMs = millis();

          xSemaphoreGive(dataMutex);
        }
      } else {
        if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
          data.bmeOK = false;
          xSemaphoreGive(dataMutex);
        }
      }
    } else {
      if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
        data.bmeOK = false;
        xSemaphoreGive(dataMutex);
      }
    }

    // BME280 est un capteur lent : lecture chaque 1 seconde = 1 Hz
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

//  TASK 2 : Lecture Potentiomètre 

void taskLirePotentiometre(void *pvParameters) {
  while (true) {
    int raw = analogRead(PIN_POT);
    int filtered = readAverageADC(PIN_POT, 5);

    // Conversion approximative ADC → tension
    float voltage = (filtered / 4095.0) * 3.3;

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
      data.potRaw = raw;
      data.potFiltered = filtered;
      data.potVoltage = voltage;
      data.lastPotMs = millis();

      xSemaphoreGive(dataMutex);
    }

    // Lecture chaque 100 ms = 10 Hz
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

//  TASK 3 : Lecture IR sensor 

void taskLireIRSensor(void *pvParameters) {
  while (true) {
    int ir = digitalRead(PIN_IR);

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
      data.irState = ir;
      data.lastIrMs = millis();

      xSemaphoreGive(dataMutex);
    }

    // Lecture chaque 50 ms = 20 Hz
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

//  TASK 4 : Supervision + Alerte + Log 

void taskSupervision(void *pvParameters) {
  while (true) {
    SensorData copie;

    // On copie les données protégées par Mutex
    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE) {
      copie = data;
      xSemaphoreGive(dataMutex);
    }

    bool alertTemp = false;
    bool alertPot = false;
    bool alertObstacle = false;
    bool errorSensor = false;

    if (!copie.bmeOK) {
      errorSensor = true;
    }

    if (copie.bmeOK && copie.temperature > TEMP_THRESHOLD) {
      alertTemp = true;
    }

    if (copie.potFiltered > POT_THRESHOLD) {
      alertPot = true;
    }

    if (copie.irState == IR_OBSTACLE_STATE) {
      alertObstacle = true;
    }

    bool alert = errorSensor || alertTemp || alertPot || alertObstacle;

    // Gestion des LEDs et du buzzer
    if (alert) {
      digitalWrite(LED_GREEN_PIN, LOW);
      digitalWrite(LED_RED_PIN, HIGH);
      digitalWrite(BUZZER_PIN, HIGH);
    } else {
      digitalWrite(LED_GREEN_PIN, HIGH);
      digitalWrite(LED_RED_PIN, LOW);
      digitalWrite(BUZZER_PIN, LOW);
    }

    // Journalisation dans le moniteur série
    Serial.print("[");
    Serial.print(millis());
    Serial.print(" ms] ");

    if (copie.bmeOK) {
      Serial.print("Temp=");
      Serial.print(copie.temperature);
      Serial.print(" °C");

      Serial.print(" | Hum=");
      Serial.print(copie.humidite);
      Serial.print(" %");

      Serial.print(" | Pression=");
      Serial.print(copie.pression);
      Serial.print(" hPa");
    } else {
      Serial.print("BME280=ERROR");
    }

    Serial.print(" | PotRaw=");
    Serial.print(copie.potRaw);

    Serial.print(" | PotFiltered=");
    Serial.print(copie.potFiltered);

    Serial.print(" | PotVoltage=");
    Serial.print(copie.potVoltage);
    Serial.print(" V");

    Serial.print(" | IR=");
    Serial.print(copie.irState);

    Serial.print(" | Status=");

    if (errorSensor) {
      Serial.println("ERROR_SENSOR");
    } else if (alertTemp) {
      Serial.println("ALERT_TEMP");
    } else if (alertPot) {
      Serial.println("ALERT_POT");
    } else if (alertObstacle) {
      Serial.println("ALERT_OBSTACLE");
    } else {
      Serial.println("OK");
    }

    // Supervision chaque 200 ms = 5 Hz
    vTaskDelay(pdMS_TO_TICKS(200));
  }
}

/*
  Explication FreeRTOS :

  Mutex :
  Il est utilisé pour protéger les données partagées entre plusieurs Tasks.
  Dans ce code, les données des capteurs sont stockées dans la structure "data".
  Comme plusieurs Tasks lisent et écrivent dans cette structure, on utilise un Mutex
  pour éviter que deux Tasks y accèdent en même temps.

  Tasks utilisées :
  - taskLireBME280          : lit la température, l'humidité et la pression chaque 1 seconde.
  - taskLirePotentiometre  : lit la valeur analogique du potentiomètre chaque 100 ms.
  - taskLireIRSensor       : lit l'état du capteur infrarouge chaque 50 ms.
  - taskSupervision        : compare les valeurs aux seuils, active les LEDs/buzzer et affiche le log.

  Fréquences :
  - BME280         = 1 Hz
  - Potentiomètre  = 10 Hz
  - IR sensor      = 20 Hz
  - Supervision    = 5 Hz

  Logique :
  - Si tout est normal : LED verte ON, LED rouge OFF, buzzer OFF.
  - Si température > 23°C : alerte température.
  - Si potentiomètre > 3000 : alerte potentiomètre.
  - Si obstacle détecté : alerte obstacle.
  - Si BME280 introuvable : erreur capteur.

  Rôle du potentiomètre :
  Le potentiomètre est utilisé comme un signal analogique contrôlable.
  Il permet de simuler une variation manuelle, par exemple un niveau de tension,
  d'énergie ou d'intensité. Lorsque sa valeur dépasse le seuil défini,
  le système déclenche une alerte.
*/