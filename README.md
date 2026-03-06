# 🛰️ Orbital Insight — Autonomous Constellation Manager

> **National Space Hackathon 2026 | IIT Delhi**  
> Real-time autonomous satellite constellation management with orbital debris avoidance for LEO.

---

## 🚀 Quick Start (Docker)

```bash
docker build -t acm .
docker run -p 8000:8000 acm
```

Open `http://localhost:8000` — the full dashboard loads automatically.

---

## 🧠 What It Does

Orbital Insight is an autonomous brain for managing a fleet of 50+ satellites in Low Earth Orbit (LEO). It continuously monitors 10,000+ debris objects, predicts conjunctions 24 hours ahead, and autonomously executes evasion maneuvers — all without human intervention.

| Capability | Implementation |
|---|---|
| **Telemetry Ingestion** | REST API accepting ECI state vectors (J2000) |
| **Conjunction Assessment** | KD-Tree spatial indexing — O(N log N) vs brute-force O(N²) |
| **Collision Avoidance** | RTN-frame retrograde burns, auto-scheduled at <100m threshold |
| **Station-Keeping** | Hohmann-like recovery transfers to 10km orbital slot box |
| **Fuel Budgeting** | Tsiolkovsky rocket equation per burn; EOL graveyard at 5% fuel |
| **Ground Station LOS** | 6-station network with elevation angle + blackout zone detection |

---

## ⚙️ Physics Engine

Built from scratch — no orbital mechanics libraries used.

- **Propagator**: 4th-order Runge-Kutta (RK4) with J2 oblateness perturbation
- **Coordinate Frame**: ECI (Earth-Centered Inertial), J2000 epoch
- **Maneuver Frame**: RTN (Radial-Transverse-Normal) → ECI rotation matrix
- **Constants**: μ = 398600.4418 km³/s², Rₑ = 6378.137 km, J2 = 1.08263×10⁻³

**Spacecraft Parameters (per satellite):**
```
Dry mass:     500 kg
Fuel mass:     50 kg  
Isp:          300 s
Max ΔV/burn:   15 m/s
Cooldown:     600 s
EOL threshold:  5% fuel
```

---

## 🏗️ Architecture

```
ACM/
├── backend/
│   ├── main.py              # FastAPI app entrypoint
│   ├── requirements.txt
│   ├── api/
│   │   ├── telemetry.py     # POST /api/telemetry
│   │   ├── maneuver.py      # POST /api/maneuver/schedule
│   │   ├── simulate.py      # POST /api/simulate/step
│   │   └── visualization.py # GET  /api/visualization/snapshot
│   ├── physics/
│   │   ├── propagator.py    # RK4 + J2 orbital propagation
│   │   ├── conjunction.py   # KD-Tree collision prediction
│   │   ├── maneuver_calc.py # RTN-frame burn planning
│   │   ├── fuel_tracker.py  # Tsiolkovsky fuel model
│   │   └── ground_station.py# LOS window calculation
│   ├── models/              # Pydantic request/response schemas
│   └── database/            # SQLite via Python sqlite3
├── frontend/
│   └── src/App.jsx          # React mission control dashboard
├── data/
│   └── ground_stations.csv  # 6-station network
├── Dockerfile               # ubuntu:22.04, port 8000
└── start.sh                 # Container startup script
```

---

## 📡 API Reference

### `POST /api/telemetry`
Ingest state vectors for satellites and debris objects.
```json
{
  "timestamp": "2026-03-06T00:00:00Z",
  "objects": [
    {
      "id": "SAT-Alpha-01",
      "type": "SATELLITE",
      "r": {"x": 7000.0, "y": 0.0, "z": 0.0},
      "v": {"x": 0.0, "y": 7.5, "z": 0.0}
    }
  ]
}
```

### `POST /api/maneuver/schedule`
Schedule a burn sequence for a satellite.
```json
{
  "satellite_id": "SAT-Alpha-01",
  "burns": [
    {"burn_time": "2026-03-06T01:00:00Z", "delta_v": {"r": -0.01, "t": 0.0, "n": 0.0}}
  ]
}
```

### `POST /api/simulate/step`
Advance simulation by N seconds.
```json
{"step_seconds": 3600}
```

### `GET /api/visualization/snapshot`
Returns compressed fleet state for the dashboard.

---

## 🖥️ Dashboard Features

| Panel | Description |
|---|---|
| **Ground Track Map** | Mercator projection with live satellite positions, ground stations |
| **Conjunction Data Messages** | Real-time CDM warnings with severity (CRITICAL/WARNING/CAUTION) |
| **Propellant Budget** | Per-satellite fuel bars with color-coded thresholds |
| **Maneuver Timeline** | Gantt-style schedule of past and upcoming burns |
| **Constellation Registry** | Live state vectors — lat, lon, altitude, fuel, status |
| **Sim Control** | Step simulation forward by custom time increment |

---

## 🌍 Ground Station Network

| ID | Location | Lat | Lon |
|---|---|---|---|
| GS-001 | ISTRAC, Bengaluru | 13.03°N | 77.52°E |
| GS-002 | Svalbard, Norway | 78.23°N | 15.41°E |
| GS-003 | Goldstone, California | 35.43°N | -116.89°E |
| GS-004 | Punta Arenas, Chile | -53.15°N | -70.92°E |
| GS-005 | IIT Delhi Ground Node | 28.55°N | 77.19°E |
| GS-006 | McMurdo, Antarctica | -77.85°N | 166.67°E |

---

## 🔬 Algorithm Details

### Conjunction Assessment — KD-Tree O(N log N)
Instead of checking every satellite against every debris object (O(N²) = 50 × 10,000 = 500,000 checks), we build a KD-Tree on debris positions and query only objects within a 10km search radius. This reduces computation by ~99%.

### Collision Avoidance — RTN Frame Burns
Evasion burns are computed in the RTN frame (Radial, Transverse, Normal) co-rotating with the satellite. A retrograde transverse burn lowers the orbit, changing the phasing to avoid the conjunction point. The burn magnitude is calculated to achieve >1km miss distance at TCA.

### Station-Keeping — Recovery Burns
After evasion, the satellite drifts from its assigned slot. Recovery is a two-burn Hohmann-like transfer back to the target orbit within the 10km station-keeping box.

---

## 📦 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10, FastAPI, Uvicorn |
| Physics | NumPy, SciPy (KD-Tree) |
| Database | SQLite |
| Frontend | React, Vite, Axios |
| Visualization | HTML5 Canvas (Mercator map) |
| Container | Docker (ubuntu:22.04) |

---

## 👤 Author

**Gaveesh Thakur**  
SRM University  
National Space Hackathon 2026 — IIT Delhi
