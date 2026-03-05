from fastapi import APIRouter
from pydantic import BaseModel
from database.db import get_connection, get_sim_time, set_sim_time
from physics.propagator import propagate
from physics.fuel_tracker import apply_burn, is_critical_fuel, DRY_MASS
from physics.conjunction import find_conjunctions, get_critical_conjunctions
from physics.maneuver_calc import is_in_station_keeping_box
from api.telemetry import get_satellite_cache, get_debris_cache
import datetime
import numpy as np

router = APIRouter()

class SimStepRequest(BaseModel):
    step_seconds: float

@router.post("/simulate/step")
async def simulate_step(payload: SimStepRequest):
    """
    Advance simulation by step_seconds.
    - Propagates all orbits forward
    - Executes scheduled maneuvers
    - Checks for collisions
    - Updates fuel levels
    """
    conn = get_connection()
    cursor = conn.cursor()

    step = payload.step_seconds
    current_time_str = get_sim_time()
    current_time = datetime.datetime.fromisoformat(
        current_time_str.replace("Z", "+00:00")
    )
    new_time = current_time + datetime.timedelta(seconds=step)
    new_time_str = new_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # --- Step 1: Propagate all satellites ---
    cursor.execute("SELECT * FROM satellites")
    satellites = cursor.fetchall()

    for sat in satellites:
        state = np.array([
            sat["x"], sat["y"], sat["z"],
            sat["vx"], sat["vy"], sat["vz"]
        ])
        new_state = propagate(state, step, dt=10.0)

        # Check station keeping
        slot = [sat["slot_x"], sat["slot_y"], sat["slot_z"]]
        in_box, distance = is_in_station_keeping_box(new_state[:3], slot)
        status = sat["status"]

        if not in_box and status == "NOMINAL":
            status = "OUT_OF_SLOT"
        elif in_box and status == "OUT_OF_SLOT":
            status = "NOMINAL"

        # Check critical fuel
        if is_critical_fuel(sat["fuel_kg"]):
            status = "EOL"

        cursor.execute("""
            UPDATE satellites SET
                x=?, y=?, z=?, vx=?, vy=?, vz=?, status=?
            WHERE id=?
        """, (
            float(new_state[0]), float(new_state[1]), float(new_state[2]),
            float(new_state[3]), float(new_state[4]), float(new_state[5]),
            status, sat["id"]
        ))

        # Update cache
        get_satellite_cache()[sat["id"]] = {
            "id": sat["id"],
            "x": float(new_state[0]), "y": float(new_state[1]), "z": float(new_state[2]),
            "vx": float(new_state[3]), "vy": float(new_state[4]), "vz": float(new_state[5])
        }

    # --- Step 2: Propagate all debris ---
    cursor.execute("SELECT * FROM debris")
    debris_list = cursor.fetchall()

    for deb in debris_list:
        state = np.array([
            deb["x"], deb["y"], deb["z"],
            deb["vx"], deb["vy"], deb["vz"]
        ])
        new_state = propagate(state, step, dt=10.0)

        cursor.execute("""
            UPDATE debris SET x=?, y=?, z=?, vx=?, vy=?, vz=?
            WHERE id=?
        """, (
            float(new_state[0]), float(new_state[1]), float(new_state[2]),
            float(new_state[3]), float(new_state[4]), float(new_state[5]),
            deb["id"]
        ))

        get_debris_cache()[deb["id"]] = {
            "id": deb["id"],
            "x": float(new_state[0]), "y": float(new_state[1]), "z": float(new_state[2]),
            "vx": float(new_state[3]), "vy": float(new_state[4]), "vz": float(new_state[5])
        }

    # --- Step 3: Execute scheduled maneuvers ---
    cursor.execute("""
        SELECT * FROM maneuvers
        WHERE status='SCHEDULED' AND burn_time <= ?
        ORDER BY burn_time ASC
    """, (new_time_str,))

    pending_burns = cursor.fetchall()
    maneuvers_executed = 0

    for burn in pending_burns:
        sat_id = burn["satellite_id"]
        dv_vec = np.array([burn["dv_x"], burn["dv_y"], burn["dv_z"]])

        # Get current satellite fuel
        cursor.execute("SELECT fuel_kg FROM satellites WHERE id=?", (sat_id,))
        sat_row = cursor.fetchone()
        if not sat_row:
            continue

        fuel_kg = sat_row["fuel_kg"]
        new_fuel, consumed, success, msg = apply_burn(fuel_kg, dv_vec * 1000.0)

        if success:
            # Apply delta-v to velocity
            cursor.execute("""
                UPDATE satellites SET
                    vx = vx + ?,
                    vy = vy + ?,
                    vz = vz + ?,
                    fuel_kg = ?
                WHERE id=?
            """, (
                float(dv_vec[0]),
                float(dv_vec[1]),
                float(dv_vec[2]),
                new_fuel,
                sat_id
            ))

            cursor.execute("""
                UPDATE maneuvers SET status='EXECUTED' WHERE id=?
            """, (burn["id"],))

            maneuvers_executed += 1

    # --- Step 4: Check for collisions ---
    cursor.execute("SELECT * FROM satellites")
    updated_sats = cursor.fetchall()
    cursor.execute("SELECT * FROM debris")
    updated_debris = cursor.fetchall()

    collisions_detected = 0
    sat_list = [dict(s) for s in updated_sats]
    deb_list = [dict(d) for d in updated_debris]

    if sat_list and deb_list:
        cdms = find_conjunctions(sat_list, deb_list, horizon_seconds=60)
        critical = get_critical_conjunctions(cdms)

        for cdm in critical:
            if cdm["miss_distance_km"] < 0.1:
                collisions_detected += 1
                cursor.execute("""
                    INSERT INTO collision_events
                        (satellite_id, debris_id, tca, miss_distance, severity, logged_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    cdm["satellite_id"],
                    cdm["debris_id"],
                    new_time_str,
                    cdm["miss_distance_km"],
                    cdm["severity"],
                    new_time_str
                ))

    # --- Step 5: Update simulation time ---
    set_sim_time(new_time_str)

    conn.commit()
    conn.close()

    return {
        "status": "STEP_COMPLETE",
        "new_timestamp": new_time_str,
        "collisions_detected": collisions_detected,
        "maneuvers_executed": maneuvers_executed
    }