import serial
import time
import json
import asyncio
import websockets
from pynput import keyboard

# ==========================================
# CONFIGURATION
# ==========================================
PORT = '/dev/cu.usbserial-1110'
BAUD_RATE = 9600
WEBSOCKET_URI = "ws://localhost:8765"

# ==========================================
# GLOBAL STATE
# ==========================================
pressed_keys = set()
current_serial_state = "0,0\n"
arduino = None

# We simulate a virtual position so the dashboard can draw it
virtual_x = 4.0
virtual_y = 4.0
virtual_zone = "X"
virtual_speed = 0.0

# ==========================================
# KEYBOARD LISTENER
# ==========================================
def on_press(key):
    try:
        pressed_keys.add(key.char.lower())
    except AttributeError:
        pressed_keys.add(key)

def on_release(key):
    try:
        if key.char.lower() in pressed_keys:
            pressed_keys.remove(key.char.lower())
    except AttributeError:
        if key in pressed_keys:
            pressed_keys.remove(key)

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

# ==========================================
# ASYNC MAIN LOOP (SERIAL + WEBSOCKETS)
# ==========================================
async def run_physical_agv():
    global current_serial_state, arduino, virtual_x, virtual_y, virtual_speed
    
    # 1. Connect to Arduino
    try:
        print(f"Connecting to Arduino on {PORT}...")
        arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
        await asyncio.sleep(2)
        print("✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        arduino = None

    print("\n--- AGV Motor & LCD Telemetry ---")
    print("MOTOR 1 : [A] Forward | [Z] Backward")
    print("MOTOR 2 : [Q] Forward | [S] Backward")
    print("[ESC]   : Quit script\n")

    # 2. Connect to WebSocket
    ws = None
    try:
        ws = await websockets.connect(WEBSOCKET_URI)
        print(f"✅ Connected to Dashboard WebSocket at {WEBSOCKET_URI}")
    except Exception as e:
        print(f"⚠️ Could not connect to WebSocket Dashboard: {e}")

    try:
        while True:
            # === Read Keys ===
            m1 = 0
            m2 = 0
            
            if 'a' in pressed_keys:
                m1 = 255
            elif 'z' in pressed_keys:
                m1 = -255

            if 'q' in pressed_keys:
                m2 = 255
            elif 's' in pressed_keys:
                m2 = -255

            if keyboard.Key.esc in pressed_keys:
                print("Closing program...")
                break

            # === Update Serial ===
            new_state = f"{m1},{m2}\n"
            if new_state != current_serial_state:
                if arduino and arduino.is_open:
                    arduino.write(new_state.encode())
                current_serial_state = new_state
                
            # === Simulate Virtual Position for Dashboard ===
            # We map motor inputs to a rough coordinate update (assuming forward = +Y, left/right = X)
            # This is purely visual so the dashboard shows the physical AGV moving!
            dt = 0.05
            speed_m1 = m1 / 255.0  # -1.0 to 1.0
            speed_m2 = m2 / 255.0  # -1.0 to 1.0
            
            forward_speed = (speed_m1 + speed_m2) / 2.0
            turn_speed = (speed_m1 - speed_m2) / 2.0
            
            virtual_speed = abs(forward_speed) + abs(turn_speed)
            
            # Simple arcade movement (not physically accurate, just visual)
            virtual_y += forward_speed * dt * 2.0
            virtual_x += turn_speed * dt * 2.0
            
            # Keep within bounds of map (0 to 8 meters)
            virtual_x = max(0.5, min(7.5, virtual_x))
            virtual_y = max(0.5, min(7.5, virtual_y))

            # === Send WebSockets Telemetry ===
            if ws:
                telemetry_payload = {
                    "command": "update_physical",
                    "agent": {
                        "agv_id": "PHYSICAL-AGV",
                        "state": "MANUAL" if virtual_speed > 0 else "IDLE",
                        "battery_pct": 100,
                        "mission_id": "MANUAL-OVERRIDE",
                        "speed_mps": virtual_speed,
                        "position": { "x": virtual_x, "y": virtual_y, "zone": "X" },
                        "target_zone": "MANUAL",
                        "distance_front_cm": 300,
                        "temperature_c": 35.0 + (virtual_speed * 10),
                        "connectivity_status": "ONLINE"
                    }
                }
                try:
                    await ws.send(json.dumps(telemetry_payload))
                except Exception as e:
                    print(f"WS Send error: {e}")

            await asyncio.sleep(0.05) 

    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        if arduino and arduino.is_open:
            arduino.write("0,0\n".encode()) 
            arduino.close()
            print("Disconnected from Arduino.")
        if ws:
            await ws.close()
            print("Disconnected from WebSocket.")

if __name__ == '__main__':
    try:
        asyncio.run(run_physical_agv())
    except KeyboardInterrupt:
        pass
