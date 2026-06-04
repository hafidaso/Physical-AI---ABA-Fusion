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
  const wsRef = useRef(null);
  const speechAllowedRef = useRef(false);
  const activeUtterancesRef = useRef([]);

  // Unlocks browser speech synthesis on first user interaction
  useEffect(() => {
    const unlockSpeech = () => {
      speechAllowedRef.current = true;
      if ('speechSynthesis' in window) {
        // Clear any blocked utterances that got queued before the user clicked
        window.speechSynthesis.cancel();
        console.log("🔊 Speech synthesis unlocked and queue cleared via user click.");
      }
      window.removeEventListener('click', unlockSpeech);
      window.removeEventListener('keydown', unlockSpeech);
    };
    window.addEventListener('click', unlockSpeech);
    window.addEventListener('keydown', unlockSpeech);
    return () => {
      window.removeEventListener('click', unlockSpeech);
      window.removeEventListener('keydown', unlockSpeech);
    };
  }, []);

  // Monitor voice changes for debugging
  useEffect(() => {
    if ('speechSynthesis' in window) {
      const logVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        console.log(`🔊 Speech voices loaded. Total: ${voices.length}`);
        const localEn = voices.filter(v => v.lang.startsWith("en") && v.localService === true).map(v => v.name);
        console.log("🔊 Local English voices available:", localEn);
      };
      window.speechSynthesis.onvoiceschanged = logVoices;
      logVoices();
    }
  }, []);

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
          if (payload.speed !== undefined) {
            setSpeed(payload.speed);
          }
          if (payload.blocked_edges !== undefined) {
            setBlockedEdges(payload.blocked_edges);
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
  const sendCommand = (cmd, payload = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: cmd, ...payload }));
      console.log(`📤 Dispatched command over WS: ${cmd}`, payload);
    }
  };

  // Smart Speech Assistant Synthesis
  const speak = (text) => {
    if (!speechAllowedRef.current) {
      console.log("🔊 Speech skipped (waiting for user interaction):", text);
      return;
    }

    if ('speechSynthesis' in window) {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      }
      
      // Yield thread slightly before playing the utterance
      setTimeout(() => {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.volume = 1.0; // Explicitly set full volume
        
        // Prevent Chrome garbage collection bug by storing a strong reference in a React Ref
        activeUtterancesRef.current.push(utterance);
        
        const cleanUp = () => {
          activeUtterancesRef.current = activeUtterancesRef.current.filter(u => u !== utterance);
        };
        
        utterance.onstart = () => console.log("🔊 Speech Started:", text);
        utterance.onend = () => {
          console.log("🔊 Speech Finished:", text);
          cleanUp();
        };
        utterance.onerror = (e) => {
          console.error("❌ Speech Error:", e);
          cleanUp();
        };
        
        const voices = window.speechSynthesis.getVoices();
        if (voices && voices.length > 0) {
          // Filter to strictly LOCAL English voices (network independent)
          const localEnglishVoices = voices.filter(v => 
            v.lang.startsWith("en") && 
            v.localService === true
          );
          
          let selectedVoice = null;
          if (localEnglishVoices.length > 0) {
            // 1. Prioritize known high-quality pre-installed spoken voices (Alex is macOS default, Fred is standard macOS backup)
            const premiumSpokenNames = [
              "Alex", 
              "Daniel", 
              "Fred", 
              "Samantha", 
              "Victoria", 
              "Microsoft David", 
              "Microsoft Zira", 
              "Karen", 
              "Moira", 
              "Tessa"
            ];
            
            for (const name of premiumSpokenNames) {
              selectedVoice = localEnglishVoices.find(v => v.name === name);
              if (selectedVoice) break;
            }
            
            // 2. Avoid Siri/Samantha (un-downloaded silence bug) and novelty sound effects (like Cellos, Bells, Organ)
            if (!selectedVoice) {
              const noveltyVoices = [
                "cello", "bell", "news", "boing", "deranged", "bubble", 
                "hysterical", "trinoid", "whisper", "zarvox", "organ", 
                "albert", "junior", "princess", "ralph", "siri"
              ];
              
              selectedVoice = localEnglishVoices.find(v => {
                const lowerName = v.name.toLowerCase();
                return !noveltyVoices.some(novelty => lowerName.includes(novelty));
              });
            }
            
            // 3. Fallback to first local English voice if all else fails
            if (!selectedVoice) {
              selectedVoice = localEnglishVoices[0];
            }
          }
          
          if (selectedVoice) {
            utterance.voice = selectedVoice;
            console.log(`🔊 Using local speech voice: ${selectedVoice.name}`);
          } else {
            console.log("🔊 No suitable local English voice found, letting browser use default system voice.");
          }
        }
        
        utterance.rate = 0.95;
        utterance.pitch = 1.0;
        
        window.speechSynthesis.speak(utterance);
      }, 50);
    }
  };

  const lastStateRef = useRef({ paused: false, estop: false, inZoneX: false, isAlert: false, targetZone: "", blockedCount: 0 });

  useEffect(() => {
    const agv = agvs.find(a => a.agv_id === "AGV-01");
    if (!agv) return;

    const inZoneX = isAgentInZoneX(agv);
    const isAlert = agv.state === "STOP" || agv.distance_front_cm <= 25;
    const targetZone = agv.target_zone;

    // Check E-Stop
    if (emergencyStop && !lastStateRef.current.estop) {
      speak("Emergency stop activated on the fleet.");
    } else if (!emergencyStop && lastStateRef.current.estop) {
      speak("Emergency stop cleared. Fleet operations resumed.");
    }

    // Check Pause
    if (!emergencyStop) {
      if (paused && !lastStateRef.current.paused) {
        speak("Fleet operations paused.");
      } else if (!paused && lastStateRef.current.paused) {
        speak("Fleet operations resumed.");
      }
    }

    // Check Zone X entry
    if (inZoneX && !lastStateRef.current.inZoneX && !paused && !emergencyStop) {
      speak("Warning. A.G.V. 0 1 has entered the critical intersection.");
    }

    // Check obstacle detection
    if (isAlert && !lastStateRef.current.isAlert && !paused && !emergencyStop) {
      speak("Alert. Obstacle detected in front of A.G.V. 0 1.");
    }

    // Check dispatch changes
    if (targetZone !== lastStateRef.current.targetZone && targetZone !== agv.position?.zone && !paused && !emergencyStop) {
      speak(`A.G.V. 0 1 dispatched to Zone ${targetZone}.`);
    }

    // Check blocked edges (re-routing warning)
    if (blockedEdges.length > lastStateRef.current.blockedCount && !paused && !emergencyStop) {
      speak("Warning. Lane obstruction detected. Recalculating path using Dijkstra's algorithm.");
    }

    // Update state ref
    lastStateRef.current = { paused, estop: emergencyStop, inZoneX, isAlert, targetZone, blockedCount: blockedEdges.length };
  }, [agvs, paused, emergencyStop, blockedEdges]);

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
                speechAllowedRef.current = true;
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
                speechAllowedRef.current = true;
                console.log("🔊 Manually triggered Test Voice button");
                speak("Voice assistant test successful. System is online.");
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
                        speechAllowedRef.current = true;
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
                speechAllowedRef.current = true;
                sendCommand("pause");
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
                speechAllowedRef.current = true;
                sendCommand("estop");
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
              onClick={() => sendCommand("reset", { agv_id: "ALL" })}
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
              onClick={() => sendCommand("reset_to_start")}
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
                speechAllowedRef.current = true;
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
                speechAllowedRef.current = true;
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
                sendCommand("set_speed", { value: newSpeed });
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
          
          <div className="gateway-line" style={{ color: '#7887a5', marginTop: '6px', fontSize: '10px' }}>
            <span>Target URI: ws://localhost:8765</span>
          </div>
        </div>
      </div>
    </>
  );
}
