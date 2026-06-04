# AGV Fleet Simulator & 3D Digital Twin (Industrial Grade)

**Developed by: Hafida Belayd & Abdelkhalek Hanbel**  
**Project: Physical AI - ABA Fusion (Semaine 2)**

This project features a multi-agent Automated Guided Vehicle (AGV) Fleet simulator using a **Cyber-Physical Architecture**. It synchronizes a real-world ESP32-based physical robot with a **3D Digital Twin** (WebSockets + React Three Fiber).

---

## 🏗️ System Architecture & Premium Features

### 1. Futuristic 3D Digital Twin Dashboard (React + Vite)
* **Glassmorphism Panels:** The HUD overlay control panel uses a frosted glass style (`backdrop-filter: blur(20px)`) with glowing border highlights (`rgba(255,255,255,0.08)`) and custom-designed dark-space color tokens.
* **Modern Typography:** Integrated Google Fonts **Outfit** for legible system metrics and **Space Grotesk** for headings and title widgets.
* **Micro-interactions:** Responsive cards slide and scale on hover (`transform: translateY(-4px)`) with dynamic shadows, while range sliders and scrollbars are customized with sleek, thin styling.
* **Junction Nodes Mapping:** Replaced simple nodes with blue emissive spherical markers at all road intersections, forming a glowing path coordinates layout in the 3D warehouse.

### 2. High-Fidelity 3D AGV Robot Models
* **Spinning LIDAR Sensor:** Each virtual AGV model renders a detailed LIDAR sensor housing with a continuously rotating head and a red laser diode dot indicating active laser scanning.
* **Dynamic State LEDs:** A status LED lens on the AGV model changes colors to match the vehicle's state (Green: moving, Orange: waiting/yielding, Red: stopped, Rose: critical intersection warning).
* **Floor PointLight Reflection:** A point-light source is attached to the AGV status LED, projecting a colored glow on the warehouse grid lines based on the robot's real-time movements.

### 3. Dual Safety System & HC-SR04 Integration
* **Hardware Override (C++ Edge Safety):** The physical ESP32 scans surroundings using an HC-SR04 ultrasonic sensor. If an obstacle is detected `< 20 cm`, the microcontroller instantly cuts power to the motors independently of the Python simulation to prevent collisions.
* **Software Confirmation (Python Layer):** The sensor distance is published via MQTT. The Digital Twin registers the obstacle, shifts the agent to a `STOP` state, and prevents further trajectory generation.

### 4. Smart ESP32 Hardware Screen & Custom Icons
* **Boot Loader Animation:** Features an animated 16-character progress loading bar (`[████████░░░░]`) displaying `Booting AGV OS... 🤖` tliha `System Active! ❤️` at startup.
* **Custom Character Sets:** Registered custom icon matrices in the LCD's memory for high-fidelity physical feedback:
  - `🤖` (Robot Icon) beside speed output.
  - `🔋` (Battery Icon) beside power level.
  - `❤️` (Heartbeat Icon) blinking to show active network loop connections.
  - `⚠️` (Warning Icon) flashing in place of the heartbeat if an obstacle is too close.

### 5. Failsafes & Latency Optimization
* **Command Watchdog Timer:** The ESP32 implements a 1.5-second (1500ms) Watchdog. If the Python server crashes or stops sending commands, the physical robot triggers an emergency stop.
* **Connection-Loss Protection:** If the Wi-Fi or MQTT connection drops, the ESP32 halts all motors instantly before attempting any blocking reconnection logic.
* **Optimized Latency:** The physical robot streams telemetry to the Dashboard every 200ms (5 Hz), providing a highly synchronized real-time response.

### 6. Traffic Coordination (Zone X Mutex)
* **ZONE X:** A central critical intersection. Access is regulated via a mutual exclusion lock (`ZoneXTrafficController`).
* **Dashboard Warning Flag:** When an AGV occupies the intersection, the React HUD overlay displays a flashing alert banner warning operators of critical traffic conditions.

