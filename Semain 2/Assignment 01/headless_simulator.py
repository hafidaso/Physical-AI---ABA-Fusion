import asyncio
import websockets
import json
import time
import random
import sys
from typing import Set

# Local imports
from warehouse_map import ZoneXTrafficController
from agv_agent import AGV
from telemetry_sender import TelemetrySender

# Track connected WebSocket clients
CONNECTED_CLIENTS: Set = set()

# Global Simulation State for frontend control overrides
GLOBAL_STATE = {
    "emergency_stop": False,
    "paused": False
}

# Global dictionary to look up active AGVs for dispatching
AGV_FLEET = {}

async def register(websocket):
    """Registers a new WebSocket connection and listens for control commands."""
    CONNECTED_CLIENTS.add(websocket)
    print(f"🔌 Client connected: {websocket.remote_address}. Active connections: {len(CONNECTED_CLIENTS)}")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")
                if command == "estop":
                    GLOBAL_STATE["emergency_stop"] = not GLOBAL_STATE["emergency_stop"]
                    print(f"⚠️ Emergency Stop toggled via WS: {GLOBAL_STATE['emergency_stop']}")
                elif command == "pause":
                    GLOBAL_STATE["paused"] = not GLOBAL_STATE["paused"]
                    print(f"⏸️ Pause toggled via WS: {GLOBAL_STATE['paused']}")
                elif command == "dispatch":
                    agv_id = data.get("agv_id")
                    target = data.get("target")
                    if agv_id in AGV_FLEET and target:
                        agv_instance = AGV_FLEET[agv_id]
                        if not GLOBAL_STATE["emergency_stop"] and not GLOBAL_STATE["paused"]:
                            agv_instance.start_mission(target)
                            print(f"✈️ Manual dispatch via WS: {agv_id} -> {target}")
            except Exception as e:
                print(f"Error handling WS command: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"🔌 Client disconnected. Active connections: {len(CONNECTED_CLIENTS)}")

async def broadcast(message: str):
    """Sends a message to all connected clients."""
    if CONNECTED_CLIENTS:
        await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS], return_exceptions=True)

async def simulation_loop():
    """Asynchronous physics loop running at 10 Hz (every 100ms) for smooth visual updates."""
    # Setup agents
    agv1 = AGV("AGV-01", "A", (255, 120, 80)) # Warm Coral
    agv2 = AGV("AGV-02", "B", (46, 204, 250)) # Bright Teal
    traffic_controller = ZoneXTrafficController()
    
    # Store globally for access by the WebSocket command handler
    AGV_FLEET["AGV-01"] = agv1
    AGV_FLEET["AGV-02"] = agv2
    
    # Setup background telemetry sender (logs to file, webhook, mqtt)
    telemetry_sender = TelemetrySender(
        webhook_url="http://127.0.0.1:5000/webhook"
    )
    
    dt = 0.1  # 100ms time step
    telemetry_timer = 0.0
    
    print("🤖 Headless Simulator loop started.")
    try:
        while True:
            # 1. Update physics if not paused
            if not GLOBAL_STATE["paused"]:
                # Generate new missions automatically when IDLE
                if agv1.state == "IDLE" and not GLOBAL_STATE["emergency_stop"]:
                    # Select any warehouse zone (A, B, C, D) different from current zone for more diverse movements
                    choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv1.current_zone]
                    agv1.start_mission(random.choice(choices))
                    
                if agv2.state == "IDLE" and not GLOBAL_STATE["emergency_stop"]:
                    choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv2.current_zone]
                    agv2.start_mission(random.choice(choices))
                    
                # Update AGVs physics and collision sensors
                agv1.update(dt, agv2, traffic_controller, GLOBAL_STATE["emergency_stop"])
                agv2.update(dt, agv1, traffic_controller, GLOBAL_STATE["emergency_stop"])
            
            # Fetch current telemetry payloads
            payload1 = agv1.get_telemetry_payload()
            payload2 = agv2.get_telemetry_payload()
            
            # Broadcast state over WebSockets for the 3D Digital Twin frontend
            twin_payload = {
                "timestamp": time.time(),
                "emergency_stop": GLOBAL_STATE["emergency_stop"],
                "paused": GLOBAL_STATE["paused"],
                "agents": [payload1, payload2]
            }
            await broadcast(json.dumps(twin_payload))
            
            # Dispatch logs and webhook alerts every 1.5 seconds (only when not paused)
            if not GLOBAL_STATE["paused"]:
                telemetry_timer += dt
                if telemetry_timer >= 1.5:
                    telemetry_timer = 0.0
                    telemetry_sender.submit_telemetry(payload1)
                    telemetry_sender.submit_telemetry(payload2)
                    print(f"[DT Stream] Telemetry Sent | AGV-01: {payload1['state']} (Bat: {payload1['battery_pct']}%) | AGV-02: {payload2['state']} (Bat: {payload2['battery_pct']}%)")
                
            await asyncio.sleep(dt)
            
    except asyncio.CancelledError:
        print("Stopping simulation loop...")
    finally:
        print("Terminating telemetry threads...")
        telemetry_sender.stop()

async def main():
    # Start WebSocket Server on port 8765
    async with websockets.serve(register, "localhost", 8765):
        print("🚀 Digital Twin WebSocket Server running at ws://localhost:8765")
        print("Press Ctrl+C to terminate.")
        
        # Start the simulator physics loop in parallel
        await simulation_loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
