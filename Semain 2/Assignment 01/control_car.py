import time
import paho.mqtt.client as mqtt
from pynput import keyboard

# --- Configuration MQTT (HiveMQ Cloud) ---
MQTT_HOST = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "hivemq.webclient.1775653497883"
MQTT_PASS = "1B%.CwaP:Kdr2I93k*Ap"

# Topics MQTT
MQTT_CONTROL_TOPIC = "robot/control"      # Topic dyal l-awamir
MQTT_DISTANCE_TOPIC = "robot/distance"    # Topic dyal l-distance d l-capteur
MQTT_ANGLE_TOPIC    = "robot/angle"       # Topic dyal l-Angle (Yaw) d MPU6050

last_command = "STOP"
current_speed = 150  # 🔧 FIX: même vitesse que l'ESP32 (robotSpeed = 150) pour éviter la désynchronisation
bypass_obstacle = False

# Variables globales pour les lectures capteurs
current_distance = 999.0
current_angle = 0.0

# --- ONE-SHOT TURN COMMANDS: ces commandes ne doivent PAS déclencher STOP au release ---
TURN_COMMANDS = {"TURN_90_L", "TURN_90_R", "TURN_180"}

# --- Affichage état du robot ---
def display_status():
    global current_distance, current_angle, bypass_obstacle

    if bypass_obstacle:
        dist_str = "BYPASSED (Désactivé)"
        icon = "🛡️"
    elif current_distance >= 999.0:
        dist_str = "Hors de portée"
        icon = "⚠️"
    elif current_distance <= 20.0:
        dist_str = f"{current_distance:.1f} cm (TROP PROCHE! ARRET)"
        icon = "🚨"
    elif current_distance <= 50.0:
        dist_str = f"{current_distance:.1f} cm (Obstacle proche)"
        icon = "🟡"
    else:
        dist_str = f"{current_distance:.1f} cm (Voie libre)"
        icon = "🟢"

    print(f"\r{icon} Distance: {dist_str:<32} | 📐 Angle (Yaw): {current_angle:+.1f}°      ", end="", flush=True)

# --- Envoi d'une commande MQTT ---
def send_command(cmd):
    global last_command
    # 🔧 FIX: Les commandes de rotation (TURN_*) doivent TOUJOURS être renvoyées
    # même si elles sont identiques à last_command (ex: appui répété sur 'i')
    # car l'ESP32 termine la rotation et passe à STOP en interne => last_command devient désynchronisé
    if cmd in TURN_COMMANDS or cmd != last_command:
        client.publish(MQTT_CONTROL_TOPIC, cmd)
        print(f"\n[+] Ordre envoyé : {cmd}")
        last_command = cmd

# --- Changement de vitesse ---
def change_speed(new_speed):
    global current_speed
    current_speed = max(0, min(255, new_speed))
    client.publish(MQTT_CONTROL_TOPIC, f"SPEED:{current_speed}")
    print(f"\n[⚡] Vitesse envoyée : {current_speed} / 255")

# --- Réception des données de l'ESP32 ---
def on_message(client, userdata, msg):
    global current_distance, current_angle

    if msg.topic == MQTT_DISTANCE_TOPIC:
        try:
            current_distance = float(msg.payload.decode())
            display_status()
        except ValueError:
            pass

    elif msg.topic == MQTT_ANGLE_TOPIC:
        try:
            current_angle = float(msg.payload.decode())
            display_status()
        except ValueError:
            pass

