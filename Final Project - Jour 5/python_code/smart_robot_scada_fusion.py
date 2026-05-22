
# SMART ROBOT SAFETY CONTROLLER - PYGAME SCADA + FUSION BRIDGE
# Compatible with: main(4).cpp / ESP32 MQTT telemetry schema
# Author: Hafida Belayd
#
# Data route:
# ESP32 -> HiveMQ MQTT -> this Pygame dashboard -> ABA Fusion Webhook


import json
import math
import os
import queue
import ssl
import threading
import time

import paho.mqtt.client as mqtt
import pygame
import requests


# 1. CONFIGURATION

MQTT_HOST = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud"
MQTT_PORT = 8883

# Never hard-code credentials in a shared file.
# Before starting this application, define:
#   export ROBOT_MQTT_USER="your_username"
#   export ROBOT_MQTT_PASS="your_password"
MQTT_USER = os.getenv("ROBOT_MQTT_USER", "")
MQTT_PASS = os.getenv("ROBOT_MQTT_PASS", "")

TOPIC_TELEMETRY = "hafida/robot/twin/telemetry"
TOPIC_COMMAND = "hafida/robot/twin/command"

FUSION_WEBHOOK_URL = (
    "https://fusion-ai-api.medifus.dev/webhooks/"
    "webhook-8b9ba1a7-2d90-4a24-98a9-9e8bf59bfce8/robot-telemetry"
)

SHOCK_STOP_THRESHOLD = 0.80
POT_WARNING_THRESHOLD = 3000

WIDTH, HEIGHT = 1280, 760
FPS = 60
TELEMETRY_STALE_AFTER_S = 3.0


# 2. SHARED LIVE DATA

data_lock = threading.Lock()
status_lock = threading.Lock()
stop_threads = threading.Event()
fusion_queue: queue.Queue[dict] = queue.Queue(maxsize=1)

# Exactly aligned with the JSON built in buildTelemetryJson() in ESP32 code.
robot_data = {
    "device": "hafida-smart-robot-safety",
    "time_ms": 0,
    "ir": 0,
    "obstacle": False,
    "pot_raw": 0,
    "pot_filtered": 0,
    "stop_pressed": False,
    "ax": 0.0,
    "ay": 0.0,
    "az": 0.0,
    "shock_delta": 0.0,
    "humidity_pct": None,
    "bme_available": False,
    "state": "WAITING",
    "reason": "NO_TELEMETRY",
    "relay": "OFF",
    "remote_stop": False,
    "rssi": 0,
}

connection_status = {
    "mqtt_connected": False,
    "last_message_time": 0.0,
    "mqtt_error": "",
}

fusion_status = {
    "state": "IDLE",
    "http_code": "-",
    "last_send_time": 0.0,
    "sent_count": 0,
    "failed_count": 0,
    "message": "Waiting for telemetry",
}


# 3. TELEMETRY AND FUSION FORWARDING

def safe_number(value, fallback=0):
    """Return a number only when the received JSON contains a usable numeric value."""
    return value if isinstance(value, (int, float)) else fallback


def normalized_telemetry(received: dict) -> dict:
    """Map only fields actually emitted by the ESP32 telemetry JSON."""
    return {
        "device": str(received.get("device", robot_data["device"])),
        "time_ms": int(safe_number(received.get("time_ms"), 0)),
        "ir": int(safe_number(received.get("ir"), 0)),
        "obstacle": bool(received.get("obstacle", False)),
        "pot_raw": int(safe_number(received.get("pot_raw"), 0)),
        "pot_filtered": int(safe_number(received.get("pot_filtered"), 0)),
        "stop_pressed": bool(received.get("stop_pressed", False)),
        "ax": float(safe_number(received.get("ax"), 0.0)),
        "ay": float(safe_number(received.get("ay"), 0.0)),
        "az": float(safe_number(received.get("az"), 0.0)),
        "shock_delta": float(safe_number(received.get("shock_delta"), 0.0)),
        "humidity_pct": safe_number(received.get("humidity_pct"), None),
        "bme_available": bool(received.get("bme_available", False)),
        "state": str(received.get("state", "UNKNOWN")).upper(),
        "reason": str(received.get("reason", "UNKNOWN")),
        "relay": str(received.get("relay", "OFF")).upper(),
        "remote_stop": bool(received.get("remote_stop", False)),
        "rssi": int(safe_number(received.get("rssi"), 0)),
    }


