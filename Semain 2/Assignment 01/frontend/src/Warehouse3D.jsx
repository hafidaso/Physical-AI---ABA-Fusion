import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Text } from '@react-three/drei';
import * as THREE from 'three';

// Map Node coordinates to 3D space
// Center of map is (400, 400) -> 3D Origin (0,0). Scale is 100px = 1.0m
const pxTo3D = (x, y) => {
  return [
    (x - 400) / 100,
    0.01, // slightly above grid to avoid z-fighting
    (y - 400) / 100
  ];
};

// Static Node Coordinates for Drawing Lane Lines
const NODES_3D = {
  'A': pxTo3D(150, 150),
  'B': pxTo3D(650, 150),
  'C': pxTo3D(150, 650),
  'D': pxTo3D(650, 650),
  'R': pxTo3D(400, 650),
  'J_AN': pxTo3D(400, 150),
  'J_W': pxTo3D(150, 400),
  'J_E': pxTo3D(650, 400),
  'X_N': pxTo3D(400, 310),
  'X_S': pxTo3D(400, 490),
  'X_W': pxTo3D(310, 400),
  'X_E': pxTo3D(490, 400),
  'X': pxTo3D(400, 400)
};

// Lane Graph Connections
const LANES = [
  ['A', 'J_AN'], ['J_AN', 'B'],
  ['A', 'J_W'], ['J_W', 'C'],
  ['C', 'R'], ['R', 'D'],
  ['B', 'J_E'], ['J_E', 'D'],
  ['J_AN', 'X_N'], ['X_N', 'X'],
  ['J_W', 'X_W'], ['X_W', 'X'],
  ['J_E', 'X_E'], ['X_E', 'X'],
  ['R', 'X_S'], ['X_S', 'X']
];

// Zone Bounding Boxes in meters
const ZONES_3D = {
  'A': { pos: pxTo3D(150, 150), size: [2.0, 2.0], color: '#101a30', label: 'ZONE A\nLOAD' },
  'B': { pos: pxTo3D(650, 150), size: [2.0, 2.0], color: '#101a30', label: 'ZONE B\nUNLOAD' },
  'C': { pos: pxTo3D(150, 650), size: [2.0, 2.0], color: '#101a30', label: 'ZONE C\nSORTING' },
  'D': { pos: pxTo3D(650, 650), size: [2.0, 2.0], color: '#101a30', label: 'ZONE D\nPACKING' },
  'R': { pos: pxTo3D(400, 650), size: [1.6, 1.2], color: '#0b201a', label: 'ZONE R\nCHARGE', textColor: '#2ecc71' }
};

// ZONE X Bounds
const ZONE_X_3D = {
  pos: [0, 0.005, 0], // Center (400, 400) -> (0,0)
  size: [2.2, 2.2],   // 220px -> 2.2m
  color: '#c34a36'
};

