#include <Arduino.h>
#include "DHT.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// DHT Sensor
#define DHTPIN A3      // Broche à laquelle le capteur est connecté
#define DHTTYPE DHT11   // Définir le type de capteur
DHT dht(DHTPIN, DHTTYPE);


// Motor A pins
const int pwmA = 3;     // ENA pin on L298N, must be PWM pin
const int inA1 = A0;    // IN1
const int inA2 = A1;    // IN2

// Potentiometer pin
const int POT_PIN = A2; // Middle pin of potentiometer

void setup() {
  Serial.begin(9600);
  dht.begin();

  lcd.init();        // Start LCD
  lcd.backlight();   // Turn on backlight
  lcd.setCursor(0, 0);
  lcd.print("System Ready...");

  pinMode(pwmA, OUTPUT);
  pinMode(inA1, OUTPUT);
  pinMode(inA2, OUTPUT);

  // Direction forward
  digitalWrite(inA1, HIGH);
  digitalWrite(inA2, LOW);
}

void loop() {
  // Read potentiometer value: 0 to 1023
  int sensorValue = analogRead(POT_PIN);

  // Convert potentiometer value to motor speed: 0 to 255
  int motorSpeed = map(sensorValue, 0, 1023, 0, 255);

  // Safety limit
  motorSpeed = constrain(motorSpeed, 0, 255);

  // Send PWM speed to motor
  analogWrite(pwmA, motorSpeed);

  // Serial monitor
  Serial.print("Sensor: ");
  Serial.print(sensorValue);
  Serial.print(" | Speed: ");
  Serial.println(motorSpeed);

  // Read DHT sensor non-blocking (every 2 seconds)
  static unsigned long lastDHTRead = 0;
  static float lastH = 0.0;
  static float lastT = 0.0;
  
  if (millis() - lastDHTRead >= 2000) {
    lastDHTRead = millis();
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    
    if (isnan(h) || isnan(t)) {
      Serial.println("Échec de lecture !");
    } else {
      lastH = h;
      lastT = t;
      Serial.print("Humidité: ");
      Serial.print(h);
      Serial.print(" %\t");
      Serial.print("Température: ");
      Serial.print(t);
      Serial.println(" *C");
    }
  }

  // Update LCD Display
  lcd.setCursor(0, 0);
  lcd.print("Spd:");
  lcd.print(motorSpeed);
  lcd.print("   T:");
  lcd.print((int)lastT);
  lcd.print("C  "); // Padding to overwrite remaining digits

  lcd.setCursor(0, 1);
  lcd.print("Hum: ");
  lcd.print(lastH, 1);
  lcd.print("%        ");

  delay(100);
}