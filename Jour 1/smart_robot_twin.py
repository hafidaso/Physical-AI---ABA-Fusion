# ========================================================
# PROJECT: Smart Robot Digital Twin - SCADA Supervisor
# UPDATED FOR: Maker Point Edition (robot_makerpoint.ino)
# ENGINEER: Hafida Belayd
# COMPATIBILITY: ESP32 MQTT Client Secure
# DATE: 18 May 2026
# ========================================================

import json
import math
import pygame
import ssl
import time
import paho.mqtt.client as mqtt


# MQTT CONFIG

MQTT_SERVER = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud"
MQTT_PORT = 8883

MQTT_USER = "hivemq.webclient.1775653497883"
MQTT_PASS = "1B%.CwaP:Kdr2I93k*Ap"

TOPIC_TELEMETRY = "hafida/robot/twin/telemetry"
TOPIC_COMMAND = "hafida/robot/twin/command"

# Python side has NO Watchdog.
# Stability is handled with MQTT reconnect, safe publish, and clean shutdown.
mqtt_connected = False
last_message_time = 0


# ROBOT DATA (MAKER POINT COMPATIBLE)

robot_data = {
    "time_ms": 0,
    "infrared_value": 1,           
    "distance_cm": 50,
    "state": "NORMAL",
    "led": "GREEN",
    "relay1_status": False,        
    "relay2_status": False,        
    "buzzer_status": False,        
    "system_healthy": True,        
    "last_error": "NONE"           
}


# MQTT CALLBACKS

def mqtt_success(rc):
    """Supports both paho-mqtt v1 integer rc and v2 ReasonCode."""
    return rc == 0 or str(rc).lower() in ("success", "0")


def on_connect(client, userdata, flags, rc, *extra):
    global mqtt_connected

    if mqtt_success(rc):
        mqtt_connected = True
        print("✅ MQTT connected")
        client.subscribe(TOPIC_TELEMETRY)
        print(f"📡 Subscribed to: {TOPIC_TELEMETRY}")
    else:
        mqtt_connected = False
        print("❌ MQTT connection error:", rc)


def on_disconnect(client, userdata, rc, *extra):
    global mqtt_connected
    mqtt_connected = False
    print("⚠️ MQTT disconnected:", rc)


def on_message(client, userdata, msg):
    global robot_data, last_message_time
    try:
        payload = msg.payload.decode()
        temp_data = json.loads(payload)

        # Updated to match robot_makerpoint.ino output
        robot_data["time_ms"] = temp_data.get("time_ms", 0)
        robot_data["infrared_value"] = temp_data.get("infrared_value", 1)
        robot_data["distance_cm"] = temp_data.get("distance_cm", 50)
        robot_data["state"] = temp_data.get("state", "NORMAL")
        robot_data["led"] = temp_data.get("led", "GREEN")

        # New fields from Maker Point
        robot_data["relay1_status"] = temp_data.get("relay1_status", False)
        robot_data["relay2_status"] = temp_data.get("relay2_status", False)
        robot_data["buzzer_status"] = temp_data.get("buzzer_status", False)
        robot_data["system_healthy"] = temp_data.get("system_healthy", True)
        robot_data["last_error"] = temp_data.get("last_error", "NONE")

        last_message_time = time.time()

        print(
            f"📡 Data received: {robot_data['state']} | "
            f"IR:{robot_data['infrared_value']} | "
            f"Distance:{robot_data['distance_cm']}cm"
        )

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON payload: {e}")
    except Exception as e:
        print(f"❌ MQTT message handling error: {e}")


# MQTT CLIENT

# Compatible with paho-mqtt v1 and v2
try:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
except Exception:
    client = mqtt.Client()

client.username_pw_set(MQTT_USER, MQTT_PASS)
client.tls_set(cert_reqs=ssl.CERT_NONE)
client.tls_insecure_set(True)

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

try:
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(MQTT_SERVER, MQTT_PORT, 60)
    client.loop_start()
    print("🔗 MQTT connection initiated...")
except Exception as e:
    print(f"❌ MQTT connection error: {e}")


# PYGAME INIT

pygame.init()

WIDTH, HEIGHT = 900, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Smart Robot Digital Twin - Maker Point SCADA")

clock = pygame.time.Clock()


# THEME COLORS (Cyberpunk / Modern Dark UI)

