import { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import Globe3D from "./Globe3D";

const API = "http://localhost:8000";

const C = {
  bg:       "#090c10",
  panel:    "#0d1117",
  border:   "#1c2a3a",
  amber:    "#f0a500",
  amberDim: "#7a5200",
  green:    "#00ff87",
  greenDim: "#004d29",
  red:      "#ff3a3a",
  redDim:   "#4d0000",
  yellow:   "#ffe066",
  blue:     "#4fc3f7",
  text:     "#c9d1d9",
  textDim:  "#4a5568",
  grid:     "rgba(255,255,255,0.03)",
};

const statusColor = (s) =>
  s === "NOMINAL" ? C.green : s === "EOL" ? C.red : s === "OUT_OF_SLOT" ? C.yellow : C.amber;

const severityColor = (s) =>
  s === "CRITICAL" ? C.red : s === "WARNING" ? C.yellow : C.green;

function usePoll(fn, ms) {
  useEffect(() => {
    fn();
    const id = setInterval(fn, ms);
    return () => clearInterval(id);
  }, []);
}

function Scanlines() {
  return (
    <div style={{
      position: "fixed", inset: 0, pointerEvents: "none", zIndex: 9999,
      background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.08) 2px,rgba(0,0,0,0.08) 4px)",
    }} />
  );
}

function Panel({ title, accent = C.amber, children, style = {}, tag }) {
  return (
    <div style={{
      background: C.panel, border: `1px solid ${C.border}`,
      borderTop: `2px solid ${accent}`, display: "flex", flexDirection: "column", ...style,
    }}>
      <div style={{
        padding: "6px 14px", display: "flex", alignItems: "center",
        justifyContent: "space-between", borderBottom: `1px solid ${C.border}`,
        background: "rgba(0,0,0,0.3)",
      }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 11, letterSpacing: 2, color: accent, textTransform: "uppercase" }}>
          {title}
        </span>
        {tag && <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.textDim, letterSpacing: 1 }}>{tag}</span>}
      </div>
      <div style={{ flex: 1, overflow: "hidden" }}>{children}</div>
    </div>
  );
}

function Stat({ label, value, color = C.amber, blink }) {
  const [vis, setVis] = useState(true);
  useEffect(() => {
    if (!blink) return;
    const id = setInterval(() => setVis(v => !v), 600);
    return () => clearInterval(id);
  }, [blink]);
  return (
    <div style={{ textAlign: "center", padding: "10px 16px" }}>
      <div style={{
        fontFamily: "'Orbitron', sans-serif", fontSize: 26, fontWeight: 700,
        color: vis ? color : "transparent", textShadow: `0 0 20px ${color}55`, transition: "color 0.1s",
      }}>{value}</div>
      <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.textDim, letterSpacing: 2, marginTop: 2 }}>{label}</div>
    </div>
  );
}

// ─── World Map ────────────────────────────────────────────────────────────────
function WorldMap({ satellites, debris }) {
  const canvasRef = useRef();
  const project = (lat, lon, W, H) => [((lon + 180) / 360) * W, ((90 - lat) / 180) * H];

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    ctx.strokeStyle = C.grid; ctx.lineWidth = 0.5;
    for (let lat = -90; lat <= 90; lat += 30) {
      const [, y] = project(lat, 0, W, H);
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    }
    for (let lon = -180; lon <= 180; lon += 30) {
      const [x] = project(0, lon, W, H);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
    }

    ctx.strokeStyle = "rgba(240,165,0,0.15)"; ctx.lineWidth = 1;
    const [, eqY] = project(0, 0, W, H);
    ctx.beginPath(); ctx.moveTo(0, eqY); ctx.lineTo(W, eqY); ctx.stroke();

    debris?.forEach(d => {
      const [x, y] = project(d[1], d[2], W, H);
      ctx.beginPath(); ctx.arc(x, y, 1, 0, Math.PI * 2);
      ctx.fillStyle = "rgba(255,100,100,0.4)"; ctx.fill();
    });

    satellites?.forEach(sat => {
      const [x, y] = project(sat.lat, sat.lon, W, H);
      const color = statusColor(sat.status);
      const grd = ctx.createRadialGradient(x, y, 0, x, y, 8);
      grd.addColorStop(0, color + "aa"); grd.addColorStop(1, "transparent");
      ctx.beginPath(); ctx.arc(x, y, 8, 0, Math.PI * 2); ctx.fillStyle = grd; ctx.fill();
      ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
      ctx.fillStyle = color; ctx.font = "8px 'Share Tech Mono', monospace";
      ctx.fillText(sat.id.replace("SAT-", ""), x + 5, y - 4);
    });

    const gs = [
      [13.03, 77.52, "BLR"], [78.23, 15.41, "SVL"], [35.43, -116.89, "GLD"],
      [-53.15, -70.92, "PTA"], [28.55, 77.19, "DEL"], [-77.85, 166.67, "MCM"],
    ];
    gs.forEach(([lat, lon, name]) => {
      const [x, y] = project(lat, lon, W, H);
      ctx.strokeStyle = C.blue + "aa"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(x - 5, y); ctx.lineTo(x + 5, y);
      ctx.moveTo(x, y - 5); ctx.lineTo(x, y + 5); ctx.stroke();
      ctx.fillStyle = C.blue; ctx.font = "7px 'Share Tech Mono', monospace";
      ctx.fillText(name, x + 6, y + 3);
    });
  }, [satellites, debris]);

  return <canvas ref={canvasRef} width={900} height={360} style={{ width: "100%", height: "100%", display: "block" }} />;
}

