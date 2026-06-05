import React, { useState, useEffect, useRef, useCallback } from 'react';
import mqtt from 'mqtt';

// ─── MQTT Configuration (same as Python script) ─────────────────────────────
const MQTT_HOST    = "ac6ac8bb96e444b3b796a80e83455529.s1.eu.hivemq.cloud";
const MQTT_PORT    = 8884;
const MQTT_USER    = "hivemq.webclient.1775653497883";
const MQTT_PASS    = "1B%.CwaP:Kdr2I93k*Ap";

const MQTT_CONTROL_TOPIC  = "robot/control";
const MQTT_DISTANCE_TOPIC = "robot/distance";
const MQTT_ANGLE_TOPIC    = "robot/angle";

// ─── ONE-SHOT TURN COMMANDS ──────────────────────────────────────────────────
const TURN_COMMANDS = new Set(["TURN_90_L", "TURN_90_R", "TURN_180"]);

// ─── SPEED PRESETS ───────────────────────────────────────────────────────────
const SPEED_PRESETS = [50, 100, 150, 200, 255];

// ─── AUTO MISSION CONSTANTS ──────────────────────────────────────────────────
// BACKWARD = physically forward (inverted wiring, same as Python Z key logic)
// RIGHT    = physically turns right
const MISSION_FWD_CMD  = "BACKWARD";
const MISSION_TURN_CMD = "RIGHT";
const TURN_TARGET_DEG  = 90.0;          // degrees to rotate at Zone A

const PHASE = {
  IDLE:      'idle',
  RUNNING:   'running_square',
  DONE:      'done',
  ABORTED:   'aborted',
};

const PHASE_LABELS = {
  idle:           { text: 'Prêt', color: '#6b7280',  icon: '⏸' },
  running_square: { text: 'جاري تنفيذ مسار المربع تلقائياً...', color: '#e67e22', icon: '🤖' },
  done:           { text: '✅ تم إكمال المربع بنجاح والروبوت واقف!',    color: '#27ae60', icon: '🎯' },
  aborted:        { text: '🛑 توقف اضطراري! تم إلغاء المسار التلقائي.', color: '#c0392b', icon: '✖' },
};