COLOR_BG = (10, 14, 23)          # Dark space background
COLOR_GRID = (22, 28, 42)        # Faint grid color
COLOR_PANEL_BG = (18, 22, 33)    # Translucent glassmorphism dark blue
COLOR_BORDER = (35, 45, 66)      # Sleek card borders
COLOR_TEXT_MAIN = (240, 245, 255) # Clean off-white
COLOR_TEXT_MUTED = (130, 145, 175) # Cool gray-blue for labels

# Status glow colors
COLOR_CYAN = (0, 240, 255)
COLOR_NEON_GREEN = (10, 230, 120)
COLOR_NEON_RED = (255, 55, 95)
COLOR_NEON_YELLOW = (255, 190, 10)

COLOR_ROBOT_BODY = (40, 85, 150)
COLOR_ROBOT_GLOW = (55, 120, 255)


# ROBOT PATH CONFIG (GO & RETURN)

robot_x = 120
robot_y = 300
robot_angle = 0.0
base_speed = 2.2
slow_speed = 0.75
current_point_idx = 1
moving_forward = True

line_points = [
    (50, 300),
    (180, 300),
    (280, 220),
    (420, 220),
    (540, 360),
    (680, 360),
    (800, 250),
    (880, 250)
]


# HELPERS: FONTS & RENDER

def get_font(size, bold=False):
    try:
        return pygame.font.SysFont("Helvetica", size, bold=bold)
    except:
        return pygame.font.SysFont("Arial", size, bold=bold)

def draw_text(text, x, y, size=18, color=COLOR_TEXT_MAIN, bold=False):
    font = get_font(size, bold=bold)
    img = font.render(text, True, color)
    screen.blit(img, (x, y))

def draw_glow_circle(surface, color, center, radius, alpha=40):
    """Draws a beautiful realistic radial glow effect."""
    glow_surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for r in range(radius, 0, -4):
        curr_alpha = int(alpha * (1.0 - r / radius))
        pygame.draw.circle(glow_surf, (*color, curr_alpha), (radius, radius), r)
    surface.blit(glow_surf, (center[0] - radius, center[1] - radius))


# INTERACTIVE BUTTON COORDS

btn_stop_rect = pygame.Rect(650, 102, 95, 36)
btn_run_rect = pygame.Rect(755, 102, 95, 36)


# DRAW FUNCTIONS

def draw_background():
    screen.fill(COLOR_BG)
    
    # Draw digital grid lines
    for x in range(0, WIDTH, 40):
        pygame.draw.line(screen, COLOR_GRID, (x, 90), (x, 460), 1)
    for y in range(90, 460, 40):
        pygame.draw.line(screen, COLOR_GRID, (0, y), (WIDTH, y), 1)
        
    # Subtle frame line
    pygame.draw.line(screen, COLOR_BORDER, (0, 90), (WIDTH, 90), 2)
    pygame.draw.line(screen, COLOR_BORDER, (0, 460), (WIDTH, 460), 2)

def state_color(state):
    if state == "STOP":
        return COLOR_NEON_RED
    if state == "WARNING":
        return COLOR_NEON_YELLOW
    return COLOR_NEON_GREEN

