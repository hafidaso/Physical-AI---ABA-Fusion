import math
import heapq
import threading
from typing import Dict, List, Tuple, Optional

# Les coordonnées des différents points (nœuds) sur la carte de 800x800 pixels.
# On compte 100 pixels pour 1 mètre, ce qui fait une zone de 8m sur 8m.
NODES = {
    'A': (150, 150),      # Zone en haut à gauche
    'B': (650, 150),      # Zone en haut à droite
    'C': (150, 650),      # Zone en bas à gauche
    'D': (650, 650),      # Zone en bas à droite
    'R': (400, 650),      # Station de recharge (au milieu en bas)
    'J_AN': (400, 150),   # Carrefour Nord (au-dessus de la Zone X)
    'J_W': (150, 400),    # Carrefour Ouest (à gauche de la Zone X)
    'J_E': (650, 400),    # Carrefour Est (à droite de la Zone X)
    'X_N': (400, 310),    # Porte d'entrée Nord de la Zone X
    'X_S': (400, 490),    # Porte d'entrée Sud de la Zone X
    'X_W': (310, 400),    # Porte d'entrée Ouest de la Zone X
    'X_E': (490, 400),    # Porte d'entrée Est de la Zone X
    'X': (400, 400)       # Le centre de la Zone X (intersection critique)
}

# Les zones physiques avec leurs coordonnées et dimensions pour le dessin.
# Format utilisé : (x, y, largeur, hauteur)
ZONES = {
    'A': (50, 50, 200, 200),     # En haut à gauche
    'B': (550, 50, 200, 200),    # En haut à droite
    'C': (50, 550, 200, 200),    # En bas à gauche
    'D': (550, 550, 200, 200),   # En bas à droite
    'R': (320, 590, 160, 120),   # Station de recharge (au milieu en bas)
    'X': (290, 290, 220, 220)    # Intersection critique centrale
}

# Le graphe des connexions : indique quelles routes relient quels points.
GRAPH = {
    'A': ['J_AN', 'J_W'],
    'B': ['J_AN', 'J_E'],
    'C': ['J_W', 'R'],
    'D': ['J_E', 'R'],
    'J_AN': ['A', 'B', 'X_N'],
    'J_W': ['A', 'C', 'X_W'],
    'J_E': ['B', 'D', 'X_E'],
    'R': ['C', 'D', 'X_S'],
    'X_N': ['J_AN', 'X'],
    'X_S': ['R', 'X'],
    'X_W': ['J_W', 'X'],
    'X_E': ['J_E', 'X'],
    'X': ['X_N', 'X_S', 'X_W', 'X_E']
}

def calculate_distance(n1: str, n2: str) -> float:
    """Calcule la distance géométrique en ligne droite entre deux points."""
    x1, y1 = NODES[n1]
    x2, y2 = NODES[n2]
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def get_edge_weight(u: str, v: str) -> float:
    """
    Calcule la distance ou le coût pour aller d'un point à un autre.
    Pour encourager les robots à prendre la voie centrale (Zone X),
    on applique une pénalité (facteur 1.6) sur les trajets extérieurs.
    """
    dist = calculate_distance(u, v)
    
    # Les liaisons extérieures de contournement.
    bypass_edges = {
        ('A', 'J_AN'), ('J_AN', 'A'),
        ('B', 'J_AN'), ('J_AN', 'B'),
        ('A', 'J_W'), ('J_W', 'A'),
        ('C', 'J_W'), ('J_W', 'C'),
        ('B', 'J_E'), ('J_E', 'B'),
        ('D', 'J_E'), ('J_E', 'D'),
        ('C', 'R'), ('R', 'C'),
        ('D', 'R'), ('R', 'D')
    }
    
    if (u, v) in bypass_edges:
        return dist * 1.6  # On rajoute 60% de pénalité sur les voies de contournement pour encourager le passage direct via la Zone X
    return dist

def find_shortest_path(start: str, end: str, blocked_edges: set = None) -> Optional[List[str]]:
    """
    Calcule le chemin le plus court entre deux points avec l'algorithme de Dijkstra.
    Retourne la liste des étapes du parcours, ou None si c'est impossible.
    """
    if blocked_edges is None:
        blocked_edges = set()
        
    if start == end:
        return [start]
        
    distances = {node: float('inf') for node in NODES}
    distances[start] = 0
    pq = [(0, start, [start])]
    
    while pq:
        current_dist, current_node, path = heapq.heappop(pq)
        
        if current_node == end:
            return path
            
        if current_dist > distances[current_node]:
            continue
            
        for neighbor in GRAPH.get(current_node, []):
            if (current_node, neighbor) in blocked_edges or (neighbor, current_node) in blocked_edges:
                continue
                
            weight = get_edge_weight(current_node, neighbor)
            distance = current_dist + weight
            
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                heapq.heappush(pq, (distance, neighbor, path + [neighbor]))
                
    return None

class ZoneXTrafficController:
    """
    Ce contrôleur régule l'accès à la Zone X centrale de manière sécurisée (Thread-safe).
    Il fonctionne comme un verrou d'exclusion mutuelle (Mutex) : un seul robot peut s'y trouver à la fois.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._occupied_by = None  # Stocke l'identifiant du robot actuellement dans la Zone X

    def request_entry(self, agv_id: str) -> bool:
        """
        Tente de réserver la Zone X pour un robot.
        Retourne True si le passage est accordé, et False si la zone est déjà occupée.
        """
        with self._lock:
            if self._occupied_by is None:
                self._occupied_by = agv_id
                return True
            elif self._occupied_by == agv_id:
                return True
            return False

    def release_zone(self, agv_id: str):
        """
        Libère l'accès à la Zone X (appelé quand le robot en sort).
        """
        with self._lock:
            if self._occupied_by == agv_id:
                self._occupied_by = None

    def get_occupant(self) -> Optional[str]:
        """Indique quel robot se trouve dans la Zone X en ce moment, s'il y en a un."""
        with self._lock:
            return self._occupied_by

    def is_occupied(self) -> bool:
        """Vérifie si la Zone X est occupée."""
        with self._lock:
            return self._occupied_by is not None
