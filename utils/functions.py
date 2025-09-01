import math

def colebrook_white(Re, roughness, D):
    epsilon_D = roughness / D
    f = 0.001
    max_iter, tol = 5000, 1e-6
    if Re <= 2300 and Re > 0:
        return 64.0 / Re
    for _ in range(max_iter):
        lhs = 1 / math.sqrt(f)
        rhs = -2 * math.log10((epsilon_D / 3.7) + (2.51 / (Re * math.sqrt(f))))
        if abs(lhs - rhs) < tol:
            break
        f = 1 / (rhs ** 2)
    return f

def convert_headtombar(h, density):
    return 9.81 * density * h / 100.0

def darcy_weisbach(f, distance, velocity, diameter):
    return f * distance * (velocity ** 2) / (2 * diameter * 9.81)

def get_equivalent_length(fittings, diameter):
    Le_D = {
        "90_elbow": 30, "45_elbow": 16, "globe_valve": 340,
        "gate_valve": 8, "ball_valve": 3, "check_valve": 100,
        "tee_run": 20, "tee_branch": 60
    }
    breakdown, Le_total = {}, 0.0
    for key, count in fittings.items():
        if key in Le_D:
            Le = Le_D[key] * count * diameter
            breakdown[key] = Le
            Le_total += Le
    for k in Le_D.keys():
        if k not in breakdown:
            breakdown[k] = 0.0
    return Le_total, breakdown

def calc_insulation_thickness(d, T_fluid_c, T_atm_c, q_max, k_ins):
    deltaT = T_fluid_c - T_atm_c
    if deltaT <= 0:
        return 0.0
    try:
        exponent = (2.0 * math.pi * k_ins * deltaT) / q_max
        if exponent > 700:
            return float('inf')
        r1 = d / 2.0
        r2 = r1 * math.exp(exponent)
        return max(0.0, (r2 - r1) * 1000.0) * 1.1
    except Exception:
        return float('nan')

import CoolProp.CoolProp as CP
import math

# ---------------- Helper Functions -----------------
def mixture_molar_mass(fluids, mass_fracs):
    """Calculate average molar mass of a mixture given fluids and mass fractions."""
    molar_masses = [CP.PropsSI("M", f) for f in fluids]
    total_mass = sum(mass_fracs)
    molar_contributions = [mass_fracs[i] / molar_masses[i] for i in range(len(fluids))]
    avg_molar_mass = total_mass / sum(molar_contributions)
    return avg_molar_mass


def required_pump_flow(V, Pi, Pf, t):
    """Calculate required pump flow for pump-down (classical)."""
    return (V / t) * math.log(Pi / Pf)


def mixture_properties(fluids, mass_fracs, T_C, P_mbar):
    """Return density and viscosity of a gas mixture using mass fractions."""
    total_mass = sum(mass_fracs)
    if total_mass == 0:
        raise ValueError("Mass fractions cannot all be zero")
    mass_fracs = [mf / total_mass for mf in mass_fracs]

    molar_masses = [CP.PropsSI("M", f) for f in fluids]
    moles = [mass_fracs[i] / molar_masses[i] for i in range(len(fluids))]
    total_moles = sum(moles)
    mole_fracs = [n / total_moles for n in moles]

    P_Pa = P_mbar * 100.0
    T_K = T_C + 273.15

    density = sum(
        mole_fracs[i] * CP.PropsSI("D", "T", T_K, "P", P_Pa, fluids[i])
        for i in range(len(fluids))
    )
    viscosity = sum(
        mole_fracs[i] * CP.PropsSI("VISCOSITY", "T", T_K, "P", P_Pa, fluids[i])
        for i in range(len(fluids))
    )

    return density, viscosity


def validate_water_state(T_C, P_mbar):
    """Check if water is superheated at given T and P."""
    T_K = T_C + 273.15
    P_Pa = P_mbar * 100.0
    Tsat = CP.PropsSI("T", "P", P_Pa, "Q", 0, "Water")
    if T_K <= Tsat:
        return False, Tsat - 273.15
    return True, Tsat - 273.15


