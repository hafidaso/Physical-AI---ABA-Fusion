#include <Arduino.h>


// Définition des pins


#define POT_PIN 34
#define BUTTON_PIN 12

#define LED_GREEN 2
#define LED_RED 4

#define BUZZER_PIN 15
#define RELAY_PIN 5


// Seuil de sécurité


// Le potentiomètre simule une tension entre 0V et 3.3V.
// Si la tension est inférieure à ce seuil, on considère qu'il y a une anomalie.
const float VOLTAGE_THRESHOLD = 1.8;


// Variables


int analogValue = 0;
float simulatedVoltage = 0.0;

bool systemOK = false;
bool buttonPressed = false;

void setup()
{
  Serial.begin(115200);

  pinMode(POT_PIN, INPUT);

  // Le bouton est connecté avec GND, donc on utilise INPUT_PULLUP.
  // Non appuyé = HIGH
  // Appuyé = LOW
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_RED, OUTPUT);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);

  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_RED, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RELAY_PIN, LOW);

  Serial.println("-------------");
  Serial.println("Physical AI - Atelier Jour 2");
  Serial.println("Mini banc de supervision energetique");
  Serial.println("Workflow: sense -> verify -> decide -> actuate -> log");
  Serial.println("-------------");
}

void loop()
{
 
  // 1. SENSE
  // Lire le potentiomètre et le bouton
 

  analogValue = analogRead(POT_PIN);
  simulatedVoltage = analogValue * 3.3 / 4095.0;

  buttonPressed = digitalRead(BUTTON_PIN) == LOW;

 
  // 2. RESET SECURITE
 

  if (buttonPressed)
  {
    digitalWrite(BUZZER_PIN, LOW);

    Serial.println("-------------");
    Serial.println("SYSTEM RESET");
    Serial.println("Bouton poussoir appuye");
    Serial.println("Relance de la verification...");
    Serial.println("-------------");

    delay(800);
    return;
  }

 
  // 3. VERIFY
  // Comparer la tension simulée avec le seuil
 

  if (simulatedVoltage >= VOLTAGE_THRESHOLD)
  {
    systemOK = true;
  }
  else
  {
    systemOK = false;
  }

 
  // 4. DECIDE + ACTUATE
  // Déclencher les sorties
 

  if (systemOK)
  {
    // Fonctionnement normal
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_RED, LOW);
    digitalWrite(BUZZER_PIN, LOW);
    digitalWrite(RELAY_PIN, HIGH);

   
    // 5. LOG
   

    Serial.println("-------------");
    Serial.println("SYSTEM OK");
    Serial.print("Analog value: ");
    Serial.println(analogValue);

    Serial.print("Simulated voltage: ");
    Serial.print(simulatedVoltage);
    Serial.println(" V");

    Serial.println("LED verte: ON");
    Serial.println("LED rouge: OFF");
    Serial.println("Buzzer: OFF");
    Serial.println("Relais: ON");
  }
  else
  {
    // Anomalie simulée
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_RED, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
    digitalWrite(RELAY_PIN, LOW);

   
    // 5. LOG
   

    Serial.println("-------------");
    Serial.println("VOLTAGE WARNING - RELAY DISABLED");
    Serial.print("Analog value: ");
    Serial.println(analogValue);

    Serial.print("Simulated voltage: ");
    Serial.print(simulatedVoltage);
    Serial.println(" V");

    Serial.println("LED verte: OFF");
    Serial.println("LED rouge: ON");
    Serial.println("Buzzer: ON");
    Serial.println("Relais: OFF");
  }

  delay(1000);
}