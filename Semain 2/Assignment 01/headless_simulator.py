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
    "paused": True,  # Starts paused by default
    "speed": 50,
    "blocked_edges": set()
}

# Dictionnaire global pour retrouver les AGV actifs lors d'un aiguillage manuel
AGV_FLEET = {}
TRAFFIC_CONTROLLER = ZoneXTrafficController()
TELEMETRY_SENDER_REF = None

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
                elif command == "set_speed":
                    speed_val = int(data.get("value", 150))
                    GLOBAL_STATE["speed"] = speed_val
                    if TELEMETRY_SENDER_REF is not None:
                        TELEMETRY_SENDER_REF.send_string_command(TELEMETRY_SENDER_REF.mqtt_topic_cmd2, f"SPEED:{speed_val}")
                    print(f"⚡ Speed set to {speed_val} via WS")
                elif command == "dispatch":
                    agv_id = data.get("agv_id")
                    target = data.get("target")
                    if agv_id in AGV_FLEET and target:
                        agv_instance = AGV_FLEET[agv_id]
                        if not GLOBAL_STATE["emergency_stop"] and not GLOBAL_STATE["paused"]:
                            agv_instance.start_mission(target)
                            print(f"✈️ Manual dispatch via WS: {agv_id} -> {target}")
                elif command == "reset":
                    agv_id = data.get("agv_id")
                    if agv_id in AGV_FLEET:
                        AGV_FLEET[agv_id].abort_mission(TRAFFIC_CONTROLLER)
                        print(f"🔄 Soft Reset via WS: {agv_id}")
                    elif agv_id == "ALL":
                        for agv in AGV_FLEET.values():
                            agv.abort_mission(TRAFFIC_CONTROLLER)
                        print(f"🔄 Soft Reset ALL via WS")
                elif command == "reset_to_start":
                    if "AGV-01" in AGV_FLEET:
                        agv_instance = AGV_FLEET["AGV-01"]
                        agv_instance.abort_mission(TRAFFIC_CONTROLLER)
                        from warehouse_map import NODES
                        start_coords = NODES[START_ZONE]
                        agv_instance.x = float(start_coords[0])
                        agv_instance.y = float(start_coords[1])
                        agv_instance.current_zone = START_ZONE
                        agv_instance.target_zone = START_ZONE
                        # Envoyer un STOP au robot physique
                        if TELEMETRY_SENDER_REF is not None:
                            TELEMETRY_SENDER_REF.send_string_command(TELEMETRY_SENDER_REF.mqtt_topic_cmd2, "STOP")
                        # Forcer l'état de pause de la simulation
                        GLOBAL_STATE["paused"] = True
                        print(f"🔄 Reset to START_ZONE ({START_ZONE}) and paused via WS")
                elif command == "simulate_obstacle":
                    if "AGV-01" in AGV_FLEET:
                        agv_instance = AGV_FLEET["AGV-01"]
                        if len(agv_instance.path) > 0 and agv_instance.current_node_idx > 0:
                            prev_node = agv_instance.path[agv_instance.current_node_idx - 1]
                            curr_node = agv_instance.path[agv_instance.current_node_idx]
                            GLOBAL_STATE["blocked_edges"].add((prev_node, curr_node))
                            GLOBAL_STATE["blocked_edges"].add((curr_node, prev_node))
                            print(f"⚠️ Simulated obstacle on segment {prev_node}-{curr_node}")
                elif command == "clear_obstacles":
                    GLOBAL_STATE["blocked_edges"].clear()
                    if "AGV-01" in AGV_FLEET:
                        AGV_FLEET["AGV-01"].blocked_edges.clear()
                    print("🧹 Cleared all blocked lanes.")
                elif command == "toggle_blocked_edge":
                    edge = data.get("edge")
                    if edge and len(edge) == 2:
                        u, v = edge[0], edge[1]
                        if (u, v) in GLOBAL_STATE["blocked_edges"]:
                            GLOBAL_STATE["blocked_edges"].discard((u, v))
                            GLOBAL_STATE["blocked_edges"].discard((v, u))
                            print(f"🛣️ Unblocked edge {u}-{v}")
                        else:
                            GLOBAL_STATE["blocked_edges"].add((u, v))
                            GLOBAL_STATE["blocked_edges"].add((v, u))
                            print(f"🛑 Blocked edge {u}-{v}")
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

