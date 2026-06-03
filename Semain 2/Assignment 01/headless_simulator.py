import asyncio
import websockets
import json
import time
import random
import sys
from typing import Set

# Imports locaux
from warehouse_map import ZoneXTrafficController
from agv_agent import AGV
from telemetry_sender import TelemetrySender

# Liste des clients WebSocket actuellement connectés
CONNECTED_CLIENTS: Set = set()

# État global de la simulation (contrôlé à distance par l'IHM)
GLOBAL_STATE = {
    "emergency_stop": False,
    "paused": False
}

# Dictionnaire global pour retrouver les AGV actifs lors d'un aiguillage manuel
AGV_FLEET = {}

async def register(websocket):
    """Enregistre un nouveau client WebSocket et écoute les commandes envoyées par l'IHM."""
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
    """Envoie un message à l'ensemble des clients connectés."""
    if CONNECTED_CLIENTS:
        await asyncio.gather(*[client.send(message) for client in CONNECTED_CLIENTS], return_exceptions=True)

async def simulation_loop():
    """Boucle de physique asynchrone tournant à 10 Hz (toutes les 100 ms) pour une animation 3D fluide."""
    # Initialisation de nos deux robots AGV
    agv1 = AGV("AGV-01", "A", (255, 120, 80)) # Warm Coral
    agv2 = AGV("AGV-02", "B", (46, 204, 250)) # Bright Teal
    traffic_controller = ZoneXTrafficController()
    
    # On les enregistre dans notre dictionnaire global pour pouvoir les aiguiller manuellement via WebSocket
    AGV_FLEET["AGV-01"] = agv1
    AGV_FLEET["AGV-02"] = agv2
    
    # Configuration de la télémétrie en arrière-plan (fichiers, MQTT, etc.)
    telemetry_sender = TelemetrySender(
        webhook_url="http://127.0.0.1:5000/webhook",
        mqtt_topic_pub="warehouse/agv/telemetry",
        mqtt_topic_twin="hafida/robot/twin/telemetry",
        mqtt_topic_cmd="hafida/robot/twin/command",
        mqtt_topic_twin2="hafida/robot/twin2/telemetry",
        mqtt_topic_cmd2="hafida/robot/twin2/command",
        mqtt_username="hivemq.webclient.1775653497883",
        mqtt_password="1B%.CwaP:Kdr2I93k*Ap"
    )
    
    dt = 0.1  # Pas de temps de 100 ms
    telemetry_timer = 0.0
    
    print("🤖 Headless Simulator loop started.")
    try:
        while True:
            # Lier les données MQTT aux AGVs
            twin_data_1 = telemetry_sender.get_physical_twin_data("hafida-smart-robot-safety")
            if twin_data_1:
                agv1.is_digital_twin_active = True
                if "distance" in twin_data_1:
                    dist_val = float(twin_data_1["distance"])
                    agv1.distance_front_cm = 300.0 if dist_val <= 0.0 else dist_val
            
            twin_data_2 = telemetry_sender.get_physical_twin_data("hafida-smart-robot-safety-2")
            if twin_data_2:
                agv2.is_digital_twin_active = True
                if "distance" in twin_data_2:
                    dist_val = float(twin_data_2["distance"])
                    agv2.distance_front_cm = 300.0 if dist_val <= 0.0 else dist_val

            # 1. Mise à jour de la physique si la simulation n'est pas en pause
            if not GLOBAL_STATE["paused"]:
                agv1.max_speed_mps = 1.0 # default autonomous speed
                if agv1.state == "IDLE" and not GLOBAL_STATE["emergency_stop"]:
                    choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv1.current_zone]
                    agv1.start_mission(random.choice(choices))
                        
                agv2.max_speed_mps = 1.0
                if agv2.state == "IDLE" and not GLOBAL_STATE["emergency_stop"]:
                    choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv2.current_zone]
                    agv2.start_mission(random.choice(choices))
                    
                # Mise à jour de la physique et des capteurs de distance
                agv1.update(dt, agv2, traffic_controller, GLOBAL_STATE["emergency_stop"])
                agv2.update(dt, agv1, traffic_controller, GLOBAL_STATE["emergency_stop"])
            
            # Récupération des données physiques actuelles
            payload1 = agv1.get_telemetry_payload()
            payload2 = agv2.get_telemetry_payload()
            
            # Calcul des vitesses finales pour les moteurs
            agv1_m1 = int(agv1.motor_left_pct * 255)
            agv1_m2 = int(agv1.motor_right_pct * 255)
            agv2_m1 = int(agv2.motor_left_pct * 255)
            agv2_m2 = int(agv2.motor_right_pct * 255)
            
            # --- DIGITAL TWIN COMMAND: SEND MOTORS TO PHYSICAL ESP32 ---
            m1_1, m3_1 = agv1_m1, agv1_m1
            m2_1, m4_1 = agv1_m2, agv1_m2
            
            m1_2, m3_2 = agv2_m1, agv2_m1
            m2_2, m4_2 = agv2_m2, agv2_m2
            
            # Si le robot physique prend le contrôle total (manuel ou arrêt d'urgence)
            if GLOBAL_STATE["emergency_stop"] or GLOBAL_STATE["paused"]:
                m1_1, m2_1, m3_1, m4_1 = 0, 0, 0, 0
                m1_2, m2_2, m3_2, m4_2 = 0, 0, 0, 0
                
            # Envoyer si changement de vitesse OU toutes les secondes (Keep-alive)
            current_time = time.time()
            if not hasattr(telemetry_sender, 'last_sent_motors') or \
               telemetry_sender.last_sent_motors != (m1_1, m2_1, m3_1, m4_1) or \
               (current_time - getattr(telemetry_sender, 'last_motor_send_time', 0) > 1.0):
                
                telemetry_sender.send_motor_command(telemetry_sender.mqtt_topic_cmd, m1_1, m2_1, m3_1, m4_1)
                telemetry_sender.last_sent_motors = (m1_1, m2_1, m3_1, m4_1)
                telemetry_sender.last_motor_send_time = current_time

            # For AGV-02
            if not hasattr(telemetry_sender, 'last_sent_motors_2') or \
               telemetry_sender.last_sent_motors_2 != (m1_2, m2_2, m3_2, m4_2) or \
               (current_time - getattr(telemetry_sender, 'last_motor_send_time_2', 0) > 1.0):
                
                telemetry_sender.send_motor_command(telemetry_sender.mqtt_topic_cmd2, m1_2, m2_2, m3_2, m4_2)
                telemetry_sender.last_sent_motors_2 = (m1_2, m2_2, m3_2, m4_2)
                telemetry_sender.last_motor_send_time_2 = current_time
            
            # Envoi des données en temps réel au jumeau numérique 3D
            twin_payload = {
                "timestamp": time.time(),
                "emergency_stop": GLOBAL_STATE["emergency_stop"],
                "paused": GLOBAL_STATE["paused"],
                "agents": [payload1, payload2],
                "motor_speeds": {
                    "m1": agv1_m1,
                    "m2": agv1_m2,
                    "m3": agv2_m1,
                    "m4": agv2_m2
                }
            }
            await broadcast(json.dumps(twin_payload))
            
            # Enregistrement des logs et requêtes webhook toutes les 1,5 secondes (si pas en pause)
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
    # Lancement du serveur WebSockets sur le port 8765
    async with websockets.serve(register, "localhost", 8765):
        print("🚀 Digital Twin WebSocket Server running at ws://localhost:8765")
        print("Press Ctrl+C to terminate.")
        
        # Lancement de la boucle physique en parallèle
        await simulation_loop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