def enqueue_latest_for_fusion(payload: dict) -> None:
    """Keep only the latest message if the webhook is temporarily slower than MQTT."""
    try:
        fusion_queue.put_nowait(payload)
    except queue.Full:
        try:
            fusion_queue.get_nowait()
        except queue.Empty:
            pass
        fusion_queue.put_nowait(payload)


def fusion_sender_worker() -> None:
    """Send MQTT telemetry to Fusion without blocking Pygame rendering or MQTT callbacks."""
    session = requests.Session()

    while not stop_threads.is_set():
        try:
            telemetry = fusion_queue.get(timeout=0.3)
        except queue.Empty:
            continue

        try:
            response = session.post(FUSION_WEBHOOK_URL, json=telemetry, timeout=5)
            ok = 200 <= response.status_code < 300
            with status_lock:
                fusion_status["http_code"] = str(response.status_code)
                fusion_status["last_send_time"] = time.time()
                if ok:
                    fusion_status["state"] = "SENT"
                    fusion_status["sent_count"] += 1
                    fusion_status["message"] = "Telemetry delivered to Fusion"
                else:
                    fusion_status["state"] = "ERROR"
                    fusion_status["failed_count"] += 1
                    fusion_status["message"] = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            with status_lock:
                fusion_status["state"] = "ERROR"
                fusion_status["last_send_time"] = time.time()
                fusion_status["failed_count"] += 1
                fusion_status["message"] = str(exc)[:55]

        fusion_queue.task_done()

    session.close()


# 4. MQTT

def mqtt_success(reason_code) -> bool:
    return reason_code == 0 or str(reason_code).lower() in ("success", "0")


def on_connect(client, userdata, flags, reason_code, *extra) -> None:
    with status_lock:
        connection_status["mqtt_connected"] = mqtt_success(reason_code)
        connection_status["mqtt_error"] = "" if mqtt_success(reason_code) else str(reason_code)

    if mqtt_success(reason_code):
        client.subscribe(TOPIC_TELEMETRY)
        # Request immediate telemetry after dashboard connection.
        client.publish(TOPIC_COMMAND, "STATUS")
        print(f"MQTT connected - subscribed to {TOPIC_TELEMETRY}")
    else:
        print(f"MQTT connection refused: {reason_code}")


def on_disconnect(client, userdata, reason_code, *extra) -> None:
    with status_lock:
        connection_status["mqtt_connected"] = False
        connection_status["mqtt_error"] = str(reason_code)
    print(f"MQTT disconnected: {reason_code}")


def on_message(client, userdata, message) -> None:
    if message.topic != TOPIC_TELEMETRY:
        return

    try:
        received = json.loads(message.payload.decode("utf-8"))
        if not isinstance(received, dict):
            raise ValueError("Telemetry payload must be a JSON object.")

        telemetry = normalized_telemetry(received)

        with data_lock:
            robot_data.update(telemetry)

        with status_lock:
            connection_status["last_message_time"] = time.time()

        # Send the same flat telemetry schema to Fusion, easy to map in Google Sheets.
        enqueue_latest_for_fusion(telemetry)

        humidity = telemetry["humidity_pct"]
        humidity_text = "--" if humidity is None else f"{humidity:.1f}%"
        print(
            "RX | "
            f"{telemetry['state']} | {telemetry['reason']} | "
            f"POT={telemetry['pot_filtered']} | "
            f"SHOCK={telemetry['shock_delta']:.2f} | "
            f"HUM={humidity_text} | "
            f"RELAY={telemetry['relay']}"
        )
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        print(f"Invalid telemetry payload: {exc}")


def build_mqtt_client() -> mqtt.Client:
    try:
        mqtt_client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id="pygame-scada-fusion-bridge",
        )
    except (AttributeError, TypeError):
        mqtt_client = mqtt.Client(client_id="pygame-scada-fusion-bridge")

    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    # Validate the TLS certificate using certifi if available, otherwise default store
    try:
        import certifi
        ca_path = certifi.where()
    except ImportError:
        ca_path = None
    mqtt_client.tls_set(ca_certs=ca_path, cert_reqs=ssl.CERT_REQUIRED)
    mqtt_client.reconnect_delay_set(min_delay=1, max_delay=10)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    return mqtt_client


