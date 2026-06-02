import serial
import time
import json
import asyncio
import websockets

# ==========================================
# CONFIGURATION
# ==========================================
PORT = '/dev/cu.usbserial-110'
BAUD_RATE = 9600
WEBSOCKET_URI = "ws://localhost:8765"

current_serial_state = "0,0\n"

# ==========================================
# ASYNC MAIN LOOP (SERIAL + WEBSOCKETS)
# ==========================================
async def run_physical_agv():
    global current_serial_state
    
    # 1. Connect to Arduino
    arduino = None
    try:
        print(f"Connecting to Arduino on {PORT}...")
        arduino = serial.Serial(PORT, BAUD_RATE, timeout=1)
        await asyncio.sleep(2)
        print("✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection error: {e}")

    print("\n--- Physical AGV Controller ---")
    print("Listening to AI Simulator at ws://localhost:8765...")
    print("AGV-01 Speed -> Motor 1")
    print("AGV-02 Speed -> Motor 2")
    print("[Ctrl+C] to Quit\n")

    # 2. Connect to WebSocket and Listen
    while True:
        try:
            async with websockets.connect(WEBSOCKET_URI) as ws:
                print(f"✅ Connected to Dashboard WebSocket at {WEBSOCKET_URI}")
                
                async for message in ws:
                    try:
                        payload = json.loads(message)
                        
                        m1 = 0
                        m2 = 0
                        m3 = 0
                        m4 = 0
                        
                        is_paused = payload.get("paused", False)
                        is_estop = payload.get("emergency_stop", False)
                        
                        if not is_paused and not is_estop:
                            if "motor_speeds" in payload:
                                ms = payload["motor_speeds"]
                                m1 = ms.get("m1", 0)
                                m2 = ms.get("m2", 0)
                                m3 = ms.get("m3", 0)
                                m4 = ms.get("m4", 0)
                        
                        # === Update Serial ===
                        new_state = f"{m1},{m2},{m3},{m4}\n"
                        if new_state != current_serial_state:
                            if arduino and arduino.is_open:
                                arduino.write(new_state.encode())
                            current_serial_state = new_state
                            
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        print(f"Error parsing message: {e}")
                        
        except websockets.exceptions.ConnectionClosed:
            print("⚠️ Connection to Simulator closed. Reconnecting in 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"⚠️ Could not connect to WebSocket Dashboard: {e}. Retrying in 3s...")
            await asyncio.sleep(3)

if __name__ == '__main__':
    try:
        asyncio.run(run_physical_agv())
    except KeyboardInterrupt:
        print("\nDisconnected from WebSocket.")
