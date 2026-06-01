import sys
import time
import math
import random
import pygame
from typing import Dict, Tuple, List

# Local imports
from warehouse_map import NODES, ZONES, ZoneXTrafficController
from agv_agent import AGV
from telemetry_sender import TelemetrySender

# --- Color Palette (Dark Mode Aesthetic) ---
COLOR_BG = (10, 15, 30)         # Deep Navy Background
COLOR_TEXT_IVORY = (234, 235, 237) # Ivory Text / Headers
COLOR_GRID = (18, 28, 50)       # Muted Ivory Grid Lines (Subtle Contrast)
COLOR_LANE = (28, 42, 70)       # Guide paths/lanes
COLOR_TERRACOTTA = (195, 74, 54) # Terracotta Alerts / Zone X
COLOR_ZONE_FILL = (16, 26, 48)  # Slightly lighter navy for zones
COLOR_PANEL_BG = (13, 20, 38)   # Solid panel background for dashboard
COLOR_PANEL_BORDER = (35, 48, 79) # Dashboard border

# Accent States Colors
COLOR_STATE_IDLE = (78, 142, 247)   # Sleek Blue
COLOR_STATE_ENROUTE = (46, 204, 113) # Vivid Green
COLOR_STATE_WAIT = (241, 196, 15)   # Amber Yellow
COLOR_STATE_STOP = (231, 76, 60)    # Soft Red
COLOR_STATE_ARRIVED = (52, 152, 219) # Electric Cyan
COLOR_STATE_OFFLINE = (127, 140, 141) # Slate Grey

# --- Initialize Pygame ---
pygame.init()
pygame.display.set_caption("Multi-Agent AGV Fleet Coordination Simulator - Developed by Hafida Belayd")
screen = pygame.display.set_mode((1200, 800))
clock = pygame.time.Clock()

# --- Load Fonts ---
# Use default system fonts in case specific files are not present
font_large = pygame.font.SysFont("Helvetica", 22, bold=True)
font_medium = pygame.font.SysFont("Helvetica", 15, bold=True)
font_small = pygame.font.SysFont("Helvetica", 13, bold=False)
font_mono = pygame.font.SysFont("monospace", 12, bold=False)
font_mono_bold = pygame.font.SysFont("monospace", 13, bold=True)
font_giant = pygame.font.SysFont("Helvetica", 64, bold=True)

# --- Drawing Utilities ---
def draw_warning_stripes(surface: pygame.Surface, rect: Tuple[int, int, int, int], color: Tuple[int, int, int], width: int = 4):
    """Draws classic safety stripes inside a rect, clipped to bounds."""
    x, y, w, h = rect
    old_clip = surface.get_clip()
    surface.set_clip(rect)
    
    stripe_spacing = 20
    for offset in range(-h, w + h, stripe_spacing):
        pygame.draw.line(surface, color, (x + offset, y), (x + offset + h, y + h), width)
        
    surface.set_clip(old_clip)

