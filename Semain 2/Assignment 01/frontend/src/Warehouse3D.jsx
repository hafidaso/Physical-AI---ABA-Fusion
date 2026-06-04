import React, { useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
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

function BlockedLane({ n1, n2 }) {
  const meshRef = useRef();
  
  const p1 = new THREE.Vector3(...NODES_3D[n1]);
  const p2 = new THREE.Vector3(...NODES_3D[n2]);
  const length = p1.distanceTo(p2);
  const midpoint = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
  midpoint.y = 0.015; // slightly above floor
  const angle = Math.atan2(p2.z - p1.z, p2.x - p1.x);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.material.opacity = 0.35 + Math.sin(clock.getElapsedTime() * 8.0) * 0.2;
    }
  });

  return (
    <group position={midpoint} rotation={[0, -angle, 0]}>
      {/* Red glowing ribbon */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} ref={meshRef}>
        <planeGeometry args={[length, 0.16]} />
        <meshBasicMaterial color="#ef4444" transparent opacity={0.6} side={THREE.DoubleSide} />
      </mesh>
      
      {/* Thin red side borders */}
      <mesh position={[0, 0.001, 0.08]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[length, 0.02]} />
        <meshBasicMaterial color="#f87171" />
      </mesh>
      <mesh position={[0, 0.001, -0.08]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[length, 0.02]} />
        <meshBasicMaterial color="#f87171" />
      </mesh>
    </group>
  );
}

function WarningSign({ position }) {
  const billboardRef = useRef();

  useFrame((state) => {
    if (billboardRef.current) {
      billboardRef.current.quaternion.copy(state.camera.quaternion);
    }
  });

  return (
    <group position={[position.x, 0.35, position.z]} ref={billboardRef}>
      {/* Hazard Warning Triangle */}
      <mesh position={[0, 0, 0]}>
        <coneGeometry args={[0.15, 0.25, 3]} />
        <meshBasicMaterial color="#ef4444" />
      </mesh>
      {/* Black exclamation mark inside or simple backing */}
      <mesh position={[0, -0.02, 0.01]}>
        <sphereGeometry args={[0.02, 8, 8]} />
        <meshBasicMaterial color="#000" />
      </mesh>
      <mesh position={[0, 0.05, 0.01]}>
        <cylinderGeometry args={[0.015, 0.01, 0.08, 8]} />
        <meshBasicMaterial color="#000" />
      </mesh>
      
      {/* Small glow ring underneath */}
      <mesh position={[0, -0.15, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0.08, 0.12, 16]} />
        <meshBasicMaterial color="#ef4444" transparent opacity={0.8} />
      </mesh>
    </group>
  );
}

function LaneLines({ blockedEdges = [] }) {
  const points = [];
  LANES.forEach(([n1, n2]) => {
    const isBlocked = blockedEdges.some(edge => 
      (edge[0] === n1 && edge[1] === n2) || (edge[0] === n2 && edge[1] === n1)
    );
    if (!isBlocked) {
      points.push(new THREE.Vector3(...NODES_3D[n1]));
      points.push(new THREE.Vector3(...NODES_3D[n2]));
    }
  });

  const lineGeometry = points.length > 0 ? new THREE.BufferGeometry().setFromPoints(points) : null;

  return (
    <group>
      {lineGeometry && (
        <lineSegments geometry={lineGeometry}>
          <lineBasicMaterial color="#1c2a46" linewidth={1.5} />
        </lineSegments>
      )}
      
      {LANES.map(([n1, n2], idx) => {
        const isBlocked = blockedEdges.some(edge => 
          (edge[0] === n1 && edge[1] === n2) || (edge[0] === n2 && edge[1] === n1)
        );
        if (isBlocked) {
          const p1 = new THREE.Vector3(...NODES_3D[n1]);
          const p2 = new THREE.Vector3(...NODES_3D[n2]);
          const midpoint = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
          return (
            <group key={idx}>
              <BlockedLane n1={n1} n2={n2} />
              <WarningSign position={midpoint} />
            </group>
          );
        }
        return null;
      })}
    </group>
  );
}