def draw_dashboard_header():
    # Header Background Panel
    header_rect = pygame.Rect(0, 0, WIDTH, 90)
    pygame.draw.rect(screen, COLOR_PANEL_BG, header_rect)
    
    # Glowing bottom line
    pygame.draw.rect(screen, COLOR_BORDER, (0, 88, WIDTH, 2))
    
    # Title & Subtitle
    draw_text("Smart Robot Digital Twin", 30, 15, 26, COLOR_TEXT_MAIN, True)
    draw_text("Maker Point SCADA • Real-time Synchronization", 30, 52, 14, COLOR_TEXT_MUTED)
    
    # Developer Signature Display
    draw_text("ENGINEERED BY", 500, 24, 11, COLOR_TEXT_MUTED, True)
    draw_text("Hafida Belayd", 500, 42, 16, COLOR_CYAN, True)
    
    # Status Badge with Heartbeat
    state = robot_data["state"]
    curr_color = state_color(state)
    
    # Heartbeat Pulse Animation
    ticks = pygame.time.get_ticks()
    pulse = int(100 + 50 * math.sin(ticks * 0.008))
    
    # Pulsing glow under indicator
    draw_glow_circle(screen, curr_color, (730, 45), 24, pulse // 4)
    pygame.draw.circle(screen, curr_color, (730, 45), 10)
    
    # State label
    draw_text("STATE:", 620, 34, 15, COLOR_TEXT_MUTED, True)
    draw_text(state, 755, 30, 22, curr_color, True)

def draw_track():
    # Outer wide shadow path
    pygame.draw.lines(
        screen,
        (25, 32, 50),
        False,
        line_points,
        22
    )
    
    # Glowing laser path line
    pygame.draw.lines(
        screen,
        COLOR_CYAN,
        False,
        line_points,
        4
    )
    
    # Glowing path waypoint circles
    for pt in line_points:
        draw_glow_circle(screen, COLOR_CYAN, pt, 12, 30)
        pygame.draw.circle(screen, COLOR_BG, pt, 6)
        pygame.draw.circle(screen, COLOR_CYAN, pt, 3)

def draw_robot():
    global robot_x, robot_y, robot_angle, current_point_idx, moving_forward
    
    state = robot_data["state"]
    led_state = robot_data["led"]
    distance = robot_data["distance_cm"]
    
    # Updated: Use relay status instead of speed
    relay1 = robot_data["relay1_status"]
    relay2 = robot_data["relay2_status"]
    relays_active = relay1 or relay2
    
    if state == "STOP" or not relays_active:
        speed = 0.0
    elif state == "WARNING":
        # Slow mode: IR sensor detects a hand/person/object in front.
        speed = slow_speed
    else:
        speed = base_speed
        
    if speed > 0:
        target_x, target_y = line_points[current_point_idx]
        dx = target_x - robot_x
        dy = target_y - robot_y
        dist = math.hypot(dx, dy)
        
        if dist < speed:
            robot_x = target_x
            robot_y = target_y
            
            # Go and Return Navigation
            if moving_forward:
                if current_point_idx < len(line_points) - 1:
                    current_point_idx += 1
                else:
                    moving_forward = False
                    current_point_idx -= 1
            else:
                if current_point_idx > 0:
                    current_point_idx -= 1
                else:
                    moving_forward = True
                    current_point_idx += 1
        else:
            robot_angle = math.atan2(dy, dx)
            robot_x += math.cos(robot_angle) * speed
            robot_y += math.sin(robot_angle) * speed

    # 1. Draw Distance Radar Scan Cone
    cone_angle = 0.45
    cone_len = max(30, min(160, int(distance * 2.2)))
    
    p_center = (int(robot_x), int(robot_y))
    p_left = (int(robot_x + math.cos(robot_angle - cone_angle) * cone_len),
              int(robot_y + math.sin(robot_angle - cone_angle) * cone_len))
    p_right = (int(robot_x + math.cos(robot_angle + cone_angle) * cone_len),
               int(robot_y + math.sin(robot_angle + cone_angle) * cone_len))
    
    cone_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    cone_color = state_color(state)
    pygame.draw.polygon(cone_surf, (*cone_color, 25), [p_center, p_left, p_right])
    pygame.draw.line(cone_surf, (*cone_color, 80), p_center, p_left, 2)
    pygame.draw.line(cone_surf, (*cone_color, 80), p_center, p_right, 2)
    screen.blit(cone_surf, (0, 0))
    
    # 2. Draw Robot Outer Glow Aura
    ticks = pygame.time.get_ticks()
    led_color = COLOR_NEON_GREEN
    if led_state == "RED": led_color = COLOR_NEON_RED
    elif led_state == "YELLOW": led_color = COLOR_NEON_YELLOW
    
    aura_pulse = int(32 + 10 * math.sin(ticks * 0.01))
    draw_glow_circle(screen, led_color, (int(robot_x), int(robot_y)), aura_pulse, 45)
    
    # 3. Metallic Outer Frame
    pygame.draw.circle(screen, (30, 36, 48), (int(robot_x), int(robot_y)), 20)
    pygame.draw.circle(screen, COLOR_BORDER, (int(robot_x), int(robot_y)), 20, 2)
    
    # 4. Glowing inner core (State Indicator)
    pygame.draw.circle(screen, state_color(state), (int(robot_x), int(robot_y)), 10)
    
    # 5. Glowing directional indicator
    front_x = int(robot_x + math.cos(robot_angle) * 16)
    front_y = int(robot_y + math.sin(robot_angle) * 16)
    pygame.draw.line(screen, COLOR_TEXT_MAIN, (int(robot_x), int(robot_y)), (front_x, front_y), 3)
    pygame.draw.circle(screen, COLOR_TEXT_MAIN, (front_x, front_y), 3)

def draw_telemetry_deck(mouse_pos):
    # Base Control Panel
    panel_rect = pygame.Rect(25, 470, 850, 110)
    pygame.draw.rect(screen, COLOR_PANEL_BG, panel_rect, border_radius=12)
    pygame.draw.rect(screen, COLOR_BORDER, panel_rect, 2, border_radius=12)
    

    # CARD 1: SYSTEM HEALTH & DIRECTION

    card1_rect = pygame.Rect(35, 482, 150, 86)
    pygame.draw.rect(screen, (15, 18, 26), card1_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, card1_rect, 1, border_radius=8)
    
    draw_text("SYSTEM STATE", 45, 492, 11, COLOR_TEXT_MUTED, True)
    state = robot_data["state"]
    draw_text(state, 45, 506, 17, state_color(state), True)
    
    # Direction indicator
    dir_text = "FORWARD →" if moving_forward else "← RETURN"
    dir_color = COLOR_CYAN if moving_forward else COLOR_NEON_YELLOW
    draw_text(dir_text, 45, 526, 11, dir_color, True)
        
    led = robot_data["led"]
    led_col = COLOR_NEON_GREEN
    if led == "RED": led_col = COLOR_NEON_RED
    elif led == "YELLOW": led_col = COLOR_NEON_YELLOW
    
    pygame.draw.circle(screen, led_col, (51, 552), 4)
    draw_text(f"LED: {led}", 63, 545, 11, COLOR_TEXT_MUTED)


    # CARD 2: RELAY STATUS (NEW - replaced speed)

    card2_rect = pygame.Rect(195, 482, 145, 86)
    pygame.draw.rect(screen, (15, 18, 26), card2_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, card2_rect, 1, border_radius=8)
    
    draw_text("RELAY STATUS", 205, 492, 11, COLOR_TEXT_MUTED, True)
    
    # Updated: Display relay status instead of speed
    relay1 = robot_data["relay1_status"]
    relay2 = robot_data["relay2_status"]
    relay_status = "ON" if (relay1 and relay2) else "OFF"
    relay_col = COLOR_NEON_GREEN if (relay1 and relay2) else COLOR_TEXT_MUTED
    
    draw_text(f"R1:{('🟢' if relay1 else '⚫')}", 205, 505, 12, COLOR_CYAN, True)
    draw_text(f"R2:{('🟢' if relay2 else '⚫')}", 205, 525, 12, COLOR_CYAN, True)
    
    # Status text
    draw_text(relay_status, 240, 515, 14, relay_col, True)


    # CARD 3: INFRARED SENSOR (Updated from line_value)

    card3_rect = pygame.Rect(350, 482, 115, 86)
    pygame.draw.rect(screen, (15, 18, 26), card3_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, card3_rect, 1, border_radius=8)
    
    draw_text("IR SENSOR", 360, 492, 11, COLOR_TEXT_MUTED, True)
    # Updated: Use infrared_value instead of line_value
    ir_val = robot_data["infrared_value"]
    draw_text(f"Val: {ir_val}", 360, 508, 17, COLOR_CYAN, True)
    
    # Sensor visualization
    for i in range(3):
        light_color = (30, 40, 55)
        if (i == 1 and ir_val == 1) or (i == 0 and ir_val == 0) or (i == 2 and ir_val == 2):
            light_color = COLOR_CYAN
            
        x_pos = 365 + (i * 18)
        if light_color == COLOR_CYAN:
            draw_glow_circle(screen, COLOR_CYAN, (x_pos, 544), 6, 25)
        pygame.draw.circle(screen, light_color, (x_pos, 544), 4)


    # CARD 4: DISTANCE SENSOR

    card4_rect = pygame.Rect(475, 482, 160, 86)
    pygame.draw.rect(screen, (15, 18, 26), card4_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, card4_rect, 1, border_radius=8)
    
    draw_text("DISTANCE SENSOR", 485, 492, 11, COLOR_TEXT_MUTED, True)
    dist = robot_data["distance_cm"]
    dist_color = COLOR_NEON_GREEN
    if dist < 20: dist_color = COLOR_NEON_RED
    elif dist < 50: dist_color = COLOR_NEON_YELLOW
    
    draw_text(f"{dist} cm", 485, 508, 17, dist_color, True)
    
    # Distance visual bar
    pygame.draw.rect(screen, (30, 36, 48), (485, 536, 140, 7), border_radius=3)
    fill_width = int(140 * min(1.0, dist / 100.0))
    if fill_width > 0:
        pygame.draw.rect(screen, dist_color, (485, 536, fill_width, 7), border_radius=3)


    # CARD 5: BUZZER & SYSTEM HEALTH (NEW)

    card5_rect = pygame.Rect(645, 482, 220, 86)
    pygame.draw.rect(screen, (15, 18, 26), card5_rect, border_radius=8)
    pygame.draw.rect(screen, COLOR_BORDER, card5_rect, 1, border_radius=8)
    
    draw_text("DEVICE STATUS", 655, 492, 10, COLOR_TEXT_MUTED, True)
    
    # Updated: Show Buzzer and System Health
    buzzer = robot_data["buzzer_status"]
    system_ok = robot_data["system_healthy"]
    
    buzz_text = "ACTIVE 🔊" if buzzer else "SILENT 🔇"
    buzz_col = COLOR_NEON_RED if buzzer else COLOR_TEXT_MUTED
    draw_text(f"Buzzer: {buzz_text}", 655, 510, 11, buzz_col, True)
    
    sys_text = "HEALTHY ✅" if system_ok else "ERROR ❌"
    sys_col = COLOR_NEON_GREEN if system_ok else COLOR_NEON_RED
    draw_text(f"System: {sys_text}", 655, 530, 11, sys_col, True)
    
    last_err = robot_data["last_error"]
    if last_err != "NONE":
        label = last_err
        if last_err == "PERSON_DETECTED_SLOW_MODE":
            label = "Person detected: SLOW"
        draw_text(f"Info: {label}", 655, 550, 9, COLOR_NEON_YELLOW)


def safe_publish_command(command):
    """Publishes STOP/RUN only when MQTT is connected."""
    if not mqtt_connected:
        print(f"⚠️ Cannot send {command}: MQTT is offline")
        return

    try:
        result = client.publish(TOPIC_COMMAND, command)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"✅ Command sent: {command}")
        else:
            print(f"❌ Command publish failed: {command} | rc={result.rc}")
    except Exception as e:
        print(f"❌ Command publish error: {e}")


