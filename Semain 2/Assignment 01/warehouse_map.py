import math
import heapq
import threading
from typing import Dict, List, Tuple, Optional

# Node coordinates in pixel space (800x800 warehouse area)
# 100 pixels = 1 meter. So the area is 8m x 8m.
NODES = {
    'A': (150, 150),      # Top-Left Zone
    'B': (650, 150),      # Top-Right Zone
    'C': (150, 650),      # Bottom-Left Zone
    'D': (650, 650),      # Bottom-Right Zone
    'R': (400, 650),      # Bottom-Middle Charging/Refuel Zone
    'J_AN': (400, 150),   # Junction above Zone X (North)
    'J_W': (150, 400),    # Junction left of Zone X (West)
    'J_E': (650, 400),    # Junction right of Zone X (East)
    'X_N': (400, 310),    # Zone X North entrance/gate
    'X_S': (400, 490),    # Zone X South entrance/gate
    'X_W': (310, 400),    # Zone X West entrance/gate
    'X_E': (490, 400),    # Zone X East entrance/gate
    'X': (400, 400)       # Zone X Center (Critical Intersection)
}

# The physical zones and their visual bounding boxes (for rendering)
# format: (x, y, width, height)
ZONES = {
    'A': (50, 50, 200, 200),
    'B': (550, 50, 200, 200),
    'C': (550, 550, 200, 200), # Note: bottom right is D, bottom left is C.
    'D': (50, 550, 200, 200),  # Wait, let's align names to coordinates:
                               # A: (150,150) -> Top-Left. So box is (50, 50, 200, 200).
                               # B: (650,150) -> Top-Right. So box is (550, 50, 200, 200).
                               # C: (150,650) -> Bottom-Left. So box is (50, 550, 200, 200).
                               # D: (650,650) -> Bottom-Right. So box is (550, 550, 200, 200).
                               # R: (400,650) -> Bottom-Center. So box is (300, 570, 200, 160).
                               # ZONE X is at the center (400, 400), bounds (290, 290, 220, 220).
}

# Re-aligning:
ZONES = {
    'A': (50, 50, 200, 200),     # Top-Left
    'B': (550, 50, 200, 200),    # Top-Right
    'C': (50, 550, 200, 200),    # Bottom-Left
    'D': (550, 550, 200, 200),   # Bottom-Right
    'R': (320, 590, 160, 120),   # Charging Station (Bottom-Center)
    'X': (290, 290, 220, 220)    # Critical Shared Zone
}

# Connectivity graph (undirected edges)
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
    """Calculate Euclidean distance between two nodes."""
    x1, y1 = NODES[n1]
    x2, y2 = NODES[n2]
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

def get_edge_weight(u: str, v: str) -> float:
    """
    Get edge weight. To force AGVs to prefer the central highway (ZONE X) 
    over long outer bypasses, we apply a penalty multiplier to outer bypass edges.
    """
    dist = calculate_distance(u, v)
    
    # Outer ring bypass edges
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
        return dist * 1.6  # 60% penalty on outer lanes to favor central Zone X routing
    return dist

def find_shortest_path(start: str, end: str) -> Optional[List[str]]:
    """
    Computes the shortest path using Dijkstra's algorithm.
    Returns a list of node names forming the path, or None if unreachable.
    """
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
            weight = get_edge_weight(current_node, neighbor)
            distance = current_dist + weight
            
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                heapq.heappush(pq, (distance, neighbor, path + [neighbor]))
                
    return None

class ZoneXTrafficController:
    """
    Thread-safe controller that regulates access to the central shared critical zone (ZONE X).
    Acts as a mutex lock. Only one AGV is permitted inside ZONE X at any given time.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._occupied_by = None  # Holds the agv_id of the agent inside ZONE X

    def request_entry(self, agv_id: str) -> bool:
        """
        Attempts to acquire the ZONE X lock for an AGV.
        Returns True if access is granted, False if another AGV is inside.
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
        Releases the lock for ZONE X. Called when the AGV exits the zone.
        """
        with self._lock:
            if self._occupied_by == agv_id:
                self._occupied_by = None

    def get_occupant(self) -> Optional[str]:
        """Returns the ID of the AGV currently inside ZONE X, if any."""
        with self._lock:
            return self._occupied_by

    def is_occupied(self) -> bool:
        """Checks if ZONE X is currently occupied."""
        with self._lock:
            return self._occupied_by is not None
