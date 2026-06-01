import time
import os
import json
from warehouse_map import ZoneXTrafficController
from agv_agent import AGV
from telemetry_sender import TelemetrySender

def test_headless_simulation():
    print("Testing AGV Simulator Headless Engine...")
    
    # 1. Initialize components
    agv1 = AGV("AGV-01", "A", (255, 0, 0))
    agv2 = AGV("AGV-02", "B", (0, 0, 255))
    traffic_controller = ZoneXTrafficController()
    
    # Start telemetry sender with dummy local listener URL
    telemetry_sender = TelemetrySender(webhook_url="http://127.0.0.1:5000/webhook")
    
    # Clear logs file
    if os.path.exists("telemetry_logs.json"):
        os.remove("telemetry_logs.json")
        
    # 2. Trigger missions
    print("Planning initial missions...")
    agv1.start_mission("D") # Requires Zone X
    agv2.start_mission("C") # Requires Zone X
    
    print(f"AGV-01 Path: {agv1.path}")
    print(f"AGV-02 Path: {agv2.path}")
    
    # 3. Simulate 10 seconds of movements (fast step: dt=0.5s, 20 iterations)
    dt = 0.5
    print("\nRunning headless simulation physics loop...")
    for step in range(20):
        # Update positions
        agv1.update(dt, agv2, traffic_controller)
        agv2.update(dt, agv1, traffic_controller)
        
        # Submit telemetry every 3 iterations (~1.5s simulated time)
        if step % 3 == 0:
            payload1 = agv1.get_telemetry_payload()
            payload2 = agv2.get_telemetry_payload()
            
            # Print state details for first few cycles
            if step <= 6:
                print(f"  [Step {step:02d}] AGV-01: pos=({payload1['position']['x']}, {payload1['position']['y']}), state={payload1['state']}, zone={payload1['position']['zone']}, bat={payload1['battery_pct']}%")
                print(f"            AGV-02: pos=({payload2['position']['x']}, {payload2['position']['y']}), state={payload2['state']}, zone={payload2['position']['zone']}, bat={payload2['battery_pct']}%")
            
            telemetry_sender.submit_telemetry(payload1)
            telemetry_sender.submit_telemetry(payload2)
            
        time.sleep(0.05) # Keep tests fast

    # Clean shutdown
    print("\nStopping telemetry sender...")
    telemetry_sender.stop()
    
    # 4. Verify logs file was generated and schema is correct
    print("\nChecking generated telemetry_logs.json file...")
    if not os.path.exists("telemetry_logs.json"):
        print("❌ Error: telemetry_logs.json was not created!")
        return False
        
    with open("telemetry_logs.json", "r") as f:
        lines = f.readlines()
        
    print(f"Successfully generated {len(lines)} telemetry entries.")
    if len(lines) == 0:
        print("❌ Error: telemetry_logs.json is empty!")
        return False
        
    # Read the first line and validate structure
    first_log = json.loads(lines[0].strip())
    print("\nFirst logged JSON Payload:")
    print(json.dumps(first_log, indent=2))
    
    # Check schema fields
    required_fields = {
        "agv_id", "state", "battery_pct", "mission_id", "speed_mps", 
        "position", "target_zone", "distance_front_cm", "temperature_c", "connectivity_status"
    }
    
    missing = required_fields - first_log.keys()
    if missing:
        print(f"❌ Error: Missing required fields: {missing}")
        return False
        
    # Verify sub-position coordinates
    if not isinstance(first_log.get("position"), dict) or not all(k in first_log["position"] for k in ["x", "y", "zone"]):
        print("❌ Error: position format is incorrect!")
        return False
        
    print("\n✅ Verification Successful: Telemetry schema is 100% compliant!")
    return True

if __name__ == '__main__':
    test_headless_simulation()
