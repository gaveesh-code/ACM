import numpy as np

# Spacecraft constants
DRY_MASS = 500.0        # kg
INITIAL_FUEL = 50.0     # kg
INITIAL_WET_MASS = 550.0  # kg
ISP = 300.0             # seconds (specific impulse)
G0 = 9.80665            # m/s^2 (standard gravity)
MAX_DV_PER_BURN = 15.0  # m/s maximum delta-v per burn
COOLDOWN_SECONDS = 600  # seconds between burns
CRITICAL_FUEL_THRESHOLD = 0.05  # 5% fuel remaining = EOL

def calculate_fuel_consumed(current_mass_kg, delta_v_ms):
    """
    Calculate propellant mass consumed for a given delta-v.
    Uses Tsiolkovsky rocket equation:
    delta_m = m_current * (1 - e^(-|dv| / (Isp * g0)))
    
    current_mass_kg: current total mass (dry + remaining fuel)
    delta_v_ms: magnitude of delta-v in m/s
    Returns: mass consumed in kg
    """
    delta_v_ms = abs(delta_v_ms)
    
    if delta_v_ms > MAX_DV_PER_BURN:
        raise ValueError(f"Delta-V {delta_v_ms} m/s exceeds max {MAX_DV_PER_BURN} m/s per burn")
    
    exponent = -delta_v_ms / (ISP * G0)
    delta_m = current_mass_kg * (1 - np.exp(exponent))
    return delta_m

def apply_burn(fuel_kg, delta_v_vector_ms):
    """
    Apply a burn and return updated fuel mass.
    
    fuel_kg: current fuel mass in kg
    delta_v_vector_ms: [dvx, dvy, dvz] in m/s
    Returns: (new_fuel_kg, mass_consumed_kg, success, message)
    """
    delta_v_magnitude = np.linalg.norm(delta_v_vector_ms)
    
    # Check max DV constraint
    if delta_v_magnitude > MAX_DV_PER_BURN:
        return fuel_kg, 0.0, False, f"Exceeds max DV limit of {MAX_DV_PER_BURN} m/s"
    
    # Check if fuel available
    if fuel_kg <= 0:
        return fuel_kg, 0.0, False, "No fuel remaining"
    
    current_total_mass = DRY_MASS + fuel_kg
    mass_consumed = calculate_fuel_consumed(current_total_mass, delta_v_magnitude)
    
    new_fuel = fuel_kg - mass_consumed
    
    # Clamp to zero (can't have negative fuel)
    if new_fuel < 0:
        new_fuel = 0.0
        mass_consumed = fuel_kg
    
    return new_fuel, mass_consumed, True, "Burn successful"

def get_fuel_percentage(fuel_kg):
    """Return fuel as percentage of initial fuel."""
    return (fuel_kg / INITIAL_FUEL) * 100.0

def is_critical_fuel(fuel_kg):
    """Check if satellite has reached critical fuel threshold (5%)."""
    return (fuel_kg / INITIAL_FUEL) <= CRITICAL_FUEL_THRESHOLD

def get_fuel_status(fuel_kg):
    """Return human-readable fuel status."""
    pct = get_fuel_percentage(fuel_kg)
    if pct <= 5:
        return "CRITICAL - EOL"
    elif pct <= 20:
        return "LOW"
    elif pct <= 50:
        return "NOMINAL"
    else:
        return "FULL"

def calculate_max_dv_remaining(fuel_kg):
    """
    Calculate maximum total delta-v remaining with current fuel.
    Uses Tsiolkovsky: dv = Isp * g0 * ln(m_wet / m_dry)
    Returns: max dv in m/s
    """
    if fuel_kg <= 0:
        return 0.0
    
    wet_mass = DRY_MASS + fuel_kg
    dv = ISP * G0 * np.log(wet_mass / DRY_MASS)
    return dv

def graveyard_orbit_dv():
    """
    Calculate approximate delta-v needed to reach graveyard orbit.
    For LEO satellites, deorbit burn is roughly 100 m/s.
    Returns: recommended dv in m/s for safe disposal
    """
    return 50.0  # Conservative estimate for LEO deorbit