// ─── Bullseye Chart ───────────────────────────────────────────────────────────
function BullseyeChart({ cdms, selectedSat }) {
  const canvasRef = useRef();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const maxR = Math.min(cx, cy) - 20;

    ctx.clearRect(0, 0, W, H);

    const rings = [
      { r: maxR,       color: C.green  + "33", labelColor: C.green,  label: "10km" },
      { r: maxR * 0.5, color: C.yellow + "44", labelColor: C.yellow, label: "5km"  },
      { r: maxR * 0.1, color: C.red    + "66", labelColor: C.red,    label: "100m" },
    ];

    rings.forEach(({ r, color, label, labelColor }) => {
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.strokeStyle = labelColor + "55"; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = color; ctx.fill();
      ctx.fillStyle = labelColor; ctx.font = "8px 'Share Tech Mono', monospace";
      ctx.fillText(label, cx + r - 26, cy - 4);
    });

    ctx.strokeStyle = C.textDim + "66"; ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(cx, cy - maxR); ctx.lineTo(cx, cy + maxR); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(cx - maxR, cy); ctx.lineTo(cx + maxR, cy); ctx.stroke();

    ctx.beginPath(); ctx.arc(cx, cy, 5, 0, Math.PI * 2);
    ctx.fillStyle = C.blue; ctx.fill();
    ctx.fillStyle = C.blue; ctx.font = "9px 'Share Tech Mono', monospace";
    ctx.fillText(selectedSat || "SAT", cx + 7, cy - 7);

    if (cdms && cdms.length > 0) {
      const maxDist = 10;
      cdms.slice(0, 20).forEach((cdm, i) => {
        const dist = Math.min(cdm.miss_distance_km, maxDist);
        const angle = (i / Math.max(cdms.length, 1)) * Math.PI * 2 - Math.PI / 2;
        const r = (dist / maxDist) * maxR;
        const x = cx + r * Math.cos(angle);
        const y = cy + r * Math.sin(angle);
        const color = severityColor(cdm.severity);

        const grd = ctx.createRadialGradient(x, y, 0, x, y, 6);
        grd.addColorStop(0, color + "cc"); grd.addColorStop(1, "transparent");
        ctx.beginPath(); ctx.arc(x, y, 6, 0, Math.PI * 2); ctx.fillStyle = grd; ctx.fill();
        ctx.beginPath(); ctx.arc(x, y, 3, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();

        if (dist < 2) {
          ctx.fillStyle = color; ctx.font = "7px 'Share Tech Mono', monospace";
          ctx.fillText(cdm.debris_id?.slice(-4), x + 4, y - 4);
        }
      });
    }

    if (!cdms || cdms.length === 0) {
      ctx.fillStyle = C.green + "88";
      ctx.font = "10px 'Share Tech Mono', monospace";
      ctx.textAlign = "center";
      ctx.fillText("ALL CLEAR", cx, cy + maxR + 14);
      ctx.textAlign = "left";
    }
  }, [cdms, selectedSat]);

  return <canvas ref={canvasRef} width={280} height={280} style={{ width: "100%", height: "100%", display: "block" }} />;
}

