# Pipe roughness in meters
PIPE_MATERIALS = {
    "Carbon Steel": 0.000045,
    "Stainless Steel": 0.000015,
    "PVC": 0.0000015,
    "Copper": 0.0000015,
    "Concrete": 0.0003,
    "Cast Iron": 0.00026,
}

# --- Physical Constants in SI units ---

# Acceleration due to gravity (m/s^2)
G = 9.80665

# Standard atmospheric pressure (Pa)
ATM_PRESSURE = 101325

# Universal gas constant (J/(mol*K))
R_GAS_CONSTANT = 8.314462618

# --- Fluid Properties (at standard conditions) ---

# Properties of Water (approx. 20°C)
# Density of water (kg/m^3)
RHO_WATER = 998.2
# Dynamic viscosity of water (Pa*s or N*s/m^2)
MU_WATER = 0.001002

# Properties of Air (at sea level, 15°C)
# Density of air (kg/m^3)
RHO_AIR = 1.225
# Dynamic viscosity of air (Pa*s or N*s/m^2)
MU_AIR = 1.81e-5

# --- Thermodynamic Constants ---

# Stefan-Boltzmann constant (W/(m^2*K^4))
STEFAN_BOLTZMANN = 5.670374419e-8

# --- Fundamental Constants ---

# Speed of light in vacuum (m/s)
C_LIGHT = 299792458

# Planck constant (J*s)
PLANCK_CONSTANT = 6.62607015e-34

# Boltzmann constant (J/K)
BOLTZMANN_CONSTANT = 1.380649e-23

# Avogadro's number (1/mol)
AVOGADRO_NUMBER = 6.02214076e23