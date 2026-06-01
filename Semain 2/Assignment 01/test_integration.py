import time
import os
import json
from warehouse_map import ZoneXTrafficController
from agv_agent import AGV
from telemetry_sender import TelemetrySender

def test_headless_simulation():
    print("Testing AGV Simulator Headless Engine...")
    
    # 1. Initialisation de nos différents composants
    agv1 = AGV("AGV-01", "A", (255, 0, 0))
    agv2 = AGV("AGV-02", "B", (0, 0, 255))
    traffic_controller = ZoneXTrafficController()
    
    # Démarrage de la télémétrie en la branchant sur l'écouteur local Flask
    telemetry_sender = TelemetrySender(webhook_url="http://127.0.0.1:5000/webhook")
    
    # Nettoyage de l'ancien fichier de logs s'il existe
    if os.path.exists("telemetry_logs.json"):
        os.remove("telemetry_logs.json")
        
    # 2. Assignation des missions de départ
    print("Planning initial missions...")
    agv1.start_mission("D") # Nécessite de traverser le carrefour central Zone X
    agv2.start_mission("C") # Nécessite de traverser le carrefour central Zone X
    
    print(f"AGV-01 Path: {agv1.path}")
    print(f"AGV-02 Path: {agv2.path}")
    
    # 3. Simulation de 10 secondes de mouvements rapides (pas de temps dt = 0.5s, 20 itérations)
    dt = 0.5
    print("\nRunning headless simulation physics loop...")
    for step in range(20):
        # Mise à jour des positions des deux robots
        agv1.update(dt, agv2, traffic_controller)
        agv2.update(dt, agv1, traffic_controller)
        
        # Envoi de la télémétrie toutes les 3 itérations (ce qui fait environ 1,5s simulées)
        if step % 3 == 0:
            payload1 = agv1.get_telemetry_payload()
            payload2 = agv2.get_telemetry_payload()
            
            # Affichage des informations d'état pour les premiers cycles
            if step <= 6:
                print(f"  [Step {step:02d}] AGV-01: pos=({payload1['position']['x']}, {payload1['position']['y']}), state={payload1['state']}, zone={payload1['position']['zone']}, bat={payload1['battery_pct']}%")
                print(f"            AGV-02: pos=({payload2['position']['x']}, {payload2['position']['y']}), state={payload2['state']}, zone={payload2['position']['zone']}, bat={payload2['battery_pct']}%")
            
            telemetry_sender.submit_telemetry(payload1)
            telemetry_sender.submit_telemetry(payload2)
            
        time.sleep(0.05) # Petit délai pour laisser le temps d'exécution tout en restant rapide

    # Extinction propre du système
    print("\nStopping telemetry sender...")
    telemetry_sender.stop()
    
    # 4. Vérification que le fichier de logs a bien été créé et que sa structure est correcte
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
        
    # On charge la première ligne pour valider sa structure JSON
    first_log = json.loads(lines[0].strip())
    print("\nFirst logged JSON Payload:")
    print(json.dumps(first_log, indent=2))
    
    # On liste les champs qui doivent obligatoirement être présents
    required_fields = {
        "agv_id", "state", "battery_pct", "mission_id", "speed_mps", 
        "position", "target_zone", "distance_front_cm", "temperature_c", "connectivity_status"
    }
    
    missing = required_fields - first_log.keys()
    if missing:
        print(f"❌ Error: Missing required fields: {missing}")
        return False
        
    # Vérification du sous-dictionnaire contenant les coordonnées de position
    if not isinstance(first_log.get("position"), dict) or not all(k in first_log["position"] for k in ["x", "y", "zone"]):
        print("❌ Error: position format is incorrect!")
        return False
        
    print("\n✅ Verification Successful: Telemetry schema is 100% compliant!")
    return True

if __name__ == '__main__':
    test_headless_simulation()