function Zone({ pos, size, color, label, textColor = '#7887a5' }) {
  return (
    <group position={pos}>
      {/* Flat Area plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={size} />
        <meshBasicMaterial color={color} transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>
      
      {/* Plane Border */}
      <lineSegments>
        <edgesGeometry args={[new THREE.PlaneGeometry(size[0], size[1])]} />
        <lineBasicMaterial color="#23304f" />
      </lineSegments>

      {/* Label Text */}
      <Text
        position={[0, 0.01, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.16}
        color={textColor}
        anchorX="center"
        anchorY="middle"
      >
        {label}
      </Text>
    </group>
  );
}

function ZoneX() {
  const lineRef = useRef();

  useFrame(({ clock }) => {
    // Pulse outline glow slightly over time
    if (lineRef.current) {
      const scale = 1.0 + Math.sin(clock.getElapsedTime() * 4.0) * 0.015;
      lineRef.current.scale.set(scale, scale, 1);
    }
  });

  return (
    <group position={ZONE_X_3D.pos}>
      {/* Area plane */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={ZONE_X_3D.size} />
        <meshBasicMaterial color={ZONE_X_3D.color} transparent opacity={0.06} side={THREE.DoubleSide} />
      </mesh>
      
      {/* Solid Border */}
      <group rotation={[-Math.PI / 2, 0, 0]} ref={lineRef}>
        <lineSegments>
          <edgesGeometry args={[new THREE.PlaneGeometry(ZONE_X_3D.size[0], ZONE_X_3D.size[1])]} />
          <lineBasicMaterial color={ZONE_X_3D.color} linewidth={2} />
        </lineSegments>
      </group>

      {/* Danger Crosshatch Stripes (Simplified visually with a cross wireframe) */}
      <line rotation={[-Math.PI / 2, 0, 0]}>
        <bufferGeometry>
          <float32BufferAttribute
            attach="attributes-position"
            args={[
              new Float32Array([
                -1.1, -1.1, 0,  1.1, 1.1, 0,
                -1.1, 1.1, 0,   1.1, -1.1, 0
              ]),
              3
            ]}
          />
        </bufferGeometry>
        <lineBasicMaterial color={ZONE_X_3D.color} transparent opacity={0.15} />
      </line>

      {/* Label */}
      <Text
        position={[0, 0.01, -0.6]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.18}
        color={ZONE_X_3D.color}
        fontWeight="bold"
        anchorX="center"
        anchorY="middle"
      >
        ZONE X
      </Text>
      <Text
        position={[0, 0.01, -0.4]}
        rotation={[-Math.PI / 2, 0, 0]}
        fontSize={0.09}
        color="#a0645f"
        anchorX="center"
        anchorY="middle"
      >
        CRITICAL INTERSECTION
      </Text>
    </group>
  );
}

function LaneLines() {
  const points = [];
  LANES.forEach(([n1, n2]) => {
    points.push(new THREE.Vector3(...NODES_3D[n1]));
    points.push(new THREE.Vector3(...NODES_3D[n2]));
  });

  const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);

  return (
    <lineSegments geometry={lineGeometry}>
      <lineBasicMaterial color="#1c2a46" linewidth={1.5} />
    </lineSegments>
  );
}

function AGVModel({ agvData }) {
  const meshRef = useRef();

  // Extract variables
  const { agv_id, position, state, target_zone, distance_front_cm } = agvData;
  const x_px = position?.x * 100 || 400;
  const y_px = position?.y * 100 || 400;
  
  // Convert position to 3D coordinate space (with right-side path offset of ~10px / 0.1m)
  // Let's compute direction of travel for rotation and offset
  // We can interpolate position smoothly using useFrame
  useFrame((state, delta) => {
    if (meshRef.current) {
      // Direct position mapping from telemetry
      const targetX = (x_px - 400) / 100;
      const targetZ = (y_px - 400) / 100;
      
      // Smooth lerp (interpolation) for ultra-smooth 3D movement
      meshRef.current.position.x = THREE.MathUtils.lerp(meshRef.current.position.x, targetX, 0.25);
      meshRef.current.position.z = THREE.MathUtils.lerp(meshRef.current.position.z, targetZ, 0.25);
      meshRef.current.position.y = 0.12; // half of height (0.24)
      
      // Calculate rotation based on travel vector
      // Standard heuristic: compare current pos to previous pos
      // Since it's direct lerp, it faces the direction of travel
    }
  });

  // Decide colors
  const chassisColor = agv_id === "AGV-01" ? "#ff7850" : "#2eccfa";
  
  // Decide sensor cone alert
  const is_in_zone_x = position?.zone === 'X' || (position?.x >= 2.9 && position?.x <= 5.1 && position?.y >= 2.9 && position?.y <= 5.1);
  const is_stop = state === "STOP" || distance_front_cm < 80;
  
  let coneColor = '#2ecc71'; // normal
  if (is_in_zone_x) {
    coneColor = '#c34a36'; // zone X (Terracotta)
  } else if (is_stop) {
    coneColor = '#e74c3c'; // emergency/safety stop (Red)
  }

  return (
    <group ref={meshRef} position={[ (x_px - 400) / 100, 0.12, (y_px - 400) / 100 ]}>
      {/* 3D AGV Chassis Box (minimalist block robot) */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.36, 0.18, 0.26]} />
        <meshStandardMaterial color={chassisColor} roughness={0.2} metalness={0.1} />
      </mesh>

      {/* Top Cap */}
      <mesh position={[0, 0.11, 0]}>
        <boxGeometry args={[0.26, 0.04, 0.18]} />
        <meshStandardMaterial color="#1a2035" roughness={0.5} />
      </mesh>

      {/* AGV Wheels (Small cylinders) */}
      {[-0.12, 0.12].map((xOffset, idx) => (
        <group key={idx} position={[xOffset, -0.09, 0]}>
          {[-0.14, 0.14].map((zOffset, zIdx) => (
            <mesh key={zIdx} position={[0, 0, zOffset]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.05, 0.05, 0.04, 8]} />
              <meshStandardMaterial color="#111" roughness={0.9} />
            </mesh>
          ))}
        </group>
      ))}

      {/* Front Label Indicator */}
      <Text
        position={[0, 0.22, 0]}
        fontSize={0.15}
        color="#fff"
        backgroundColor="#050a15"
        padding={[0.02, 0.06]}
        borderRadius={0.03}
        anchorX="center"
        anchorY="bottom"
      >
        {agv_id}
      </Text>

      {/* Translucent Front-facing Sensor Cone */}
      {/* Represented as a flat wedge shape projected on the ground */}
      <mesh position={[0.26, -0.1, 0]} rotation={[0, 0, 0]}>
        <coneGeometry args={[0.45, 0.8, 4, 1, false, 0]} />
        <meshBasicMaterial color={coneColor} transparent opacity={0.2} />
      </mesh>
    </group>
  );
}

export default function Warehouse3D({ agvsData, lightMode }) {
  return (
    <group>
      {/* Ambient and Directional Lights for clean 3D shadows */}
      <ambientLight intensity={lightMode ? 0.8 : 0.4} />
      <directionalLight 
        position={[8, 12, 5]} 
        intensity={lightMode ? 1.5 : 0.9} 
        castShadow 
        shadow-mapSize={[1024, 1024]} 
      />
      
      {/* Subtle floor grid */}
      <gridHelper args={[8.2, 82, lightMode ? '#cbd5e1' : '#353050', lightMode ? '#e2e8f0' : '#12182c']} position={[0, 0, 0]} />
      
      {/* Lane Lines */}
      <LaneLines />

      {/* Render Zones */}
      {Object.entries(ZONES_3D).map(([key, value]) => (
        <Zone key={key} {...value} />
      ))}
      
      {/* Zone X */}
      <ZoneX />

      {/* Render Dynamic AGV models */}
      {agvsData.map((agv) => (
        <AGVModel key={agv.agv_id} agvData={agv} />
      ))}
    </group>
  );
}
