# 🚀 Day 1: Smart Robot & Digital Twin (SCADA)

This workshop focuses on creating a "Digital Twin" for a smart robot, establishing bidirectional communication using the MQTT protocol.

## 📁 Contents

- **`main.cpp` (ESP32 Firmware):**
  C++ code designed for the ESP32 microcontroller (Maker Point Board). It uses the FreeRTOS framework for concurrent task management to:
  - Read from Infrared (IR) and Distance (Potentiometer-simulated) sensors.
  - Control Relays, LEDs, and a Buzzer.
  - Publish real-time telemetry and subscribe to commands via the HiveMQ cloud broker.

- **`smart_robot_twin.py` (Python SCADA Interface):**
  A modern, cyberpunk-themed Graphical User Interface (GUI) built with `pygame`. It acts as the Digital Twin by:
  - Connecting to the same MQTT broker.
  - Visualizing the real-time state, sensor readings, and movement of the robot.
  - Providing interactive `RUN` and `STOP` controls to command the physical hardware.

- **`Assignment 1/` (Sterile Zone Guardian):**
  An assignment related to the concepts learned in this workshop.

- **Documentation & Design:**
  - `TP_Robot_Suiveur_MQTT_Code_Complet.pdf`: Comprehensive lab manual.
  - `Rapport_Atelier_Jour1_PhysicalAI.docx`: Workshop report.
  - `Design_templates_Atelier_1_Hafida_Belayd.xlsx`: UI and system design templates.

## ⚙️ How to Run

1. **Hardware (ESP32):**
   - Update your WiFi credentials (`ssid`, `password`) in `main.cpp`.
   - Ensure the HiveMQ credentials are correct.
   - Flash the firmware using Arduino IDE or PlatformIO.

2. **Digital Twin (Python):**
   - Install dependencies: `pip install paho-mqtt pygame`
   - Run the interface: `python smart_robot_twin.py`
