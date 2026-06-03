# AGV Fleet Simulator & 3D Digital Twin (Industrial Grade)

**Developed by: Hafida Belayd**
**Project: Physical AI - ABA Fusion (Semaine 2)**

This project features a multi-agent Automated Guided Vehicle (AGV) Fleet simulator using a **Cyber-Physical Architecture**. It synchronizes a real-world ESP32-based physical robot with a **3D Digital Twin** (WebSockets + React Three Fiber). 

*Note: The legacy 2D Pygame simulator has been fully deprecated in favor of this advanced 3D Web architecture.*

---

## 🏗️ System Architecture & Features

### 1. The 3D Digital Twin (React + Three.js)
* **Headless Server (`headless_simulator.py`):** Computes Dijkstra paths, runs obstacle detection, handles Zone X Mutex locks, and hosts an async WebSocket server at `ws://localhost:8765` broadcasting telemetry frames at **10 Hz** for fluid 3D updates.
* **3D React Client (`frontend/`):** React + Three.js + React Three Fiber (R3F) application. Renders zones, paths, and dynamic AGV 3D meshes. Features a **Cyber-Industrial Theme** (Dark Mode `Deep Navy`) with highly responsive UI dashboard overlays.

### 2. Dual Safety System & HC-SR04 Integration
To guarantee absolute safety against network latency, a two-layer collision prevention system is active:
* **Hardware Override (C++):** The ESP32 scans using an HC-SR04 ultrasonic sensor. If an obstacle is detected `< 20 cm`, the microcontroller instantly cuts power to the motors independently of the Python server.
* **Software Confirmation (Python):** The sensor distance is published via MQTT. The Digital Twin registers the obstacle, shifts the agent to a `STOP` state, and prevents further trajectory generation.

### 3. Failsafe Mechanisms & Latency Optimization
* **Command Watchdog Timer:** The ESP32 implements a 1.5-second (1500ms) Watchdog. If the Python server crashes or stops sending commands, the physical robot triggers an emergency stop to prevent rogue movement.
* **Connection-Loss Protection:** If the Wi-Fi or MQTT connection drops, the ESP32 halts all motors instantly before attempting any blocking reconnection logic.
* **Optimized Latency:** The physical robot streams telemetry to the Dashboard every 200ms (5 Hz), providing a highly synchronized Real-Time response.

### 4. Interactive Manual Dispatch & Abort Missions
* **Manual Dispatching HUD:** Each AGV telemetry card in the React interface features a **MANUAL DISPATCH** button panel (`[A]`, `[B]`, `[C]`, `[D]`, `[R]`). 
* **Soft Reset / Abort Mission:** A prominent `ABORT MISSIONS` button allows operators to instantly cancel current trajectories, release Mutex locks, and halt the robots in place (`IDLE`), ready for a new command.
* **E-Stop Override:** Instantly halts all fleet movement while preserving current mission data.

### 5. Traffic Coordination (Zone X Mutex)
* **ZONE X:** A central critical intersection. Access is regulated via a mutual exclusion lock (`ZoneXTrafficController`).
* **Enhanced Traceability:** The Python backend explicitly logs terminal traces when an AGV requests, is denied, or releases access to the Critical Zone, while the React Dashboard flashes a prominent ⚠️ Red Alert banner.

### 6. Cloud Telemetry & MQTT
* **HiveMQ Cloud MQTT Broker:** The system uses TLS-encrypted MQTT to sync the ESP32 Hardware with the Python Backend over `hafida/robot/twin2/telemetry` and `hafida/robot/twin2/command`.

---

## 📂 File Directory

* `requirements.txt` - Python dependency requirements.
* `warehouse_map.py` - Coordinate node graph, Dijkstra pathfinder, and Zone X Mutex traffic controller.
* `agv_agent.py` - AGV class, physics, states, sensor cone logic, differential drive, and JSON payloads.
* `telemetry_sender.py` - Asynchronous background Queue logger (HTTP Webhook POST, MQTT Bridge).
* `headless_simulator.py` - Backend WebSocket streaming server for the 3D twin.
* `../main/main.cpp` - C++ Source Code for the physical ESP32 AGV controller (WiFi, MQTT, HC-SR04, L298N, Watchdog).
* `documentation_jour_3.pdf` - Comprehensive technical documentation of the Dual Safety & 3D Dashboard.
* **`frontend/`** - React-Vite Web Project.
  * `src/App.jsx` - Core React logic handling WebSocket dispatching, telemetry, and the HUD.
  * `src/Warehouse3D.jsx` - Three.js scene containing 3D zones, grid mesh, paths, and dynamic AGV boxes.
  * `src/index.css` - Cyber-Industrial Dark Theme CSS.

---

## 🚀 Running Instructions

### 1. Flash Physical Hardware (ESP32)
1. Open `../main/main.cpp` in the Arduino IDE or PlatformIO.
2. Enter your Wi-Fi credentials and upload to the ESP32.

### 2. Start the Digital Twin (Python Backend)
```bash
pip install -r requirements.txt
python3 headless_simulator.py
```

### 3. Start the React Dashboard (Frontend)
Open a separate terminal window:
```bash
cd frontend
npm run dev
```
Visit **[http://localhost:5173/](http://localhost:5173/)** in your browser.