def draw_sensor_cone(surface: pygame.Surface, agv: AGV):
    """Draws a translucent sensor cone in front of the AGV."""
    if not agv.path or agv.current_node_idx >= len(agv.path):
        return
        
    # Get direction of travel
    target_node = agv.path[agv.current_node_idx]
    tx, ty = NODES[target_node]
    dx = tx - agv.x
    dy = ty - agv.y
    dist = math.sqrt(dx**2 + dy**2)
    
    if dist > 0:
        angle = math.atan2(dy, dx)
        fov_rad = math.radians(agv.sensor_angle_deg)
        cone_length = min(150, max(60, agv.distance_front_cm))  # Visual cap
        
        # Calculate vertices of the cone triangle
        p1 = (agv.x, agv.y)
        p2 = (agv.x + math.cos(angle - fov_rad/2) * cone_length, agv.y + math.sin(angle - fov_rad/2) * cone_length)
        p3 = (agv.x + math.cos(angle + fov_rad/2) * cone_length, agv.y + math.sin(angle + fov_rad/2) * cone_length)
        
        # Determine if AGV is inside ZONE X
        is_in_zone_x = (agv.current_zone == 'X' or (290 <= agv.x <= 510 and 290 <= agv.y <= 510))
        
        # Determine cone color based on obstacle state or zone X presence
        is_alert = (agv.state == "STOP" or agv.distance_front_cm < 80.0)
        
        if is_in_zone_x:
            # Change sensor cone to Terracotta in ZONE X
            cone_color = (COLOR_TERRACOTTA[0], COLOR_TERRACOTTA[1], COLOR_TERRACOTTA[2], 60)
        elif is_alert:
            cone_color = (195, 74, 54, 40)
        else:
            cone_color = (46, 204, 113, 20)
        
        # Pygame requires an alpha-enabled surface to draw translucent shapes
        cone_surface = pygame.Surface((800, 800), pygame.SRCALPHA)
        pygame.draw.polygon(cone_surface, cone_color, [p1, p2, p3])
        
        # Draw dotted indicator lines on the cone boundaries
        pygame.draw.line(cone_surface, (cone_color[0], cone_color[1], cone_color[2], 100), p1, p2, 1)
        pygame.draw.line(cone_surface, (cone_color[0], cone_color[1], cone_color[2], 100), p1, p3, 1)
        
        surface.blit(cone_surface, (0, 0))

def draw_state_tag(surface: pygame.Surface, x: int, y: int, state: str):
    """Draws a styled status badge/tag for the AGV state."""
    state_colors = {
        "IDLE": COLOR_STATE_IDLE,
        "EN_ROUTE": COLOR_STATE_ENROUTE,
        "WAIT": COLOR_STATE_WAIT,
        "STOP": COLOR_STATE_STOP,
        "ARRIVED": COLOR_STATE_ARRIVED
    }
    color = state_colors.get(state, COLOR_STATE_OFFLINE)
    
    # Draw pill container
    rect = pygame.Rect(x, y, 90, 22)
    pygame.draw.rect(surface, (color[0], color[1], color[2], 40), rect, border_radius=4)
    pygame.draw.rect(surface, color, rect, width=1, border_radius=4)
    
    # Draw text
    text_surf = font_small.render(state, True, color)
    text_rect = text_surf.get_rect(center=rect.center)
    surface.blit(text_surf, text_rect)

