# 🔌 Day 2: ESP32 Basics & Simulation

This workshop serves as an introduction to basic hardware interactions using the ESP32 microcontroller, managed through PlatformIO and simulated via Wokwi.

## 📁 Contents

- **`esp32_led_button/` Project:**
  A foundational PlatformIO project that demonstrates how to interface with digital inputs and outputs.
  
  **Key Features:**
  - Configures a physical push button as an input (`INPUT_PULLUP`).
  - Controls two external LEDs (Red and Green) as outputs.
  - Reads the button state in a loop to toggle the LEDs on and off, logging the status to the Serial Monitor.
  - Includes a `wokwi.toml` and `diagram.json` to allow full electronic circuit simulation within VS Code or the web browser without needing physical hardware.

## ⚙️ How to Run

1. Open the `esp32_led_button` folder in **VS Code** with the **PlatformIO** extension installed.
2. Build the project to resolve dependencies.
3. Use the **Wokwi** extension to start the simulation using `diagram.json`, or connect a real ESP32 and click "Upload".
