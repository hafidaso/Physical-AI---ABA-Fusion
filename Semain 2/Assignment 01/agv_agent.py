import time
import math
import random
from typing import List, Tuple, Dict, Optional, Any
from warehouse_map import NODES, find_shortest_path, ZoneXTrafficController

class AGV:
    """
    Represents an Automated Guided Vehicle (AGV) with navigation, 
    obstacle avoidance, battery management, and telemetry generation.
    """
    def __init__(self, agv_id: str, start_zone: str, color: Tuple[int, int, int]):
        self.agv_id = agv_id
        self.color = color
        
        # State Machine States: 'IDLE', 'EN_ROUTE', 'WAIT', 'STOP', 'ARRIVED'
        self.state = "IDLE"
        
        # Navigation
        self.current_zone = start_zone
        self.target_zone = start_zone
        self.path: List[str] = []
        self.current_node_idx = 0
        
        # Position (floats, pixel coordinates matching NODES)
        start_coords = NODES[start_zone]
        self.x = float(start_coords[0])
        self.y = float(start_coords[1])
        
        # Physical Attributes
        self.battery_pct = 100.0
        self.max_speed_mps = 1.0  # 1.0 m/s = 100 px/s
        self.speed_mps = 0.0
        self.total_distance_m = 0.0
        self.temperature_c = 25.0
        self.connectivity_status = "ONLINE"
        
        # Sensor
        self.distance_front_cm = 300.0  # obstacle distance in cm
        self.sensor_angle_deg = 45.0    # 45-degree field of view cone
        
        # Mission Tracking
        self.mission_count = 0
        self.mission_id = "N/A"
        self.last_state_change = time.time()
        
        # Charging flag
        self.is_charging = False
        
        # Lock acquired flag for Zone X
        self.has_zone_x_lock = False

    @property
    def position_meters(self) -> Dict[str, float]:
        """Convert pixel coordinates to meters (assuming (0,0) is top-left, 100px = 1m)."""
        # Truncate to 2 decimal places to match target JSON schema
        return {
            "x": round(self.x / 100.0, 2),
            "y": round(self.y / 100.0, 2),
            "zone": self.current_zone
        }

    def start_mission(self, target_zone: str):
        """Plans a path and starts a mission to the target zone."""
        self.target_zone = target_zone
        path = find_shortest_path(self.current_zone, target_zone)
        
        if path:
            self.path = path
            self.current_node_idx = 0
            self.mission_count += 1
            # Generate Mission ID in format M-YYYY-MM-DD-XX
            date_str = time.strftime("%Y-%m-%d")
            self.mission_id = f"M-{date_str}-{self.agv_id[-2:]}-{self.mission_count:02d}"
            self.state = "EN_ROUTE"
            self.is_charging = False
            self.speed_mps = self.max_speed_mps
        else:
            self.state = "IDLE"
            self.speed_mps = 0.0

    def update(self, dt: float, other_agv: 'AGV', traffic_controller: ZoneXTrafficController, emergency_stop: bool = False):
        """
        Updates AGV physics, navigation, battery, temperature, sensors, 
        and coordinates yielding at ZONE X.
        dt: delta time in seconds.
        """
        # Handle emergency stop immediately
        if emergency_stop:
            self.state = "STOP"
            self.speed_mps = 0.0
            # Cool down slowly when stopped
            self.temperature_c = max(24.0, self.temperature_c - 0.05 * dt)
            return
        # 1. Connectivity status simulation (mostly ONLINE, brief dropouts for realism)
        if self.connectivity_status == "ONLINE":
            if random.random() < 0.0005:  # very rare connection drop
                self.connectivity_status = "OFFLINE"
        else:
            if random.random() < 0.2:     # quick automatic reconnection
                self.connectivity_status = "ONLINE"
        
        # 2. Battery & Temperature physics
        if self.state == "EN_ROUTE" and self.speed_mps > 0:
            # Deplete battery (takes ~3 minutes of continuous movement to empty)
            self.battery_pct = max(0.0, self.battery_pct - 0.5 * dt)
            # Motor heats up under load
            self.temperature_c = min(48.5, self.temperature_c + 0.15 * dt + random.uniform(-0.05, 0.05))
        elif self.is_charging:
            # Charge battery at 8.0% per second
            self.battery_pct = min(100.0, self.battery_pct + 8.0 * dt)
            # Cool down while charging
            self.temperature_c = max(24.5, self.temperature_c - 0.3 * dt)
        else:
            # Cool down slowly when stopped or idle
            self.temperature_c = max(24.0, self.temperature_c - 0.05 * dt)

        # 3. Handle Auto-charging logic
        if self.battery_pct < 20.0 and not self.is_charging and self.target_zone != "R":
            # If battery is low, wait until current mission is complete, then go charge.
            # If currently IDLE, go charge immediately.
            if self.state in ["IDLE", "ARRIVED"]:
                self.start_mission("R")

        # 4. Obstacle Proximity Detection (Distance to other AGV)
        # Compute distance and relative direction
        dx = other_agv.x - self.x
        dy = other_agv.y - self.y
        dist_px = math.sqrt(dx**2 + dy**2)
        
        # We assume 1 pixel = 1 cm for obstacle detection distance.
        self.distance_front_cm = dist_px
        
        # Detect if other AGV is in front (45-degree field of view cone)
        is_obstacle_ahead = False
        if self.state == "EN_ROUTE" and len(self.path) > 0 and self.current_node_idx < len(self.path):
            # Direction vector of travel
            target_node = self.path[self.current_node_idx]
            tx, ty = NODES[target_node]
            vx = tx - self.x
            vy = ty - self.y
            v_len = math.sqrt(vx**2 + vy**2)
            
            if v_len > 0 and dist_px > 0:
                ux, uy = vx / v_len, vy / v_len
                # Cosine of angle between direction of travel and vector to other AGV
                dot = (dx * ux + dy * uy) / dist_px
                # If dot product > cos(45 degrees) = 0.707, it's inside our forward cone
                if dot > 0.707:
                    # Determine if they are traveling in opposite directions
                    is_opposite = False
                    if other_agv.state == "EN_ROUTE" and other_agv.path and other_agv.current_node_idx < len(other_agv.path):
                        otx, oty = NODES[other_agv.path[other_agv.current_node_idx]]
                        ovx = otx - other_agv.x
                        ovy = oty - other_agv.y
                        ov_len = math.sqrt(ovx**2 + ovy**2)
                        if ov_len > 0:
                          oux, ouy = ovx / ov_len, ovy / ov_len
                          align = ux * oux + uy * ouy
                          if align < -0.5:
                              is_opposite = True
                    
                    if not is_opposite:
                        is_obstacle_ahead = True

        # Handle stopping for close obstacles
        obstacle_stop = False
        if is_obstacle_ahead and self.distance_front_cm < 80.0:
            # Safety stop! Wait for other AGV to clear
            obstacle_stop = True
            
        # 5. Path navigation, Zone X yielding, or Charging
        if obstacle_stop:
            self.state = "STOP"
            self.speed_mps = 0.0
        else:
            if self.state in ["EN_ROUTE", "STOP"]:
                self.navigate_path(dt, traffic_controller)
            elif self.state == "WAIT":
                if self.is_charging:
                    self.speed_mps = 0.0
                    if self.battery_pct >= 100.0:
                        self.is_charging = False
                        self.state = "ARRIVED"
                        self.target_zone = "R_CHARGED"  # Prevent infinite charging loop
                        self.current_zone = "R"
                        self.last_state_change = time.time()
                else:
                    self.navigate_path(dt, traffic_controller)
            elif self.state == "ARRIVED":
                self.speed_mps = 0.0
                # Wait 1.5 seconds at arrival, then become IDLE (or start charging if at R)
                if time.time() - self.last_state_change > 1.5:
                    if self.target_zone == "R":
                        self.is_charging = True
                        self.state = "WAIT"  # wait in WAIT state while charging
                        self.last_state_change = time.time()
                    else:
                        self.state = "IDLE"
                        self.last_state_change = time.time()

    def navigate_path(self, dt: float, traffic_controller: ZoneXTrafficController):
        """Executes one step of movement along the path and coordinates Zone X locks."""
        if not self.path or self.current_node_idx >= len(self.path):
            self.state = "ARRIVED"
            self.last_state_change = time.time()
            self.speed_mps = 0.0
            return

        target_node = self.path[self.current_node_idx]
        tx, ty = NODES[target_node]
        
        # Calculate displacement to next node
        dx = tx - self.x
        dy = ty - self.y
        dist = math.sqrt(dx**2 + dy**2)
        
        # Traffic Coordination logic for ZONE X
        # Check if we are approaching Zone X
        # Node 'X' is the critical node. If the target node is 'X' and we don't have the lock:
        if target_node == 'X' and not self.has_zone_x_lock:
            # Request lock
            if traffic_controller.request_entry(self.agv_id):
                self.has_zone_x_lock = True
                self.state = "EN_ROUTE"
                self.speed_mps = self.max_speed_mps
            else:
                # Must yield! Stop at gate and set state to WAIT
                self.state = "WAIT"
                self.speed_mps = 0.0
                return  # Do not advance position

        # Release Zone X lock once we have crossed it
        # Release occurs when we reach the node *after* 'X' in our path
        if self.has_zone_x_lock and self.current_node_idx > 0:
            previous_node = self.path[self.current_node_idx - 1]
            if previous_node == 'X':
                traffic_controller.release_zone(self.agv_id)
                self.has_zone_x_lock = False

        # Calculate speed in pixels per frame
        # max_speed_mps = 1.0 -> 100 pixels/s.
        speed_px_s = self.max_speed_mps * 100.0
        step = speed_px_s * dt
        
        if dist <= step:
            # Reached the node
            self.x = float(tx)
            self.y = float(ty)
            
            # Accumulate odometer
            self.total_distance_m += dist / 100.0
            
            # Determine current zone context (if node corresponds to a major zone)
            if target_node in ['A', 'B', 'C', 'D', 'R']:
                self.current_zone = target_node
            elif target_node == 'X':
                self.current_zone = 'X'
            
            # Move to next node
            self.current_node_idx += 1
            if self.current_node_idx >= len(self.path):
                self.state = "ARRIVED"
                self.last_state_change = time.time()
                self.speed_mps = 0.0
                self.path = []
                # If we arrived at our target, make sure we update current_zone
                if target_node in ['A', 'B', 'C', 'D', 'R']:
                    self.current_zone = target_node
            else:
                self.state = "EN_ROUTE"
                self.speed_mps = self.max_speed_mps
        else:
            # Move towards the node
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step
            self.total_distance_m += step / 100.0
            self.state = "EN_ROUTE"
            self.speed_mps = self.max_speed_mps

    def get_render_position(self, offset_px: float = 12.0) -> Tuple[float, float]:
        """
        Computes a position slightly offset to the right of the path direction.
        This prevents two AGVs from visually overlapping when using the same lane in opposite directions.
        """
        if not self.path or self.current_node_idx >= len(self.path):
            return self.x, self.y
            
        target_node = self.path[self.current_node_idx]
        tx, ty = NODES[target_node]
        dx = tx - self.x
        dy = ty - self.y
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist > 0:
            # Direction vector (ux, uy)
            ux = dx / dist
            uy = dy / dist
            # Normal vector pointing to the right (uy, -ux)
            nx = uy
            ny = -ux
            # Return offset position
            return self.x + nx * offset_px, self.y + ny * offset_px
            
        return self.x, self.y

    def get_telemetry_payload(self) -> Dict[str, Any]:
        """Generates a telemetry JSON payload matching the requested structure."""
        return {
            "agv_id": self.agv_id,
            "state": self.state,
            "battery_pct": int(round(self.battery_pct)),
            "mission_id": self.mission_id,
            "speed_mps": round(self.speed_mps, 2),
            "position": self.position_meters,
            "target_zone": self.target_zone,
            "distance_front_cm": int(round(self.distance_front_cm)),
            "temperature_c": round(self.temperature_c, 1),
            "connectivity_status": self.connectivity_status
        }
