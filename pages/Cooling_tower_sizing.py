import streamlit as st
from utils.functions import psychrometric_properties, cooling_tower_performance, cooling_tower_losses
from utils.styling import apply_custom_css

st.set_page_config(page_title="Cooling Tower Sizing", page_icon="💧")
# apply_custom_css()

st.markdown("<h1 style='color:red;'>Cooling Tower Sizing</h1>", unsafe_allow_html=True)

st.sidebar.header("Inputs")
altitude = st.sidebar.number_input("Altitude [m]", value=1884.0)
t_dry = st.sidebar.number_input("Dry Bulb Temperature [°C]", value=24.0)
RH = st.sidebar.number_input("Relative Humidity [%]", value=60.0)
Q_kW = st.sidebar.number_input("Heat Load [kW]", value=80.0)
Cp_water = 4.18  # kJ/kg·K
t_in = st.sidebar.number_input("Hot Water Inlet Temp [°C]", value=31.0)
approach = st.sidebar.number_input("Approach Temperature [°C]", value=3.0)
CoC = st.sidebar.number_input("Cycles of Concentration", value=3.0)

if st.sidebar.button("Calculate"):
    props = psychrometric_properties(t_dry, RH, altitude)
    m_dot, eff, delta_T, t_out = cooling_tower_performance(Q_kW, Cp_water, t_in, props["t_wet"], approach)
    evap_loss, drift_loss, blowdown_loss = cooling_tower_losses(m_dot, delta_T, CoC)

    st.subheader("🌡️ Psychrometric Properties")
    st.write(f"Atmospheric Pressure: {props['P_atm']:.2f} kPa")
    st.write(f"Wet Bulb Temperature: {props['t_wet']:.2f} °C")
    st.write(f"Specific Humidity: {props['SH']:.5f} kg/kg")

    st.subheader("💧 Cooling Tower Performance")
    st.write(f"Outlet Water Temperature: {t_out:.2f} °C")
    st.write(f"Mass Flow Rate of Water: {m_dot*3600:.0f} kg/hr")
    st.write(f"Effectiveness: {eff*100:.1f} %")

    st.subheader("📉 Cooling Tower Losses")
    st.write(f"Evaporation Loss: {evap_loss:.0f} kg/hr")
    st.write(f"Drift Loss: {drift_loss:.0f} kg/hr")
    st.write(f"Blowdown Loss: {blowdown_loss:.0f} kg/hr")
