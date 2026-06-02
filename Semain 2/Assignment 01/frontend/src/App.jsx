import React, { useState, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import Warehouse3D from './Warehouse3D';
import './index.css';

// Default starter states in case backend is offline
const initialAgents = [
  {
    agv_id: "AGV-01",
    state: "OFFLINE",
    battery_pct: 100,
    mission_id: "M-PENDING-01",
    speed_mps: 0.0,
    position: { x: 1.5, y: 1.5, zone: "A" },
    target_zone: "A",
    distance_front_cm: 300,
    temperature_c: 25.0,
    connectivity_status: "OFFLINE"
  },
  {
    agv_id: "AGV-02",
    state: "OFFLINE",
    battery_pct: 100,
    mission_id: "M-PENDING-02",
    speed_mps: 0.0,
    position: { x: 6.5, y: 1.5, zone: "B" },
    target_zone: "B",
    distance_front_cm: 300,
    temperature_c: 25.0,
    connectivity_status: "OFFLINE"
  }
];

export default function App() {
  const [agvs, setAgvs] = useState(initialAgents);
  const [wsStatus, setWsStatus] = useState("DISCONNECTED");
  const [paused, setPaused] = useState(false);
  const [emergencyStop, setEmergencyStop] = useState(false);
  const [lightMode, setLightMode] = useState(false);
  const wsRef = useRef(null);

  // Establish WebSocket connection with auto-reconnection
  useEffect(() => {
    let reconnectTimer;

    const connectWS = () => {
      setWsStatus("CONNECTING");
      const ws = new WebSocket("ws://localhost:8765");
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus("CONNECTED");
        console.log("🔌 Telemetry WebSocket Stream established.");
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.agents) {
            setAgvs(payload.agents);
          }
          if (payload.paused !== undefined) {
            setPaused(payload.paused);
          }
          if (payload.emergency_stop !== undefined) {
            setEmergencyStop(payload.emergency_stop);
          }
        } catch (err) {
          console.error("Error parsing telemetry payload:", err);
        }
      };

      ws.onerror = (err) => {
        setWsStatus("ERROR");
        console.error("WebSocket connection error:", err);
      };

      ws.onclose = () => {
        setWsStatus("DISCONNECTED");
        console.log("🔌 WebSocket Connection closed. Reconnecting in 3s...");
        reconnectTimer = setTimeout(connectWS, 3000);
      };
    };

    connectWS();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      clearTimeout(reconnectTimer);
    };
  }, []);

  // Send a control command to the Python simulation backend
  const sendCommand = (cmd) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd }));
      console.log(`📤 Dispatched command over WS: ${cmd}`);
    }
  };

  // Toggle Light/Dark Mode
  const toggleLightMode = () => {
    setLightMode(prev => {
      const newMode = !prev;
      if (newMode) {
        document.body.classList.add('light-mode');
      } else {
        document.body.classList.remove('light-mode');
      }
      return newMode;
    });
  };

  // Check if an AGV is in Zone X (for dashboard alert styling)
  const isAgentInZoneX = (agv) => {
    const x = agv.position?.x || 4.0;
    const y = agv.position?.y || 4.0;
    return agv.position?.zone === 'X' || (x >= 2.9 && x <= 5.1 && y >= 2.9 && y <= 5.1);
  };

  return (
    <>
      {/* Flashing Emergency Stop Alert Border & Banner */}
      {emergencyStop && (
        <div className="estop-screen-overlay" style={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          border: '8px solid var(--color-terracotta)',
          pointerEvents: 'none',
          zIndex: 5,
          boxSizing: 'border-box',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'flex-start',
          paddingTop: '30px'
        }}>
          <div className="estop-banner" style={{
            background: 'var(--color-bg)',
            color: 'var(--color-terracotta)',
            border: '1px solid var(--color-terracotta)',
            borderRadius: '6px',
            padding: '12px 24px',
            fontSize: '22px',
            fontWeight: 'bold',
            boxShadow: '0 0 15px rgba(195, 74, 54, 0.4)',
            pointerEvents: 'auto',
            animation: 'blinker 1s linear infinite'
          }}>
            ⚠️ EMERGENCY STOP ACTIVE ⚠️
          </div>
        </div>
      )}

      {/* 3D Visualizer Canvas */}
      <div className="canvas-container">
        <Canvas 
          camera={{ position: [0, 7, 7], fov: 50 }} 
          shadows
        >
          <color attach="background" args={[lightMode ? '#f4f6f8' : '#0a0f1d']} />
          <OrbitControls 
            maxPolarAngle={Math.PI / 2 - 0.05} 
            minDistance={2} 
            maxDistance={15} 
          />
          <Warehouse3D agvsData={agvs} lightMode={lightMode} />
        </Canvas>
      </div>

      {/* Map Controls Legend */}
      <div className="map-legend">
        <div>🔧 3D CONTROLS:</div>
        <div>• Rotate: Left-Click + Drag</div>
        <div>• Pan: Right-Click + Drag</div>
        <div>• Zoom: Scroll Wheel</div>
        <div style={{ marginTop: '8px', color: '#eaebed' }}>
          📐 Scale: 1.0 unit = 1.0 meter
        </div>
      </div>

      {/* HTML Telemetry Dashboard HUD */}
      <div className="hud-overlay">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h1 className="hud-title">FLEET MONITOR 3D</h1>
            <p className="hud-subtitle">Live Digital Twin Coordinate Stream</p>
          </div>
          <button 
            onClick={toggleLightMode}
            style={{
              background: 'var(--color-panel-border)',
              border: 'none',
              color: 'var(--color-text-ivory)',
              padding: '6px 12px',
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '18px'
            }}
            title="Toggle Theme"
          >
            {lightMode ? '🌙' : '☀️'}
          </button>
        </div>
        <p className="hud-developer" style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '-10px', marginBottom: '15px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>Developed by: Hafida Belayd</p>

        {agvs.map((agv) => {
          const inZoneX = isAgentInZoneX(agv);
          const speedPct = Math.min(100, (agv.speed_mps / 1.0) * 100);
          const isAlert = agv.state === "STOP" || agv.distance_front_cm < 80;

          // Battery state color mapping
          let batteryColor = "var(--state-enroute)";
          if (agv.battery_pct <= 20) batteryColor = "var(--state-stop)";
          else if (agv.battery_pct <= 50) batteryColor = "var(--state-wait)";

          return (
            <div 
              key={agv.agv_id} 
              className={`telemetry-card ${inZoneX ? 'alert-active' : ''}`}
            >
              <div 
                className="card-indicator" 
                style={{ backgroundColor: inZoneX ? 'var(--color-terracotta)' : agv.agv_id === 'AGV-01' ? '#ff7850' : '#2eccfa' }}
              />
              
              <div className="card-header">
                <span className="agv-id">{agv.agv_id}</span>
                <span className={`agv-connectivity ${agv.connectivity_status === 'OFFLINE' ? 'offline' : ''}`}>
                  <span className="status-dot" />
                  {agv.connectivity_status}
                </span>
                <span className={`state-tag ${agv.state.toLowerCase()}`}>
                  {agv.state}
                </span>
              </div>

              <hr className="card-divider" />

              {/* Row 1: Battery & Motor Temp */}
              <div className="metrics-row">
                <div className="metric-item">
                  <div className="metric-label">Battery</div>
                  <div className="metric-value-mono" style={{ color: batteryColor }}>
                    {agv.battery_pct}%
                  </div>
                  <div className="progress-bar-bg">
                    <div 
                      className="progress-bar-fill" 
                      style={{ width: `${agv.battery_pct}%`, backgroundColor: batteryColor }}
                    />
                  </div>
                </div>
                
                <div className="metric-item right">
                  <div className="metric-label">Motor Temp</div>
                  <div className="metric-value-mono">
                    {agv.temperature_c.toFixed(1)}°C
                  </div>
                </div>
              </div>

              {/* Row 2: Speed & Obstacle Distance */}
              <div className="metrics-row">
                <div className="metric-item">
                  <div className="metric-label">Speed</div>
                  <div className="metric-value-mono">
                    {agv.speed_mps.toFixed(2)} m/s
                  </div>
                  <div className="progress-bar-bg">
                    <div 
                      className="progress-bar-fill" 
                      style={{ width: `${speedPct}%`, backgroundColor: 'var(--state-arrived)' }}
                    />
                  </div>
                </div>
                
                <div className="metric-item right">
                  <div className="metric-label">Obstacle Front</div>
                  <div className="metric-value-mono" style={{ color: isAlert ? 'var(--color-terracotta)' : 'var(--color-text-ivory)' }}>
                    {agv.distance_front_cm} cm
                  </div>
                </div>
              </div>

              {/* Row 3: Critical Zone Alert Banner */}
              {inZoneX && (
                <div className="zone-x-warning">
                  ⚠️ WARNING: {agv.agv_id} IN CRITICAL ZONE X
                </div>
              )}

              <hr className="card-divider" />

              {/* Row 4: Route Details & Odometer */}
              <div className="gateway-line">
                <span>Mission ID:</span>
                <span style={{ color: '#7887a5' }}>{agv.mission_id}</span>
              </div>
              <div className="gateway-line">
                <span>Route:</span>
                <span>
                  {agv.position?.zone} ➔ {agv.target_zone}
                </span>
              </div>
              <div className="gateway-line" style={{ color: 'var(--state-arrived)' }}>
                <span>Odometer:</span>
                <span className="metric-value-mono">
                  {(agv.total_distance_m || 0).toFixed(2)} m
                </span>
              </div>

              <div className="manual-dispatch-section" style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed rgba(234, 235, 237, 0.1)' }}>
                <div style={{ fontSize: '10px', color: '#7887a5', marginBottom: '5px', fontWeight: 'bold', letterSpacing: '0.05em' }}>MANUAL DISPATCH:</div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  {['A', 'B', 'C', 'D', 'R'].map((zone) => (
                    <button
                      key={zone}
                      onClick={() => {
                        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                          wsRef.current.send(JSON.stringify({ 
                            command: "dispatch", 
                            agv_id: agv.agv_id, 
                            target: zone 
                          }));
                        }
                      }}
                      disabled={agv.connectivity_status === "OFFLINE" || emergencyStop || paused}
                      style={{
                        flex: 1,
                        padding: '5px 0',
                        fontSize: '11px',
                        background: agv.target_zone === zone ? 'var(--state-wait)' : '#1c2a46',
                        color: agv.target_zone === zone ? '#000' : '#eaebed',
                        border: '1px solid var(--color-panel-border)',
                        borderRadius: '4px',
                        fontWeight: 'bold',
                        cursor: agv.connectivity_status === "OFFLINE" || emergencyStop || paused ? 'not-allowed' : 'pointer',
                        opacity: agv.connectivity_status === "OFFLINE" || emergencyStop || paused ? 0.4 : 1,
                        transition: 'background 0.2s, color 0.2s'
                      }}
                    >
                      {zone}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          );
        })}

        {/* System Controls Panel */}
        <div className="gateways-panel" style={{ marginBottom: '15px' }}>
          <div className="gateways-title">SYSTEM CONTROLS</div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button 
              onClick={() => sendCommand("pause")}
              style={{
                flex: 1,
                padding: '10px 5px',
                background: paused ? 'var(--state-wait)' : '#1c2a46',
                color: paused ? '#000' : '#fff',
                border: '1px solid var(--color-panel-border)',
                borderRadius: '6px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'background 0.2s'
              }}
            >
              {paused ? "RESUME" : "PAUSE"}
            </button>
            <button 
              onClick={() => sendCommand("estop")}
              style={{
                flex: 1,
                padding: '10px 5px',
                background: emergencyStop ? 'var(--color-terracotta)' : '#73231e',
                color: '#fff',
                border: '1px solid var(--color-panel-border)',
                borderRadius: '6px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'background 0.2s'
              }}
            >
              {emergencyStop ? "RESUME FLEET" : "STOP FLEET (E-STOP)"}
            </button>
          </div>
        </div>

        {/* Global Connection Stats Panel */}
        <div className="gateways-panel">
          <div className="gateways-title">TELEMETRY GATEWAYS</div>
          
          <div className={`gateway-line ${wsStatus === 'CONNECTED' ? 'ok' : wsStatus === 'CONNECTING' ? 'pending' : 'err'}`}>
            <span>WebSocket Stream:</span>
            <span>{wsStatus}</span>
          </div>
          
          <div className="gateway-line ok">
            <span>NDJSON Logger:</span>
            <span>ACTIVE</span>
          </div>
          
          <div className="gateway-line" style={{ color: '#7887a5', marginTop: '6px', fontSize: '10px' }}>
            <span>Target URI: ws://localhost:8765</span>
          </div>
        </div>
      </div>
    </>
  );
}