# --- Calibrage de la vitesse physique ---
# Ajustez cette valeur (de 0 à 255) pour calibrer la vitesse de votre voiture réelle
# afin qu'elle parcoure la distance de 1.5m de manière synchrone avec le jumeau 3D.
PHYSICAL_MAX_PWM = 130

# Puissance pour la rotation en place (souvent plus élevée pour surmonter le frottement au sol)
PHYSICAL_ROTATION_PWM = 170

# Zone de départ initiale (A, B, C ou D)
START_ZONE = "C"

async def simulation_loop():
    """Boucle de physique asynchrone tournant à 10 Hz (toutes les 100 ms) pour une animation 3D fluide."""
    # Initialisation d'un seul robot AGV-01 démarrant de la Zone de départ configurée
    agv1 = AGV("AGV-01", START_ZONE, (255, 120, 80)) # Warm Coral
    agv1.rotation_speed_dps = 40.91 # Calibrated for exactly 2.2s turn duration (90 degrees)
    dummy_agv = AGV("DUMMY", "R", (0, 0, 0))
    dummy_agv.x = 9999.0
    dummy_agv.y = 9999.0
    dummy_agv.state = "OFFLINE"
    
    # On l'enregistre dans notre dictionnaire global pour pouvoir l'aiguiller manuellement via WebSocket
    AGV_FLEET["AGV-01"] = agv1
    
    global TELEMETRY_SENDER_REF
    # Configuration de la télémétrie en arrière-plan (fichiers, MQTT, etc.)
    telemetry_sender = TelemetrySender(
        webhook_url="http://127.0.0.1:5000/webhook",
        mqtt_topic_pub="warehouse/agv/telemetry",
        mqtt_topic_twin="hafida/robot/twin/telemetry",
        mqtt_topic_cmd="hafida/robot/twin/command",
        mqtt_topic_twin2="hafida/robot/twin2/telemetry",
        mqtt_topic_cmd2="robot/control",
        mqtt_username="hivemq.webclient.1775653497883",
        mqtt_password="1B%.CwaP:Kdr2I93k*Ap"
    )
    TELEMETRY_SENDER_REF = telemetry_sender
    
    dt = 0.1  # Pas de temps de 100 ms
    telemetry_timer = 0.0
    
    print("🤖 Headless Simulator loop started (Single AGV mode - C -> A -> B sequence).")
    try:
        while True:
            # Lier les données MQTT à AGV-01 (ID de votre ESP32: hafida-smart-robot-safety-2)
            twin_data_1 = telemetry_sender.get_physical_twin_data("hafida-smart-robot-safety-2")
            if twin_data_1:
                agv1.is_digital_twin_active = True
                if "distance" in twin_data_1:
                    dist_val = float(twin_data_1["distance"])
                    agv1.distance_front_cm = 300.0 if dist_val <= 0.0 else dist_val
                    # If physical AGV detects obstacle, block the current path segment globally
                    if 0 < agv1.distance_front_cm <= 20.0:
                        if len(agv1.path) > 0 and agv1.current_node_idx > 0:
                            p_node = agv1.path[agv1.current_node_idx - 1]
                            c_node = agv1.path[agv1.current_node_idx]
                            GLOBAL_STATE["blocked_edges"].add((p_node, c_node))
                            GLOBAL_STATE["blocked_edges"].add((c_node, p_node))
                            print(f"⚠️ Physical AGV detected obstacle! Blocked segment {p_node}-{c_node}")

            # 1. Mise à jour de la physique si la simulation n'est pas en pause
            if not GLOBAL_STATE["paused"]:
                # Calibrated speed at 150 PWM is 1.5385 m/s
                pwm_speed = GLOBAL_STATE.get("speed", 50)
                agv1.max_speed_mps = (pwm_speed / 150.0) * 1.5385
                
                # Calibrated turn speed at 170 PWM is 40.91 dps
                # Turning is locked to max speed 255
                agv1.rotation_speed_dps = (255 / 170.0) * 40.91
                if agv1.state == "IDLE" and not GLOBAL_STATE["emergency_stop"]:
                    # Séquence de mission : C -> A -> B
                    # Séquence de mission : boucle complète continue (C -> A -> B -> D -> C)
                    if agv1.current_zone == "C":
                        print("🏁 Starting leg: C -> A")
                        agv1.start_mission("A")
                    elif agv1.current_zone == "A":
                        print("🏁 Starting leg: A -> B")
                        agv1.start_mission("B")
                    elif agv1.current_zone == "B":
                        print("🏁 Starting leg: B -> D")
                        agv1.start_mission("D")
                    elif agv1.current_zone == "D":
                        print("🏁 Starting leg: D -> C")
                        agv1.start_mission("C")
                    
                # Mise à jour de la physique
                agv1.update(dt, dummy_agv, TRAFFIC_CONTROLLER, GLOBAL_STATE["emergency_stop"], GLOBAL_STATE["blocked_edges"])
            
            # Récupération des données physiques actuelles
            payload1 = agv1.get_telemetry_payload()
            
            # Calcul des vitesses pour le Dashboard 3D uniquement
            is_rotating = (agv1.motor_left_pct * agv1.motor_right_pct) < 0
            pwm_speed = GLOBAL_STATE.get("speed", 50)
            pwm_limit = 255 if is_rotating else pwm_speed
            
            agv1_m1 = int(agv1.motor_left_pct * pwm_limit)
            agv1_m2 = int(agv1.motor_right_pct * pwm_limit)
            
            # --- DIGITAL TWIN COMMAND: SEND STRING DIRECTION TO PHYSICAL ESP32 ---
            if GLOBAL_STATE["emergency_stop"] or GLOBAL_STATE["paused"]:
                cmd_str = "STOP"
            elif agv1.motor_left_pct > 0 and agv1.motor_right_pct > 0:
                cmd_str = "FORWARD"
            elif agv1.motor_left_pct < 0 and agv1.motor_right_pct < 0:
                cmd_str = "BACKWARD"
            elif agv1.motor_left_pct < 0 and agv1.motor_right_pct > 0:
                cmd_str = "LEFT"
            elif agv1.motor_left_pct > 0 and agv1.motor_right_pct < 0:
                cmd_str = "RIGHT"
            else:
                cmd_str = "STOP"
                
            # Envoyer si changement de commande OU toutes les secondes (Keep-alive)
            current_time = time.time()
            if not hasattr(telemetry_sender, 'last_sent_cmd') or \
               telemetry_sender.last_sent_cmd != cmd_str or \
               (current_time - getattr(telemetry_sender, 'last_cmd_send_time', 0) > 1.0):
                
                # Envoyer la commande de mouvement textuelle sur robot/control
                telemetry_sender.send_string_command(telemetry_sender.mqtt_topic_cmd2, cmd_str)
                telemetry_sender.last_sent_cmd = cmd_str
                telemetry_sender.last_cmd_send_time = current_time
            
            # Envoi des données en temps réel au jumeau numérique 3D
            twin_payload = {
                "timestamp": time.time(),
                "emergency_stop": GLOBAL_STATE["emergency_stop"],
                "paused": GLOBAL_STATE["paused"],
                "speed": GLOBAL_STATE.get("speed", 150),
                "agents": [payload1],
                "blocked_edges": [list(edge) for edge in GLOBAL_STATE["blocked_edges"]],
                "motor_speeds": {
                    "m1": agv1_m1,
                    "m2": agv1_m2,
                    "m3": agv1_m1,
                    "m4": agv1_m2
                }
            }
            await broadcast(json.dumps(twin_payload))
            
            # Enregistrement des logs toutes les 1,5 secondes (si pas en pause)
            if not GLOBAL_STATE["paused"]:
                telemetry_timer += dt
                if telemetry_timer >= 1.5:
                    telemetry_timer = 0.0
                    telemetry_sender.submit_telemetry(payload1)
                    print(f"[DT Stream] Telemetry Sent | AGV-01: {payload1['state']} (Bat: {payload1['battery_pct']}%)")
                
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