def draw_command_buttons(mouse_pos):
    """Visible STOP/RUN controls for the SCADA interface."""
    stop_hover = btn_stop_rect.collidepoint(mouse_pos)
    run_hover = btn_run_rect.collidepoint(mouse_pos)

    stop_color = (180, 35, 60) if stop_hover else COLOR_NEON_RED
    run_color = (15, 190, 100) if run_hover else COLOR_NEON_GREEN

    pygame.draw.rect(screen, stop_color, btn_stop_rect, border_radius=9)
    pygame.draw.rect(screen, COLOR_BORDER, btn_stop_rect, 2, border_radius=9)
    draw_text("STOP", btn_stop_rect.x + 24, btn_stop_rect.y + 9, 14, COLOR_TEXT_MAIN, True)

    pygame.draw.rect(screen, run_color, btn_run_rect, border_radius=9)
    pygame.draw.rect(screen, COLOR_BORDER, btn_run_rect, 2, border_radius=9)
    draw_text("RUN", btn_run_rect.x + 30, btn_run_rect.y + 9, 14, COLOR_TEXT_MAIN, True)

    draw_text("Keyboard: S = STOP | R = RUN", 650, 145, 11, COLOR_TEXT_MUTED)


# MAIN LOOP

running = True

while running:
    mouse_pos = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                safe_publish_command("STOP")
            elif event.key == pygame.K_r:
                safe_publish_command("RUN")
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1: # Left mouse click
                if btn_stop_rect.collidepoint(event.pos):
                    safe_publish_command("STOP")
                elif btn_run_rect.collidepoint(event.pos):
                    safe_publish_command("RUN")

    # Render pipeline
    draw_background()
    draw_track()
    draw_robot()
    draw_dashboard_header()
    draw_command_buttons(mouse_pos)
    draw_telemetry_deck(mouse_pos)
    
    # Sub-footer instructions
    draw_text("SCADA Maker Point Edition • Relay Control, IR Sensor & Distance Monitoring Active", 30, 102, 13, COLOR_TEXT_MUTED)
    
    pygame.display.flip()
    clock.tick(60)


# CLEAN EXIT

print("\n🛑 Shutting down...")
client.loop_stop()
client.disconnect()
pygame.quit()
print("Goodbye!")