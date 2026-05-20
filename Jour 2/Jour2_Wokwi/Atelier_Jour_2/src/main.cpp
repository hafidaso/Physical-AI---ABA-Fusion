#include <Arduino.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"


// Définition des pins


#define POT_PIN 34
#define BUTTON_PIN 12

#define LED_GREEN 2
#define LED_RED 4

#define BUZZER_PIN 15
#define RELAY_PIN 5

// 7-segment pins
#define SEG_A 13
#define SEG_B 14
#define SEG_C 18
#define SEG_D 19
#define SEG_E 21
#define SEG_F 22
#define SEG_G 23


// Seuil de sécurité

// Le potentiomètre simule une tension entre 0V et 3.3V.
// Si la tension est inférieure à ce seuil, on considère qu'il y a une anomalie.
const float VOLTAGE_THRESHOLD = 1.8;


// Variables partagées


int analogValue = 0;
float simulatedVoltage = 0.0;
bool buttonPressed = false;

enum SystemState
{
  STATE_OK,
  STATE_WARNING,
  STATE_RESET
};

SystemState currentState = STATE_WARNING;

// Mutex pour protéger les variables partagées entre les tâches FreeRTOS
SemaphoreHandle_t dataMutex;

// Pins du 7-segment dans l’ordre A, B, C, D, E, F, G
const int segmentPins[7] = {
  SEG_A, SEG_B, SEG_C, SEG_D, SEG_E, SEG_F, SEG_G
};

// Table des chiffres pour un 7-segment common cathode
// 1 = segment ON, 0 = segment OFF
const byte digitPatterns[10][7] = {
  // A, B, C, D, E, F, G
  {1, 1, 1, 1, 1, 1, 0}, // 0
  {0, 1, 1, 0, 0, 0, 0}, // 1
  {1, 1, 0, 1, 1, 0, 1}, // 2
  {1, 1, 1, 1, 0, 0, 1}, // 3
  {0, 1, 1, 0, 0, 1, 1}, // 4
  {1, 0, 1, 1, 0, 1, 1}, // 5
  {1, 0, 1, 1, 1, 1, 1}, // 6
  {1, 1, 1, 0, 0, 0, 0}, // 7
  {1, 1, 1, 1, 1, 1, 1}, // 8
  {1, 1, 1, 1, 0, 1, 1}  // 9
};

// Fonctions 7-segment

void clearDisplay()
{
  for (int i = 0; i < 7; i++)
  {
    digitalWrite(segmentPins[i], LOW);
  }
}

void displayDigit(int digit)
{
  if (digit < 0 || digit > 9)
  {
    clearDisplay();
    return;
  }

  for (int i = 0; i < 7; i++)
  {
    digitalWrite(segmentPins[i], digitPatterns[digit][i] ? HIGH : LOW);
  }
}

const char *getStateName(SystemState state)
{
  switch (state)
  {
    case STATE_OK:
      return "SYSTEM OK";

    case STATE_WARNING:
      return "VOLTAGE WARNING";

    case STATE_RESET:
      return "SYSTEM RESET";

    default:
      return "UNKNOWN";
  }
}

// Task 1: SENSE
// Lire potentiomètre + bouton

