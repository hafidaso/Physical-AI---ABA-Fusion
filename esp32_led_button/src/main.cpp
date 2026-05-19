#include <Arduino.h>

#define LED_RED 2
#define LED_GREEN 4
#define BUTTON 12

void setup()
{
  Serial.begin(115200);

  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);

  pinMode(BUTTON, INPUT_PULLUP);
}

void loop()
{
  bool buttonPressed = digitalRead(BUTTON) == LOW;

  if (buttonPressed)
  {
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, HIGH);

    Serial.println("button enfoncé");
    Serial.println("LED RED is ON");
    Serial.println("LED GREEN is ON");
  }
  else
  {
    digitalWrite(LED_RED, LOW);
    digitalWrite(LED_GREEN, LOW);

    Serial.println("button relâché");
    Serial.println("LED RED is OFF");
    Serial.println("LED GREEN is OFF");
  }

  delay(500);
}