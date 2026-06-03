import time
import math
import random
from typing import List, Tuple, Dict, Optional, Any
from warehouse_map import NODES, find_shortest_path, ZoneXTrafficController

class AGV:
    """
    Cette classe représente un robot AGV. Elle gère ses déplacements, 
    l'évitement des obstacles, sa batterie et la génération des données de télémétrie.
    """
    def __init__(self, agv_id: str, start_zone: str, color: Tuple[int, int, int]):
        self.agv_id = agv_id
        self.color = color
        
        # Les états possibles de notre automate : 'IDLE' (libre), 'EN_ROUTE' (en mouvement), 'WAIT' (en attente), 'STOP' (arrêt d'urgence), 'ARRIVED' (arrivé)
        self.state = "IDLE"
        
        # Variables pour gérer le trajet du robot
        self.current_zone = start_zone
        self.target_zone = start_zone
        self.path: List[str] = []
        self.current_node_idx = 0
        
        # Coordonnées physiques actuelles (en pixels, calquées sur la carte NODES)
        start_coords = NODES[start_zone]
        self.x = float(start_coords[0])
        self.y = float(start_coords[1])
        
        # Les caractéristiques physiques du robot (batterie, vitesse, température...)
        self.battery_pct = 100.0
        self.max_speed_mps = 1.0  # 1.0 m/s = 100 px/s
        self.speed_mps = 0.0
        self.total_distance_m = 0.0
        self.temperature_c = 25.0
        self.connectivity_status = "ONLINE"
        
        # Paramètres du capteur de distance frontal (pour éviter les collisions)
        self.distance_front_cm = 300.0  # distance de l'obstacle en cm
        self.sensor_angle_deg = 45.0    # cône de vision de 45 degrés
        
        # Suivi de la mission en cours (identifiant unique et compteur)
        self.mission_count = 0
        self.mission_id = "N/A"
        self.last_state_change = time.time()
        
        # Differential drive parameters
        self.angle_deg = 0.0
        self.motor_left_pct = 0.0
        self.motor_right_pct = 0.0
        
        # --- DIGITAL TWIN PARAMS ---
        self.is_digital_twin_active = False
        
        # Indique si le robot est en train de recharger ses batteries
        self.is_charging = False
        
        # Indique si le robot a obtenu l'autorisation de traverser l'intersection critique Zone X
        self.has_zone_x_lock = False

    @property
    def position_meters(self) -> Dict[str, float]:
        """On convertit les coordonnées pixels en mètres (100 pixels = 1 mètre)."""
        # On arrondit à 2 décimales pour rester conforme au schéma JSON attendu
        return {
            "x": round(self.x / 100.0, 2),
            "y": round(self.y / 100.0, 2),
            "zone": self.current_zone
        }

    def start_mission(self, target_zone: str):
        """Planifie le chemin le plus court et lance le robot vers sa destination."""
        self.target_zone = target_zone
        path = find_shortest_path(self.current_zone, target_zone)
        
        if path:
            self.path = path
            self.current_node_idx = 0
            self.mission_count += 1
            # On génère un identifiant de mission unique sous la forme M-AAAA-MM-JJ-ID
            date_str = time.strftime("%Y-%m-%d")
            self.mission_id = f"M-{date_str}-{self.agv_id[-2:]}-{self.mission_count:02d}"
            self.state = "EN_ROUTE"
            self.is_charging = False
            self.speed_mps = self.max_speed_mps
        else:
            self.state = "IDLE"
            self.speed_mps = 0.0
            self.motor_left_pct = 0.0
            self.motor_right_pct = 0.0

    def abort_mission(self, traffic_controller):
        """Annule la mission en cours (Soft Reset) et libère la zone X si occupée."""
        if self.has_zone_x_lock:
            traffic_controller.release_zone(self.agv_id)
            self.has_zone_x_lock = False
            print(f"[TRAFFIC] 🟢 {self.agv_id} libère la Zone X suite à un RESET.")
            
        self.path = []
        self.target_node = None
        self.state = "IDLE"
        self.speed_mps = 0.0
        self.motor_left_pct = 0.0
        self.motor_right_pct = 0.0
        print(f"🔄 {self.agv_id} MISSION ABORTED (Soft Reset). Prêt pour une nouvelle mission.")

    def update(self, dt: float, other_agv: 'AGV', traffic_controller: ZoneXTrafficController, emergency_stop: bool = False):
        """
        Met à jour tout le comportement physique du robot : sa position, sa batterie, 
        sa température, ses capteurs et la gestion du carrefour Zone X.
        dt : le temps écoulé depuis la dernière mise à jour (en secondes).
        """
        # Si un arrêt d'urgence est demandé, on coupe tout immédiatement !
        if emergency_stop:
            self.state = "STOP"
            self.speed_mps = 0.0
            self.motor_left_pct = 0.0
            self.motor_right_pct = 0.0
            # Le moteur refroidit tout doucement lorsqu'il est à l'arrêt
            self.temperature_c = max(24.0, self.temperature_c - 0.05 * dt)
            return
        
        # 1. Simulation d'une connexion Wi-Fi réaliste (avec parfois de légères déconnexions)
        if self.connectivity_status == "ONLINE":
            if random.random() < 0.0005:  # Perte de connexion très occasionnelle
                self.connectivity_status = "OFFLINE"
        else:
            if random.random() < 0.2:     # Reconnexion automatique rapide
                self.connectivity_status = "ONLINE"
        
        # 2. Évolution de la batterie et de la température
        if not self.is_digital_twin_active:
            if self.state == "EN_ROUTE" and self.speed_mps > 0:
                # La batterie se décharge (environ 3 minutes d'activité continue pour la vider)
                self.battery_pct = max(0.0, self.battery_pct - 0.5 * dt)
                # Le moteur chauffe quand le robot roule
                self.temperature_c = min(48.5, self.temperature_c + 0.15 * dt + random.uniform(-0.05, 0.05))
            elif self.is_charging:
                # Recharge super rapide (environ 8% par seconde)
                self.battery_pct = min(100.0, self.battery_pct + 8.0 * dt)
                # Le moteur refroidit pendant que le robot recharge ses batteries
                self.temperature_c = max(24.5, self.temperature_c - 0.3 * dt)
            else:
                # Le moteur refroidit lentement lorsque le robot attend ou est inactif
                self.temperature_c = max(24.0, self.temperature_c - 0.05 * dt)

        # 3. Gestion du retour automatique à la station de charge
        if self.battery_pct < 20.0 and not self.is_charging and self.target_zone != "R":
            # Si la batterie est basse, on attend la fin de la mission courante pour aller charger.
            # Si le robot est déjà inactif (IDLE), on l'envoie charger tout de suite.
            if self.state in ["IDLE", "ARRIVED"]:
                self.start_mission("R")

        # 4. Détection d'obstacles (distance par rapport à l'autre robot AGV)
        dx = other_agv.x - self.x
        dy = other_agv.y - self.y
        dist_px = math.sqrt(dx**2 + dy**2)
        
        # On considère que 1 pixel = 1 cm pour notre capteur de proximité
        if not self.is_digital_twin_active:
            self.distance_front_cm = dist_px
        
        # On vérifie si l'autre AGV est situé devant nous (dans notre cône de vision de 45 degrés)
        is_obstacle_ahead = False
        yielding = False
        
        if self.state in ["EN_ROUTE", "STOP", "YIELDING"] and len(self.path) > 0 and self.current_node_idx < len(self.path):
            # Vecteur de direction vers le prochain point du trajet
            target_node = self.path[self.current_node_idx]
            tx, ty = NODES[target_node]
            vx = tx - self.x
            vy = ty - self.y
            v_len = math.sqrt(vx**2 + vy**2)
            
            if v_len > 0 and dist_px > 0:
                ux, uy = vx / v_len, vy / v_len
                # Produit scalaire pour savoir si l'autre robot est dans notre champ de vision frontal
                dot = (dx * ux + dy * uy) / dist_px
                
                # Si le produit scalaire est supérieur à 0.6, l'autre AGV est bien dans notre cône de vision
                if dot > 0.6:
                    align = 0.0
                    # On vérifie s'ils se croisent en sens inverse (pour éviter de se bloquer mutuellement)
                    if other_agv.state in ["EN_ROUTE", "STOP", "YIELDING"] and other_agv.path and other_agv.current_node_idx < len(other_agv.path):
                        otx, oty = NODES[other_agv.path[other_agv.current_node_idx]]
                        ovx = otx - other_agv.x
                        ovy = oty - other_agv.y
                        ov_len = math.sqrt(ovx**2 + ovy**2)
                        if ov_len > 0:
                            oux, ouy = ovx / ov_len, ovy / ov_len
                            align = ux * oux + uy * ouy
                            
                            if self.agv_id < other_agv.agv_id:
                                is_obstacle_ahead = True
                                yielding = True
                                # Intelligence: Instead of waiting forever, calculate a new path!
                                if self.state in ["EN_ROUTE", "STOP"] and self.current_node_idx > 0:
                                    prev_node = self.path[self.current_node_idx - 1]
                                    curr_node = self.path[self.current_node_idx]
                                    from warehouse_map import find_shortest_path
                                    # Find path from prev_node to target, blocking the blocked edge
                                    new_path = find_shortest_path(prev_node, self.target_zone, blocked_edges={(prev_node, curr_node), (curr_node, prev_node)})
                                    if new_path:
                                        # Turn around: go back to prev_node, then follow new path
                                        self.path = [prev_node] + new_path[1:]
                                        self.current_node_idx = 0
                                        # Now we are not blocked anymore on the new route!
                                        is_obstacle_ahead = False
                                        yielding = False
                                        print(f"🤖 {self.agv_id} REROUTING to avoid collision! New path: {self.path}")
                    else:
                        # Même direction ou perpendiculaire, celui qui est derrière s'arrête
                        is_obstacle_ahead = True

        # Handle stopping for close obstacles
        obstacle_stop = False
        
        # 1. Si le robot physique détecte un vrai obstacle à moins de 20 cm (HC-SR04)
        if self.is_digital_twin_active and (0 < self.distance_front_cm <= 20.0):
            obstacle_stop = True
            yielding = False
            
        # 2. Mode simulation : on s'arrête si l'autre AGV virtuel est devant nous (distance virtuelle dist_px)
        if is_obstacle_ahead and dist_px < 110.0:
            obstacle_stop = True
                
        # 5. Suivi du chemin, passage du carrefour Zone X ou recharge
        if obstacle_stop:
            self.state = "YIELDING" if yielding else "STOP"
            self.speed_mps = 0.0
            self.motor_left_pct = 0.0
            self.motor_right_pct = 0.0
        else:
            if self.state in ["EN_ROUTE", "STOP", "YIELDING"]:
                self.navigate_path(dt, traffic_controller)
            elif self.state == "WAIT":
                if self.is_charging:
                    self.speed_mps = 0.0
                    self.motor_left_pct = 0.0
                    self.motor_right_pct = 0.0
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
                self.motor_left_pct = 0.0
                self.motor_right_pct = 0.0
                # On marque une pause de 1.5s à l'arrivée avant de redevenir disponible (ou de commencer à charger si on est en R)
                if time.time() - self.last_state_change > 1.5:
                    if self.target_zone == "R":
                        self.is_charging = True
                        self.state = "WAIT"  # On se met en attente pendant la recharge
                        self.last_state_change = time.time()
                    else:
                        self.state = "IDLE"
                        self.last_state_change = time.time()

    def navigate_path(self, dt: float, traffic_controller: ZoneXTrafficController):
        """Avance d'un pas le long du trajet et demande l'accès au carrefour Zone X si nécessaire."""
        if not self.path or self.current_node_idx >= len(self.path):
            self.state = "ARRIVED"
            self.last_state_change = time.time()
            self.speed_mps = 0.0
            return

        target_node = self.path[self.current_node_idx]
        tx, ty = NODES[target_node]
        
        # On calcule le déplacement nécessaire vers le prochain nœud
        dx = tx - self.x
        dy = ty - self.y
        dist = math.sqrt(dx**2 + dy**2)
        
        # Coordination du trafic pour le carrefour central (Zone X)
        # On approche de la Zone X :
        # Le nœud 'X' est l'intersection critique. Si on y va et qu'on n'a pas le verrou de passage :
        if target_node == 'X' and not self.has_zone_x_lock:
            # On demande le droit d'entrer au contrôleur de trafic
            if traffic_controller.request_entry(self.agv_id):
                self.has_zone_x_lock = True
                self.state = "EN_ROUTE"
                self.speed_mps = self.max_speed_mps
                print(f"[TRAFFIC] 🚥 {self.agv_id} a obtenu l'accès exclusif à la CRITICAL ZONE X.")
            else:
                # Le carrefour est occupé ! On s'arrête à la porte d'entrée et on attend notre tour
                if self.state != "WAIT":
                    print(f"[TRAFFIC] 🛑 {self.agv_id} accès refusé à la Zone X (occupée). Mise en attente...")
                self.state = "WAIT"
                self.speed_mps = 0.0
                return  # Do not advance position

        # On libère le carrefour Zone X dès qu'on l'a entièrement traversé (c'est-à-dire quand on atteint le nœud suivant)
        if self.has_zone_x_lock and self.current_node_idx > 0:
            previous_node = self.path[self.current_node_idx - 1]
            if previous_node == 'X':
                traffic_controller.release_zone(self.agv_id)
                self.has_zone_x_lock = False
                print(f"[TRAFFIC] 🟢 {self.agv_id} a quitté la CRITICAL ZONE X. Verrou libéré.")

        # Vitesse de déplacement du robot convertie en pixels par image (1.0 m/s équivaut à 100 pixels par seconde)
        speed_px_s = self.max_speed_mps * 100.0
        step = speed_px_s * dt
        
        # Check if we need to rotate first
        target_angle_deg = math.degrees(math.atan2(dy, dx))
        angle_diff = (target_angle_deg - self.angle_deg + 180) % 360 - 180
        
        if dist > 2.0 and abs(angle_diff) > 2.0:
            # Rotate in place
            rot_step = 180.0 * dt  # 180 degrees per second
            if abs(angle_diff) <= rot_step:
                self.angle_deg = target_angle_deg
            else:
                if angle_diff > 0:
                    self.angle_deg += rot_step
                    self.motor_left_pct = 1.0
                    self.motor_right_pct = -1.0
                else:
                    self.angle_deg -= rot_step
                    self.motor_left_pct = -1.0
                    self.motor_right_pct = 1.0
            
            self.angle_deg = (self.angle_deg + 180) % 360 - 180
            self.speed_mps = self.max_speed_mps  # Keep speed > 0 for battery logic
            return  # Wait until rotation completes before translating
            
        if dist <= step:
            # On est arrivé pile sur le nœud cible !
            self.x = float(tx)
            self.y = float(ty)
            
            # On incrémente notre compteur kilométrique (odomètre)
            self.total_distance_m += dist / 100.0
            
            # On met à jour la zone dans laquelle se trouve le robot
            if target_node in ['A', 'B', 'C', 'D', 'R']:
                self.current_zone = target_node
            elif target_node == 'X':
                self.current_zone = 'X'
            
            # On passe au nœud suivant dans notre liste de navigation
            self.current_node_idx += 1
            if self.current_node_idx >= len(self.path):
                self.state = "ARRIVED"
                self.last_state_change = time.time()
                self.speed_mps = 0.0
                self.motor_left_pct = 0.0
                self.motor_right_pct = 0.0
                self.path = []
                # Arrivé au terminus ! On met à jour notre zone courante
                if target_node in ['A', 'B', 'C', 'D', 'R']:
                    self.current_zone = target_node
            else:
                self.state = "EN_ROUTE"
                self.speed_mps = self.max_speed_mps
                self.motor_left_pct = 1.0
                self.motor_right_pct = 1.0
        else:
            # On avance vers le nœud intermédiaire
            self.x += (dx / dist) * step
            self.y += (dy / dist) * step
            self.total_distance_m += step / 100.0
            self.state = "EN_ROUTE"
            self.speed_mps = self.max_speed_mps
            self.motor_left_pct = 1.0
            self.motor_right_pct = 1.0

    def get_render_position(self, offset_px: float = 12.0) -> Tuple[float, float]:
        """
        Calcule une position légèrement décalée sur la droite de notre axe de marche.
        Cela évite que les deux robots se superposent visuellement lorsqu'ils se croisent dans la même voie.
        """
        if not self.path or self.current_node_idx >= len(self.path):
            return self.x, self.y
            
        target_node = self.path[self.current_node_idx]
        tx, ty = NODES[target_node]
        dx = tx - self.x
        dy = ty - self.y
        dist = math.sqrt(dx**2 + dy**2)
        
        if dist > 0:
            # Vecteur directeur du mouvement
            ux = dx / dist
            uy = dy / dist
            # Vecteur normal pointant vers la droite pour le décalage visuel
            nx = uy
            ny = -ux
            # Return offset position
            return self.x + nx * offset_px, self.y + ny * offset_px
            
        return self.x, self.y

    def get_telemetry_payload(self) -> Dict[str, Any]:
        """Génère le dictionnaire de télémétrie au format JSON attendu."""
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