# --- Main Simulator Controller ---
def main():
    # Setup agents
    agv1 = AGV("AGV-01", "A", (255, 120, 80)) # Warm Coral
    agv2 = AGV("AGV-02", "B", (46, 204, 250)) # Bright Teal
    
    # Setup coordinators
    traffic_controller = ZoneXTrafficController()
    telemetry_sender = TelemetrySender(
        webhook_url="http://127.0.0.1:5000/webhook"
    )
    
    # Simulation Control Variables
    paused = False
    emergency_stop = False
    telemetry_timer = 0.0
    
    # Clickable Buttons Coordinates
    btn_pause_rect = pygame.Rect(850, 715, 130, 45)
    btn_estop_rect = pygame.Rect(1010, 715, 140, 45)
    
    # Pre-populate the telemetry logs file with headers/formatting note
    with open("telemetry_logs.json", "w") as f:
        # Erase existing log and start fresh
        pass

    print("🔑 Interactive Controls:")
    print("  [SPACE] - Toggle Pause/Resume")
    print("  [E]     - Toggle Emergency Stop")
    print("  [ESC]   - Exit Simulation")

    # --- Game Loop ---
    running = True
    while running:
        # Delta time calculation
        dt = clock.tick(60) / 1000.0
        
        # 1. Event Handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_e:
                    emergency_stop = not emergency_stop
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_pos = pygame.mouse.get_pos()
                    if btn_pause_rect.collidepoint(mouse_pos):
                        paused = not paused
                    elif btn_estop_rect.collidepoint(mouse_pos):
                        emergency_stop = not emergency_stop

        # 2. Physics & Logic Updates
        if not paused:
            # Generate new missions automatically when IDLE
            # AGV-01 Mission Planning Loop
            if agv1.state == "IDLE" and not emergency_stop:
                choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv1.current_zone]
                target = random.choice(choices)
                agv1.start_mission(target)
                
            # AGV-02 Mission Planning Loop
            if agv2.state == "IDLE" and not emergency_stop:
                choices = [z for z in ['A', 'B', 'C', 'D'] if z != agv2.current_zone]
                target = random.choice(choices)
                agv2.start_mission(target)

            # Update AGVs physics and collision sensors
            agv1.update(dt, agv2, traffic_controller, emergency_stop)
            agv2.update(dt, agv1, traffic_controller, emergency_stop)
            
            # Telemetry dispatch clock (every 1.5 seconds)
            telemetry_timer += dt
            if telemetry_timer >= 1.5:
                telemetry_timer = 0.0
                # Dispatch payload snapshots to background thread Queue
                telemetry_sender.submit_telemetry(agv1.get_telemetry_payload())
                telemetry_sender.submit_telemetry(agv2.get_telemetry_payload())

        # 3. DRAWING PHASE
        # Clear Screen
        screen.fill(COLOR_BG)
        
        # --- PART A: WAREHOUSE MAP (LEFT 800x800) ---
        # Draw grid lines (Ivory with low contrast for blueprint aesthetic)
        grid_surface = pygame.Surface((800, 800))
        grid_surface.fill(COLOR_BG)
        for x in range(0, 800, 50):
            pygame.draw.line(grid_surface, COLOR_GRID, (x, 0), (x, 800), 1)
        for y in range(0, 800, 50):
            pygame.draw.line(grid_surface, COLOR_GRID, (0, y), (800, y), 1)
        screen.blit(grid_surface, (0, 0))

        # Draw Guide Paths / Lanes
        # Connect nodes visually
        for node, connections in NODES.items():
            for conn_node in connections:
                # To prevent drawing duplicate lines in graph
                if conn_node in NODES:
                    pygame.draw.line(screen, COLOR_LANE, NODES[node], NODES[conn_node], 2)

        # Draw Zones
        for zone_name, rect in ZONES.items():
            # Zone X gets custom warning styles
            if zone_name == 'X':
                # Translucent terracotta container
                fill_surf = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
                fill_surf.fill((COLOR_TERRACOTTA[0], COLOR_TERRACOTTA[1], COLOR_TERRACOTTA[2], 25))
                screen.blit(fill_surf, (rect[0], rect[1]))
                
                # Warning stripes inside Zone X
                draw_warning_stripes(screen, rect, (COLOR_TERRACOTTA[0], COLOR_TERRACOTTA[1], COLOR_TERRACOTTA[2], 12), width=3)
                
                # Thick alert outline
                is_x_busy = traffic_controller.is_occupied()
                border_width = 3 if is_x_busy else 1
                pygame.draw.rect(screen, COLOR_TERRACOTTA, rect, border_width, border_radius=12)
                
                # Pulsing outline if occupied
                if is_x_busy:
                    pulse = int(abs(math.sin(time.time() * 5)) * 4) + 1
                    pygame.draw.rect(screen, COLOR_TERRACOTTA, 
                                     (rect[0]-pulse, rect[1]-pulse, rect[2]+pulse*2, rect[3]+pulse*2), 
                                     1, border_radius=12+pulse)
                
                # Zone X Labels
                lbl_surf = font_medium.render("ZONE X", True, COLOR_TERRACOTTA)
                screen.blit(lbl_surf, (rect[0] + 15, rect[1] + 15))
                
                lbl_sub = font_small.render("CRITICAL INTERSECTION", True, (160, 100, 95))
                screen.blit(lbl_sub, (rect[0] + 15, rect[1] + 40))
                
                # Show current lock holder
                occupant = traffic_controller.get_occupant()
                if occupant:
                    lbl_occ = font_mono.render(f"LOCKED BY: {occupant}", True, COLOR_TEXT_IVORY)
                    screen.blit(lbl_occ, (rect[0] + 15, rect[1] + rect[3] - 30))
            else:
                # Draw standard zones (A, B, C, D, R)
                # Background panel
                pygame.draw.rect(screen, COLOR_ZONE_FILL, rect, border_radius=12)
                pygame.draw.rect(screen, COLOR_PANEL_BORDER, rect, 1, border_radius=12)
                
                # Big background letter
                letter_color = (40, 50, 75) if zone_name != 'R' else (46, 204, 113, 30)
                letter_surf = font_giant.render(zone_name, True, letter_color)
                letter_rect = letter_surf.get_rect(center=(rect[0] + rect[2]//2, rect[1] + rect[3]//2))
                screen.blit(letter_surf, letter_rect)
                
                # Zone name label
                zone_titles = {
                    'A': "ZONE A - LOAD",
                    'B': "ZONE B - UNLOAD",
                    'C': "ZONE C - SORTING",
                    'D': "ZONE D - PACKING",
                    'R': "ZONE R - CHARGING"
                }
                title_color = COLOR_TEXT_IVORY if zone_name != 'R' else COLOR_STATE_ENROUTE
                lbl_surf = font_small.render(zone_titles[zone_name], True, title_color)
                screen.blit(lbl_surf, (rect[0] + 10, rect[1] + 10))

        # Draw Node checkpoints (Small anchor circles)
        for node_name, coord in NODES.items():
            if node_name not in ['X', 'A', 'B', 'C', 'D', 'R']:
                pygame.draw.circle(screen, (30, 45, 75), coord, 5)
                pygame.draw.circle(screen, COLOR_PANEL_BORDER, coord, 3)

        # Draw AGV Sensor Cones (Drawn below the actual AGVs)
        draw_sensor_cone(screen, agv1)
        draw_sensor_cone(screen, agv2)

        # Draw AGV Agents
        for agv in [agv1, agv2]:
            rx, ry = agv.get_render_position(offset_px=10) # offset right
            
            # Pulse glow if waiting or stopped
            if agv.state in ["WAIT", "STOP"]:
                p_color = COLOR_TERRACOTTA if agv.state == "STOP" else COLOR_STATE_WAIT
                pulse = int(abs(math.sin(time.time() * 8)) * 5) + 2
                pygame.draw.circle(screen, (p_color[0], p_color[1], p_color[2], 50), (int(rx), int(ry)), 20 + pulse, 1)

            # AGV Chassis circle
            pygame.draw.circle(screen, agv.color, (int(rx), int(ry)), 16)
            pygame.draw.circle(screen, COLOR_TEXT_IVORY, (int(rx), int(ry)), 16, 2)
            
            # Direction Arrow overlay
            if agv.path and agv.current_node_idx < len(agv.path):
                tn = agv.path[agv.current_node_idx]
                tx, ty = NODES[tn]
                adx = tx - agv.x
                ady = ty - agv.y
                adist = math.sqrt(adx**2 + ady**2)
                if adist > 0:
                    ax = rx + (adx / adist) * 12
                    ay = ry + (ady / adist) * 12
                    pygame.draw.line(screen, COLOR_BG, (rx, ry), (ax, ay), 3)
                    pygame.draw.circle(screen, COLOR_TEXT_IVORY, (int(ax), int(ay)), 3)

            # Draw tiny AGV ID label
            lbl_surf = font_mono.render(agv.agv_id, True, COLOR_TEXT_IVORY)
            lbl_rect = lbl_surf.get_rect(center=(int(rx), int(ry) - 25))
            # Background behind label
            lbl_bg = pygame.Rect(lbl_rect.x - 4, lbl_rect.y - 2, lbl_rect.width + 8, lbl_rect.height + 4)
            pygame.draw.rect(screen, COLOR_BG, lbl_bg, border_radius=3)
            pygame.draw.rect(screen, COLOR_PANEL_BORDER, lbl_bg, 1, border_radius=3)
            screen.blit(lbl_surf, lbl_rect)
            
            # Tiny battery bar above label
            bat_color = COLOR_STATE_ENROUTE if agv.battery_pct > 50 else (COLOR_STATE_WAIT if agv.battery_pct > 20 else COLOR_STATE_STOP)
            bat_rect_bg = pygame.Rect(lbl_rect.x - 4, lbl_rect.y - 8, lbl_rect.width + 8, 4)
            pygame.draw.rect(screen, (40, 45, 55), bat_rect_bg)
            bat_width = int((lbl_rect.width + 8) * (agv.battery_pct / 100.0))
            pygame.draw.rect(screen, bat_color, (bat_rect_bg.x, bat_rect_bg.y, bat_width, 4))


        # --- PART B: DASHBOARD PANEL (RIGHT 400x800) ---
        # Panel Background
        pygame.draw.rect(screen, COLOR_PANEL_BG, (800, 0, 400, 800))
        pygame.draw.line(screen, COLOR_PANEL_BORDER, (800, 0), (800, 800), 2)
        
        # Panel Title
        title_surf = font_large.render("FLEET MANAGER", True, COLOR_TEXT_IVORY)
        screen.blit(title_surf, (820, 20))
        
        subtitle_surf = font_small.render("Real-Time Telemetry & Systems Status", True, (120, 135, 165))
        screen.blit(subtitle_surf, (820, 50))
        
        dev_surf = font_mono.render("DEVELOPED BY: HAFIDA BELAYD", True, (100, 120, 150))
        screen.blit(dev_surf, (820, 70))
        
        # Draw Telemetry Cards
        # Draw Telemetry Cards
        y_offset = 90
        for agv in [agv1, agv2]:
            # Detect if AGV is inside ZONE X
            is_in_zone_x = (agv.current_zone == 'X' or (290 <= agv.x <= 510 and 290 <= agv.y <= 510))
            
            # Sophisticated flat styling - border color turns Terracotta when inside Zone X
            card_border_color = COLOR_TERRACOTTA if is_in_zone_x else COLOR_PANEL_BORDER
            left_indicator_color = COLOR_TERRACOTTA if is_in_zone_x else agv.color
            
            # Card Container
            card_rect = pygame.Rect(820, y_offset, 360, 240)
            pygame.draw.rect(screen, COLOR_ZONE_FILL, card_rect, border_radius=12)
            pygame.draw.rect(screen, card_border_color, card_rect, 1, border_radius=12)
            
            # Highlight border with left indicator stripe
            pygame.draw.rect(screen, left_indicator_color, (820, y_offset, 6, 240), border_radius=12)
            
            # Card Header
            id_surf = font_large.render(agv.agv_id, True, COLOR_TEXT_IVORY)
            screen.blit(id_surf, (840, y_offset + 15))
            
            # ONLINE/OFFLINE Status LED
            led_color = COLOR_STATE_ENROUTE if agv.connectivity_status == "ONLINE" else COLOR_STATE_OFFLINE
            pygame.draw.circle(screen, led_color, (940, y_offset + 28), 6)
            status_lbl = font_mono.render(agv.connectivity_status, True, led_color)
            screen.blit(status_lbl, (952, y_offset + 22))

            # State tag
            draw_state_tag(screen, 1070, y_offset + 17, agv.state)

            # Divider line inside card
            pygame.draw.line(screen, COLOR_PANEL_BORDER, (840, y_offset + 48), (1160, y_offset + 48), 1)

            # Row 1: Battery & Temperature
            bat_pct = int(round(agv.battery_pct))
            bat_lbl = font_small.render("Battery:", True, (120, 135, 165))
            bat_val = font_mono_bold.render(f"{bat_pct:3d}%", True, COLOR_TEXT_IVORY)
            screen.blit(bat_lbl, (840, y_offset + 56))
            screen.blit(bat_val, (900, y_offset + 55))
            
            # Flat Minimalist Battery Progress Bar
            bat_color = COLOR_STATE_ENROUTE if agv.battery_pct > 50 else (COLOR_STATE_WAIT if agv.battery_pct > 20 else COLOR_STATE_STOP)
            pygame.draw.rect(screen, (25, 35, 55), (840, y_offset + 74, 140, 6), border_radius=3)
            pygame.draw.rect(screen, bat_color, (840, y_offset + 74, int(140 * (agv.battery_pct/100.0)), 6), border_radius=3)

            temp_sub = font_small.render("Motor Temp", True, (120, 135, 165))
            temp_val = font_mono_bold.render(f"{agv.temperature_c:4.1f}°C", True, COLOR_TEXT_IVORY)
            screen.blit(temp_sub, (1030, y_offset + 56))
            screen.blit(temp_val, (1030, y_offset + 74))

            # Row 2: Speed & Proximity Distance
            speed_sub = font_small.render("Speed:", True, (120, 135, 165))
            speed_val = font_mono_bold.render(f"{agv.speed_mps:4.2f} m/s", True, COLOR_TEXT_IVORY)
            screen.blit(speed_sub, (840, y_offset + 95))
            screen.blit(speed_val, (900, y_offset + 94))
            
            # Flat Minimalist Speed Progress Bar
            speed_pct = min(1.0, max(0.0, agv.speed_mps / agv.max_speed_mps))
            pygame.draw.rect(screen, (25, 35, 55), (840, y_offset + 113, 140, 6), border_radius=3)
            pygame.draw.rect(screen, COLOR_STATE_ARRIVED, (840, y_offset + 113, int(140 * speed_pct), 6), border_radius=3)

            dist_alert = (agv.distance_front_cm < 80.0 and agv.state in ["STOP", "EN_ROUTE"])
            dist_color = COLOR_TERRACOTTA if dist_alert else COLOR_TEXT_IVORY
            dist_val = font_mono_bold.render(f"{int(agv.distance_front_cm):3d} cm", True, dist_color)
            dist_sub = font_small.render("Obstacle Front", True, (120, 135, 165))
            screen.blit(dist_sub, (1030, y_offset + 95))
            screen.blit(dist_val, (1030, y_offset + 113))

            # Row 3: Critical Zone X Alert Warning
            if is_in_zone_x:
                if int(time.time() * 3.0) % 2 == 0:
                    warn_surf = font_mono_bold.render(f"⚠️ WARNING: {agv.agv_id} IN ZONE X", True, COLOR_TERRACOTTA)
                    screen.blit(warn_surf, (840, y_offset + 130))

            # Divider 2
            pygame.draw.line(screen, COLOR_PANEL_BORDER, (840, y_offset + 152), (1160, y_offset + 152), 1)

            # Row 4: Mission ID, Route and Odometer
            mission_lbl = font_mono.render(f"Mission: {agv.mission_id}", True, (140, 155, 185))
            screen.blit(mission_lbl, (840, y_offset + 162))

            route_txt = f"Route  : {agv.current_zone} ➔ {agv.target_zone}" if agv.path else f"Route  : Static at {agv.current_zone}"
            route_lbl = font_small.render(route_txt, True, COLOR_TEXT_IVORY)
            screen.blit(route_lbl, (840, y_offset + 182))

            odo_lbl = font_small.render("Odometer:", True, (120, 135, 165))
            odo_val = font_mono_bold.render(f"{agv.total_distance_m:5.2f} m", True, COLOR_STATE_ARRIVED)
            screen.blit(odo_lbl, (840, y_offset + 205))
            screen.blit(odo_val, (920, y_offset + 204))

            y_offset += 260

        # --- PART C: SYSTEM NETWORK STATS PANEL (BOTTOM RIGHT) ---
        sys_rect = pygame.Rect(820, 600, 360, 95)
        pygame.draw.rect(screen, COLOR_ZONE_FILL, sys_rect, border_radius=12)
        pygame.draw.rect(screen, COLOR_PANEL_BORDER, sys_rect, 1, border_radius=12)
        
        sys_title = font_medium.render("TELEMETRY GATEWAYS", True, COLOR_TEXT_IVORY)
        screen.blit(sys_title, (835, 610))
        
        # Webhook Indicator
        web_ok = "OK" in telemetry_sender.last_webhook_status
        web_color = COLOR_STATE_ENROUTE if web_ok else (COLOR_STATE_OFFLINE if "IDLE" in telemetry_sender.last_webhook_status else COLOR_TERRACOTTA)
        web_lbl = font_mono.render(f"Webhook Gateway: {telemetry_sender.last_webhook_status}", True, web_color)
        screen.blit(web_lbl, (835, 635))

        # MQTT Indicator
        mqtt_ok = "CONNECTED" in telemetry_sender.last_mqtt_status
        mqtt_color = COLOR_STATE_ENROUTE if mqtt_ok else (COLOR_STATE_WAIT if "CONNECTING" in telemetry_sender.last_mqtt_status else COLOR_TERRACOTTA)
        mqtt_lbl = font_mono.render(f"MQTT Broker: {telemetry_sender.last_mqtt_status}", True, mqtt_color)
        screen.blit(mqtt_lbl, (835, 655))

        # Local logs helper note
        logs_lbl = font_mono.render("Local Logs     : telemetry_logs.json [APPENDING]", True, (130, 200, 130))
        screen.blit(logs_lbl, (835, 675))

        # --- PART D: INTERACTIVE CONTROL BUTTONS (BOTTOM) ---
        # 1. Pause Button
        btn_pause_color = COLOR_STATE_WAIT if paused else (50, 65, 95)
        pygame.draw.rect(screen, btn_pause_color, btn_pause_rect, border_radius=5)
        pygame.draw.rect(screen, COLOR_TEXT_IVORY, btn_pause_rect, 1, border_radius=5)
        p_txt = "RESUME" if paused else "PAUSE"
        btn_p_surf = font_medium.render(p_txt, True, COLOR_TEXT_IVORY)
        btn_p_rect = btn_p_surf.get_rect(center=btn_pause_rect.center)
        screen.blit(btn_p_surf, btn_p_rect)

        # 2. Emergency Stop Button
        btn_estop_color = COLOR_TERRACOTTA if emergency_stop else (115, 35, 30)
        pygame.draw.rect(screen, btn_estop_color, btn_estop_rect, border_radius=5)
        pygame.draw.rect(screen, COLOR_TEXT_IVORY, btn_estop_rect, 2 if emergency_stop else 1, border_radius=5)
        
        # Pulse the text if active
        e_color = COLOR_TEXT_IVORY
        if emergency_stop:
            e_color = (255, 200, 200) if int(time.time() * 4) % 2 == 0 else COLOR_TEXT_IVORY
        btn_e_surf = font_medium.render("E-STOP", True, e_color)
        btn_e_rect = btn_e_surf.get_rect(center=btn_estop_rect.center)
        screen.blit(btn_e_surf, btn_e_rect)

        # 3. Flashing Big Warning Overlay if E-Stop is active
        if emergency_stop:
            # We can flash an alert border around the map
            if int(time.time() * 2) % 2 == 0:
                pygame.draw.rect(screen, COLOR_TERRACOTTA, (0, 0, 800, 800), 8)
                
                # Draw small HUD warning text
                warn_surf = font_large.render("⚠️ EMERGENCY STOP ACTIVE ⚠️", True, COLOR_TERRACOTTA)
                warn_rect = warn_surf.get_rect(center=(400, 40))
                pygame.draw.rect(screen, COLOR_BG, (warn_rect.x-10, warn_rect.y-5, warn_rect.width+20, warn_rect.height+10), border_radius=4)
                pygame.draw.rect(screen, COLOR_TERRACOTTA, (warn_rect.x-10, warn_rect.y-5, warn_rect.width+20, warn_rect.height+10), 1, border_radius=4)
                screen.blit(warn_surf, warn_rect)

        # Draw visual coordinates legend/help at top of the map
        help_surf = font_small.render("Grid: 100px = 1.0m | Press [SPACE] Pause | [E] E-Stop", True, (100, 115, 140))
        screen.blit(help_surf, (15, 15))

        # Render screen
        pygame.display.flip()

    # Clean shutdown
    print("Terminating telemetry threads...")
    telemetry_sender.stop()
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
