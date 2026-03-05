import numpy as np

# Physical constants
MU = 398600.4418        # Earth's gravitational parameter (km^3/s^2)
RE = 6378.137           # Earth's radius (km)
J2 = 1.08263e-3         # J2 perturbation coefficient

def j2_acceleration(r):
    """
    Calculate J2 perturbation acceleration vector.
    r: position vector [x, y, z] in km
    Returns acceleration vector in km/s^2
    """
    x, y, z = r
    r_norm = np.linalg.norm(r)
    factor = (3/2) * J2 * MU * RE**2 / r_norm**5

    ax = factor * x * (5*z**2/r_norm**2 - 1)
    ay = factor * y * (5*z**2/r_norm**2 - 1)
    az = factor * z * (5*z**2/r_norm**2 - 3)

    return np.array([ax, ay, az])

def equations_of_motion(state):
    """
    Full equations of motion with J2 perturbation.
    state: [x, y, z, vx, vy, vz]
    Returns: [vx, vy, vz, ax, ay, az]
    """
    r = state[:3]
    v = state[3:]
    r_norm = np.linalg.norm(r)

    # Two-body gravity
    a_gravity = -MU / r_norm**3 * r

    # J2 perturbation
    a_j2 = j2_acceleration(r)

    # Total acceleration
    a_total = a_gravity + a_j2

    return np.concatenate([v, a_total])

def rk4_step(state, dt):
    """
    Runge-Kutta 4th Order integration step.
    state: [x, y, z, vx, vy, vz]
    dt: time step in seconds
    Returns: new state after dt seconds
    """
    k1 = equations_of_motion(state)
    k2 = equations_of_motion(state + 0.5 * dt * k1)
    k3 = equations_of_motion(state + 0.5 * dt * k2)
    k4 = equations_of_motion(state + dt * k3)

    new_state = state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
    return new_state

def propagate(state, total_seconds, dt=10.0):
    """
    Propagate orbit forward by total_seconds using RK4.
    state: [x, y, z, vx, vy, vz]
    total_seconds: how far to propagate
    dt: integration step size in seconds (default 10s)
    Returns: new state vector
    """
    state = np.array(state, dtype=float)
    elapsed = 0.0

    while elapsed < total_seconds:
        step = min(dt, total_seconds - elapsed)
        state = rk4_step(state, step)
        elapsed += step

    return state

def propagate_with_history(state, total_seconds, dt=30.0):
    """
    Propagate and return full trajectory history.
    Useful for ground track visualization.
    Returns: list of state vectors
    """
    state = np.array(state, dtype=float)
    history = [state.copy()]
    elapsed = 0.0

    while elapsed < total_seconds:
        step = min(dt, total_seconds - elapsed)
        state = rk4_step(state, step)
        history.append(state.copy())
        elapsed += step

    return history

def eci_to_latlon(r):
    """
    Convert ECI position vector to latitude/longitude.
    r: [x, y, z] in km
    Returns: (latitude_deg, longitude_deg, altitude_km)
    """
    x, y, z = r
    r_norm = np.linalg.norm(r)

    lat = np.degrees(np.arcsin(z / r_norm))
    lon = np.degrees(np.arctan2(y, x))
    alt = r_norm - RE

    return lat, lon, alt