def publish_command(mqtt_client: mqtt.Client, command: str) -> None:
    with status_lock:
        connected = connection_status["mqtt_connected"]

    if not connected:
        print(f"Command not sent while MQTT is offline: {command}")
        return

    result = mqtt_client.publish(TOPIC_COMMAND, command)
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"Command sent: {command}")
    else:
        print(f"Command error rc={result.rc}: {command}")


# 5. PYGAME THEME AND HELPERS

BG = (8, 13, 22)
PANEL = (15, 22, 34)
CARD = (19, 28, 43)
BORDER = (37, 50, 69)
GRID = (25, 34, 49)
TEXT = (235, 242, 250)
MUTED = (132, 148, 168)
CYAN = (40, 201, 219)
GREEN = (38, 203, 128)
YELLOW = (243, 185, 55)
RED = (241, 75, 92)
ORANGE = (244, 130, 48)
BLUE = (53, 132, 228)


def state_color(state: str):
    return {
        "NORMAL": GREEN,
        "WARNING": YELLOW,
        "STOP": RED,
        "FAULT": ORANGE,
        "WAITING": MUTED,
    }.get(state, MUTED)


def reason_label(reason: str) -> str:
    labels = {
        "ALL_OK": "Toutes les conditions sont normales",
        "IR_OBSTACLE": "Obstacle infrarouge detecte",
        "HIGH_SPEED": "Vitesse simulee elevee",
        "STOP_BUTTON": "Bouton d'arret appuye",
        "STRONG_SHOCK": "Choc important detecte",
        "REMOTE_STOP": "Arret distant actif",
        "MPU_NOT_FOUND": "Accelerometre introuvable",
        "MPU_INVALID_VALUE": "Valeur MPU invalide",
        "NO_TELEMETRY": "En attente des donnees MQTT",
    }
    return labels.get(reason, reason)


def font(size: int, bold: bool = False):
    return pygame.font.SysFont("Arial", size, bold=bold)


def text(surface, value, x, y, size=16, color=TEXT, bold=False):
    surface.blit(font(size, bold).render(str(value), True, color), (x, y))


def panel(surface, rect, fill=PANEL, radius=16):
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    pygame.draw.rect(surface, BORDER, rect, 1, border_radius=radius)


def glow(surface, color, center, radius):
    layer = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
    cx = cy = radius * 2
    for r, alpha in ((radius * 2, 10), (int(radius * 1.5), 18), (radius, 35)):
        pygame.draw.circle(layer, (*color, alpha), (cx, cy), r)
    surface.blit(layer, (center[0] - cx, center[1] - cy))


