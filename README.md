# 🤖 Physical AI - ABA Fusion Program

Welcome to the repository for the **Physical AI** training program in collaboration with **ABA Fusion**.
This training program spans **two months** and aims to cover everything related to integrating software and Artificial Intelligence with physical systems (IoT, Embedded Systems, Digital Twins).

## 🗂️ Project Structure & Contents (Progress So Far)

The program is divided into multiple days and practical workshops (Jours). Here is what has been accomplished so far:

### 📅 Day 1 (Jour 1): Smart Robot & Digital Twin (SCADA)
The first day's workshop focuses on building a complete SCADA system to create a "Digital Twin" for a smart robot using the MQTT protocol.

- **`main.cpp` (ESP32 Firmware):** 
  C++ code designed to run on an ESP32 microcontroller (Maker Point Board). It utilizes FreeRTOS for task management (reading infrared and distance sensors, controlling motors via relays, and handling LED/Buzzer alerts). It connects to WiFi and sends/receives telemetry data via the HiveMQ cloud broker.
- **`smart_robot_twin.py` (Python SCADA Interface):** 
  An interactive Graphical User Interface (GUI) built with `pygame`. It represents the digital twin and displays real-time robot telemetry (sensor readings, robot path, and alerts), along with the ability to send control commands (RUN/STOP).
- **Assignments & Docs:** 
  Includes documentation for the tracking robot (`TP_Robot_Suiveur_MQTT_Code_Complet.pdf`), workshop reports, and an `Assignment 1` folder containing the "Sterile Zone Guardian" project.

### 📅 Day 2 (Jour 2): ESP32 Basics & Simulation
A practical workshop to practice hardware basics and circuit simulation using the PlatformIO environment.

- **`esp32_led_button` Project:** 
  A simple practical application to bridge hardware components, where it reads the state of a push button and controls the toggling of LEDs accordingly. The project includes a `wokwi.toml` file to support electronic circuit simulation.

---

## 🛠️ Technologies & Tools Used
- **Hardware:** ESP32, Maker Point Board, Sensors (IR, Distance).
- **Embedded Programming:** C/C++, Arduino Framework, FreeRTOS.
- **Connectivity & IoT:** WiFi, MQTT Protocol (via HiveMQ Cloud).
- **Control Interfaces (SCADA/Digital Twin):** Python (Pygame, Paho-MQTT).
- **Development & Simulation Environments:** VS Code, PlatformIO, Wokwi.

---

## 🚀 How to Run (Digital Twin Example)

1. **Hardware Setup (ESP32):**
   - Connect the board and ensure the WiFi credentials and MQTT account settings in `main.cpp` are configured.
   - Upload the code to the ESP32 board.
2. **Run the Digital Twin Interface:**
   - Make sure to install the required Python libraries:
     ```bash
     pip install paho-mqtt pygame
     ```
   - Run the interface:
     ```bash
     python "Jour 1/smart_robot_twin.py"
     ```

---
*This repository is under continuous development and will be updated with new folders and projects over the next two months to cover more Physical AI concepts.*
