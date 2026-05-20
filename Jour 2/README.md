# 🔌 Day 2: ESP32 Basics & Simulation

This workshop serves as an introduction to basic hardware interactions using the ESP32 microcontroller, managed through PlatformIO and simulated via Wokwi.

---

## 📁 Contents

### 1. `esp32_led_button/` (Basic Digital I/O)
A foundational PlatformIO project that demonstrates how to interface with digital inputs and outputs.

**Key Features:**
- Configures a physical push button as an input with internal pull-up (`INPUT_PULLUP`).
- Controls two external LEDs (Red and Green) as outputs.
- Reads the button state in a standard loop to toggle the LEDs on/off and log the status to the Serial Monitor.
- Includes `diagram.json` and `wokwi.toml` for full visual circuit simulation.

### 2. `Jour2_Wokwi/Atelier_Jour_2/` (FreeRTOS Supervision System)
An advanced, concurrent energy supervision system using FreeRTOS multitasking to manage multiple asynchronous operations in real-time.

**Key Features & Workflow:**
- **FreeRTOS Multitasking:** Runs four concurrent, pinned-to-core tasks synchronized with a secure Mutex (`dataMutex`).
- **`taskSense` (Priority 3):** Reads the potentiometer input (analog simulation of voltage) and the emergency button state.
- **`taskDecision` (Priority 2):** Processes telemetry data and transitions system states:
  - `STATE_OK` (Voltage $\ge$ 1.8V)
  - `STATE_WARNING` (Voltage $<$ 1.8V)
  - `STATE_RESET` (Button Pressed)
- **`taskActuate` (Priority 2):** Orchestrates physical actuators:
  - Green/Red LEDs & Relay status toggles.
  - Active buzzer warnings.
  - Common-cathode 7-segment display status visualizer (`0` = OK, `1` = WARNING, `2` = RESET).
- **`taskLog` (Priority 1):** Periodically prints comprehensive state summaries and debug telemetry to the Serial Monitor.
- Includes a complete simulated breadboard diagram with individual current-limiting resistors and clean power rails.

---

## ⚙️ How to Run

1. Open either project folder (`esp32_led_button` or `Jour2_Wokwi/Atelier_Jour_2`) in **VS Code** with the **PlatformIO** extension installed.
2. Build the project to resolve dependencies and compile the firmware.
3. Open the `diagram.json` file.
4. Use the **Wokwi** extension to start the simulation within VS Code or web browser, or click **Upload** to flash the firmware onto a physical ESP32 board.
