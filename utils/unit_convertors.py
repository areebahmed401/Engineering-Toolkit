def length_m_to_ft(meters):
    return meters * 3.28084

def length_ft_to_m(feet):
    return feet / 3.28084

def pressure_pa_to_psi(pascals):
    return pascals / 6894.757

def pressure_psi_to_pa(psi):
    return psi * 6894.757

def temperature_c_to_f(celsius):
    return celsius * 9/5 + 32

def temperature_f_to_c(fahrenheit):
    return (fahrenheit - 32) * 5/9

def mass_kg_to_lb(kg):
    return kg * 2.20462

def mass_lb_to_kg(lb):
    return lb / 2.20462

def flow_m3s_to_cfs(m3s):
    return m3s * 35.3147

def flow_cfs_to_m3s(cfs):
    return cfs / 35.3147

def energy_j_to_btu(joules):
    return joules / 1055.06

def energy_btu_to_j(btu):
    return btu * 1055.06

def power_w_to_hp(watts):
    return watts / 745.7

def power_hp_to_w(hp):
    return hp

def energy_kj_to_kwh(kj):
    return kj / 3600

def energy_kwh_to_kj(kwh):
    return kwh * 3600