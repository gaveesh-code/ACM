import numpy as np
from scipy.spatial import KDTree
from physics.propagator import propagate

# Conjunction threshold (100 meters = 0.1 km)
CRITICAL_DISTANCE_KM = 0.1
WARNING_DISTANCE_KM = 5.0
CAUTION_DISTANCE_KM = 10.0

# How far ahead to look (24 hours in seconds)
PREDICTION_HORIZON = 86400

# Time step for conjunction search (60 seconds)
SEARCH_STEP = 60.0

def build_debris_tree(debris_list):
    """
    Build a KD-Tree from current debris positions.
    debris_list: list of dicts with x, y, z fields
    Returns: (KDTree, list of debris ids)
    """
    if not debris_list:
        return None, []

    positions = np.array([[d["x"], d["y"], d["z"]] for d in debris_list])
    ids = [d["id"] for d in debris_list]
    tree = KDTree(positions)
    return tree, ids

def find_conjunctions(satellites, debris_list, horizon_seconds=3600):
    """
    Find all conjunctions between satellites and debris.
    Uses KD-Tree for O(N log N) instead of O(N^2).
    
    satellites: list of satellite dicts
    debris_list: list of debris dicts
    horizon_seconds: how far ahead to predict
    
    Returns: list of CDM (Conjunction Data Message) dicts
    """
    if not debris_list or not satellites:
        return []

    cdms = []
    time_steps = int(horizon_seconds / SEARCH_STEP)

    # Propagate all debris positions forward
    debris_states = {}
    for d in debris_list:
        debris_states[d["id"]] = np.array([
            d["x"], d["y"], d["z"],
            d["vx"], d["vy"], d["vz"]
        ])

    # Propagate all satellite positions forward
    sat_states = {}
    for s in satellites:
        sat_states[s["id"]] = np.array([
            s["x"], s["y"], s["z"],
            s["vx"], s["vy"], s["vz"]
        ])

    # Check at each time step
    for step in range(1, time_steps + 1):
        t = step * SEARCH_STEP

        # Propagate debris to time t
        debris_positions_at_t = []
        debris_ids_at_t = []
        for d_id, d_state in debris_states.items():
            new_state = propagate(d_state, t, dt=30.0)
            debris_positions_at_t.append(new_state[:3])
            debris_ids_at_t.append(d_id)

        if not debris_positions_at_t:
            continue

        # Build KD-Tree at time t
        tree = KDTree(np.array(debris_positions_at_t))

        # Check each satellite against the tree
        for s in satellites:
            s_state = propagate(sat_states[s["id"]], t, dt=30.0)
            sat_pos = s_state[:3]

            # Query tree for nearby debris (within 10 km)
            nearby_indices = tree.query_ball_point(sat_pos, CAUTION_DISTANCE_KM)

            for idx in nearby_indices:
                debris_pos = debris_positions_at_t[idx]
                miss_distance = np.linalg.norm(sat_pos - debris_pos)
                debris_id = debris_ids_at_t[idx]

                # Determine severity
                if miss_distance < CRITICAL_DISTANCE_KM:
                    severity = "CRITICAL"
                elif miss_distance < WARNING_DISTANCE_KM:
                    severity = "WARNING"
                else:
                    severity = "CAUTION"

                cdm = {
                    "satellite_id": s["id"],
                    "debris_id": debris_id,
                    "tca_seconds": t,
                    "miss_distance_km": round(miss_distance, 4),
                    "severity": severity,
                    "sat_pos_at_tca": sat_pos.tolist(),
                    "deb_pos_at_tca": debris_pos.tolist()
                }
                cdms.append(cdm)

    # Deduplicate: keep only closest approach per satellite-debris pair
    best_cdms = {}
    for cdm in cdms:
        key = f"{cdm['satellite_id']}_{cdm['debris_id']}"
        if key not in best_cdms:
            best_cdms[key] = cdm
        else:
            if cdm["miss_distance_km"] < best_cdms[key]["miss_distance_km"]:
                best_cdms[key] = cdm

    return list(best_cdms.values())

def get_critical_conjunctions(cdms):
    """Filter only CRITICAL conjunctions requiring immediate action."""
    return [c for c in cdms if c["severity"] == "CRITICAL"]

def get_warning_conjunctions(cdms):
    """Filter WARNING level conjunctions."""
    return [c for c in cdms if c["severity"] == "WARNING"]