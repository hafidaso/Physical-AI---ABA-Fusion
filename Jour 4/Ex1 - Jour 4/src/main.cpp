#include <Arduino.h>

// Afficheur 7 segments cathode commune
// ordre obligatoire : a, b, c, d, e, f, g
const int segmentPins[] = {11, 10, 7, 9, 8, 13, 12};

// LEDs
const int BLUE_LED = 2;
const int LIGHT_LED = 3;

// Potentiometer
const int POT_PIN = A4; // PIN_A4 est défini dans pins_arduino.h comme étant égal à A4

// Button
const int BUTTON_PIN = 4;
int offset = 0; // variable pour stocker l'offset ajouté par le bouton
int lastButtonState = HIGH;

// 1 = segment allumé
// 0 = segment éteint
byte numbers[10][7] = {
  // a, b, c, d, e, f, g
  {LOW,  LOW,  LOW,  LOW,  LOW,  LOW,  HIGH}, // 0
{HIGH, LOW,  LOW,  HIGH, HIGH, HIGH, HIGH}, // 1
{LOW,  LOW,  HIGH, LOW,  LOW,  HIGH, LOW},  // 2
{LOW,  LOW,  LOW,  LOW,  HIGH, HIGH, LOW},  // 3
{HIGH, LOW,  LOW,  HIGH, HIGH, LOW,  LOW},  // 4
{LOW,  HIGH, LOW,  LOW,  HIGH, LOW,  LOW},  // 5
{LOW,  HIGH, LOW,  LOW,  LOW,  LOW,  LOW},  // 6
{LOW,  LOW,  LOW,  HIGH, HIGH, HIGH, HIGH}, // 7
{LOW,  LOW,  LOW,  LOW,  LOW,  LOW,  LOW},  // 8
{LOW,  LOW,  LOW,  LOW,  HIGH, LOW,  LOW}   // 9
};

void displayDigit(int digit) {
  for (int segment = 0; segment < 7; segment++) {
    digitalWrite(segmentPins[segment], numbers[digit][segment] ? HIGH : LOW);
  }
}

void clearDisplay() {
  for (int segment = 0; segment < 7; segment++) {
    digitalWrite(segmentPins[segment], LOW);
  }
}

void setup() {
  for (int i = 0; i < 7; i++) {
    pinMode(segmentPins[i], OUTPUT);
  }

  pinMode(BLUE_LED, OUTPUT);
  pinMode(LIGHT_LED, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  clearDisplay();
}

void loop() {
  // Gérer le bouton pour ajouter un offset
  int buttonState = digitalRead(BUTTON_PIN);
  if (buttonState == LOW && lastButtonState == HIGH) {
    offset++; // Ajout d'un à l'offset
    delay(50); // Debounce
  }
  lastButtonState = buttonState;

  // Lire la valeur du potentiomètre (de 0 à 1023)
  int potValue = analogRead(POT_PIN);
  
  // Convertir la valeur lue en un nombre entre 0 et 9 et ajouter l'offset
  int digit = (map(potValue, 0, 1023, 0, 9) + offset) % 10;
  
  // Afficher le chiffre
  displayDigit(digit);
  
  // Allumer la LED bleue si le chiffre est pair, sinon allumer la LED blanche
  if (digit % 2 == 0) {
    digitalWrite(BLUE_LED, HIGH);
    digitalWrite(LIGHT_LED, LOW);
  } else {
    digitalWrite(BLUE_LED, LOW);
    digitalWrite(LIGHT_LED, HIGH);
  }
  
  delay(100); // petit délai pour éviter de lire trop rapidement le potentiomètre
}