### 7. 🆕 Moroccan Arabic (Darija) Neural TTS Voice System
* **Backend-Driven Speech Generation:** All voice announcements are now generated on the Python backend using **Microsoft Edge TTS** (`edge-tts` Python package), completely replacing the unreliable browser-level `speechSynthesis` API.
* **High-Quality Neural Voice:** Uses the `ar-MA-MounaNeural` neural voice — a native **Moroccan Arabic (Darija)** voice model that delivers natural, high-fidelity pronunciation of all system announcements.
* **WebSocket Audio Streaming:** The Python backend generates MP3 audio (~26KB per announcement), encodes it as **Base64**, and broadcasts it through the existing WebSocket connection as a `{"type": "speech", "audio": "..."}` payload.
* **Browser Audio Playback:** The React frontend receives the speech payload and plays it using the Web Audio API (`new Audio("data:audio/mp3;base64,...").play()`), requiring zero additional dependencies.
* **Event-Triggered Announcements in Darija:** The following events trigger spoken Darija announcements:
  - 🛑 **E-Stop Activated:** *"توقيف الطوارئ تخدم، الأسطول كامل وقف."*
  - ✅ **E-Stop Cleared:** *"حيد توقف الطوارئ، الأسطول رجع يخدم."*
  - ⏸️ **Fleet Paused:** *"الأسطول موقف دابا."*
  - ▶️ **Fleet Resumed:** *"الأسطول رجع يخدم دابا."*
  - 🚗 **Dispatch to Zone:** *"العربة آ جي في واحد غادة دابا لمنطقة [Zone]."*
  - ⚠️ **Zone X Entry:** *"رد البال، العربة دخلات لمنطقة التقاطع الخطيرة إكس."*
  - 🚧 **Obstacle Detected:** *"حضي راسك، كاين عائق قدام العربة. جاري إعادة حساب مسار جديد."*
  - 🗺️ **Lane Blocked (Re-routing):** *"كاين طريق مقطوعة. جاري إعادة حساب مسار جديد باستعمال ديكسترا."*
  - 🧹 **Obstacles Cleared:** *"تمت إزالة الحواجز والعوائق، الطريق دابا مسرحة."*
  - 🔊 **Voice Test:** *"فحص الصوت خدام مزيان، النظام دابا أونلاين."*

---

## 📂 File Directory

* `requirements.txt` - Python dependency requirements (includes `edge-tts` for Darija TTS).
* `warehouse_map.py` - Coordinate node graph, Dijkstra pathfinder, and Zone X Mutex traffic controller.
* `agv_agent.py` - AGV class, physics, states, sensor cone logic, differential drive, and JSON payloads.
* `telemetry_sender.py` - Asynchronous background Queue logger (HTTP Webhook POST, MQTT Bridge).
* `headless_simulator.py` - Backend WebSocket streaming server for the 3D twin. Hosts the Darija TTS generator (`generate_darija_speech`) and announcement broadcaster (`announce`).
* `../main/main.cpp` - C++ Source Code for the physical ESP32 AGV controller (WiFi, MQTT, HC-SR04, L298N, LCD boot loader, Custom characters, Watchdog).
* **`frontend/`** - React-Vite Web Project.
  * `src/App.jsx` - Core React logic handling WebSocket dispatching, glassmorphic HUD controls, dashboard indicators, and base64 MP3 audio playback from backend TTS.
  * `src/Warehouse3D.jsx` - Three.js scene containing glowing junction nodes, grid mesh, zones, and dynamic AGV LIDAR/LED models.
  * `src/index.css` - Custom cyber-industrial glassmorphism dark theme CSS using Outfit & Space Grotesk Google Fonts.

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

### 4. 🔊 Test the Darija Voice System
1. Open the dashboard at `http://localhost:5173/`
2. Click anywhere on the page first (required by browsers to unlock audio)
3. Click the **🔊 Test Voice** button in the top-right header
4. You will hear: *"فحص الصوت خدام مزيان، النظام دابا أونلاين."*