function AGVModel({ agvData, fpvMode }) {
  const meshRef = useRef();
  const lidarRef = useRef();

  // Extract variables
  const { agv_id, position, state, target_zone, distance_front_cm } = agvData;
  const x_px = position?.x * 100 || 400;
  const y_px = position?.y * 100 || 400;
  
  // Convert position to 3D coordinate space (with smooth interpolation)
  useFrame((state, delta) => {
    if (meshRef.current) {
      const targetX = (x_px - 400) / 100;
      const targetZ = (y_px - 400) / 100;
      
      meshRef.current.position.x = THREE.MathUtils.lerp(meshRef.current.position.x, targetX, 0.22);
      meshRef.current.position.z = THREE.MathUtils.lerp(meshRef.current.position.z, targetZ, 0.22);
      meshRef.current.position.y = 0.12; 

      // Interpolate heading rotation smoothly
      const targetAngleRad = -((agvData.angle_deg || 0) * Math.PI) / 180;
      let diff = targetAngleRad - meshRef.current.rotation.y;
      while (diff < -Math.PI) diff += 2 * Math.PI;
      while (diff > Math.PI) diff -= 2 * Math.PI;
      meshRef.current.rotation.y += diff * 0.22;

      // If FPV Camera mode is enabled for AGV-01, track it
      if (fpvMode && agv_id === "AGV-01") {
        const angleRad = meshRef.current.rotation.y;
        const forwardX = Math.cos(angleRad);
        const forwardZ = -Math.sin(angleRad);

        // Position camera behind and above AGV
        const camDistBehind = 0.75;
        const camHeight = 0.42;

        const targetCamX = meshRef.current.position.x - forwardX * camDistBehind;
        const targetCamZ = meshRef.current.position.z - forwardZ * camDistBehind;
        const targetCamY = meshRef.current.position.y + camHeight;

        // Smooth camera movement
        state.camera.position.x = THREE.MathUtils.lerp(state.camera.position.x, targetCamX, 0.18);
        state.camera.position.y = THREE.MathUtils.lerp(state.camera.position.y, targetCamY, 0.18);
        state.camera.position.z = THREE.MathUtils.lerp(state.camera.position.z, targetCamZ, 0.18);

        // Target to look at (slightly ahead of the AGV)
        const lookAheadDist = 1.2;
        const targetLookX = meshRef.current.position.x + forwardX * lookAheadDist;
        const targetLookZ = meshRef.current.position.z + forwardZ * lookAheadDist;
        const targetLookY = meshRef.current.position.y + 0.05;

        state.camera.lookAt(new THREE.Vector3(targetLookX, targetLookY, targetLookZ));
      }
    }
    
    // Rotate the LIDAR sensor module continuously
    if (lidarRef.current) {
      lidarRef.current.rotation.y += delta * 10.0;
    }
  });

  // Decide colors
  const chassisColor = agv_id === "AGV-01" ? "#ff7850" : "#2eccfa";
  
  // Decide sensor cone alert
  const is_in_zone_x = position?.zone === 'X' || (position?.x >= 2.9 && position?.x <= 5.1 && position?.y >= 2.9 && position?.y <= 5.1);
  const is_stop = state === "STOP" || distance_front_cm <= 25;
  
  let coneColor = '#2ecc71'; // normal
  let ledColor = '#10b981';  // green (Normal Moving)
  let ledEmissive = '#059669';

  if (is_in_zone_x) {
    coneColor = '#c34a36'; // zone X (Terracotta)
    ledColor = '#f43f5e';  // Rose-red (Intersection Warn)
    ledEmissive = '#e11d48';
  } else if (is_stop) {
    coneColor = '#e74c3c'; // emergency/safety stop (Red)
    ledColor = '#ef4444';  // red (Stopped)
    ledEmissive = '#dc2626';
  } else if (state === 'WAIT' || state === 'YIELDING') {
    ledColor = '#f59e0b';  // Orange (Waiting)
    ledEmissive = '#d97706';
  }

  return (
    <group ref={meshRef} position={[ (x_px - 400) / 100, 0.12, (y_px - 400) / 100 ]}>
      {/* 3D AGV Chassis Box */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[0.36, 0.18, 0.26]} />
        <meshStandardMaterial color={chassisColor} roughness={0.2} metalness={0.1} />
      </mesh>

      {/* Top Cap */}
      <mesh position={[0, 0.11, 0]}>
        <boxGeometry args={[0.26, 0.04, 0.18]} />
        <meshStandardMaterial color="#111528" roughness={0.5} />
      </mesh>

      {/* Rotating LIDAR Unit */}
      {/* Base */}
      <mesh position={[0, 0.13, 0.04]}>
        <cylinderGeometry args={[0.04, 0.04, 0.02, 16]} />
        <meshStandardMaterial color="#0b0f19" roughness={0.5} />
      </mesh>
      {/* Rotating Cylinder head */}
      <group ref={lidarRef} position={[0, 0.15, 0.04]}>
        <mesh castShadow>
          <cylinderGeometry args={[0.035, 0.035, 0.025, 16]} />
          <meshStandardMaterial color="#1a202c" roughness={0.2} />
        </mesh>
        {/* Red Lidar laser dot */}
        <mesh position={[0.032, 0, 0]}>
          <boxGeometry args={[0.008, 0.008, 0.015]} />
          <meshBasicMaterial color="#ef4444" />
        </mesh>
      </group>

      {/* Glowing Status LED indicator */}
      <mesh position={[0, 0.138, -0.06]}>
        <cylinderGeometry args={[0.02, 0.02, 0.02, 8]} />
        <meshStandardMaterial 
          color={ledColor} 
          emissive={ledEmissive} 
          emissiveIntensity={2.5} 
          roughness={0.1} 
        />
      </mesh>

      {/* Dynamic floor PointLight reflection */}
      <pointLight 
        position={[0, 0.22, -0.06]} 
        color={ledColor} 
        intensity={is_stop ? 2.5 : 1.2} 
        distance={2.5} 
        decay={2.0}
      />

      {/* AGV Wheels (Small cylinders) */}
      {[-0.12, 0.12].map((xOffset, idx) => (
        <group key={idx} position={[xOffset, -0.09, 0]}>
          {[-0.14, 0.14].map((zOffset, zIdx) => (
            <mesh key={zIdx} position={[0, 0, zOffset]} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.05, 0.05, 0.04, 8]} />
              <meshStandardMaterial color="#080808" roughness={0.9} />
            </mesh>
          ))}
        </group>
      ))}

      {/* Front Label Indicator */}
      <Text
        position={[0, 0.25, 0]}
        fontSize={0.13}
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
      <mesh position={[0.26, -0.1, 0]} rotation={[0, 0, 0]}>
        <coneGeometry args={[0.45, 0.8, 4, 1, false, 0]} />
        <meshBasicMaterial color={coneColor} transparent opacity={0.18} />
      </mesh>
    </group>
  );
}

