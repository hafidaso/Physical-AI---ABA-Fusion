#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// Initialize LCD (0x27 is the most common I2C address)
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Motor 1
const int PWMA1 = 3;
const int AIN1_1 = 2;
const int AIN2_1 = 4;

// Motor 2
const int PWMA2 = 5;
const int AIN1_2 = A0;
const int AIN2_2 = A1;

// Variables to track previous speeds and prevent LCD flickering
int lastSpeed1 = 999; 
int lastSpeed2 = 999;

void setMotor(int motorIndex, int speed) {
  bool dir = (speed >= 0) ? HIGH : LOW; 
  int pwmValue = abs(speed); 

  if (motorIndex == 1) {
    digitalWrite(AIN1_1, dir);
    digitalWrite(AIN2_1, !dir);
    analogWrite(PWMA1, pwmValue);
  } else if (motorIndex == 2) {
    digitalWrite(AIN1_2, dir);
    digitalWrite(AIN2_2, !dir);
    analogWrite(PWMA2, pwmValue);
  }
}

// Update LCD only when speed changes
void updateLCD(int s1, int s2) {
  if (s1 != lastSpeed1 || s2 != lastSpeed2) {
    lcd.setCursor(0, 0);
    lcd.print("M1 Spd: "); 
    lcd.print(s1);
    lcd.print("   "); // Padding clears old characters cleanly

    lcd.setCursor(0, 1);
    lcd.print("M2 Spd: "); 
    lcd.print(s2);
    lcd.print("   ");

    lastSpeed1 = s1;
    lastSpeed2 = s2;
  }
}

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(10); 

  // Initialize LCD
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("AGV System Ready");
  delay(1500);
  lcd.clear();

  // Motor outputs
  pinMode(PWMA1, OUTPUT); pinMode(AIN1_1, OUTPUT); pinMode(AIN2_1, OUTPUT);
  pinMode(PWMA2, OUTPUT); pinMode(AIN1_2, OUTPUT); pinMode(AIN2_2, OUTPUT);
  
  setMotor(1, 0);
  setMotor(2, 0);
  updateLCD(0, 0);
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n'); 
    int commaIndex = data.indexOf(',');

    if (commaIndex > 0) {
      int speed1 = data.substring(0, commaIndex).toInt();
      int speed2 = data.substring(commaIndex + 1).toInt();

      setMotor(1, speed1);
      setMotor(2, speed2);
      
      // Send the new values to the screen
      updateLCD(speed1, speed2);
    }
  }
}