def badge(surface, label, rect, color):
    layer = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(layer, (*color, 35), layer.get_rect(), border_radius=rect.height // 2)
    pygame.draw.rect(layer, color, layer.get_rect(), 1, border_radius=rect.height // 2)
    surface.blit(layer, rect.topleft)
    pygame.draw.circle(surface, color, (rect.x + 14, rect.centery), 5)
    rendered = font(12, True).render(label, True, color)
    surface.blit(rendered, (rect.x + 26, rect.centery - rendered.get_height() // 2))


def clipped(value, minimum, maximum):
    return max(minimum, min(maximum, value))



# 6. DASHBOARD DRAWING

track_points = [
    (72, 336),
    (190, 336),
    (280, 260),
    (400, 260),
    (505, 362),
    (630, 362),
    (730, 270),
]
robot_position = [72.0, 336.0]
target_index = 1
travel_forward = True
robot_heading = 0.0

stop_button = pygame.Rect(849, 464, 124, 44)
release_button = pygame.Rect(984, 464, 150, 44)
status_button = pygame.Rect(849, 518, 285, 38)


def snapshot():
    with data_lock:
        data = dict(robot_data)
    with status_lock:
        conn = dict(connection_status)
        fusion = dict(fusion_status)
    return data, conn, fusion


def draw_background(surface):
    surface.fill(BG)
    for x in range(0, WIDTH, 40):
        pygame.draw.line(surface, GRID, (x, 0), (x, HEIGHT), 1)
    for y in range(0, HEIGHT, 40):
        pygame.draw.line(surface, GRID, (0, y), (WIDTH, y), 1)


def draw_header(surface, data, conn, fusion):
    panel(surface, pygame.Rect(22, 18, 1236, 74))
    text(surface, "SMART ROBOT SAFETY CONTROLLER", 44, 34, 22, TEXT, True)
    text(surface, "Digital Twin  /  MQTT  /  Fusion ABA", 44, 61, 13, MUTED)

    mqtt_live = conn["mqtt_connected"]
    age = time.time() - conn["last_message_time"] if conn["last_message_time"] else 10_000
    live_color = GREEN if mqtt_live and age <= TELEMETRY_STALE_AFTER_S else YELLOW if mqtt_live else RED
    live_label = "MQTT LIVE" if mqtt_live and age <= TELEMETRY_STALE_AFTER_S else "MQTT STALE" if mqtt_live else "MQTT OFFLINE"
    badge(surface, live_label, pygame.Rect(702, 39, 136, 32), live_color)

    fusion_color = GREEN if fusion["state"] == "SENT" else RED if fusion["state"] == "ERROR" else MUTED
    badge(surface, f"FUSION {fusion['state']}", pygame.Rect(850, 39, 160, 32), fusion_color)

    current_state = data["state"]
    badge(surface, current_state, pygame.Rect(1024, 33, 204, 43), state_color(current_state))


def update_robot_motion(data):
    global target_index, travel_forward, robot_heading
    relay_on = data["relay"] == "ON"
    state = data["state"]

    speed = 0.0
    if relay_on and state == "NORMAL":
        speed = 2.1
    elif relay_on and state == "WARNING":
        speed = 0.75

    if speed <= 0:
        return

    tx, ty = track_points[target_index]
    dx, dy = tx - robot_position[0], ty - robot_position[1]
    distance = math.hypot(dx, dy)
    robot_heading = math.atan2(dy, dx)

    if distance <= speed:
        robot_position[0], robot_position[1] = tx, ty
        if travel_forward and target_index == len(track_points) - 1:
            travel_forward = False
        elif not travel_forward and target_index == 0:
            travel_forward = True
        target_index += 1 if travel_forward else -1
    else:
        robot_position[0] += math.cos(robot_heading) * speed
        robot_position[1] += math.sin(robot_heading) * speed


def draw_scene(surface, data):
    scene = pygame.Rect(22, 108, 780, 423)
    panel(surface, scene)
    text(surface, "ZONE DE DEPLACEMENT DU ROBOT", 44, 129, 13, MUTED, True)
    text(surface, "Simulation visuelle liee au relais et a l'etat de securite", 44, 151, 12, MUTED)

    for x in range(scene.x + 18, scene.right - 18, 36):
        pygame.draw.line(surface, GRID, (x, 178), (x, scene.bottom - 20), 1)
    for y in range(178, scene.bottom - 20, 36):
        pygame.draw.line(surface, GRID, (scene.x + 18, y), (scene.right - 18, y), 1)

    pygame.draw.lines(surface, (27, 40, 57), False, track_points, 24)
    pygame.draw.lines(surface, BLUE, False, track_points, 3)
    for point in track_points:
        pygame.draw.circle(surface, BG, point, 8)
        pygame.draw.circle(surface, CYAN, point, 5)

    update_robot_motion(data)
    rx, ry = int(robot_position[0]), int(robot_position[1])
    status_color = state_color(data["state"])

    # IR sensing cone: shorter and red/yellow when an obstacle is reported.
    scan_length = 66 if data["obstacle"] else 122
    cone_color = YELLOW if data["obstacle"] else CYAN
    cone_angle = 0.38
    left = (
        int(rx + math.cos(robot_heading - cone_angle) * scan_length),
        int(ry + math.sin(robot_heading - cone_angle) * scan_length),
    )
    right = (
        int(rx + math.cos(robot_heading + cone_angle) * scan_length),
        int(ry + math.sin(robot_heading + cone_angle) * scan_length),
    )
    cone_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.polygon(cone_surface, (*cone_color, 28), [(rx, ry), left, right])
    pygame.draw.line(cone_surface, (*cone_color, 120), (rx, ry), left, 2)
    pygame.draw.line(cone_surface, (*cone_color, 120), (rx, ry), right, 2)
    surface.blit(cone_surface, (0, 0))

    glow(surface, status_color, (rx, ry), 24)
    pygame.draw.circle(surface, (29, 39, 53), (rx, ry), 23)
    pygame.draw.circle(surface, BORDER, (rx, ry), 23, 2)
    pygame.draw.circle(surface, status_color, (rx, ry), 12)
    front = (int(rx + math.cos(robot_heading) * 19), int(ry + math.sin(robot_heading) * 19))
    pygame.draw.line(surface, TEXT, (rx, ry), front, 3)

    mode = "MOUVEMENT" if data["relay"] == "ON" else "IMMOBILISE"
    text(surface, f"RELAIS: {data['relay']}  /  {mode}", 46, 493, 13, status_color, True)


def draw_right_controls(surface, data, conn, fusion, mouse_pos):
    area = pygame.Rect(818, 108, 440, 423)
    panel(surface, area)
    text(surface, "SUPERVISION & COMMANDES", 842, 130, 15, TEXT, True)

    # State decision
    text(surface, "DECISION LOCALE ESP32", 842, 169, 11, MUTED, True)
    text(surface, data["state"], 842, 190, 28, state_color(data["state"]), True)
    text(surface, reason_label(data["reason"]), 842, 226, 14, TEXT)

    relay_color = GREEN if data["relay"] == "ON" else RED
    badge(surface, f"RELAIS {data['relay']}", pygame.Rect(842, 259, 126, 31), relay_color)
    remote_color = RED if data["remote_stop"] else MUTED
    badge(surface, "REMOTE STOP" if data["remote_stop"] else "REMOTE READY",
          pygame.Rect(980, 259, 154, 31), remote_color)

    # Fusion information
    text(surface, "TRANSFERT FUSION", 842, 315, 11, MUTED, True)
    fusion_color = GREEN if fusion["state"] == "SENT" else RED if fusion["state"] == "ERROR" else MUTED
    text(surface, f"{fusion['state']}  HTTP: {fusion['http_code']}", 842, 336, 15, fusion_color, True)
    text(surface, f"Envoyes: {fusion['sent_count']}   Echecs: {fusion['failed_count']}", 842, 360, 12, MUTED)
    text(surface, fusion["message"], 842, 380, 11, MUTED)

    text(surface, "COMMANDES DISTANTES", 842, 423, 11, MUTED, True)

    def button(rect, label, color, outline=False):
        hover = rect.collidepoint(mouse_pos)
        if outline:
            fill = tuple(min(255, c + 18) for c in CARD) if hover else CARD
            pygame.draw.rect(surface, fill, rect, border_radius=10)
            pygame.draw.rect(surface, color, rect, 1, border_radius=10)
            rendered = font(13, True).render(label, True, color)
        else:
            fill = tuple(min(255, c + 18) for c in color) if hover else color
            pygame.draw.rect(surface, fill, rect, border_radius=10)
            rendered = font(13, True).render(label, True, TEXT)
        text_rect = rendered.get_rect(center=rect.center)
        surface.blit(rendered, text_rect)

    button(stop_button, "STOP", RED)
    button(release_button, "RELEASE STOP", GREEN)
    button(status_button, "REQUEST STATUS", CYAN, outline=True)


def gauge(surface, x, y, width, value, maximum, color):
    pygame.draw.rect(surface, GRID, (x, y, width, 8), border_radius=4)
    fill = int(width * clipped(value / maximum if maximum else 0, 0, 1))
    if fill > 0:
        pygame.draw.rect(surface, color, (x, y, fill, 8), border_radius=4)


def draw_telemetry_cards(surface, data, conn):
    text(surface, "TELEMETRIE TEMPS REEL", 27, 557, 13, MUTED, True)

    cards = [
        pygame.Rect(22, 586, 234, 143),
        pygame.Rect(268, 586, 234, 143),
        pygame.Rect(514, 586, 234, 143),
        pygame.Rect(760, 586, 234, 143),
        pygame.Rect(1006, 586, 252, 143),
    ]
    for rect in cards:
        panel(surface, rect, CARD, 12)

    # Card 1 - Infrared
    text(surface, "CAPTEUR INFRAROUGE", 38, 603, 11, MUTED, True)
    ir_color = YELLOW if data["obstacle"] else GREEN
    text(surface, "OBSTACLE" if data["obstacle"] else "ZONE LIBRE", 38, 627, 20, ir_color, True)
    text(surface, f"Lecture brute: {data['ir']}", 38, 661, 12, TEXT)
    badge(surface, "ACTIVE" if data["obstacle"] else "CLEAR",
          pygame.Rect(38, 685, 98, 29), ir_color)

    # Card 2 - Potentiometer speed
    text(surface, "VITESSE SIMULEE / POT", 284, 603, 11, MUTED, True)
    speed_color = YELLOW if data["pot_filtered"] >= POT_WARNING_THRESHOLD else CYAN
    text(surface, f"{data['pot_filtered']} / 4095", 284, 627, 20, speed_color, True)
    gauge(surface, 284, 663, 196, data["pot_filtered"], 4095, speed_color)
    text(surface, f"Seuil warning: {POT_WARNING_THRESHOLD}", 284, 684, 11, MUTED)

    # Card 3 - Shock
    text(surface, "MPU6050 / CHOC", 530, 603, 11, MUTED, True)
    shock_color = RED if data["shock_delta"] >= SHOCK_STOP_THRESHOLD else GREEN
    text(surface, f"Delta: {data['shock_delta']:.2f} g", 530, 627, 20, shock_color, True)
    gauge(surface, 530, 663, 196, data["shock_delta"], SHOCK_STOP_THRESHOLD, shock_color)
    text(surface, f"Stop >= {SHOCK_STOP_THRESHOLD:.2f} g", 530, 684, 11, MUTED)

    # Card 4 - Acceleration axes
    text(surface, "ACCELERATION", 776, 603, 11, MUTED, True)
    text(surface, f"X   {data['ax']:+.2f} g", 776, 628, 14, TEXT)
    text(surface, f"Y   {data['ay']:+.2f} g", 776, 653, 14, TEXT)
    text(surface, f"Z   {data['az']:+.2f} g", 776, 678, 14, TEXT)

    # Card 5 - Network and physical stop
    text(surface, "CONNECTIVITE & SECURITE", 1022, 603, 11, MUTED, True)
    age = time.time() - conn["last_message_time"] if conn["last_message_time"] else None
    age_text = f"{age:.1f} s" if age is not None else "--"
    text(surface, f"RSSI WiFi: {data['rssi']} dBm", 1022, 628, 13, TEXT)
    text(surface, f"Dernier paquet: {age_text}", 1022, 652, 13, TEXT)
    pressed_color = RED if data["stop_pressed"] else GREEN
    text(surface, "BTN STOP: APPUYE" if data["stop_pressed"] else "BTN STOP: RELACHE",
         1022, 681, 13, pressed_color, True)



# 7. APPLICATION


def main() -> None:
    if not MQTT_USER or not MQTT_PASS:
        raise SystemExit(
            "Missing MQTT credentials. Define ROBOT_MQTT_USER and ROBOT_MQTT_PASS "
            "before launching this dashboard."
        )

    fusion_thread = threading.Thread(target=fusion_sender_worker, daemon=True)
    fusion_thread.start()

    mqtt_client = build_mqtt_client()
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
    except Exception as exc:
        with status_lock:
            connection_status["mqtt_error"] = str(exc)
        print(f"Initial MQTT connection error: {exc}")

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Smart Robot Safety Controller - MQTT / Fusion SCADA")
    clock = pygame.time.Clock()

    running = True
    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_s:
                    publish_command(mqtt_client, "STOP")
                elif event.key == pygame.K_r:
                    publish_command(mqtt_client, "RELEASE_STOP")
                elif event.key == pygame.K_t:
                    publish_command(mqtt_client, "STATUS")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if stop_button.collidepoint(event.pos):
                    publish_command(mqtt_client, "STOP")
                elif release_button.collidepoint(event.pos):
                    publish_command(mqtt_client, "RELEASE_STOP")
                elif status_button.collidepoint(event.pos):
                    publish_command(mqtt_client, "STATUS")

        data, conn, fusion = snapshot()
        draw_background(screen)
        draw_header(screen, data, conn, fusion)
        draw_scene(screen, data)
        draw_right_controls(screen, data, conn, fusion, mouse_pos)
        draw_telemetry_cards(screen, data, conn)

        text(
            screen,
            "Touches: S = STOP distant   |   R = liberer STOP distant   |   T = demander un statut",
            25, 739, 11, MUTED,
        )

        pygame.display.flip()
        clock.tick(FPS)

    stop_threads.set()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    pygame.quit()


if __name__ == "__main__":
    main()