export default function RobotController() {
  const [mqttStatus, setMqttStatus]     = useState("DISCONNECTED");
  const [currentDistance, setDistance]  = useState(999.0);
  const [currentAngle, setAngle]        = useState(0.0);
  const [currentSpeed, setCurrentSpeed] = useState(100);
  const [bypassObstacle, setBypass]     = useState(false);
  const [lastCommand, setLastCommand]   = useState("STOP");
  const [activeBtn, setActiveBtn]       = useState(null);

  // Auto-mission state
  const [missionPhase, setMissionPhase]         = useState(PHASE.IDLE);
  const [timeToA, setTimeToA]                   = useState(3.0);
  const [timeToB, setTimeToB]                   = useState(3.0);
  const [liveAngleDelta, setLiveAngleDelta]      = useState(0.0);
  const [countdownSec, setCountdownSec]          = useState(0);   // ← NEW: seconds remaining display

  const clientRef        = useRef(null);
  const lastCmdRef       = useRef("STOP");
  const pressedKeys      = useRef(new Set());
  const missionAbortRef  = useRef(false);
  const missionPhaseRef  = useRef(PHASE.IDLE);   // ← keeps phase synced for async callbacks
  const currentAngleRef  = useRef(0.0);

  // ── MQTT Connect ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const brokerUrl = `wss://${MQTT_HOST}:${MQTT_PORT}/mqtt`;
    const client = mqtt.connect(brokerUrl, {
      username: MQTT_USER, password: MQTT_PASS,
      clientId: `dashboard-${Math.random().toString(16).slice(2)}`,
      clean: true, reconnectPeriod: 3000,
    });
    clientRef.current = client;

    client.on('connect', () => {
      setMqttStatus("CONNECTED");
      client.subscribe(MQTT_DISTANCE_TOPIC);
      client.subscribe(MQTT_ANGLE_TOPIC);
      client.publish(MQTT_CONTROL_TOPIC, `SPEED:100`);
    });
    client.on('reconnect', () => setMqttStatus("CONNECTING..."));
    client.on('offline',   () => setMqttStatus("DISCONNECTED"));
    client.on('error',     () => setMqttStatus("ERROR"));

    client.on('message', (topic, payload) => {
      const val = parseFloat(payload.toString());
      if (isNaN(val)) return;
      if (topic === MQTT_DISTANCE_TOPIC) setDistance(val);
      if (topic === MQTT_ANGLE_TOPIC) {
        setAngle(val);
        currentAngleRef.current = val;
      }
    });

    return () => { client.end(); };
  }, []);

  // ── send_command (Python logic: only publish if changed) ─────────────────────
  const sendCommand = useCallback((cmd) => {
    if (!clientRef.current) return;
    if (TURN_COMMANDS.has(cmd) || cmd !== lastCmdRef.current) {
      clientRef.current.publish(MQTT_CONTROL_TOPIC, cmd);
      lastCmdRef.current = cmd;
      setLastCommand(cmd);
    }
  }, []);

  const forceCommand = useCallback((cmd) => {
    // Force-publish even if same as last (for mission use)
    if (!clientRef.current) return;
    clientRef.current.publish(MQTT_CONTROL_TOPIC, cmd);
    lastCmdRef.current = cmd;
    setLastCommand(cmd);
  }, []);

  const changeSpeed = useCallback((newSpeed) => {
    const clamped = Math.max(0, Math.min(255, newSpeed));
    setCurrentSpeed(clamped);
    clientRef.current?.publish(MQTT_CONTROL_TOPIC, `SPEED:${clamped}`);
  }, []);

  const toggleBypass = useCallback(() => {
    setBypass(prev => {
      const next = !prev;
      clientRef.current?.publish(MQTT_CONTROL_TOPIC, next ? "BYPASS:ON" : "BYPASS:OFF");
      return next;
    });
  }, []);

  // ── Direction handlers ───────────────────────────────────────────────────────
  const onDirectionDown = useCallback((cmd) => {
    setActiveBtn(cmd); sendCommand(cmd);
  }, [sendCommand]);

  const onDirectionUp = useCallback(() => {
    setActiveBtn(null); sendCommand("STOP");
  }, [sendCommand]);

  const onTurnClick = useCallback((cmd) => {
    clientRef.current?.publish(MQTT_CONTROL_TOPIC, cmd);
    lastCmdRef.current = cmd; setLastCommand(cmd);
  }, []);

  // ── Keyboard (same as Python on_press/on_release) ────────────────────────────
  useEffect(() => {
    const onKeyDown = (e) => {
      if (pressedKeys.current.has(e.key)) return;
      pressedKeys.current.add(e.key);
      switch (e.key) {
        case 'z': case 'Z': case 'w': case 'W': case 'ArrowUp':
          e.preventDefault(); onDirectionDown("BACKWARD"); setActiveBtn("BACKWARD"); break; // physically moves FWD
        case 's': case 'S': case 'ArrowDown':
          e.preventDefault(); onDirectionDown("FORWARD");  setActiveBtn("FORWARD");  break; // physically moves BACK
        case 'q': case 'Q': case 'a': case 'A': case 'ArrowLeft':
          e.preventDefault(); onDirectionDown("LEFT");     setActiveBtn("LEFT");     break;
        case 'd': case 'D': case 'ArrowRight':
          e.preventDefault(); onDirectionDown("RIGHT");    setActiveBtn("RIGHT");    break;
        case 'i': case 'I': onTurnClick("TURN_90_L"); break;
        case 'o': case 'O': onTurnClick("TURN_90_R"); break;
        case 'u': case 'U': onTurnClick("TURN_180");  break;
        case 'b': case 'B': toggleBypass(); break;
        case '1': changeSpeed(50);  break;
        case '2': changeSpeed(100); break;
        case '3': changeSpeed(150); break;
        case '4': changeSpeed(200); break;
        case '5': changeSpeed(255); break;
        case '+': changeSpeed(currentSpeed + 25); break;
        case '-': changeSpeed(currentSpeed - 25); break;
      }
    };
    const onKeyUp = (e) => {
      pressedKeys.current.delete(e.key);
      const isDir = ['z','Z','w','W','ArrowUp','s','S','ArrowDown',
                     'q','Q','a','A','ArrowLeft','d','D','ArrowRight'].includes(e.key);
      if (isDir) { setActiveBtn(null); sendCommand("STOP"); }
    };
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup',   onKeyUp);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup',   onKeyUp);
    };
  }, [onDirectionDown, onTurnClick, toggleBypass, changeSpeed, sendCommand, currentSpeed]);

  // ── AUTO MISSION ─────────────────────────────────────────────────────────────
  // Sequence:
  //   Phase 1 : BACKWARD (= physically forward) for timeToA seconds  → Zone A
  //   Pause 0.6s
  //   Phase 2 : RIGHT until gyro delta ≥ 20° (live MQTT angle polling)  → done
  //   Pause 0.6s
  //   Phase 3 : BACKWARD for timeToB seconds                         → Zone B
  //   STOP → Mission complete
  // ─────────────────────────────────────────────────────────────────────────────
  const runMission = useCallback(async () => {
    if (!clientRef.current || mqttStatus !== "CONNECTED") {
      alert("❌ MQTT non connecté ! Attendez la connexion.");
      return;
    }
    missionAbortRef.current = false;

    const sleep = (ms) => new Promise(res => setTimeout(res, ms));
    const setPhase = (p) => { missionPhaseRef.current = p; setMissionPhase(p); };
    const pub     = (cmd) => {
      clientRef.current?.publish(MQTT_CONTROL_TOPIC, cmd);
      lastCmdRef.current = cmd;
      setLastCommand(cmd);
    };
    const STEP = 100; // poll interval ms

    setPhase(PHASE.RUNNING);
    // Reuse timeToA for Forward time, timeToB for Turn time
    const msFwd = Math.round(timeToA * 1000);
    const msTurn = Math.round(timeToB * 1000);

    try {
      for (let side = 1; side <= 4; side++) {
        if (missionAbortRef.current) break;
        
        // 1. التقدم للأمام (يرسل BACKWARD في المنطق المعكوس)
        pub(MISSION_FWD_CMD);
        for (let elapsed = 0; elapsed < msFwd; elapsed += STEP) {
          if (missionAbortRef.current) break;
          setCountdownSec(parseFloat(((msFwd - elapsed) / 1000).toFixed(1)));
          await sleep(STEP);
        }
        if (missionAbortRef.current) break;

        // 2. الدوران لليمين بـ 90 درجة 
        pub(MISSION_TURN_CMD);
        for (let elapsed = 0; elapsed < msTurn; elapsed += STEP) {
          if (missionAbortRef.current) break;
          setCountdownSec(parseFloat(((msTurn - elapsed) / 1000).toFixed(1)));
          await sleep(STEP);
        }
      }

      // نهاية المسار التلقائي بنجاح
      if (!missionAbortRef.current) {
        pub("STOP");
        setPhase(PHASE.DONE);
      } else {
        setPhase(PHASE.ABORTED);
      }
    } catch (e) {
      console.error(e);
      setPhase(PHASE.ABORTED);
    } finally {
      setCountdownSec(0);
    }
  }, [mqttStatus, timeToA, timeToB]);

  const abortMission = useCallback(() => {
    missionAbortRef.current = true;
    clientRef.current?.publish(MQTT_CONTROL_TOPIC, "STOP");
    lastCmdRef.current = "STOP";
    setLastCommand("STOP");
    missionPhaseRef.current = PHASE.ABORTED;
    setMissionPhase(PHASE.ABORTED);
    setCountdownSec(0);
  }, []);

  // ── UI helpers ───────────────────────────────────────────────────────────────
  const getDistanceInfo = () => {
    if (bypassObstacle)         return { icon: '🛡️', color: '#f59e0b', label: 'BYPASSED' };
    if (currentDistance >= 999) return { icon: '⚠️', color: '#9ca3af', label: 'Hors de portée' };
    if (currentDistance <= 20)  return { icon: '🚨', color: '#ef4444', label: `${currentDistance.toFixed(1)} cm — TROP PROCHE!` };
    if (currentDistance <= 50)  return { icon: '🟡', color: '#f59e0b', label: `${currentDistance.toFixed(1)} cm — Proche` };
    return                             { icon: '🟢', color: '#10b981', label: `${currentDistance.toFixed(1)} cm — Libre` };
  };
  const distInfo  = getDistanceInfo();
  const mqttColor = mqttStatus === "CONNECTED" ? '#10b981' : mqttStatus === "CONNECTING..." ? '#f59e0b' : '#ef4444';
  const isMissionRunning = missionPhase === PHASE.RUNNING;
  const phaseInfo = PHASE_LABELS[missionPhase] || PHASE_LABELS.idle;

  // Remove unused forceCommand (now inlined in runMission)
  // eslint-disable-next-line no-unused-vars

  const dirBtnStyle = (cmd) => ({
    width: '72px', height: '72px', borderRadius: '12px', fontSize: '22px',
    fontWeight: '700', cursor: isMissionRunning ? 'not-allowed' : 'pointer',
    border: `2px solid ${activeBtn === cmd ? 'rgba(255,120,80,0.8)' : 'rgba(255,255,255,0.12)'}`,
    background: activeBtn === cmd ? 'rgba(255,120,80,0.25)' : 'rgba(255,255,255,0.05)',
    color: activeBtn === cmd ? '#ff7850' : '#e2e8f0',
    boxShadow: activeBtn === cmd ? '0 0 18px rgba(255,120,80,0.4)' : 'none',
    transition: 'all 0.1s ease', userSelect: 'none',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexDirection: 'column', gap: '2px',
    opacity: isMissionRunning ? 0.4 : 1,
  });

  return (
    <div style={{
      background: 'rgba(10,15,29,0.95)', border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: '16px', padding: '20px', backdropFilter: 'blur(12px)',
      fontFamily: 'Space Grotesk, sans-serif',
    }}>

      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '13px', fontWeight: '800', letterSpacing: '0.1em', color: '#ff7850' }}>
            🎮 ROBOT CONTROLLER
          </div>
          <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '2px' }}>
            Direct MQTT → ESP32 (HiveMQ Cloud)
          </div>
        </div>
        <div style={{
          fontSize: '11px', fontWeight: '700', padding: '4px 10px', borderRadius: '20px',
          border: `1px solid ${mqttColor}`, color: mqttColor, background: `${mqttColor}15`,
        }}>
          ● {mqttStatus}
        </div>
      </div>

      {/* ── Live Sensor Data ── */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '14px' }}>
        <div style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ fontSize: '9px', color: '#6b7280', fontWeight: '700', letterSpacing: '0.08em', marginBottom: '4px' }}>DISTANCE (HC-SR04)</div>
          <div style={{ fontSize: '13px', fontWeight: '700', color: distInfo.color }}>{distInfo.icon} {distInfo.label}</div>
        </div>
        <div style={{ flex: 1, padding: '10px', borderRadius: '10px', background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ fontSize: '9px', color: '#6b7280', fontWeight: '700', letterSpacing: '0.08em', marginBottom: '4px' }}>YAW ANGLE (MPU6050)</div>
          <div style={{ fontSize: '15px', fontWeight: '700', color: '#a78bfa', display: 'flex', alignItems: 'center', gap: '6px' }}>
            📐 {currentAngle >= 0 ? '+' : ''}{currentAngle.toFixed(1)}°
            <div style={{ width: '22px', height: '22px', borderRadius: '50%', border: '1px solid rgba(167,139,250,0.3)', position: 'relative' }}>
              <div style={{
                position: 'absolute', top: '50%', left: '50%', width: '2px', height: '9px',
                background: '#a78bfa', borderRadius: '2px', transformOrigin: 'bottom center',
                transform: `translate(-50%, -100%) rotate(${currentAngle}deg)`, transition: 'transform 0.2s ease',
              }} />
            </div>
          </div>
        </div>
      </div>

      {/* ── CMD Badge ── */}
      <div style={{ textAlign: 'center', marginBottom: '12px' }}>
        <span style={{ fontSize: '11px', padding: '4px 14px', borderRadius: '20px', background: 'rgba(255,120,80,0.1)', border: '1px solid rgba(255,120,80,0.3)', color: '#ff7850', fontWeight: '700' }}>
          CMD: {lastCommand}
        </span>
      </div>

      {/* ════════════════════════════════════════════════════════════
          AUTO MISSION PANEL
          ════════════════════════════════════════════════════════════ */}
      <div style={{
        marginBottom: '16px', padding: '14px', borderRadius: '12px',
        background: isMissionRunning ? 'rgba(56,189,248,0.07)' : 'rgba(255,255,255,0.03)',
        border: `1px solid ${isMissionRunning ? 'rgba(56,189,248,0.35)' : 'rgba(255,255,255,0.08)'}`,
        transition: 'all 0.3s ease',
      }}>
        <div style={{ fontSize: '11px', fontWeight: '800', letterSpacing: '0.08em', color: '#38bdf8', marginBottom: '10px' }}>
          🤖 AUTO MISSION: مسار المربع التلقائي (Square Runner)
        </div>

        {/* Mission status bar */}
        <div style={{
          padding: '8px 12px', borderRadius: '8px', marginBottom: '12px',
          background: `${phaseInfo.color}15`, border: `1px solid ${phaseInfo.color}40`,
          display: 'flex', alignItems: 'center', gap: '8px',
        }}>
          <span style={{ fontSize: '16px' }}>{phaseInfo.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '11px', fontWeight: '700', color: phaseInfo.color, display: 'flex', justifyContent: 'space-between' }}>
              <span>{phaseInfo.text}</span>
              {/* countdown timer shown during timed phases */}
              {(missionPhase === PHASE.RUNNING) && countdownSec > 0 && (
                <span style={{ fontFamily: 'monospace', fontSize: '12px' }}>⏱ {countdownSec}s</span>
              )}
            </div>

            {/* time-based progress bar */}
            {(missionPhase === PHASE.RUNNING) && (
              <div style={{ marginTop: '5px' }}>
                <div style={{ height: '4px', borderRadius: '2px', background: `${phaseInfo.color}25` }}>
                  <div style={{
                    height: '100%', borderRadius: '2px', background: phaseInfo.color,
                    width: lastCommand === MISSION_FWD_CMD
                      ? `${Math.max(0, 100 - (countdownSec / timeToA) * 100)}%`
                      : `${Math.max(0, 100 - (countdownSec / timeToB) * 100)}%`,
                    transition: 'width 0.1s linear',
                  }} />
                </div>
              </div>
            )}
          </div>
        </div>


        {/* Time configuration */}
        <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '9px', color: '#6b7280', fontWeight: '700', marginBottom: '4px' }}>⏱️ مدة تقدم الأمام (ثانية)</div>
            <input
              type="number" min="0.5" max="30" step="0.5" value={timeToA}
              onChange={e => setTimeToA(parseFloat(e.target.value) || 3.0)}
              disabled={isMissionRunning}
              style={{
                width: '100%', padding: '6px 8px', borderRadius: '7px', fontSize: '13px',
                fontFamily: 'monospace', fontWeight: '700', textAlign: 'center',
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
                color: '#f1f5f9', outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', paddingTop: '16px', color: '#6b7280', fontSize: '12px' }}>
            🔄
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '9px', color: '#6b7280', fontWeight: '700', marginBottom: '4px' }}>⏱️ مدة الدوران 90° (ثانية)</div>
            <input
              type="number" min="0.1" max="10" step="0.1" value={timeToB}
              onChange={e => setTimeToB(parseFloat(e.target.value) || 0.5)}
              disabled={isMissionRunning}
              style={{
                width: '100%', padding: '6px 8px', borderRadius: '7px', fontSize: '13px',
                fontFamily: 'monospace', fontWeight: '700', textAlign: 'center',
                background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
                color: '#f1f5f9', outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
        </div>

        {/* Mission start / abort buttons */}
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={runMission}
            disabled={isMissionRunning || mqttStatus !== "CONNECTED"}
            style={{
              flex: 2, padding: '11px', borderRadius: '10px', fontSize: '13px',
              fontWeight: '800', cursor: isMissionRunning || mqttStatus !== "CONNECTED" ? 'not-allowed' : 'pointer',
              border: '1px solid rgba(56,189,248,0.5)',
              background: isMissionRunning ? 'rgba(56,189,248,0.05)' : 'rgba(56,189,248,0.18)',
              color: isMissionRunning ? '#38bdf880' : '#38bdf8',
              transition: 'all 0.2s ease', fontFamily: 'Space Grotesk, sans-serif',
              boxShadow: !isMissionRunning && mqttStatus === "CONNECTED" ? '0 0 16px rgba(56,189,248,0.2)' : 'none',
            }}
          >
            {isMissionRunning ? '⏳ Mission en cours…' : '▶ START MISSION'}
          </button>
          <button
            onClick={abortMission}
            disabled={!isMissionRunning}
            style={{
              flex: 1, padding: '11px', borderRadius: '10px', fontSize: '12px',
              fontWeight: '800', cursor: !isMissionRunning ? 'not-allowed' : 'pointer',
              border: '1px solid rgba(239,68,68,0.4)',
              background: isMissionRunning ? 'rgba(239,68,68,0.2)' : 'rgba(239,68,68,0.05)',
              color: isMissionRunning ? '#ef4444' : '#ef444440',
              transition: 'all 0.2s ease', fontFamily: 'Space Grotesk, sans-serif',
            }}
          >
            ⏹ ABORT
          </button>
        </div>
      </div>

      {/* ── Directional D-Pad ── */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
        <div>
          <button style={dirBtnStyle("BACKWARD")}
            onMouseDown={() => !isMissionRunning && onDirectionDown("BACKWARD")}
            onMouseUp={onDirectionUp} onMouseLeave={onDirectionUp}
            onTouchStart={(e) => { e.preventDefault(); !isMissionRunning && onDirectionDown("BACKWARD"); }}
            onTouchEnd={onDirectionUp} title="Z / W / ↑ — FORWARD (sends BACKWARD)">
            <span>↑</span><span style={{ fontSize: '9px', opacity: 0.7 }}>FWD</span>
          </button>
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button style={dirBtnStyle("LEFT")}
            onMouseDown={() => !isMissionRunning && onDirectionDown("LEFT")}
            onMouseUp={onDirectionUp} onMouseLeave={onDirectionUp}
            onTouchStart={(e) => { e.preventDefault(); !isMissionRunning && onDirectionDown("LEFT"); }}
            onTouchEnd={onDirectionUp} title="Q / A / ←">
            <span>←</span><span style={{ fontSize: '9px', opacity: 0.7 }}>LEFT</span>
          </button>
          <button onClick={() => !isMissionRunning && sendCommand("STOP")} style={{
            width: '72px', height: '72px', borderRadius: '12px', fontSize: '11px',
            fontWeight: '800', cursor: isMissionRunning ? 'not-allowed' : 'pointer',
            border: '2px solid rgba(239,68,68,0.5)',
            background: lastCommand === 'STOP' ? 'rgba(239,68,68,0.2)' : 'rgba(239,68,68,0.07)',
            color: '#ef4444', opacity: isMissionRunning ? 0.4 : 1,
          }}>⏹<br/>STOP</button>
          <button style={dirBtnStyle("RIGHT")}
            onMouseDown={() => !isMissionRunning && onDirectionDown("RIGHT")}
            onMouseUp={onDirectionUp} onMouseLeave={onDirectionUp}
            onTouchStart={(e) => { e.preventDefault(); !isMissionRunning && onDirectionDown("RIGHT"); }}
            onTouchEnd={onDirectionUp} title="D / →">
            <span>→</span><span style={{ fontSize: '9px', opacity: 0.7 }}>RIGHT</span>
          </button>
        </div>
        <div>
          <button style={dirBtnStyle("FORWARD")}
            onMouseDown={() => !isMissionRunning && onDirectionDown("FORWARD")}
            onMouseUp={onDirectionUp} onMouseLeave={onDirectionUp}
            onTouchStart={(e) => { e.preventDefault(); !isMissionRunning && onDirectionDown("FORWARD"); }}
            onTouchEnd={onDirectionUp} title="S / ↓ — BACKWARD (sends FORWARD)">
            <span>↓</span><span style={{ fontSize: '9px', opacity: 0.7 }}>BACK</span>
          </button>
        </div>
      </div>

      {/* ── Precision Gyro Turns ── */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ fontSize: '10px', color: '#6b7280', fontWeight: '700', letterSpacing: '0.08em', marginBottom: '7px' }}>
          🔄 GYRO PRECISE TURNS — [i] [o] [u]
        </div>
        <div style={{ display: 'flex', gap: '6px' }}>
          {[
            { label: '↺ 90° L', cmd: 'TURN_90_L', key: 'i' },
            { label: '↻↺ 180°', cmd: 'TURN_180',  key: 'u' },
            { label: '↻ 90° R', cmd: 'TURN_90_R', key: 'o' },
          ].map(({ label, cmd, key }) => (
            <button key={cmd} onClick={() => !isMissionRunning && onTurnClick(cmd)}
              style={{
                flex: 1, padding: '10px 4px', borderRadius: '10px', fontSize: '12px',
                fontWeight: '700', cursor: isMissionRunning ? 'not-allowed' : 'pointer',
                border: '1px solid rgba(167,139,250,0.35)',
                background: 'rgba(167,139,250,0.12)', color: '#a78bfa',
                opacity: isMissionRunning ? 0.4 : 1, transition: 'all 0.15s ease',
              }}
              onMouseEnter={e => { if (!isMissionRunning) e.currentTarget.style.background = 'rgba(167,139,250,0.28)'; }}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(167,139,250,0.12)'}
            >
              {label}<div style={{ fontSize: '9px', opacity: 0.6, marginTop: '2px' }}>[{key}]</div>
            </button>
          ))}
        </div>
      </div>

      {/* ── Speed Control ── */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ fontSize: '10px', color: '#6b7280', fontWeight: '700', letterSpacing: '0.08em', marginBottom: '7px', display: 'flex', justifyContent: 'space-between' }}>
          <span>⚡ SPEED — [1]-[5] / [+] [-]</span>
          <span style={{ color: '#ff7850', fontFamily: 'monospace' }}>{currentSpeed}/255</span>
        </div>
        <div style={{ display: 'flex', gap: '4px', marginBottom: '8px' }}>
          {SPEED_PRESETS.map((spd, idx) => (
            <button key={spd} onClick={() => changeSpeed(spd)} style={{
              flex: 1, padding: '7px 0', borderRadius: '8px', fontSize: '11px',
              fontWeight: '700', cursor: 'pointer',
              border: `1px solid ${currentSpeed === spd ? 'rgba(255,120,80,0.6)' : 'rgba(255,255,255,0.1)'}`,
              background: currentSpeed === spd ? 'rgba(255,120,80,0.2)' : 'rgba(255,255,255,0.04)',
              color: currentSpeed === spd ? '#ff7850' : '#9ca3af',
            }}>
              {idx + 1}<div style={{ fontSize: '8px', opacity: 0.7 }}>{spd}</div>
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button onClick={() => changeSpeed(currentSpeed - 25)} style={{ padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: '#e2e8f0', cursor: 'pointer', fontSize: '16px', fontWeight: '700' }}>−</button>
          <input type="range" min="0" max="255" value={currentSpeed} onChange={e => changeSpeed(parseInt(e.target.value))} style={{ flex: 1, accentColor: '#ff7850', cursor: 'pointer' }} />
          <button onClick={() => changeSpeed(currentSpeed + 25)} style={{ padding: '4px 10px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.04)', color: '#e2e8f0', cursor: 'pointer', fontSize: '16px', fontWeight: '700' }}>+</button>
        </div>
      </div>

      {/* ── Bypass Toggle ── */}
      <button onClick={toggleBypass} style={{
        width: '100%', padding: '10px', borderRadius: '10px', fontSize: '12px',
        fontWeight: '700', cursor: 'pointer',
        border: `1px solid ${bypassObstacle ? 'rgba(245,158,11,0.6)' : 'rgba(255,255,255,0.1)'}`,
        background: bypassObstacle ? 'rgba(245,158,11,0.2)' : 'rgba(255,255,255,0.04)',
        color: bypassObstacle ? '#f59e0b' : '#9ca3af', transition: 'all 0.2s ease',
        boxShadow: bypassObstacle ? '0 0 14px rgba(245,158,11,0.2)' : 'none',
      }}>
        🛡️ BYPASS SENSOR [b]: {bypassObstacle ? 'ON — Désactivé' : 'OFF — Actif'}
      </button>

      {/* ── Keyboard hints ── */}
      <div style={{ marginTop: '12px', padding: '8px 10px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', fontSize: '9px', color: '#4b5563', lineHeight: '1.7' }}>
        <div style={{ color: '#6b7280', fontWeight: '700', marginBottom: '3px' }}>⌨️ KEYBOARD:</div>
        <div>↑/Z/W → FWD &nbsp;|&nbsp; ↓/S → BACK &nbsp;|&nbsp; ←/Q/A → LEFT &nbsp;|&nbsp; →/D → RIGHT</div>
        <div>[i] 90°L &nbsp;|&nbsp; [o] 90°R &nbsp;|&nbsp; [u] 180° &nbsp;|&nbsp; [b] bypass &nbsp;|&nbsp; [1-5] vitesse</div>
      </div>
    </div>
  );
}