// Glowing spheres at junction nodes
function JunctionNodes() {
  return (
    <group>
      {Object.entries(NODES_3D).map(([key, pos]) => (
        <mesh key={key} position={pos}>
          <sphereGeometry args={[0.05, 16, 16]} />
          <meshStandardMaterial 
            color="#3b82f6" 
            emissive="#1d4ed8" 
            emissiveIntensity={1.2}
            roughness={0.1}
          />
        </mesh>
      ))}
    </group>
  );
}

export default function Warehouse3D({ agvsData, lightMode, fpvMode, blockedEdges = [] }) {
  const { camera } = useThree();
  const prevFpvMode = useRef(fpvMode);

  React.useEffect(() => {
    if (prevFpvMode.current && !fpvMode) {
      camera.position.set(0, 7, 7);
      camera.lookAt(new THREE.Vector3(0, 0, 0));
    }
    prevFpvMode.current = fpvMode;
  }, [fpvMode, camera]);

  return (
    <group>
      {/* Ambient and Directional Lights for clean 3D shadows */}
      <ambientLight intensity={lightMode ? 0.8 : 0.35} />
      <directionalLight 
        position={[8, 12, 5]} 
        intensity={lightMode ? 1.5 : 1.0} 
        castShadow 
        shadow-mapSize={[1024, 1024]} 
      />
      
      {/* Subtle floor grid */}
      <gridHelper args={[8.2, 82, lightMode ? '#cbd5e1' : '#22293f', lightMode ? '#e2e8f0' : '#0a0d18']} position={[0, 0, 0]} />
      
      {/* Lane Lines */}
      <LaneLines blockedEdges={blockedEdges} />

      {/* Glowing junction nodes */}
      <JunctionNodes />

      {/* Render Zones */}
      {Object.entries(ZONES_3D).map(([key, value]) => (
        <Zone key={key} {...value} />
      ))}
      
      {/* Zone X */}
      <ZoneX />

      {/* Render Dynamic AGV models */}
      {agvsData.map((agv) => (
        <AGVModel key={agv.agv_id} agvData={agv} fpvMode={fpvMode} />
      ))}
    </group>
  );
}
