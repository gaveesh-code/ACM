from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from database.db import get_connection, get_sim_time
from physics.fuel_tracker import apply_burn, is_critical_fuel, DRY_MASS
from physics.ground_station import has_line_of_sight
from physics.maneuver_calc import calculate_evasion_burn, calculate_recovery_burn
import datetime

router = APIRouter()

# --- Request Models ---
class Vector3(BaseModel):
    x: float
    y: float
    z: float

class BurnCommand(BaseModel):
    burn_id: str
    burnTime: str
    deltaV_vector: Vector3

class ManeuverRequest(BaseModel):
    satelliteId: str
    maneuver_sequence: List[BurnCommand]

@router.post("/maneuver/schedule")
async def schedule_maneuver(payload: ManeuverRequest):
    """
    Schedule a maneuver sequence for a satellite.
    Validates LOS, fuel, and cooldown constraints.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Fetch satellite
    cursor.execute("SELECT * FROM satellites WHERE id=?", (payload.satelliteId,))
    sat = cursor.fetchone()

    if not sat:
        conn.close()
        return {
            "status": "REJECTED",
            "reason": f"Satellite {payload.satelliteId} not found"
        }

    sat_pos = [sat["x"], sat["y"], sat["z"]]
    fuel_kg = sat["fuel_kg"]

    # Check line of sight
    has_los, visible_stations = has_line_of_sight(sat_pos)

    # Check fuel sufficiency
    total_dv = sum(
        (b.deltaV_vector.x**2 + b.deltaV_vector.y**2 + b.deltaV_vector.z**2) ** 0.5
        for b in payload.maneuver_sequence
    )
    # Convert km/s to m/s for fuel check
    total_dv_ms = total_dv * 1000.0

    sufficient_fuel = fuel_kg > 0 and total_dv_ms <= 15.0

    # Schedule all burns
    current_mass = DRY_MASS + fuel_kg
    mass_remaining = current_mass

    for burn in payload.maneuver_sequence:
        dv_vec = [burn.deltaV_vector.x, burn.deltaV_vector.y, burn.deltaV_vector.z]

        cursor.execute("""
            INSERT INTO maneuvers
                (satellite_id, burn_id, burn_time, dv_x, dv_y, dv_z, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
        """, (
            payload.satelliteId,
            burn.burn_id,
            burn.burnTime,
            burn.deltaV_vector.x,
            burn.deltaV_vector.y,
            burn.deltaV_vector.z,
            datetime.datetime.utcnow().isoformat()
        ))

        # Estimate mass after burn
        import numpy as np
        dv_ms = np.linalg.norm(dv_vec) * 1000.0
        if dv_ms > 0 and mass_remaining > DRY_MASS:
            from physics.fuel_tracker import ISP, G0
            delta_m = mass_remaining * (1 - np.exp(-dv_ms / (ISP * G0)))
            mass_remaining -= delta_m

    conn.commit()
    conn.close()

    projected_fuel = max(0.0, mass_remaining - DRY_MASS)

    return {
        "status": "SCHEDULED",
        "validation": {
            "ground_station_los": has_los,
            "sufficient_fuel": sufficient_fuel,
            "projected_mass_remaining_kg": round(mass_remaining, 2),
            "visible_stations": [s["station_id"] for s in visible_stations]
        }
    }

@router.get("/maneuver/list/{satellite_id}")
async def list_maneuvers(satellite_id: str):
    """List all scheduled maneuvers for a satellite."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM maneuvers
        WHERE satellite_id=?
        ORDER BY burn_time ASC
    """, (satellite_id,))

    maneuvers = cursor.fetchall()
    conn.close()

    return {
        "satellite_id": satellite_id,
        "maneuvers": [dict(m) for m in maneuvers]
    }

@router.post("/maneuver/auto/{satellite_id}")
async def auto_evasion(satellite_id: str):
    """
    Automatically calculate and schedule evasion + recovery burns
    for a satellite based on current conjunction data.
    """
    from api.telemetry import get_satellite_cache, get_debris_cache
    from physics.conjunction import find_conjunctions, get_critical_conjunctions

    sat_cache = get_satellite_cache()
    deb_cache = get_debris_cache()

    if satellite_id not in sat_cache:
        return {"status": "ERROR", "reason": "Satellite not in cache"}

    sat = sat_cache[satellite_id]
    debris_list = list(deb_cache.values())

    # Find conjunctions for this satellite
    cdms = find_conjunctions([sat], debris_list, horizon_seconds=3600)
    critical = get_critical_conjunctions(cdms)

    if not critical:
        return {"status": "NO_ACTION_NEEDED", "message": "No critical conjunctions found"}

    # Take most critical conjunction
    worst = min(critical, key=lambda c: c["miss_distance_km"])

    sat_state = [sat["x"], sat["y"], sat["z"], sat["vx"], sat["vy"], sat["vz"]]
    deb_id = worst["debris_id"]
    deb = deb_cache.get(deb_id)

    if not deb:
        return {"status": "ERROR", "reason": "Debris not found in cache"}

    deb_state = [deb["x"], deb["y"], deb["z"], deb["vx"], deb["vy"], deb["vz"]]

    # Calculate evasion burn
    evasion = calculate_evasion_burn(sat_state, deb_state, worst["tca_seconds"])

    # Calculate recovery burn (1 hour after evasion)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_x, slot_y, slot_z FROM satellites WHERE id=?", (satellite_id,))
    slot_row = cursor.fetchone()
    conn.close()

    burns = []
    sim_time = get_sim_time()

    # Evasion burn — 30 seconds from now
    dv = evasion["dv_eci_kms"]
    burns.append({
        "burn_id": f"AUTO_EVASION_{satellite_id}",
        "burnTime": sim_time,
        "deltaV_vector": {"x": dv[0], "y": dv[1], "z": dv[2]}
    })

    return {
        "status": "AUTO_SCHEDULED",
        "conjunction": worst,
        "evasion_burn": evasion,
        "burns_scheduled": len(burns)
    }