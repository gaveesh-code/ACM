from fastapi import APIRouter
from pydantic import BaseModel
from database.db import get_connection, get_sim_time, set_sim_time
from physics.propagator import propagate
from physics.fuel_tracker import apply_burn, is_critical_fuel, DRY_MASS
from physics.conjunction import find_conjunctions, get_critical_conjunctions
from physics.maneuver_calc import is_in_station_keeping_box, calculate_evasion_burn, calculate_recovery_burn
from physics.ground_station import has_line_of_sight
from api.telemetry import get_satellite_cache, get_debris_cache
import datetime
import numpy as np
import logging

logger = logging.getLogger("ACM.simulate")

router = APIRouter()

class SimStepRequest(BaseModel):
    step_seconds: float

@router.post("/simulate/step")
async def simulate_step(payload: SimStepRequest):
    """
    Advance simulation by step_seconds.
    1. Propagate all orbits (RK4 + J2)
    2. AUTO-EVASION: detect conjunctions and schedule burns autonomously
    3. Execute scheduled maneuvers + apply fuel burn (Tsiolkovsky)
    4. Check for collisions and log events
    5. Update station-keeping status
    6. Recovery burns for out-of-slot satellites
    """
    conn = get_connection()
    cursor = conn.cursor()

    step = payload.step_seconds
    current_time_str = get_sim_time()
    current_time = datetime.datetime.fromisoformat(current_time_str.replace("Z", "+00:00"))
    new_time = current_time + datetime.timedelta(seconds=step)
    new_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    logger.info(f"Simulation step: {step}s | {current_time_str} → {new_time_str}")

    # ─── Step 1: Propagate all satellites ─────────────────────────────────────
    cursor.execute("SELECT * FROM satellites")
    satellites = cursor.fetchall()
    logger.info(f"Propagating {len(satellites)} satellites")

    for sat in satellites:
        state = np.array([sat["x"], sat["y"], sat["z"], sat["vx"], sat["vy"], sat["vz"]])
        new_state = propagate(state, step, dt=10.0)

        slot = [sat["slot_x"], sat["slot_y"], sat["slot_z"]]
        in_box, distance = is_in_station_keeping_box(new_state[:3], slot)
        status = sat["status"]

        if not in_box and status == "NOMINAL":
            status = "OUT_OF_SLOT"
            logger.warning(f"Satellite {sat['id']} OUT_OF_SLOT — distance: {distance:.2f} km")
        elif in_box and status == "OUT_OF_SLOT":
            status = "NOMINAL"
            logger.info(f"Satellite {sat['id']} recovered to NOMINAL slot")

        if is_critical_fuel(sat["fuel_kg"]):
            status = "EOL"
            logger.warning(f"Satellite {sat['id']} EOL — fuel critical: {sat['fuel_kg']:.2f} kg")

        cursor.execute("""
            UPDATE satellites SET x=?, y=?, z=?, vx=?, vy=?, vz=?, status=? WHERE id=?
        """, (float(new_state[0]), float(new_state[1]), float(new_state[2]),
              float(new_state[3]), float(new_state[4]), float(new_state[5]),
              status, sat["id"]))

        get_satellite_cache()[sat["id"]] = {
            "id": sat["id"],
            "x": float(new_state[0]), "y": float(new_state[1]), "z": float(new_state[2]),
            "vx": float(new_state[3]), "vy": float(new_state[4]), "vz": float(new_state[5])
        }

    # ─── Step 2: Propagate all debris ─────────────────────────────────────────
    cursor.execute("SELECT * FROM debris")
    debris_list = cursor.fetchall()
    logger.info(f"Propagating {len(debris_list)} debris objects")

    for deb in debris_list:
        state = np.array([deb["x"], deb["y"], deb["z"], deb["vx"], deb["vy"], deb["vz"]])
        new_state = propagate(state, step, dt=10.0)

        cursor.execute("""
            UPDATE debris SET x=?, y=?, z=?, vx=?, vy=?, vz=? WHERE id=?
        """, (float(new_state[0]), float(new_state[1]), float(new_state[2]),
              float(new_state[3]), float(new_state[4]), float(new_state[5]), deb["id"]))

        get_debris_cache()[deb["id"]] = {
            "id": deb["id"],
            "x": float(new_state[0]), "y": float(new_state[1]), "z": float(new_state[2]),
            "vx": float(new_state[3]), "vy": float(new_state[4]), "vz": float(new_state[5])
        }

    # ─── Step 3: AUTO-EVASION — detect and schedule burns autonomously ────────
    sat_cache = get_satellite_cache()
    deb_cache = get_debris_cache()
    auto_burns_scheduled = 0

    if sat_cache and deb_cache:
        sat_list_full = list(sat_cache.values())
        deb_list_full = list(deb_cache.values())

        # Check 1-hour ahead for conjunctions
        cdms = find_conjunctions(sat_list_full, deb_list_full, horizon_seconds=3600)
        critical_cdms = get_critical_conjunctions(cdms)

        if critical_cdms:
            logger.warning(f"AUTO-EVASION: {len(critical_cdms)} critical conjunctions detected!")

        for cdm in critical_cdms:
            sat_id = cdm["satellite_id"]
            deb_id = cdm["debris_id"]

            # Skip if already has a scheduled evasion burn for this pair
            cursor.execute("""
                SELECT id FROM maneuvers
                WHERE satellite_id=? AND status='SCHEDULED'
                AND burn_id LIKE 'AUTO_EVADE%'
            """, (sat_id,))
            existing = cursor.fetchone()
            if existing:
                continue

            sat = sat_cache.get(sat_id)
            deb = deb_cache.get(deb_id)
            if not sat or not deb:
                continue

            sat_state = [sat["x"], sat["y"], sat["z"], sat["vx"], sat["vy"], sat["vz"]]
            deb_state = [deb["x"], deb["y"], deb["z"], deb["vx"], deb["vy"], deb["vz"]]

            # Check LOS — must have ground contact to uplink burn
            has_los, stations = has_line_of_sight(sat_state[:3])

            burn = calculate_evasion_burn(sat_state, deb_state, cdm["tca_seconds"])
            dv = burn["dv_eci_kms"]

            cursor.execute("""
                INSERT INTO maneuvers
                    (satellite_id, burn_id, burn_time, dv_x, dv_y, dv_z, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
            """, (
                sat_id,
                f"AUTO_EVADE_{sat_id}_{deb_id[:8]}",
                new_time_str,
                dv[0], dv[1], dv[2],
                new_time_str
            ))

            auto_burns_scheduled += 1
            los_str = f"via {stations[0]['station_id']}" if has_los and stations else "BLACKOUT-PRE-UPLINKED"
            logger.warning(
                f"AUTO-EVASION burn scheduled: {sat_id} vs {deb_id} | "
                f"miss={cdm['miss_distance_km']:.3f}km | Δv={burn['dv_magnitude_ms']:.3f}m/s | {los_str}"
            )

        # Recovery burns for OUT_OF_SLOT satellites
        cursor.execute("SELECT * FROM satellites WHERE status='OUT_OF_SLOT'")
        oos_sats = cursor.fetchall()
        for sat in oos_sats:
            cursor.execute("""
                SELECT id FROM maneuvers
                WHERE satellite_id=? AND status='SCHEDULED' AND burn_id LIKE 'AUTO_RECOVERY%'
            """, (sat["id"],))
            if cursor.fetchone():
                continue

            sat_state = [sat["x"], sat["y"], sat["z"], sat["vx"], sat["vy"], sat["vz"]]
            slot_state = [sat["slot_x"], sat["slot_y"], sat["slot_z"],
                          sat["vx"], sat["vy"], sat["vz"]]  # same velocity target

            burn = calculate_recovery_burn(sat_state, slot_state)
            dv = burn["dv_eci_kms"]

            # Schedule recovery 1 orbit later (~5400s)
            recovery_time = new_time + datetime.timedelta(seconds=5400)
            recovery_time_str = recovery_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

            cursor.execute("""
                INSERT INTO maneuvers
                    (satellite_id, burn_id, burn_time, dv_x, dv_y, dv_z, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'SCHEDULED', ?)
            """, (
                sat["id"],
                f"AUTO_RECOVERY_{sat['id']}",
                recovery_time_str,
                dv[0], dv[1], dv[2],
                new_time_str
            ))
            logger.info(f"Recovery burn scheduled for {sat['id']} — error: {burn['position_error_km']:.2f} km")

    # ─── Step 4: Execute scheduled maneuvers ──────────────────────────────────
    cursor.execute("""
        SELECT * FROM maneuvers WHERE status='SCHEDULED' AND burn_time <= ?
        ORDER BY burn_time ASC
    """, (new_time_str,))

    pending_burns = cursor.fetchall()
    maneuvers_executed = 0

    for burn in pending_burns:
        sat_id = burn["satellite_id"]
        dv_vec = np.array([burn["dv_x"], burn["dv_y"], burn["dv_z"]])

        cursor.execute("SELECT fuel_kg FROM satellites WHERE id=?", (sat_id,))
        sat_row = cursor.fetchone()
        if not sat_row:
            continue

        fuel_kg = sat_row["fuel_kg"]
        new_fuel, consumed, success, msg = apply_burn(fuel_kg, dv_vec * 1000.0)

        if success:
            cursor.execute("""
                UPDATE satellites SET vx=vx+?, vy=vy+?, vz=vz+?, fuel_kg=? WHERE id=?
            """, (float(dv_vec[0]), float(dv_vec[1]), float(dv_vec[2]), new_fuel, sat_id))

            cursor.execute("UPDATE maneuvers SET status='EXECUTED' WHERE id=?", (burn["id"],))
            maneuvers_executed += 1
            logger.info(f"Burn EXECUTED: {burn['burn_id']} | fuel: {fuel_kg:.2f}→{new_fuel:.2f} kg | consumed: {consumed:.4f} kg")
        else:
            logger.error(f"Burn FAILED: {burn['burn_id']} | reason: {msg}")

    # ─── Step 5: Collision detection ──────────────────────────────────────────
    cursor.execute("SELECT * FROM satellites")
    updated_sats = [dict(s) for s in cursor.fetchall()]
    cursor.execute("SELECT * FROM debris")
    updated_debris = [dict(d) for d in cursor.fetchall()]

    collisions_detected = 0
    if updated_sats and updated_debris:
        cdms = find_conjunctions(updated_sats, updated_debris, horizon_seconds=60)
        for cdm in get_critical_conjunctions(cdms):
            if cdm["miss_distance_km"] < 0.1:
                collisions_detected += 1
                cursor.execute("""
                    INSERT INTO collision_events
                        (satellite_id, debris_id, tca, miss_distance, severity, logged_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (cdm["satellite_id"], cdm["debris_id"], new_time_str,
                      cdm["miss_distance_km"], cdm["severity"], new_time_str))
                logger.critical(
                    f"COLLISION DETECTED: {cdm['satellite_id']} x {cdm['debris_id']} "
                    f"miss={cdm['miss_distance_km']*1000:.1f}m"
                )

    # ─── Step 6: Advance sim time ──────────────────────────────────────────────
    set_sim_time(new_time_str)
    conn.commit()
    conn.close()

    logger.info(
        f"Step complete | maneuvers={maneuvers_executed} | "
        f"auto_burns={auto_burns_scheduled} | collisions={collisions_detected}"
    )

    return {
        "status": "STEP_COMPLETE",
        "new_timestamp": new_time_str,
        "collisions_detected": collisions_detected,
        "maneuvers_executed": maneuvers_executed,
        "auto_evasions_scheduled": auto_burns_scheduled
    }