# pages/Refrigerant_Diagrams.py
import streamlit as st
import matplotlib.pyplot as plt
import CoolProp.CoolProp as CP
from utils.functions import get_refrigeration_cycle, get_environmental_ratings,get_health_ratings   # Keep your function for the refrigeration cycle

st.set_page_config(page_title="Refrigerant Diagrams", layout="wide")
st.title("🧊 Refrigerant Diagrams & Heat Pump Cycle")

# ----------------- Inputs -----------------
st.subheader("Refrigerant Selection")

# Common refrigerants as buttons
common_refrigerants = ['Water', 'R134a', 'R245fa', 'R1234ze(E)', 'Butane', 'Ammonia', 'IsoButane', 'Isopentane']
col_buttons = st.columns(len(common_refrigerants))
selected_refrigerant = None
for i, ref in enumerate(common_refrigerants):
    if col_buttons[i].button(ref):
        selected_refrigerant = ref

# Less common refrigerants as dropdown
less_common_refrigerants = ['1-Butene', 'Acetone', 'Air', 'Ammonia', 'Argon', 'Benzene', 'CarbonDioxide',
                            'CarbonMonoxide', 'CarbonylSulfide', 'cis-2-Butene', 'CycloHexane', 'Cyclopentane',
                            'CycloPropane', 'D4', 'D5', 'D6', 'Deuterium', 'Dichloroethane', 'DiethylEther',
                            'DimethylCarbonate', 'DimethylEther', 'Ethane', 'Ethanol', 'EthylBenzene', 'Ethylene',
                            'EthyleneOxide', 'Fluorine', 'HeavyWater', 'Helium', 'HFE143m', 'Hydrogen',
                            'HydrogenChloride', 'HydrogenSulfide', 'IsoButane', 'IsoButene', 'Isohexane',
                            'Isopentane', 'Krypton', 'm-Xylene', 'MD2M', 'MD3M', 'MD4M', 'MDM', 'Methane',
                            'Methanol', 'MethylLinoleate', 'MethylLinolenate', 'MethylOleate', 'MethylPalmitate',
                            'MethylStearate', 'MM', 'n-Butane', 'n-Decane', 'n-Dodecane', 'n-Heptane', 'n-Hexane',
                            'n-Nonane', 'n-Octane', 'n-Pentane', 'n-Propane', 'n-Undecane', 'Neon', 'Neopentane',
                            'Nitrogen', 'NitrousOxide', 'Novec649', 'o-Xylene', 'OrthoDeuterium', 'OrthoHydrogen',
                            'Oxygen', 'p-Xylene', 'ParaDeuterium', 'ParaHydrogen', 'Propylene', 'Propyne', 'R11',
                            'R113', 'R114', 'R115', 'R116', 'R12', 'R123', 'R1233zd(E)', 'R1234yf', 'R1234ze(E)',
                            'R1234ze(Z)', 'R124', 'R1243zf', 'R125', 'R13', 'R134a', 'R13I1', 'R14', 'R141b', 'R142b',
                            'R143a', 'R152A', 'R161', 'R21', 'R218', 'R22', 'R227EA', 'R23', 'R236EA', 'R236FA',
                            'R245ca', 'R245fa', 'R32', 'R365MFC', 'R40', 'R404A', 'R407C', 'R41', 'R410A', 'R507A',
                            'RC318', 'SES36', 'SulfurDioxide', 'SulfurHexafluoride', 'Toluene', 'trans-2-Butene', 'Water',
                            'Xenon']

dropdown_ref = st.selectbox("Or select less common refrigerant:", options=[""] + less_common_refrigerants)
if dropdown_ref:
    selected_refrigerant = dropdown_ref

if selected_refrigerant:
    st.subheader(f"Selected Refrigerant: {selected_refrigerant}")

    # Input fields for cycle
    st.subheader("Cycle Parameters")
    t_evap = st.number_input("Evaporator Temperature (°C)", value=25.0)
    t_cond = st.number_input("Condenser Temperature (°C)", value=100.0)
    comp_power = st.number_input("Compressor Power (kW)", value=40.0)

    # Create two columns for P-H and T-S diagrams
    col1, col2 = st.columns(2)
    fig, ax = plt.subplots(1, 2, figsize=(12, 5))

    # ----------------- Plot Saturated Curves -----------------
    Tmin = CP.PropsSI(selected_refrigerant, 'Tmin')
    Tmax = CP.PropsSI(selected_refrigerant, 'Tcrit')
    T = [Tmin + i * (Tmax - Tmin)/100 for i in range(101)]

    p_sat = [CP.PropsSI('P','T',t,'Q',0,selected_refrigerant)/1000 for t in T]
    h_sat_v = [CP.PropsSI('H','T',t,'Q',1,selected_refrigerant)/1000 for t in T]
    h_sat_l = [CP.PropsSI('H','T',t,'Q',0,selected_refrigerant)/1000 for t in T]
    s_sat_v = [CP.PropsSI('S','T',t,'Q',1,selected_refrigerant)/1000 for t in T]
    s_sat_l = [CP.PropsSI('S','T',t,'Q',0,selected_refrigerant)/1000 for t in T]

    # P-H diagram
    ax[0].plot(h_sat_v, p_sat, 'r-', label='Saturated Vapor')
    ax[0].plot(h_sat_l, p_sat, 'b-', label='Saturated Liquid')
    ax[0].set_xlabel('Enthalpy (kJ/kg)')
    ax[0].set_ylabel('Pressure (kPa)')
    ax[0].set_title('P-H Diagram')
    ax[0].grid(True)
    ax[0].legend()

    # T-S diagram
    ax[1].plot(s_sat_v, T, 'r-', label='Saturated Vapor')
    ax[1].plot(s_sat_l, T, 'b-', label='Saturated Liquid')
    ax[1].set_xlabel('Entropy (kJ/(kg*K))')
    ax[1].set_ylabel('Temperature (K)')
    ax[1].set_title('T-S Diagram')
    ax[1].grid(True)
    ax[1].legend()

    # ----------------- Plot Heat Pump Cycle -----------------
    # Get cycle points from your function
    p_evap, p_cond, t_1, p_1, h_1, s_1, s_2, t_2, p_2, h_2, s_2x, t_2x, p_2x, h_2x, h_3, s_3, t_3, p_3, h_4, p_4, t_4, s_4, COP, ref_flowrate, heat_load, cooling_load, temp_lift = get_refrigeration_cycle(selected_refrigerant, t_evap, t_cond, comp_power)

    # P-H cycle
    ax[0].plot([h_1, h_2, h_2x, h_3, h_4, h_1],
               [p_1, p_2, p_2x, p_3, p_4, p_1], 'g-', label='Heat Pump Cycle')
    # T-S cycle
    ax[1].plot([s_1, s_2, s_2x, s_3, s_4, s_1],
               [t_1, t_2, t_2x, t_3, t_4, t_1], 'g-', label='Heat Pump Cycle')

    st.pyplot(fig, use_container_width=True)

    # Display key outputs
    st.success(f"Refrigerant Flow Rate: {round(ref_flowrate,4)} kg/s")
    st.success(f"COP: {round(COP,2)}")
    st.info(f"Heat Load: {round(heat_load,2)} kW")
    st.info(f"Cooling Load: {round(cooling_load,2)} kW")
    st.success(f"Temperature Lift: {round(temp_lift,2)} K")

    # Display environmental and health ratings
    env_data = get_environmental_ratings(selected_refrigerant)
    health_data = get_health_ratings(selected_refrigerant)
    st.write(f"**Environmental Ratings:** {env_data}")
    st.write(f"**Health Ratings:** {health_data}")