# ---------------- High-Level Sizing Functions -----------------
def pumpdown_sizing(fluids, mass_fracs, V, Pi_mbar, Pf_mbar, T_C, t):
    """Perform pump-down sizing calculations."""
    if Pf_mbar >= Pi_mbar:
        raise ValueError("Final pressure must be less than initial pressure")

    if "Water" in fluids:
        valid, Tsat_C = validate_water_state(T_C, Pi_mbar)
        if not valid:
            raise ValueError(
                f"Water must be superheated. At {Pi_mbar} mbar, Tsat ≈ {Tsat_C:.2f} °C. "
                f"Your T = {T_C:.2f} °C"
            )

    Pi_Pa = Pi_mbar * 100.0
    Pf_Pa = Pf_mbar * 100.0
    T_K = T_C + 273.15

    # Pump flow
    Q_m3s_classical = required_pump_flow(V, Pi_Pa, Pf_Pa, t)

    # Convert to Nm³/hr
    P_norm = 101325.0
    T_norm = 273.15
    Q_Nm3hr_classical = Q_m3s_classical * 3600.0 * (Pi_Pa / P_norm) * (T_norm / T_K)

    # Mixture props
    density, viscosity = mixture_properties(fluids, mass_fracs, T_C, Pi_mbar)
    M_mix = mixture_molar_mass(fluids, mass_fracs)

    return {
        "Q_m3hr": Q_m3s_classical * 3600.0,
        "Q_Nm3hr": Q_Nm3hr_classical,
        "M_mix": M_mix,
        "density": density,
        "viscosity": viscosity,
        "T_C": T_C,
    }


def continuous_operation_sizing(P_mbar, T_C, mdot_steam_kg_hr, mdot_co2_kg_hr):
    """Perform continuous operation pump sizing calculations."""
    T_K = T_C + 273.15
    P_Pa = P_mbar * 100.0

    valid, Tsat_C = validate_water_state(T_C, P_mbar)
    if not valid:
        raise ValueError(
            f"Steam must be superheated. At {P_mbar} mbar, Tsat ≈ {Tsat_C:.2f} °C. "
            f"Your T = {T_C:.2f} °C"
        )

    mdot_steam = mdot_steam_kg_hr / 3600.0
    mdot_co2 = mdot_co2_kg_hr / 3600.0

    M_steam = CP.PropsSI("M", "Water")
    M_co2 = CP.PropsSI("M", "CO2")

    n_steam = mdot_steam / M_steam
    n_co2 = mdot_co2 / M_co2
    n_total = n_steam + n_co2

    y_steam = n_steam / n_total
    y_co2 = n_co2 / n_total

    R = 8.314
    Vdot_m3s = n_total * R * T_K / P_Pa
    Vdot_m3hr = Vdot_m3s * 3600.0

    # Convert to Nm³/hr
    P_norm = 101325.0
    T_norm = 273.15
    Vdot_Nm3hr = Vdot_m3s * 3600.0 * (P_Pa / P_norm) * (T_norm / T_K)

    fluids = ["Water", "CO2"]
    mass_fracs = [mdot_steam, mdot_co2]
    density, viscosity = mixture_properties(fluids, mass_fracs, T_C, P_mbar)

    return {
        "Vdot_m3hr": Vdot_m3hr,
        "Vdot_Nm3hr": Vdot_Nm3hr,
        "y_steam": y_steam,
        "y_co2": y_co2,
        "density": density,
        "viscosity": viscosity,
    }


import math
import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)

def atmospheric_pressure(altitude_m):
    return 101.3 * (1 - 2.25577e-5 * altitude_m) ** 5.25588  # kPa

def psychrometric_properties(t_dry, RH, altitude):
    P_atm = atmospheric_pressure(altitude)
    P_sat = 0.611 * 10 ** (7.5 * t_dry / (t_dry + 237.3))
    P_v = RH / 100 * P_sat
    P_d = P_atm - P_v
    SH = 0.622 * P_v / (P_atm - P_v)
    t_wet = psychrolib.GetTWetBulbFromRelHum(t_dry, RH / 100, P_atm * 1000)
    return {
        "P_atm": P_atm,
        "P_sat": P_sat,
        "P_v": P_v,
        "P_d": P_d,
        "SH": SH,
        "t_wet": t_wet,
    }

def cooling_tower_performance(Q_kW, Cp_water, t_in, t_wet, approach):
    t_out = t_wet + approach
    delta_T = t_in - t_out
    m_dot = Q_kW / (Cp_water * delta_T)  # kg/s
    effectiveness = delta_T / (delta_T + approach)
    return m_dot, effectiveness, delta_T, t_out