# --- Gestion des touches pressées ---
def on_press(key):
    global bypass_obstacle
    try:
        # Touches de direction (ZQSD / WASD)
        if key.char in ['z', 'w']:
            send_command("FORWARD")
        elif key.char == 's':
            send_command("BACKWARD")
        elif key.char in ['q', 'a']:
            send_command("LEFT")
        elif key.char == 'd':
            send_command("RIGHT")

        # --- ROTATIONS PRÉCISES via Gyroscope MPU6050 ---
        # 🔧 Ces commandes sont envoyées en ONE-SHOT, l'ESP32 gère la fin de rotation lui-même
        elif key.char == 'i':
            send_command("TURN_90_L")    # Rotation 90° Gauche précise
        elif key.char == 'o':
            send_command("TURN_90_R")    # Rotation 90° Droite précise
        elif key.char == 'u':
            send_command("TURN_180")     # Demi-tour 180° précis

        # --- BYPASS capteur de distance (anti-bruit moteurs) ---
        elif key.char == 'b':
            bypass_obstacle = not bypass_obstacle
            cmd = "BYPASS:ON" if bypass_obstacle else "BYPASS:OFF"
            client.publish(MQTT_CONTROL_TOPIC, cmd)
            status_text = "DÉSACTIVÉ (Bypass ON)" if bypass_obstacle else "ACTIVÉ (Bypass OFF)"
            print(f"\n[🛡️] Système d'évitement d'obstacle : {status_text}")

        # Raccourcis vitesse (1-5)
        elif key.char == '1': change_speed(50)
        elif key.char == '2': change_speed(100)
        elif key.char == '3': change_speed(150)
        elif key.char == '4': change_speed(200)
        elif key.char == '5': change_speed(255)

        # Ajustement fin (+/-)
        elif key.char == '+': change_speed(current_speed + 25)
        elif key.char == '-': change_speed(current_speed - 25)

    except AttributeError:
        # Flèches directionnelles
        if key == keyboard.Key.up:
            send_command("FORWARD")
        elif key == keyboard.Key.down:
            send_command("BACKWARD")
        elif key == keyboard.Key.left:
            send_command("LEFT")
        elif key == keyboard.Key.right:
            send_command("RIGHT")

# --- Gestion du relâchement des touches ---
def on_release(key):
    global last_command
    is_movement_key = False

    try:
        # 🔧 FIX: Les touches de rotation (i, o, u) ne déclenchent PAS de STOP au release
        # car l'ESP32 gère lui-même la fin de rotation via le gyroscope
        if key.char in ['z', 'w', 's', 'q', 'a', 'd']:
            is_movement_key = True
    except AttributeError:
        if key in [keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right]:
            is_movement_key = True

    if is_movement_key:
        send_command("STOP")

    if key == keyboard.Key.esc:
        print("\n[!] Fermeture du programme...")
        send_command("STOP")
        return False

# --- Initialisation MQTT ---
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set()
client.on_message = on_message

print("[...] Connexion à HiveMQ Cloud en cours...")
client.connect(MQTT_HOST, MQTT_PORT)

# Abonnement aux topics capteurs
client.subscribe(MQTT_DISTANCE_TOPIC)
client.subscribe(MQTT_ANGLE_TOPIC)

client.loop_start()
time.sleep(1)
print("[+] Connexion réussie au Broker !")

# 🔧 FIX: Synchronisation vitesse avec l'ESP32 (150 = robotSpeed par défaut dans le firmware)
client.publish(MQTT_CONTROL_TOPIC, f"SPEED:{current_speed}")
print(f"[⚡] Vitesse initiale synchronisée : {current_speed}/255")

print("\n--------------------------------------------------")
print("🎮 CONTRÔLE DU ROBOT (Clavier / ZQSD) :")
print("   -> [Z/W] ou [↑] : AVANT (FORWARD)")
print("   -> [S]   ou [↓] : ARRIÈRE (BACKWARD)")
print("   -> [Q/A] ou [←] : GAUCHE (LEFT)")
print("   -> [D]   ou [→] : DROITE (RIGHT)")
print("\n🔄 ROTATIONS PRÉCISES — Gyroscope MPU6050 :")
print("   -> [i] : Rotation exacte 90° Gauche  (TURN_90_L)")
print("   -> [o] : Rotation exacte 90° Droite  (TURN_90_R)")
print("   -> [u] : Demi-tour exact 180°         (TURN_180)")
print("   ⚠️  Relâcher la touche NE STOPPE PAS la rotation")
print("      → L'ESP32 s'arrête seul quand le Gyro atteint l'angle cible")
print("\n🛡️ BYPASS CAPTEUR (anti-bruit) :")
print("   -> [b] : Activer/Désactiver le capteur de distance")
print("\n⚡ VITESSE (PWM 0-255) :")
print("   -> [1] = 50  | [2] = 100 | [3] = 150 | [4] = 200 | [5] = 255")
print("   -> [+] : +25 | [-] : -25")
print("\n📊 DONNÉES EN DIRECT : Distance Ultrason & Angle Yaw (MPU6050)")
print("❌ [ESC] pour quitter proprement.")
print("--------------------------------------------------\n")

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()

client.loop_stop()
client.disconnect()
