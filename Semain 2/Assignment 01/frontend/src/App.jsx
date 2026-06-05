import React, { useState, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import Warehouse3D from './Warehouse3D';
import RobotController from './RobotController';
import mqtt from 'mqtt';
import './index.css';

// ─ MQTT direct-to-robot config (same as RobotController & Python script) ─────
const MQTT_BROKER_URL = "wss://ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud:8884/mqtt";
const MQTT_USER       = "hivemq.webclient.1775653497883";
const MQTT_PASS       = "1B%.CwaP:Kdr2I93k*Ap";
const MQTT_CMD_TOPIC  = "robot/control";

// Default starter states in case backend is offline
const initialAgents = [
  {
    agv_id: "AGV-01",
    state: "OFFLINE",
    battery_pct: 100,
    mission_id: "M-PENDING-01",
    speed_mps: 0.0,
    position: { x: 1.5, y: 6.5, zone: "C" },
    target_zone: "C",
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
  const [speed, setSpeed] = useState(50);
  const [fpvMode, setFpvMode] = useState(false);
  const [blockedEdges, setBlockedEdges] = useState([]);
  // Gyroscope (MPU6050) live data from physical robot via MQTT→WebSocket
  const [gyroYaw, setGyroYaw] = useState(0.0);
  const [gyroOnline, setGyroOnline] = useState(false);
  const [physDistance, setPhysDistance] = useState(999.0);
  const wsRef   = useRef(null);
  const mqttRef = useRef(null);   // ← direct MQTT to ESP32 (same as RobotController)
  // Speech queue: ensures only one audio plays at a time
  const audioQueueRef = useRef([]);
  const currentAudioRef = useRef(null);
  const isPlayingRef = useRef(false);

  const playNextInQueue = () => {
    if (audioQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      currentAudioRef.current = null;
      return;
    }
    const nextAudioB64 = audioQueueRef.current.shift();
    const audio = new Audio("data:audio/mp3;base64," + nextAudioB64);
    currentAudioRef.current = audio;
    isPlayingRef.current = true;
    audio.onended = () => playNextInQueue();
    audio.onerror = () => playNextInQueue();
    audio.play().catch(() => playNextInQueue());
  };

  const enqueueSpeech = (audioB64, interrupt = false) => {
    if (interrupt) {
      // Stop current audio immediately and clear the queue
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current.src = "";
        currentAudioRef.current = null;
      }
      audioQueueRef.current = [];
      isPlayingRef.current = false;
    }
    audioQueueRef.current.push(audioB64);
    if (!isPlayingRef.current) {
      playNextInQueue();
    }
  };

  // Establish WebSocket connection with auto-reconnection
  useEffect(() => {
    let reconnectTimer;
    let isDestroyed = false; // guard against StrictMode double-invoke

    const connectWS = () => {
      // Close any existing connection first (StrictMode safety)
      if (wsRef.current && wsRef.current.readyState <= 1) {
        wsRef.current.onclose = null; // prevent auto-reconnect loop
        wsRef.current.close();
      }
      if (isDestroyed) return;
      setWsStatus("CONNECTING");
      const ws = new WebSocket("ws://localhost:8765");
      wsRef.current = ws;

      ws.onopen = () => {
        if (isDestroyed) { ws.close(); return; }
        setWsStatus("CONNECTED");
        console.log("🔌 Telemetry WebSocket Stream established.");
      };

      ws.onmessage = (event) => {
        if (isDestroyed) return;
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === "speech" && payload.audio) {
            // interrupt=true for urgent events (estop, pause), false for regular announcements
            const interrupt = payload.interrupt === true;
            enqueueSpeech(payload.audio, interrupt);
            return;
          }
          if (payload.agents) {
            setAgvs(payload.agents);
          }
          if (payload.paused !== undefined) {
            setPaused(payload.paused);
          }
          if (payload.emergency_stop !== undefined) {
            setEmergencyStop(payload.emergency_stop);
          }
          if (payload.speed !== undefined) {
            setSpeed(payload.speed);
          }
          if (payload.blocked_edges !== undefined) {
            setBlockedEdges(payload.blocked_edges);
          }
          // Physical robot gyroscope + sensor data forwarded via twin telemetry
          if (payload.gyro_yaw !== undefined) {
            setGyroYaw(payload.gyro_yaw);
            setGyroOnline(true);
          }
          if (payload.phys_distance !== undefined) {
            setPhysDistance(payload.phys_distance);
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
      isDestroyed = true; // silence any in-flight handlers (React StrictMode safety)
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null; // don't auto-reconnect on intentional teardown
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Send a control command to the Python simulation backend
  const sendCommand = (cmd, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd, ...payload }));
      console.log(`📤 WS command: ${cmd}`, payload);
    }
  };

  // ── MQTT shortcuts for physical robot (called alongside WS commands) ─────────
  // These ensure the physical car responds even if the backend is offline.
  const mqttStop  = () => mqttPub("STOP");
  const mqttSpeed = (v) => mqttPub(`SPEED:${v}`);




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

  // ── MQTT direct connection to physical robot ───────────────────────────
  useEffect(() => {
    const client = mqtt.connect(MQTT_BROKER_URL, {
      username: MQTT_USER, password: MQTT_PASS,
      clientId: `app-ctrl-${Math.random().toString(16).slice(2)}`,
      clean: true, reconnectPeriod: 4000,
    });
    mqttRef.current = client;
    client.on('connect', () => console.log('[MQTT] App connected to HiveMQ (system controls)'));
    client.on('error',   (e) => console.warn('[MQTT] App error:', e.message));
    return () => client.end();
  }, []);

  // Helper: publish a raw MQTT command to the physical robot
  const mqttPub = (cmd) => {
    mqttRef.current?.publish(MQTT_CMD_TOPIC, cmd);
  };


  const isAgentInZoneX = (agv) => {
    const x = agv.position?.x || 4.0;
    const y = agv.position?.y || 4.0;
    return x >= 2.9 && x <= 5.1 && y >= 2.9 && y <= 5.1;
  };

  useEffect(() => {
    const anyInZoneX = agvs.some(isAgentInZoneX);
    if (anyInZoneX) {
      document.body.classList.add('shake-screen');
    } else {
      document.body.classList.remove('shake-screen');
    }
  }, [agvs]);
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
          {!fpvMode && (
            <OrbitControls 
              maxPolarAngle={Math.PI / 2 - 0.05} 
              minDistance={2} 
              maxDistance={15} 
            />
          )}
          <Warehouse3D agvsData={agvs} lightMode={lightMode} fpvMode={fpvMode} blockedEdges={blockedEdges} />
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
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <button 
              onClick={() => {
                setFpvMode(prev => !prev);
              }}
              style={{
                background: fpvMode ? 'var(--state-wait)' : 'var(--color-panel-border)',
                border: 'none',
                color: fpvMode ? '#000' : 'var(--color-text-ivory)',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 'bold',
                fontFamily: 'Space Grotesk, sans-serif',
                transition: 'all 0.2s ease',
                boxShadow: fpvMode ? '0 0 10px rgba(245, 158, 11, 0.4)' : 'none'
              }}
              title="Toggle First Person View Camera"
            >
              🎥 {fpvMode ? 'FPV Camera ON' : 'FPV Camera OFF'}
            </button>
            <button 
              onClick={() => {
                console.log("🔊 Manually triggered Test Voice button via WebSocket");
                sendCommand("test_voice");
              }}
              style={{
                background: 'rgba(59, 130, 246, 0.2)',
                border: '1px solid rgba(59, 130, 246, 0.4)',
                color: '#3b82f6',
                padding: '6px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 'bold',
                fontFamily: 'Space Grotesk, sans-serif',
                transition: 'all 0.2s ease'
              }}
              title="Test Voice Announcement"
            >
              🔊 Test Voice
            </button>
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
        </div>
        <p className="hud-developer" style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginTop: '-10px', marginBottom: '15px', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>Developed by: Hafida Belayd & Abdelkhalek Hanbel</p>

        {/* ── Physical Robot Controller (MQTT direct to ESP32) ── */}
        <RobotController />

        {agvs.map((agv) => {
          const inZoneX = isAgentInZoneX(agv);
          const speedPct = Math.min(100, (agv.speed_mps / 1.0) * 100);
          const isAlert = agv.state === "STOP" || agv.distance_front_cm <= 25;

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

              {/* Row 3b: Gyroscope Yaw Angle (MPU6050) */}
              <div className="metrics-row" style={{ marginTop: '4px' }}>
                <div className="metric-item">
                  <div className="metric-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <span>Gyro Yaw</span>
                    <span style={{
                      fontSize: '9px',
                      padding: '1px 5px',
                      borderRadius: '4px',
                      background: gyroOnline ? 'rgba(16,185,129,0.2)' : 'rgba(100,100,100,0.2)',
                      color: gyroOnline ? '#10b981' : '#6b7280',
                      fontWeight: 'bold'
                    }}>
                      {gyroOnline ? 'MPU6050 ●' : 'NO GYRO'}
                    </span>
                  </div>
                  <div className="metric-value-mono" style={{
                    color: gyroOnline ? '#a78bfa' : 'var(--color-text-muted)',
                    fontSize: '18px'
                  }}>
                    {gyroOnline ? `${gyroYaw >= 0 ? '+' : ''}${gyroYaw.toFixed(1)}°` : '— °'}
                  </div>
                  {/* Compass visual */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px' }}>
                    <div style={{
                      width: '28px', height: '28px', borderRadius: '50%',
                      border: '1px solid rgba(167,139,250,0.3)',
                      position: 'relative', flexShrink: 0
                    }}>
                      <div style={{
                        position: 'absolute', top: '50%', left: '50%',
                        width: '2px', height: '11px',
                        background: gyroOnline ? '#a78bfa' : '#374151',
                        transformOrigin: 'bottom center',
                        transform: `translate(-50%, -100%) rotate(${gyroYaw}deg)`,
                        transition: 'transform 0.3s ease',
                        borderRadius: '2px'
                      }} />
                    </div>
                    <div className="progress-bar-bg" style={{ flex: 1 }}>
                      <div className="progress-bar-fill" style={{
                        width: `${Math.min(100, Math.abs(gyroYaw) / 1.8)}%`,
                        backgroundColor: '#a78bfa',
                        transition: 'width 0.3s ease'
                      }} />
                    </div>
                  </div>
                </div>
                <div className="metric-item right">
                  <div className="metric-label">Phys. Distance</div>
                  <div className="metric-value-mono" style={{
                    color: physDistance <= 20 ? 'var(--color-terracotta)' :
                           physDistance <= 50 ? 'var(--state-wait)' : 'var(--color-text-ivory)'
                  }}>
                    {physDistance >= 999 ? '— cm' : `${physDistance.toFixed(0)} cm`}
                  </div>
                  <div style={{ fontSize: '9px', color: 'var(--color-text-muted)', marginTop: '2px' }}>
                    {physDistance <= 20 ? '🚨 TOO CLOSE' : physDistance <= 50 ? '🟡 NEAR' : '🟢 CLEAR'}
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

              <div className="manual-dispatch-section" style={{ marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed var(--color-panel-border)' }}>
                <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', marginBottom: '5px', fontWeight: 'bold', letterSpacing: '0.05em' }}>MANUAL DISPATCH:</div>
                <div style={{ display: 'flex', gap: '4px', marginBottom: '4px' }}>
                  {['A', 'B', 'C', 'D', 'R'].map((zone) => (
                    <button
                      key={zone}
                      onClick={() => {
                        sendCommand("dispatch", { agv_id: agv.agv_id, target: zone });
                      }}
                      disabled={agv.connectivity_status === "OFFLINE" || emergencyStop || paused}
                      style={{
                        flex: 1,
                        padding: '6px 0',
                        fontSize: '11px',
                        background: agv.target_zone === zone ? 'var(--state-wait)' : 'rgba(255, 255, 255, 0.05)',
                        color: agv.target_zone === zone ? '#000' : 'var(--color-text-ivory)',
                        border: '1px solid var(--color-panel-border)',
                        borderRadius: '6px',
                        fontWeight: '700',
                        fontFamily: 'Space Grotesk, sans-serif',
                        cursor: agv.connectivity_status === "OFFLINE" || emergencyStop || paused ? 'not-allowed' : 'pointer',
                        opacity: agv.connectivity_status === "OFFLINE" || emergencyStop || paused ? 0.4 : 1,
                        transition: 'all 0.2s ease',
                        boxShadow: agv.target_zone === zone ? '0 0 10px rgba(245, 158, 11, 0.4)' : 'none'
                      }}
                      onMouseEnter={(e) => {
                        if (agv.connectivity_status !== "OFFLINE" && !emergencyStop && !paused && agv.target_zone !== zone) {
                          e.target.style.background = 'rgba(255, 255, 255, 0.12)';
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (agv.target_zone !== zone) {
                          e.target.style.background = 'rgba(255, 255, 255, 0.05)';
                        }
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
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              onClick={() => {
                sendCommand("pause");          // WS → backend simulator
                mqttStop();                    // MQTT → physical robot STOP immediately
              }}
              style={{
                flex: 1,
                padding: '10px 5px',
                background: paused ? 'var(--state-wait)' : 'rgba(255, 255, 255, 0.05)',
                color: paused ? '#000' : 'var(--color-text-ivory)',
                border: '1px solid var(--color-panel-border)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: paused ? '0 0 10px rgba(245, 158, 11, 0.4)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (!paused) e.target.style.background = 'rgba(255, 255, 255, 0.12)';
              }}
              onMouseLeave={(e) => {
                if (!paused) e.target.style.background = 'rgba(255, 255, 255, 0.05)';
              }}
            >
              {paused ? "RESUME" : "PAUSE"}
            </button>
            <button 
              onClick={() => {
                sendCommand("estop");          // WS → backend
                mqttStop();                   // MQTT → physical robot hard STOP
              }}
              style={{
                flex: 1.2,
                padding: '10px 5px',
                background: emergencyStop ? 'var(--color-terracotta)' : '#991b1b',
                color: '#fff',
                border: '1px solid var(--color-panel-border)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: emergencyStop ? '0 0 15px rgba(239, 68, 68, 0.5)' : 'none'
              }}
              onMouseEnter={(e) => {
                if (!emergencyStop) e.target.style.background = '#7f1d1d';
              }}
              onMouseLeave={(e) => {
                if (!emergencyStop) e.target.style.background = '#991b1b';
              }}
            >
              {emergencyStop ? "RESUME FLEET" : "STOP FLEET (E-STOP)"}
            </button>
            <button 
              onClick={() => {
                sendCommand("reset", { agv_id: "ALL" });   // WS → backend
                mqttStop();                                  // MQTT → physical robot STOP
              }}
              style={{
                flex: 1.1,
                padding: '10px 5px',
                background: 'rgba(217, 119, 6, 0.2)',
                color: '#f59e0b',
                border: '1px solid rgba(217, 119, 6, 0.4)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.target.style.background = 'rgba(217, 119, 6, 0.35)';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(217, 119, 6, 0.2)';
              }}
            >
              ABORT
            </button>
            <button 
              onClick={() => {
                sendCommand("reset_to_start");   // WS → backend
                mqttStop();                       // MQTT → physical robot STOP
              }}
              style={{
                flex: 1.1,
                padding: '10px 5px',
                background: 'rgba(59, 130, 246, 0.2)',
                color: '#3b82f6',
                border: '1px solid rgba(59, 130, 246, 0.4)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: 'pointer',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.target.style.background = 'rgba(59, 130, 246, 0.35)';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(59, 130, 246, 0.2)';
              }}
            >
              RESET TO C
            </button>
          </div>
        </div>

        {/* Obstacle Avoidance Panel */}
        <div className="gateways-panel" style={{ marginBottom: '15px' }}>
          <div className="gateways-title">DYNAMIC OBSTACLE RE-ROUTING</div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              onClick={() => {
                sendCommand("simulate_obstacle");
              }}
              disabled={agvs.some(a => a.connectivity_status === "OFFLINE") || emergencyStop || paused || agvs.some(a => a.state === "IDLE")}
              style={{
                flex: 1,
                padding: '10px 5px',
                background: 'rgba(239, 68, 68, 0.15)',
                color: '#ef4444',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: agvs.some(a => a.connectivity_status === "OFFLINE") || emergencyStop || paused || agvs.some(a => a.state === "IDLE") ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
                opacity: agvs.some(a => a.connectivity_status === "OFFLINE") || emergencyStop || paused || agvs.some(a => a.state === "IDLE") ? 0.4 : 1
              }}
              onMouseEnter={(e) => {
                if (!(agvs.some(a => a.connectivity_status === "OFFLINE") || emergencyStop || paused || agvs.some(a => a.state === "IDLE"))) {
                  e.target.style.background = 'rgba(239, 68, 68, 0.3)';
                }
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(239, 68, 68, 0.15)';
              }}
            >
              ⚠️ SIMULATE OBSTACLE
            </button>
            <button 
              onClick={() => {
                sendCommand("clear_obstacles");
              }}
              disabled={emergencyStop}
              style={{
                flex: 1,
                padding: '10px 5px',
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                borderRadius: '8px',
                fontWeight: '700',
                fontFamily: 'Space Grotesk, sans-serif',
                cursor: emergencyStop ? 'not-allowed' : 'pointer',
                transition: 'all 0.2s ease',
                opacity: emergencyStop ? 0.4 : 1
              }}
              onMouseEnter={(e) => {
                if (!emergencyStop) {
                  e.target.style.background = 'rgba(16, 185, 129, 0.3)';
                }
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(16, 185, 129, 0.15)';
              }}
            >
              🧹 CLEAR OBSTACLES
            </button>
          </div>
        </div>

        {/* Speed Control Panel */}
        <div className="gateways-panel" style={{ marginBottom: '15px' }}>
          <div className="gateways-title">SPEED CONTROL (PWM)</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <span style={{ fontFamily: 'monospace', width: '40px', fontSize: '14px', color: 'var(--color-text-ivory)', fontWeight: 'bold' }}>
              {speed}
            </span>
            <input 
              type="range" 
              min="50" 
              max="255" 
              value={speed} 
              onChange={(e) => {
                const newSpeed = parseInt(e.target.value);
                setSpeed(newSpeed);
                sendCommand("set_speed", { value: newSpeed });   // WS → backend
                mqttSpeed(newSpeed);                              // MQTT → physical robot
              }}
              style={{
                flex: 1,
                cursor: 'pointer',
                accentColor: '#ff7850',
                height: '6px',
                borderRadius: '3px'
              }}
            />
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

          <div className={`gateway-line ${gyroOnline ? 'ok' : 'err'}`}>
            <span>MPU6050 Gyroscope:</span>
            <span>{gyroOnline ? `ONLINE — ${gyroYaw >= 0 ? '+' : ''}${gyroYaw.toFixed(1)}°` : 'OFFLINE / Safe Mode'}</span>
          </div>

          <div className="gateway-line ok">
            <span>Distance Sensor:</span>
            <span>{physDistance >= 999 ? 'CLEAR' : `${physDistance.toFixed(0)} cm`}</span>
          </div>
          
          <div className="gateway-line" style={{ color: '#7887a5', marginTop: '6px', fontSize: '10px' }}>
            <span>Target URI: ws://localhost:8765</span>
          </div>
        </div>
      </div>
    </>
  );
}
