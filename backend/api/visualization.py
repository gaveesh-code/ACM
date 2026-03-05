from fastapi import APIRouter
from database.db import get_connection, get_sim_time
from physics.propagator import eci_to_latlon
from physics.conjunction import find_conjunctions, get_critical_conjunctions
from api.telemetry import get_satellite_cache, get_debris_cache

router = APIRouter()

@router.get("/visualization/snapshot")
async def get_snapshot():
    """
    Highly optimized snapshot endpoint for the frontend.
    Returns compressed satellite + debris data for real-time rendering.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch all satellites
    cursor.execute("SELECT * FROM satellites")
    satellites = cursor.fetchall()

    # Fetch all debris
    cursor.execute("SELECT * FROM debris")
    debris_list = cursor.fetchall()

    # Fetch scheduled maneuvers
    cursor.execute("""
        SELECT * FROM maneuvers
        WHERE status='SCHEDULED'
        ORDER BY burn_time ASC
    """)
    maneuvers = cursor.fetchall()

    # Fetch recent collision events
    cursor.execute("""
        SELECT * FROM collision_events
        ORDER BY logged_at DESC
        LIMIT 20
    """)
    events = cursor.fetchall()

    conn.close()

    # --- Build satellite list ---
    sat_output = []
    for sat in satellites:
        lat, lon, alt = eci_to_latlon([sat["x"], sat["y"], sat["z"]])
        sat_output.append({
            "id": sat["id"],
            "lat": round(lat, 4),
            "lon": round(lon, 4),
            "alt_km": round(alt, 2),
            "fuel_kg": round(sat["fuel_kg"], 2),
            "fuel_pct": round((sat["fuel_kg"] / 50.0) * 100, 1),
            "status": sat["status"]
        })

    # --- Build debris cloud (compressed tuple format) ---
    # Format: [ID, lat, lon, alt]
    debris_output = []
    for deb in debris_list:
        lat, lon, alt = eci_to_latlon([deb["x"], deb["y"], deb["z"]])
        debris_output.append([
            deb["id"],
            round(lat, 2),
            round(lon, 2),
            round(alt, 1)
        ])

    # --- Build maneuver timeline ---
    maneuver_output = []
    for m in maneuvers:
        maneuver_output.append({
            "satellite_id": m["satellite_id"],
            "burn_id": m["burn_id"],
            "burn_time": m["burn_time"],
            "dv_x": m["dv_x"],
            "dv_y": m["dv_y"],
            "dv_z": m["dv_z"],
            "status": m["status"]
        })

    # --- Build conjunction warnings ---
    sat_list = list(get_satellite_cache().values())
    deb_list_cache = list(get_debris_cache().values())

    cdm_output = []
    if sat_list and deb_list_cache:
        cdms = find_conjunctions(sat_list, deb_list_cache, horizon_seconds=3600)
        for cdm in cdms:
            cdm_output.append({
                "satellite_id": cdm["satellite_id"],
                "debris_id": cdm["debris_id"],
                "tca_seconds": cdm["tca_seconds"],
                "miss_distance_km": cdm["miss_distance_km"],
                "severity": cdm["severity"]
            })

    # --- Collision events log ---
    events_output = []
    for e in events:
        events_output.append({
            "satellite_id": e["satellite_id"],
            "debris_id": e["debris_id"],
            "miss_distance": e["miss_distance"],
            "severity": e["severity"],
            "logged_at": e["logged_at"]
        })

    return {
        "timestamp": get_sim_time(),
        "satellites": sat_output,
        "debris_cloud": debris_output,
        "maneuvers": maneuver_output,
        "conjunctions": cdm_output,
        "collision_events": events_output,
        "stats": {
            "total_satellites": len(sat_output),
            "total_debris": len(debris_output),
            "active_warnings": len([c for c in cdm_output if c["severity"] == "WARNING"]),
            "critical_conjunctions": len([c for c in cdm_output if c["severity"] == "CRITICAL"]),
            "nominal_satellites": len([s for s in sat_output if s["status"] == "NOMINAL"]),
        }
    }

@router.get("/visualization/satellite/{satellite_id}")
async def get_satellite_detail(satellite_id: str):
    """
    Get detailed info for a single satellite including
    conjunction bullseye data.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM satellites WHERE id=?", (satellite_id,))
    sat = cursor.fetchone()

    if not sat:
        conn.close()
        return {"error": "Satellite not found"}

    cursor.execute("""
        SELECT * FROM maneuvers WHERE satellite_id=?
        ORDER BY burn_time ASC LIMIT 10
    """, (satellite_id,))
    burns = cursor.fetchall()

    conn.close()

    lat, lon, alt = eci_to_latlon([sat["x"], sat["y"], sat["z"]])

    # Get conjunction data for bullseye plot
    from api.telemetry import get_satellite_cache, get_debris_cache
    sat_data = get_satellite_cache().get(satellite_id)
    deb_cache = get_debris_cache()

    bullseye_data = []
    if sat_data and deb_cache:
        cdms = find_conjunctions([sat_data], list(deb_cache.values()), horizon_seconds=7200)
        for cdm in cdms[:20]:  # Top 20 closest
            bullseye_data.append({
                "debris_id": cdm["debris_id"],
                "tca_seconds": cdm["tca_seconds"],
                "miss_distance_km": cdm["miss_distance_km"],
                "severity": cdm["severity"]
            })

    return {
        "id": sat["id"],
        "position": {"lat": lat, "lon": lon, "alt_km": alt},
        "eci": {"x": sat["x"], "y": sat["y"], "z": sat["z"]},
        "velocity": {"vx": sat["vx"], "vy": sat["vy"], "vz": sat["vz"]},
        "fuel_kg": sat["fuel_kg"],
        "fuel_pct": round((sat["fuel_kg"] / 50.0) * 100, 1),
        "status": sat["status"],
        "scheduled_burns": [dict(b) for b in burns],
        "bullseye": bullseye_data
    }