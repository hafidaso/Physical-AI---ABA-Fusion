#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

LiquidCrystal_I2C lcd(0x27, 16, 2);

// Motor 1 (Left Wheel)
const int PWMA1 = 3;
const int AIN1_1 = 2;
const int AIN2_1 = 4;

// Motor 2 (Right Wheel)
const int PWMA2 = 5;
const int AIN1_2 = A0;
const int AIN2_2 = A1;

// Motor 3 (Left Wheel 2 - Second Driver A)
const int PWMA3 = 9;
const int AIN1_3 = 11;
const int AIN2_3 = 10;

// Motor 4 (Right Wheel 2 - Second Driver B)
const int PWMA4 = 6;
const int AIN1_4 = 12;
const int AIN2_4 = 13;

// Simulated Battery Levels
const int BATTERY_1_LEVEL = 80;
const int BATTERY_2_LEVEL = 100;

int lastSpeed1 = 999; 
int lastSpeed2 = 999;
int lastBat1 = 999;
int lastBat2 = 999;

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
  } else if (motorIndex == 3) {
    digitalWrite(AIN1_3, dir);
    digitalWrite(AIN2_3, !dir);
    analogWrite(PWMA3, pwmValue);
  } else if (motorIndex == 4) {
    digitalWrite(AIN1_4, dir);
    digitalWrite(AIN2_4, !dir);
    analogWrite(PWMA4, pwmValue);
  }
}

void updateLCD(int s1, int s2, int bat1, int bat2) {
  if (s1 != lastSpeed1 || s2 != lastSpeed2 || bat1 != lastBat1 || bat2 != lastBat2) {
    char line1[17];
    char line2[17];
    
    // Format exactly 16 characters for the 16x2 LCD
    sprintf(line1, "R1 S:%-4d B:%-3d%%", s1, bat1);
    sprintf(line2, "R2 S:%-4d B:%-3d%%", s2, bat2);
    
    lcd.setCursor(0, 0);
    lcd.print(line1);
    lcd.setCursor(0, 1);
    lcd.print(line2);

    lastSpeed1 = s1;
    lastSpeed2 = s2;
    lastBat1 = bat1;
    lastBat2 = bat2;
  }
}

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(10); 

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("AGV System Ready");
  delay(1500);
  lcd.clear();

  pinMode(PWMA1, OUTPUT); pinMode(AIN1_1, OUTPUT); pinMode(AIN2_1, OUTPUT);
  pinMode(PWMA2, OUTPUT); pinMode(AIN1_2, OUTPUT); pinMode(AIN2_2, OUTPUT);
  pinMode(PWMA3, OUTPUT); pinMode(AIN1_3, OUTPUT); pinMode(AIN2_3, OUTPUT);
  pinMode(PWMA4, OUTPUT); pinMode(AIN1_4, OUTPUT); pinMode(AIN2_4, OUTPUT);
  
  setMotor(1, 0);
  setMotor(2, 0);
  setMotor(3, 0);
  setMotor(4, 0);
  
  updateLCD(0, 0, BATTERY_1_LEVEL, BATTERY_2_LEVEL);
}

void loop() {
  if (Serial.available() > 0) {
    String data = Serial.readStringUntil('\n'); 
    int m1 = 0, m2 = 0, m3 = 0, m4 = 0;
    
    if (sscanf(data.c_str(), "%d,%d,%d,%d", &m1, &m2, &m3, &m4) == 4) {
      setMotor(1, m1);
      setMotor(2, m2);
      setMotor(3, m3);
      setMotor(4, m4);
      
      updateLCD(m1, m3, BATTERY_1_LEVEL, BATTERY_2_LEVEL);
    }
  }
}