void taskSense(void *parameter)
{
  while (true)
  {
    int localAnalogValue = analogRead(POT_PIN);
    float localVoltage = localAnalogValue * 3.3 / 4095.0;
    bool localButtonPressed = digitalRead(BUTTON_PIN) == LOW;

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE)
    {
      analogValue = localAnalogValue;
      simulatedVoltage = localVoltage;
      buttonPressed = localButtonPressed;

      xSemaphoreGive(dataMutex);
    }

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// Task 2: VERIFY + DECIDE
// Déterminer l’état du système

void taskDecision(void *parameter)
{
  while (true)
  {
    float localVoltage;
    bool localButtonPressed;

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE)
    {
      localVoltage = simulatedVoltage;
      localButtonPressed = buttonPressed;

      xSemaphoreGive(dataMutex);
    }

    SystemState newState;

    if (localButtonPressed)
    {
      newState = STATE_RESET;
    }
    else if (localVoltage >= VOLTAGE_THRESHOLD)
    {
      newState = STATE_OK;
    }
    else
    {
      newState = STATE_WARNING;
    }

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE)
    {
      currentState = newState;
      xSemaphoreGive(dataMutex);
    }

    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// Task 3: ACTUATE
// Commander LED, buzzer, relais, 7-segment

void taskActuate(void *parameter)
{
  while (true)
  {
    SystemState localState;

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE)
    {
      localState = currentState;
      xSemaphoreGive(dataMutex);
    }

    if (localState == STATE_OK)
    {
      digitalWrite(LED_GREEN, HIGH);
      digitalWrite(LED_RED, LOW);
      digitalWrite(BUZZER_PIN, LOW);
      digitalWrite(RELAY_PIN, HIGH);

      // 0 = état normal
      displayDigit(0);
    }
    else if (localState == STATE_WARNING)
    {
      digitalWrite(LED_GREEN, LOW);
      digitalWrite(LED_RED, HIGH);
      digitalWrite(BUZZER_PIN, HIGH);
      digitalWrite(RELAY_PIN, LOW);

      // 1 = anomalie / warning
      displayDigit(1);
    }
    else if (localState == STATE_RESET)
    {
      digitalWrite(LED_GREEN, LOW);
      digitalWrite(LED_RED, LOW);
      digitalWrite(BUZZER_PIN, LOW);
      digitalWrite(RELAY_PIN, LOW);

      // 2 = reset sécurité
      displayDigit(2);
    }

    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// Task 4: LOG
// Afficher les informations dans le Serial Monitor

void taskLog(void *parameter)
{
  while (true)
  {
    int localAnalogValue;
    float localVoltage;
    bool localButtonPressed;
    SystemState localState;

    if (xSemaphoreTake(dataMutex, portMAX_DELAY) == pdTRUE)
    {
      localAnalogValue = analogValue;
      localVoltage = simulatedVoltage;
      localButtonPressed = buttonPressed;
      localState = currentState;

      xSemaphoreGive(dataMutex);
    }

    Serial.println("-------------");
    Serial.print("State: ");
    Serial.println(getStateName(localState));

    Serial.print("Analog value: ");
    Serial.println(localAnalogValue);

    Serial.print("Simulated voltage: ");
    Serial.print(localVoltage);
    Serial.println(" V");

    Serial.print("Button pressed: ");
    Serial.println(localButtonPressed ? "YES" : "NO");

    if (localState == STATE_OK)
    {
      Serial.println("LED verte: ON");
      Serial.println("LED rouge: OFF");
      Serial.println("Buzzer: OFF");
      Serial.println("Relais: ON");
      Serial.println("7-segment: 0");
    }
    else if (localState == STATE_WARNING)
    {
      Serial.println("LED verte: OFF");
      Serial.println("LED rouge: ON");
      Serial.println("Buzzer: ON");
      Serial.println("Relais: OFF");
      Serial.println("7-segment: 1");
    }
    else if (localState == STATE_RESET)
    {
      Serial.println("LED verte: OFF");
      Serial.println("LED rouge: OFF");
      Serial.println("Buzzer: OFF");
      Serial.println("Relais: OFF");
      Serial.println("7-segment: 2");
    }

    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// SETUP

void setup()
{
  Serial.begin(115200);

  pinMode(POT_PIN, INPUT);

  // Le bouton est connecté avec GND.
  // INPUT_PULLUP:
  // Non appuyé = HIGH
  // Appuyé = LOW
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);

  for (int i = 0; i < 7; i++)
  {
    pinMode(segmentPins[i], OUTPUT);
  }

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RELAY_PIN, LOW);
  clearDisplay();

  Serial.println("-------------");
  Serial.println("Physical AI - Atelier Jour 2");
  Serial.println("Mini banc de supervision energetique");
  Serial.println("Version FreeRTOS multitasking");
  Serial.println("Workflow: sense -> verify -> decide -> actuate -> log");
  Serial.println("7-segment: 0=OK, 1=WARNING, 2=RESET");
  Serial.println("-------------");

  dataMutex = xSemaphoreCreateMutex();

  if (dataMutex == NULL)
  {
    Serial.println("Erreur: Mutex non cree");
    return;
  }

  // Création des tâches FreeRTOS
  xTaskCreatePinnedToCore(
    taskSense,
    "Task Sense",
    4096,
    NULL,
    3,
    NULL,
    1
  );

  xTaskCreatePinnedToCore(
    taskDecision,
    "Task Decision",
    4096,
    NULL,
    2,
    NULL,
    1
  );

  xTaskCreatePinnedToCore(
    taskActuate,
    "Task Actuate",
    4096,
    NULL,
    2,
    NULL,
    0
  );

  xTaskCreatePinnedToCore(
    taskLog,
    "Task Log",
    4096,
    NULL,
    1,
    NULL,
    0
  );
}

// LOOP

// La loop reste presque vide parce que FreeRTOS gère les tâches.
void loop()
{
  vTaskDelay(pdMS_TO_TICKS(1000));
}