import numpy as np

# Earth radius in km
RE = 6378.137

# Ground stations from the problem statement
GROUND_STATIONS = [
    {"id": "GS-001", "name": "ISTRAC_Bengaluru",      "lat": 13.0333,  "lon": 77.5167,  "alt_m": 820,  "min_elev_deg": 5.0},
    {"id": "GS-002", "name": "Svalbard_Sat_Station",  "lat": 78.2297,  "lon": 15.4077,  "alt_m": 400,  "min_elev_deg": 5.0},
    {"id": "GS-003", "name": "Goldstone_Tracking",    "lat": 35.4266,  "lon": -116.8900,"alt_m": 1000, "min_elev_deg": 10.0},
    {"id": "GS-004", "name": "Punta_Arenas",          "lat": -53.1500, "lon": -70.9167, "alt_m": 30,   "min_elev_deg": 5.0},
    {"id": "GS-005", "name": "IIT_Delhi_Ground_Node", "lat": 28.5450,  "lon": 77.1926,  "alt_m": 225,  "min_elev_deg": 15.0},
    {"id": "GS-006", "name": "McMurdo_Station",       "lat": -77.8463, "lon": 166.6682, "alt_m": 10,   "min_elev_deg": 5.0},
]

def latlon_to_ecef(lat_deg, lon_deg, alt_m):
    """
    Convert ground station lat/lon/alt to ECEF (km).
    For simplicity we treat ECEF ≈ ECI at simulation epoch.
    """
    lat = np.radians(lat_deg)
    lon = np.radians(lon_deg)
    alt_km = alt_m / 1000.0

    r = RE + alt_km
    x = r * np.cos(lat) * np.cos(lon)
    y = r * np.cos(lat) * np.sin(lon)
    z = r * np.sin(lat)

    return np.array([x, y, z])

def calculate_elevation_angle(gs_pos_ecef, sat_pos_eci):
    """
    Calculate elevation angle of satellite as seen from ground station.
    gs_pos_ecef: ground station position in ECEF/ECI (km)
    sat_pos_eci: satellite position in ECI (km)
    Returns: elevation angle in degrees
    """
    gs_pos = np.array(gs_pos_ecef)
    sat_pos = np.array(sat_pos_eci)

    # Vector from ground station to satellite
    range_vec = sat_pos - gs_pos
    range_mag = np.linalg.norm(range_vec)

    if range_mag == 0:
        return 90.0

    # Unit vector pointing up from ground station (nadir direction)
    up_vec = gs_pos / np.linalg.norm(gs_pos)

    # Elevation = angle between range vector and local horizontal plane
    sin_elev = np.dot(range_vec, up_vec) / range_mag
    elevation_deg = np.degrees(np.arcsin(np.clip(sin_elev, -1, 1)))

    return elevation_deg

def has_line_of_sight(sat_pos_eci):
    """
    Check if satellite has line-of-sight to any ground station.
    sat_pos_eci: [x, y, z] satellite position in ECI (km)
    Returns: (bool, list of visible station ids)
    """
    sat_pos = np.array(sat_pos_eci)
    visible_stations = []

    for gs in GROUND_STATIONS:
        gs_pos = latlon_to_ecef(gs["lat"], gs["lon"], gs["alt_m"])
        elev = calculate_elevation_angle(gs_pos, sat_pos)

        if elev >= gs["min_elev_deg"]:
            visible_stations.append({
                "station_id": gs["id"],
                "station_name": gs["name"],
                "elevation_deg": round(elev, 2)
            })

    return len(visible_stations) > 0, visible_stations

def get_next_contact_window(sat_state, current_time_s, search_horizon=7200):
    """
    Find the next time a satellite will have ground station contact.
    Useful for scheduling burns before blackout zones.
    
    sat_state: [x,y,z,vx,vy,vz]
    current_time_s: current simulation time in seconds
    search_horizon: how far ahead to search in seconds
    Returns: time offset in seconds when contact is available
    """
    from physics.propagator import propagate

    step = 30  # check every 30 seconds
    for t in range(0, search_horizon, step):
        future_state = propagate(sat_state, t, dt=10.0)
        has_los, stations = has_line_of_sight(future_state[:3])
        if has_los:
            return t, stations

    return None, []  # No contact window found in horizon

def is_in_blackout(sat_pos_eci):
    """
    Check if satellite is currently in a blackout zone.
    Returns True if NO ground station has line of sight.
    """
    has_los, _ = has_line_of_sight(sat_pos_eci)
    return not has_los