def cooling_tower_losses(m_dot, delta_T, CoC):
    m_dot_hr = m_dot * 3600
    evap_loss = 0.00085 * m_dot_hr * delta_T
    drift_loss = 0.002 * m_dot_hr
    blowdown_loss = evap_loss / (CoC - 1)
    return evap_loss, drift_loss, blowdown_loss

import CoolProp.CoolProp as CP

def get_refrigeration_cycle( refrigerant, t_evap, t_cond, comp_power):
    
    t_evap = t_evap + 273.15
    t_cond = t_cond + 273.15
    
    try:
        p_evap = CP.PropsSI('P', 'T', t_evap, 'Q', 0, refrigerant) 
        p_cond = CP.PropsSI('P', 'T', t_cond, 'Q', 0, refrigerant)
        t_1 = t_evap
        p_1 = p_evap
        h_1 = CP.PropsSI('H', 'P', p_evap, 'Q', 1, refrigerant)
        s_1 = CP.PropsSI('S', 'P', p_evap, 'Q', 1, refrigerant)

        s_2 = s_1 + 100
        p_2 = p_cond
        h_2 = CP.PropsSI('H', 'S', s_2, 'P', p_cond, refrigerant)
        t_2 = CP.PropsSI('T', 'P', p_cond, 'S', s_2, refrigerant)
        
        p_2x =p_2
        h_2x = CP.PropsSI('H', 'P', p_2x, 'Q', 1, refrigerant)
        s_2x = CP.PropsSI('S', 'P', p_2x, 'Q', 1, refrigerant)
        t_2x = CP.PropsSI('T', 'P', p_2x, 'Q', 1, refrigerant)

        h_3 = CP.PropsSI('H', 'P', p_cond, 'Q', 0, refrigerant)
        s_3 = CP.PropsSI('S', 'P', p_cond, 'Q', 0, refrigerant)
        t_3 = t_cond
        p_3 = p_cond

        h_4 = h_3
        q_4 = CP.PropsSI('Q', 'P', p_cond, 'H', h_4, refrigerant) 
        p_4 = p_evap
        t_4 = t_evap
        s_4 = CP.PropsSI('S', 'P', p_evap, 'Q', q_4, refrigerant)
        
        
        p_1 = p_1 / 1000
        p_2 = p_2 / 1000
        p_2x = p_2x / 1000
        p_3 = p_3 / 1000
        p_4 = p_4 / 1000
        h_1 = h_1 / 1000
        h_2 = h_2 / 1000
        h_2x = h_2x / 1000
        h_3 = h_3 / 1000
        h_4 = h_4 / 1000
        s_1 = s_1 / 1000
        s_2 = s_2 / 1000
        s_2x = s_2x / 1000
        s_3 = s_3 / 1000
        s_4 = s_4 / 1000
        
        COP= (h_2-h_3)/(h_2-h_1)
        rdot = comp_power / (h_2 - h_1) #kg/s
        heat_load = rdot *(h_2 - h_3) #kW
        cooling_load = rdot *(h_1 - h_4) #kW
        temp_lift = t_cond - t_evap #K

        return p_evap, p_cond, t_1, p_1, h_1, s_1, s_2, t_2, p_2, h_2,s_2x, t_2x, p_2x, h_2x, h_3, s_3, t_3, p_3, h_4, p_4, t_4, s_4, COP, rdot, heat_load, cooling_load, temp_lift
    except ValueError:
        
        return 'Values not in range'
    
def get_environmental_ratings(refrigerant):
    if refrigerant.lower() == "water":
        return "Water has no environmental impact"
    else:
        try:
            gwp_100 = CP.PropsSI('GWP100', refrigerant)
            gwp_20 = CP.PropsSI('GWP20', refrigerant)
            odp = CP.PropsSI('GWP20', refrigerant)
            environmental_ratings = f"GWP100: {gwp_100}, GWP20: {gwp_20}, ODP: {odp}"
        except ValueError:
            environmental_ratings = "No environmental ratings available"
    return environmental_ratings


def get_health_ratings(refrigerant):
    Health_Hazard = CP.PropsSI('HH', refrigerant)
    flammability = CP.PropsSI('FH', refrigerant)
    Physical_hazard = CP.PropsSI('PH', refrigerant)
    health_ratings = f"Health Hazard: {Health_Hazard}, Flammability: {flammability}, Physical Hazard: {Physical_hazard}"
    return health_ratings