# AGV Fleet Simulator & 3D Digital Twin

**Developed by: Hafida Belayd**

This directory contains a multi-agent Automated Guided Vehicle (AGV) Fleet simulator with a **Dual-Architecture Design**:
1. **2D Pygame Simulator:** A local desktop application featuring a minimalist dark-mode HUD.
2. **3D Digital Twin (WebSockets + React Three Fiber):** A headless Python backend coordinating fleet physics and path planning, paired with a web-based 3D Three.js frontend rendering the warehouse in real time.

---

## 🏗️ System Architecture & Features

### 1. Dual-Simulation Modes
* **2D Desktop Mode (`simulator.py`):** Runs the Pygame visualization loop with grid overlay, zones, dynamic sensor cones, and a telemetry side-panel dashboard.
* **3D Digital Twin Mode:**
  * **Headless Server (`headless_simulator.py`):** Removes rendering overhead. Computes Dijkstra paths, runs obstacle detection, handles Zone X Mutex locks, and hosts an async WebSocket server at `ws://localhost:8765` broadcasting telemetry frames at **10 Hz** for fluid 3D updates.
  * **3D React Client (`frontend/`):** React + Three.js + React Three Fiber (R3F) application that connects to the WebSockets stream. Renders zones as flat floor planes, paths as lines, and AGVs as 3D block meshes with OrbitControls (allowing rotate, pan, and zoom).

### 2. Interactive Manual Dispatch & Diverse Trajectories
* **Manual Dispatching HUD:** Each AGV telemetry card in the React interface features a **MANUAL DISPATCH** button panel (`[A]`, `[B]`, `[C]`, `[D]`, `[R]`). Users can click any button to send an override command via WebSockets, instantly planning a route and sending the AGV to that zone.
* **Diversified Autonomous Paths:** Idle AGVs automatically choose new targets from any warehouse zone different from their current position. This produces varied horizontal, vertical, and diagonal paths across the map.

### 3. Traffic Coordination & Mutex
* **ZONE X:** A central critical intersection. Access is regulated via a mutual exclusion lock (`ZoneXTrafficController` mutex). Only one AGV is granted entry. Yielding AGVs wait at the gate and transition to a `WAIT` state.
* **Lane Offsets:** AGVs automatically offset their position to the right relative to their heading (like road traffic) to allow passing on two-way lines.

### 4. Collision Avoidance, Safety Halting & Wifi Dropping
* **Collision Avoidance:** Proximity sensor (`distance_front_cm`) scans in a 45-degree forward cone. If a leading AGV is detected closer than **80 cm**, the trailing AGV performs a safety halt (`STOP` state) until the path is clear.
* **E-Stop Override:** When the emergency stop is triggered (Key `E` or `S` in desktop mode, or clicking **STOP FLEET (E-STOP)** in the web view), AGVs instantly halt all movement, set speed to `0.0`, and enter the `"STOP"` state.
* **Connectivity Dropouts:** Simulates real-world Wi-Fi drops by having AGVs occasionally lose connection (marked `OFFLINE` on telemetry HUD cards) for brief half-second drops while maintaining safe edge-computing physical navigation.

### 5. Telemetry Gateways
* **Local Logs:** Payloads are logged asynchronously to `telemetry_logs.json` in NDJSON (JSON Lines) format every **1.5 seconds**.
* **HTTP Webhook:** Pushes payload snapshots to a local webhook server at `http://127.0.0.1:5000/webhook` every **1.5 seconds**.
* **Cloud MQTT Broker:** Connects securely to the **HiveMQ Cloud MQTT Broker** (`ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud`) on port **8883** using TLS socket wrapping and authenticated user credentials, publishing payloads to `warehouse/agv/telemetry`.

---

## 📂 File Directory

* [requirements.txt](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/requirements.txt) - Python dependency requirements.
* [warehouse_map.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/warehouse_map.py) - Coordinate node graph, Dijkstra pathfinder, and Zone X Mutex traffic controller.
* [agv_agent.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/agv_agent.py) - AGV class, physics, states, sensor cone logic, and JSON payload generators.
* [telemetry_sender.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/telemetry_sender.py) - Asynchronous background Queue logger (file append, HTTP Webhook POST, MQTT).
* [webhook_server.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/webhook_server.py) - Zero-dependency HTTP receiver on port 5000 that logs incoming telemetry.
* [simulator.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/simulator.py) - Desktop Pygame simulation executable.
* [headless_simulator.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/headless_simulator.py) - Backend WebSocket streaming server for the 3D twin.
* **[frontend/](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/frontend/)** - React-Vite web project.
  * [src/App.jsx](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/frontend/src/App.jsx) - App core managing WebSocket listeners and HTML HUD overlay cards.
  * [src/Warehouse3D.jsx](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/frontend/src/Warehouse3D.jsx) - Three.js scene containing 3D zones, grid mesh, paths, and dynamic AGV boxes.
  * [src/index.css](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/frontend/src/index.css) - CSS overlay styles for glassmorphism HUD and flat progress bars.
* [test_integration.py](file:///Users/hafida/Documents/Physical-AI---ABA-Fusion/Semain%202/Assignment%2001/test_integration.py) - Headless test suite validating physics and telemetry schema.

---

## 🚀 Running Instructions

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Telemetry Webhook Receiver (Optional)
In a separate terminal tab:
```bash
python3 webhook_server.py
```

### 3. Choose Running Mode

#### Mode A: 2D Pygame Simulator (Desktop)
Run the desktop GUI directly:
```bash
python3 simulator.py
```
* **`SPACE`:** Pause/Resume physics.
* **`E` or `S`:** Trigger Emergency Stop / Stop.
* **`ESC`:** Close window and exit.

---

#### Mode B: 3D Digital Twin (Web Canvas)
1. **Start the Headless WebSocket Server:**
   ```bash
   python3 headless_simulator.py
   ```
2. **Start the React Frontend:**
   Open a separate terminal window inside the `frontend` folder and run:
   ```bash
   cd frontend
   npm run dev
   ```
3. **Open the Webpage:**
   Visit **[http://localhost:5173/](http://localhost:5173/)** in your browser.
   * **Left-Click + Drag:** Rotate 3D map.
   * **Right-Click + Drag:** Pan 3D map.
   * **Scroll Wheel:** Zoom.

---

## 📋 Telemetry Payload Schema
Each telemetry log conforms exactly to this JSON schema:
```json
{
  "agv_id": "AGV-01",
  "state": "EN_ROUTE",
  "battery_pct": 78,
  "mission_id": "M-2026-06-01-01-01",
  "speed_mps": 0.85,
  "position": {
    "x": 1.5,
    "y": 4.0,
    "zone": "A"
  },
  "target_zone": "D",
  "distance_front_cm": 135,
  "temperature_c": 28.6,
  "connectivity_status": "ONLINE"
}
```
