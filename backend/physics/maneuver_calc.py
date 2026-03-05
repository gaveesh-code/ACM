import numpy as np
from physics.propagator import propagate

# Constants
SAFE_STANDOFF_KM = 0.5      # Target miss distance after evasion (500m)
STATION_KEEPING_BOX = 10.0  # km radius for nominal slot

def get_rtn_frame(r, v):
    """
    Calculate RTN (Radial-Transverse-Normal) unit vectors.
    r: position vector in ECI (km)
    v: velocity vector in ECI (km/s)
    Returns: (R_hat, T_hat, N_hat) unit vectors
    """
    r = np.array(r)
    v = np.array(v)

    R_hat = r / np.linalg.norm(r)                    # Radial: points away from Earth
    N_hat = np.cross(r, v) / np.linalg.norm(np.cross(r, v))  # Normal: perpendicular to orbital plane
    T_hat = np.cross(N_hat, R_hat)                   # Transverse: along velocity direction

    return R_hat, T_hat, N_hat

def rtn_to_eci(dv_rtn, r, v):
    """
    Convert delta-v from RTN frame to ECI frame.
    dv_rtn: [dv_R, dv_T, dv_N] in km/s
    r: satellite position in ECI (km)
    v: satellite velocity in ECI (km/s)
    Returns: delta-v vector in ECI frame (km/s)
    """
    R_hat, T_hat, N_hat = get_rtn_frame(r, v)

    # Rotation matrix: columns are RTN unit vectors
    rotation_matrix = np.column_stack([R_hat, T_hat, N_hat])

    dv_eci = rotation_matrix @ np.array(dv_rtn)
    return dv_eci

def calculate_evasion_burn(sat_state, debris_state, tca_seconds):
    """
    Calculate optimal evasion burn to avoid conjunction.
    Uses prograde/retrograde burn (most fuel efficient).
    
    sat_state: [x,y,z,vx,vy,vz] of satellite
    debris_state: [x,y,z,vx,vy,vz] of debris
    tca_seconds: time to closest approach in seconds
    
    Returns: dict with burn details
    """
    r_sat = np.array(sat_state[:3])
    v_sat = np.array(sat_state[3:])
    r_deb = np.array(debris_state[:3])

    # Calculate relative approach vector
    relative_pos = r_deb - r_sat
    miss_distance = np.linalg.norm(relative_pos)

    # Determine burn direction
    # Retrograde burn slows satellite, letting debris pass ahead
    # This is most fuel efficient for same-plane conjunctions
    v_magnitude = np.linalg.norm(v_sat)

    # Required delta-v to achieve safe standoff
    # Small retrograde burn shifts the satellite's position at TCA
    required_dv_ms = min(
        (SAFE_STANDOFF_KM * 1000) / max(tca_seconds, 1) * 2,
        10.0  # Cap at 10 m/s for efficiency
    )

    # Convert to km/s
    required_dv_kms = required_dv_ms / 1000.0

    # Apply as retrograde burn (negative transverse = slow down)
    dv_rtn = [0.0, -required_dv_kms, 0.0]

    # Convert to ECI
    dv_eci = rtn_to_eci(dv_rtn, r_sat, v_sat)

    return {
        "dv_eci_kms": dv_eci.tolist(),
        "dv_magnitude_ms": required_dv_ms,
        "burn_type": "RETROGRADE",
        "frame": "ECI"
    }

def calculate_recovery_burn(sat_state, slot_state):
    """
    Calculate recovery burn to return satellite to its nominal slot.
    Uses Hohmann-like transfer for fuel efficiency.
    
    sat_state: current satellite state [x,y,z,vx,vy,vz]
    slot_state: nominal slot state [x,y,z,vx,vy,vz]
    
    Returns: dict with recovery burn details
    """
    r_sat = np.array(sat_state[:3])
    v_sat = np.array(sat_state[3:])
    r_slot = np.array(slot_state[:3])
    v_slot = np.array(slot_state[3:])

    # Calculate position error
    position_error = np.linalg.norm(r_slot - r_sat)

    # Calculate velocity correction needed
    dv_correction = v_slot - v_sat
    dv_magnitude_kms = np.linalg.norm(dv_correction)
    dv_magnitude_ms = dv_magnitude_kms * 1000.0

    # Cap recovery burn
    dv_magnitude_ms = min(dv_magnitude_ms, 8.0)
    dv_magnitude_kms = dv_magnitude_ms / 1000.0

    if np.linalg.norm(dv_correction) > 0:
        dv_eci = dv_correction / np.linalg.norm(dv_correction) * dv_magnitude_kms
    else:
        dv_eci = np.zeros(3)

    return {
        "dv_eci_kms": dv_eci.tolist(),
        "dv_magnitude_ms": dv_magnitude_ms,
        "position_error_km": position_error,
        "burn_type": "RECOVERY",
        "frame": "ECI"
    }

def is_in_station_keeping_box(sat_pos, slot_pos):
    """
    Check if satellite is within its 10km station-keeping box.
    sat_pos: [x, y, z] in km
    slot_pos: [x, y, z] in km
    Returns: (bool, distance_km)
    """
    distance = np.linalg.norm(np.array(sat_pos) - np.array(slot_pos))
    return distance <= STATION_KEEPING_BOX, distance

def calculate_graveyard_burn(sat_state):
    """
    Calculate deorbit burn to move satellite to graveyard orbit.
    Applies retrograde burn to lower perigee for atmospheric reentry.
    
    sat_state: current satellite state [x,y,z,vx,vy,vz]
    Returns: burn dict
    """
    r_sat = np.array(sat_state[:3])
    v_sat = np.array(sat_state[3:])

    # Strong retrograde burn to deorbit
    dv_ms = 50.0  # m/s retrograde
    dv_kms = dv_ms / 1000.0

    dv_rtn = [0.0, -dv_kms, 0.0]
    dv_eci = rtn_to_eci(dv_rtn, r_sat, v_sat)

    return {
        "dv_eci_kms": dv_eci.tolist(),
        "dv_magnitude_ms": dv_ms,
        "burn_type": "GRAVEYARD_DEORBIT",
        "frame": "ECI"
    }