// ─── Fuel Bar ─────────────────────────────────────────────────────────────────
function FuelBar({ id, fuel_pct }) {
  const color = fuel_pct > 50 ? C.green : fuel_pct > 20 ? C.yellow : C.red;
  return (
    <div style={{ marginBottom: 6, padding: "4px 12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.textDim }}>{id}</span>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color }}>{fuel_pct?.toFixed(1)}%</span>
      </div>
      <div style={{ height: 4, background: C.border, borderRadius: 2 }}>
        <div style={{
          height: "100%", width: `${fuel_pct}%`, borderRadius: 2,
          background: color, boxShadow: `0 0 6px ${color}88`, transition: "width 0.5s ease",
        }} />
      </div>
    </div>
  );
}

// ─── CDM Row ──────────────────────────────────────────────────────────────────
function CDMRow({ cdm }) {
  const color = severityColor(cdm.severity);
  const [blink, setBlink] = useState(true);
  useEffect(() => {
    if (cdm.severity !== "CRITICAL") return;
    const id = setInterval(() => setBlink(v => !v), 500);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1fr 1fr 80px 70px 80px",
      padding: "5px 12px", borderBottom: `1px solid ${C.border}`,
      background: cdm.severity === "CRITICAL" ? `${C.redDim}33` : "transparent",
      opacity: cdm.severity === "CRITICAL" ? (blink ? 1 : 0.6) : 1,
    }}>
      {[cdm.satellite_id, cdm.debris_id, `${cdm.tca_seconds?.toFixed(0)}s`, `${cdm.miss_distance_km?.toFixed(3)}km`, cdm.severity]
        .map((val, i) => (
          <span key={i} style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: i === 4 ? color : C.text }}>{val}</span>
        ))}
    </div>
  );
}

// ─── Maneuver Timeline ────────────────────────────────────────────────────────
function ManeuverTimeline({ maneuvers }) {
  if (!maneuvers || maneuvers.length === 0)
    return <div style={{ padding: 16, fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: C.textDim, textAlign: "center" }}>NO SCHEDULED MANEUVERS</div>;
  return (
    <div style={{ padding: "8px 12px", overflowY: "auto", maxHeight: 180 }}>
      {maneuvers.map((m, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "5px 0", borderBottom: `1px solid ${C.border}` }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.amber, boxShadow: `0 0 6px ${C.amber}` }} />
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.amber, minWidth: 80 }}>{m.satellite_id}</span>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.textDim, flex: 1 }}>{m.burn_id}</span>
          <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.blue }}>{m.dv_magnitude?.toFixed(4)} km/s</span>
          <div style={{
            padding: "1px 6px", borderRadius: 2,
            background: m.status === "SCHEDULED" ? C.amberDim : C.greenDim,
            color: m.status === "SCHEDULED" ? C.amber : C.green,
            fontFamily: "'Share Tech Mono', monospace", fontSize: 8,
          }}>{m.status}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Sim Control ──────────────────────────────────────────────────────────────
function SimControl() {
  const [secs, setSecs] = useState(3600);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const step = async () => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/api/simulate/step`, { step_seconds: secs });
      setResult(res.data);
    } catch { setResult({ status: "ERROR" }); }
    setLoading(false);
  };
  return (
    <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 9, color: C.textDim }}>STEP (s)</span>
        <input type="number" value={secs} onChange={e => setSecs(Number(e.target.value))} style={{
          background: C.bg, border: `1px solid ${C.border}`, color: C.amber,
          fontFamily: "'Share Tech Mono', monospace", fontSize: 11,
          padding: "3px 8px", width: 80, outline: "none", borderRadius: 2,
        }} />
        <button onClick={step} disabled={loading} style={{
          background: loading ? C.amberDim : C.amber, color: C.bg, border: "none",
          padding: "5px 16px", cursor: loading ? "not-allowed" : "pointer",
          fontFamily: "'Share Tech Mono', monospace", fontSize: 10, fontWeight: 700,
          letterSpacing: 1, borderRadius: 2,
        }}>{loading ? "RUNNING..." : "▶ EXECUTE"}</button>
      </div>
      {result && (
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
          color: result.status === "STEP_COMPLETE" ? C.green : C.red,
          padding: "4px 8px", background: "rgba(0,0,0,0.3)", borderRadius: 2,
        }}>
          {result.status === "STEP_COMPLETE"
            ? `✓ T+${secs}s | COLLISIONS: ${result.collisions_detected} | BURNS: ${result.maneuvers_executed}`
            : "✗ STEP FAILED"}
        </div>
      )}
    </div>
  );
}

// ─── Telemetry Injector ───────────────────────────────────────────────────────
function TelemetryInjector() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const inject = async () => {
    setLoading(true);
    const now = new Date().toISOString();
    const objects = [];
    for (let i = 1; i <= 5; i++) {
      const angle = (i / 5) * 2 * Math.PI;
      objects.push({ id: `SAT-Alpha-0${i}`, type: "SATELLITE",
        r: { x: 7000 * Math.cos(angle), y: 7000 * Math.sin(angle), z: 500 * Math.sin(angle * 2) },
        v: { x: -7.5 * Math.sin(angle), y: 7.5 * Math.cos(angle), z: 0.1 } });
    }
    for (let i = 1; i <= 20; i++) {
      const angle = Math.random() * 2 * Math.PI;
      const r = 6800 + Math.random() * 400;
      objects.push({ id: `DEB-${99400 + i}`, type: "DEBRIS",
        r: { x: r * Math.cos(angle), y: r * Math.sin(angle), z: (Math.random() - 0.5) * 1000 },
        v: { x: -(7.6 + Math.random() * 0.2) * Math.sin(angle), y: (7.6 + Math.random() * 0.2) * Math.cos(angle), z: (Math.random() - 0.5) * 0.5 } });
    }
    try {
      const res = await axios.post(`${API}/api/telemetry`, { timestamp: now, objects });
      setResult(res.data);
    } catch { setResult({ status: "ERROR" }); }
    setLoading(false);
  };
  return (
    <div style={{ padding: "10px 14px", display: "flex", flexDirection: "column", gap: 8 }}>
      <button onClick={inject} disabled={loading} style={{
        background: "transparent", color: C.green, border: `1px solid ${C.green}`,
        padding: "6px 14px", cursor: loading ? "not-allowed" : "pointer",
        fontFamily: "'Share Tech Mono', monospace", fontSize: 10,
        letterSpacing: 1, borderRadius: 2, opacity: loading ? 0.5 : 1,
      }}>{loading ? "INJECTING..." : "⬆ INJECT TEST TELEMETRY"}</button>
      {result && (
        <div style={{
          fontFamily: "'Share Tech Mono', monospace", fontSize: 9,
          color: result.status === "ACK" ? C.green : C.red,
          padding: "4px 8px", background: "rgba(0,0,0,0.3)", borderRadius: 2,
        }}>
          {result.status === "ACK"
            ? `✓ ACK | OBJECTS: ${result.processed_count} | WARNINGS: ${result.active_cdm_warnings}`
            : "✗ INJECT FAILED"}
        </div>
      )}
    </div>
  );
}

// ─── Clock ────────────────────────────────────────────────────────────────────
function Clock({ simTime }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const id = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(id); }, []);
  return (
    <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
      <div>
        <div style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 13, color: C.amber, letterSpacing: 2 }}>
          {now.toUTCString().split(" ").slice(1, 5).join(" ")}
        </div>
        <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: C.textDim, letterSpacing: 1 }}>SYSTEM UTC</div>
      </div>
      {simTime && (
        <div>
          <div style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 13, color: C.green, letterSpacing: 2 }}>
            {simTime.replace("T", " ").replace(".000Z", "")}
          </div>
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 8, color: C.textDim, letterSpacing: 1 }}>SIM TIME</div>
        </div>
      )}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [snapshot, setSnapshot] = useState(null);
  const [connected, setConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [selectedSat, setSelectedSat] = useState(null);
  const [view, setView] = useState("2d");

  const fetchSnapshot = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/api/visualization/snapshot`);
      setSnapshot(res.data);
      setConnected(true);
      setLastUpdate(new Date());
    } catch { setConnected(false); }
  }, []);

  usePoll(fetchSnapshot, 2000);

  const stats  = snapshot?.fleet_stats;
  const sats   = snapshot?.satellites || [];
  const debris = snapshot?.debris_cloud || [];
  const cdms   = snapshot?.cdm_warnings || [];
  const timeline = snapshot?.maneuver_timeline || [];

  const bullseyeCdms = selectedSat
    ? cdms.filter(c => c.satellite_id === selectedSat)
    : cdms;

  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'Share Tech Mono', monospace",
      backgroundImage: `radial-gradient(ellipse at 20% 20%, rgba(240,165,0,0.03) 0%, transparent 60%),
                        radial-gradient(ellipse at 80% 80%, rgba(0,255,135,0.03) 0%, transparent 60%)`,
    }}>
      <Scanlines />

      {/* Header */}
      <div style={{
        padding: "10px 20px", borderBottom: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(0,0,0,0.5)", backdropFilter: "blur(10px)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            width: 32, height: 32, borderRadius: "50%", border: `2px solid ${C.amber}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: `0 0 16px ${C.amber}55`,
          }}>
            <span style={{ fontSize: 14 }}>⊕</span>
          </div>
          <div>
            <div style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 14, color: C.amber, letterSpacing: 3 }}>ORBITAL INSIGHT</div>
            <div style={{ fontSize: 8, color: C.textDim, letterSpacing: 2 }}>AUTONOMOUS CONSTELLATION MANAGER v1.0</div>
          </div>
          <div style={{
            padding: "2px 10px", borderRadius: 2,
            background: connected ? C.greenDim : C.redDim,
            border: `1px solid ${connected ? C.green : C.red}`,
            color: connected ? C.green : C.red, fontSize: 8, letterSpacing: 2,
          }}>{connected ? "◉ ONLINE" : "○ OFFLINE"}</div>
        </div>

        <Clock simTime={snapshot?.timestamp} />

        <div style={{ display: "flex", gap: 16 }}>
          {[
            ["SATS", stats?.total_satellites ?? "—", C.blue],
            ["NOMINAL", stats?.nominal ?? "—", C.green],
            ["WARNINGS", stats?.active_warnings ?? "—", stats?.active_warnings > 0 ? C.red : C.textDim],
            ["DEBRIS", stats?.total_debris_tracked ?? "—", C.textDim],
          ].map(([label, val, color]) => (
            <div key={label} style={{ textAlign: "center" }}>
              <div style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 16, color, fontWeight: 700 }}>{val}</div>
              <div style={{ fontSize: 7, color: C.textDim, letterSpacing: 1 }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Grid */}
      <div style={{ padding: 12, display: "grid", gap: 10 }}>

        {/* Row 1: Map with 2D/3D toggle */}
        <Panel
          title={view === "2d" ? "Ground Track — Mercator Projection" : "3D Orbital View — ECI Frame"}
          tag={view === "2d" ? "ECI → GEO CONVERTED" : "DRAG TO ROTATE · SCROLL TO ZOOM"}
          style={{ height: 420 }}
          accent={view === "3d" ? C.blue : C.amber}
        >
          <div style={{ display: "flex", gap: 8, padding: "6px 12px", borderBottom: `1px solid ${C.border}` }}>
            {["2d", "3d"].map(v => (
              <button key={v} onClick={() => setView(v)} style={{
                background: view === v ? C.amber : "transparent",
                color: view === v ? C.bg : C.textDim,
                border: `1px solid ${view === v ? C.amber : C.border}`,
                padding: "3px 14px", fontSize: 9, cursor: "pointer",
                fontFamily: "'Share Tech Mono', monospace",
                letterSpacing: 2, borderRadius: 2,
              }}>{v === "2d" ? "2D MAP" : "3D GLOBE"}</button>
            ))}
          </div>
          {view === "2d"
            ? <WorldMap satellites={sats} debris={debris} />
            : <Globe3D satellites={sats} debris={debris} />
          }
        </Panel>

        {/* Row 2: Stats + CDMs + Bullseye */}
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr 320px", gap: 10 }}>

          {/* Fleet Stats */}
          <Panel title="Fleet Status" accent={C.green}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", borderBottom: `1px solid ${C.border}` }}>
              <Stat label="TOTAL SATS"  value={stats?.total_satellites ?? "—"} color={C.blue} />
              <Stat label="NOMINAL"     value={stats?.nominal ?? "—"} color={C.green} />
              <Stat label="OUT OF SLOT" value={stats?.out_of_slot ?? "—"} color={C.yellow} />
              <Stat label="EOL"         value={stats?.eol ?? "—"} color={C.red} />
            </div>
            <div style={{ padding: "8px 12px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 9, color: C.textDim }}>FLEET FUEL RESERVE</span>
                <span style={{ fontSize: 9, color: C.amber }}>{stats?.total_fuel_kg?.toFixed(1) ?? "—"} kg</span>
              </div>
              <div style={{ height: 6, background: C.border, borderRadius: 3 }}>
                <div style={{
                  height: "100%", borderRadius: 3,
                  width: `${Math.min(100, (stats?.total_fuel_kg ?? 0) / (50 * (stats?.total_satellites || 1)) * 100)}%`,
                  background: `linear-gradient(90deg, ${C.green}, ${C.amber})`,
                  boxShadow: `0 0 8px ${C.amber}66`,
                }} />
              </div>
            </div>
            <TelemetryInjector />
            <SimControl />
            <div style={{ padding: "0 14px 8px" }}>
              <div style={{ fontSize: 8, color: C.textDim, letterSpacing: 1 }}>LAST REFRESH</div>
              <div style={{ fontSize: 9, color: C.blue, marginTop: 2 }}>{lastUpdate ? lastUpdate.toTimeString().slice(0, 8) : "—"}</div>
            </div>
          </Panel>

          {/* CDM Warnings */}
          <Panel title="Conjunction Data Messages" accent={cdms.length > 0 ? C.red : C.amber} tag={`${cdms.length} ACTIVE`}>
            <div style={{
              display: "grid", gridTemplateColumns: "1fr 1fr 80px 70px 80px",
              padding: "4px 12px", borderBottom: `1px solid ${C.border}`,
              background: "rgba(0,0,0,0.3)",
            }}>
              {["SATELLITE", "DEBRIS", "TCA", "MISS DIST", "SEVERITY"].map(h => (
                <span key={h} style={{ fontSize: 8, color: C.textDim, letterSpacing: 1 }}>{h}</span>
              ))}
            </div>
            <div style={{ overflowY: "auto", maxHeight: 260 }}>
              {cdms.length === 0
                ? <div style={{ padding: 16, fontSize: 9, color: C.textDim, textAlign: "center" }}>ALL CLEAR — NO CONJUNCTIONS DETECTED</div>
                : cdms.map((c, i) => (
                  <div key={i} onClick={() => setSelectedSat(c.satellite_id)} style={{ cursor: "pointer" }}>
                    <CDMRow cdm={c} />
                  </div>
                ))
              }
            </div>
          </Panel>

          {/* Bullseye Chart */}
          <Panel title="Conjunction Bullseye" accent={C.red} tag={selectedSat || "SELECT SAT"}>
            <div style={{ padding: "6px 12px 2px", display: "flex", gap: 6, flexWrap: "wrap" }}>
              {sats.map(s => (
                <button key={s.id} onClick={() => setSelectedSat(s.id === selectedSat ? null : s.id)} style={{
                  background: selectedSat === s.id ? C.amber : "transparent",
                  color: selectedSat === s.id ? C.bg : C.textDim,
                  border: `1px solid ${selectedSat === s.id ? C.amber : C.border}`,
                  padding: "2px 6px", fontSize: 7, cursor: "pointer", borderRadius: 2,
                  fontFamily: "'Share Tech Mono', monospace", letterSpacing: 1,
                }}>{s.id.replace("SAT-", "")}</button>
              ))}
            </div>
            <div style={{ padding: "4px 12px" }}>
              <BullseyeChart cdms={bullseyeCdms} selectedSat={selectedSat} />
            </div>
            <div style={{ padding: "0 12px 8px", display: "flex", gap: 12 }}>
              {[["■", C.red, "CRITICAL"], ["■", C.yellow, "WARNING"], ["■", C.green, "CAUTION"]].map(([sym, col, label]) => (
                <div key={label} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ color: col, fontSize: 10 }}>{sym}</span>
                  <span style={{ fontSize: 7, color: C.textDim, letterSpacing: 1 }}>{label}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Row 3: Fuel + Timeline */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <Panel title="Propellant Budget — Fleet Overview" accent={C.yellow}>
            <div style={{ overflowY: "auto", maxHeight: 200, paddingTop: 8 }}>
              {sats.length === 0
                ? <div style={{ padding: 16, fontSize: 9, color: C.textDim, textAlign: "center" }}>NO SATELLITES IN REGISTRY</div>
                : sats.map(s => <FuelBar key={s.id} {...s} />)}
            </div>
          </Panel>
          <Panel title="Maneuver Timeline — Gantt Schedule" accent={C.amber}>
            <div style={{
              display: "grid", gridTemplateColumns: "80px 1fr 80px 70px 80px",
              padding: "4px 12px", borderBottom: `1px solid ${C.border}`, background: "rgba(0,0,0,0.3)",
            }}>
              {["SAT ID", "BURN ID", "BURN TIME", "Δv (km/s)", "STATUS"].map(h => (
                <span key={h} style={{ fontSize: 8, color: C.textDim, letterSpacing: 1 }}>{h}</span>
              ))}
            </div>
            <ManeuverTimeline maneuvers={timeline} />
          </Panel>
        </div>

        {/* Row 4: Constellation Registry */}
        <Panel title="Constellation Registry — Live State Vectors" tag="J2 PROPAGATED · RK4">
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 9 }}>
              <thead>
                <tr style={{ background: "rgba(0,0,0,0.3)" }}>
                  {["SAT ID", "LAT", "LON", "ALT (km)", "FUEL (kg)", "FUEL %", "STATUS"].map(h => (
                    <th key={h} style={{ padding: "6px 12px", textAlign: "left", color: C.textDim, letterSpacing: 1, fontWeight: "normal", borderBottom: `1px solid ${C.border}` }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sats.length === 0
                  ? <tr><td colSpan={7} style={{ padding: 16, textAlign: "center", color: C.textDim }}>AWAITING TELEMETRY — INJECT DATA TO POPULATE</td></tr>
                  : sats.map(s => (
                    <tr key={s.id}
                      onClick={() => setSelectedSat(s.id === selectedSat ? null : s.id)}
                      style={{ borderBottom: `1px solid ${C.border}`, cursor: "pointer", background: selectedSat === s.id ? "rgba(240,165,0,0.07)" : "transparent" }}
                      onMouseEnter={e => e.currentTarget.style.background = "rgba(240,165,0,0.05)"}
                      onMouseLeave={e => e.currentTarget.style.background = selectedSat === s.id ? "rgba(240,165,0,0.07)" : "transparent"}>
                      {[s.id, s.lat?.toFixed(3) + "°", s.lon?.toFixed(3) + "°", s.alt_km?.toFixed(1), s.fuel_kg?.toFixed(2), s.fuel_pct?.toFixed(1) + "%"].map((val, i) => (
                        <td key={i} style={{ padding: "5px 12px", color: C.text, fontFamily: "'Share Tech Mono', monospace" }}>{val}</td>
                      ))}
                      <td style={{ padding: "5px 12px" }}>
                        <span style={{
                          padding: "2px 8px", borderRadius: 2, fontSize: 8,
                          color: statusColor(s.status),
                          background: statusColor(s.status) + "22",
                          border: `1px solid ${statusColor(s.status)}55`,
                        }}>{s.status}</span>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* Footer */}
        <div style={{ padding: "8px 0", display: "flex", justifyContent: "space-between", borderTop: `1px solid ${C.border}` }}>
          <span style={{ fontSize: 8, color: C.textDim, letterSpacing: 1 }}>ACM ORBITAL INSIGHT · NATIONAL SPACE HACKATHON 2026 · IIT DELHI</span>
          <span style={{ fontSize: 8, color: C.textDim, letterSpacing: 1 }}>PHYSICS: RK4+J2 · COLLISION: KD-TREE O(N LOG N) · FRAME: ECI J2000</span>
        </div>
      </div>
    </div>
  );
}