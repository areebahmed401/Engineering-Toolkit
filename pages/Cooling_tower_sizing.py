import streamlit as st
from utils.functions import psychrometric_properties, cooling_tower_performance, cooling_tower_losses

import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Cooling Tower Sizing")

st.markdown("<h1 style='color:red;'>Cooling Tower Sizing</h1>", unsafe_allow_html=True)

st.header("Inputs")

col1, col2, col3 = st.columns(3)

with col1:
    altitude = st.number_input("Altitude [m]", value=1884.0, key="altitude")
    t_dry = st.number_input("Dry Bulb Temperature [°C]", value=24.0, key="t_dry")
    RH = st.number_input("Relative Humidity [%]", value=60.0, key="RH")

with col2:
    Q_kW = st.number_input("Heat Load [kW]", value=80.0, key="Q_kW")
    t_in = st.number_input("Hot Water Inlet Temp [°C]", value=31.0, key="t_in")

with col3:
    approach = st.number_input("Approach Temperature [°C]", value=3.0, key="approach")
    CoC = st.number_input("Cycles of Concentration", value=3.0, key="CoC")

Cp_water = 4.18  # kJ/kg·K

if st.button("Calculate"):
    props = psychrometric_properties(t_dry, RH, altitude)
    m_dot, eff, delta_T, t_out = cooling_tower_performance(Q_kW, Cp_water, t_in, props["t_wet"], approach)
    evap_loss, drift_loss, blowdown_loss = cooling_tower_losses(m_dot, delta_T, CoC)

    out_col1, out_col2, out_col3 = st.columns(3)

    with out_col1:
        st.subheader("Psychrometric Properties")
        st.write(f"Atmospheric Pressure: {props['P_atm']:.2f} kPa")
        st.write(f"Wet Bulb Temperature: {props['t_wet']:.2f} °C")
        st.write(f"Specific Humidity: {props['SH']:.5f} kg/kg")

    with out_col2:
        st.subheader("Cooling Tower Performance")
        st.write(f"Outlet Water Temperature: {t_out:.2f} °C")
        st.write(f"Mass Flow Rate of Water: {m_dot*3600:.0f} kg/hr")
        st.write(f"Effectiveness: {eff*100:.1f} %")

    with out_col3:
        st.subheader("Cooling Tower Losses")
        st.write(f"Evaporation Loss: {evap_loss:.0f} kg/hr")
        st.write(f"Drift Loss: {drift_loss:.0f} kg/hr")
        st.write(f"Blowdown Loss: {blowdown_loss:.0f} kg/hr")

    # --- Psychrometric Chart Plot ---
    st.subheader("Psychrometric Chart")

    # Generate dry bulb temperature range
    t_db_range = np.linspace(0, 50, 100)
    # Calculate saturation specific humidity (approximate, for plotting)
    def sat_vapor_pressure(T):
        return 0.6108 * np.exp((17.27 * T) / (T + 237.3))  # kPa

    def specific_humidity(Pws, Patm):
        return 0.622 * Pws / (Patm - Pws)

    Patm = props['P_atm']  # kPa
    ws = [specific_humidity(sat_vapor_pressure(T), Patm) for T in t_db_range]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(t_db_range, ws, label="Saturation Curve", color='b')

    # Plot current air state
    ax.scatter(t_dry, props['SH'], color='red', label='Inlet', zorder=5)
    ax.scatter(t_dry, props['SH'], color='red')    
    ax.annotate("inlet", (t_dry, props['SH']), textcoords="offset points", xytext=(10,10), ha='left', color='red')

    ax.scatter(props['t_wet'], props['SH'], color='green', label='Outlet', zorder=5)
    ax.annotate("Outlet", (props['t_wet'], props['SH']), textcoords="offset points", xytext=(10,-15), ha='left', color='green')

    # --- Add Wet Bulb Temperature Lines ---
    # Plot several wet bulb lines (e.g., 10°C, 15°C, 20°C, 25°C, 30°C)
    wet_bulb_temps = [10, 15, 20, 25, 30]
    for t_wb in wet_bulb_temps:
        sh_line = []
        for t_db in t_db_range:
            if t_db < t_wb:
                sh_line.append(np.nan)
            else:
                # Approximate: assume 100% RH at wet bulb
                Pws_wb = sat_vapor_pressure(t_wb)
                sh_line.append(specific_humidity(Pws_wb, Patm))
        ax.plot(t_db_range, sh_line, linestyle='--', color='gray', alpha=0.7)
        # Label the line at the end
        ax.text(t_db_range[-1], sh_line[-1], f"{t_wb}°C WB", color='gray', fontsize=8, va='bottom')

      # --- Add Enthalpy Lines ---
    # Enthalpy (h) in kJ/kg (dry air): h = 1.006*T + SH*(2501 + 1.805*T)
    enthalpy_lines = [30, 40, 50, 60, 70, 80]  # kJ/kg
    for h in enthalpy_lines:
        sh_line = []
        for t_db in t_db_range:
            # Rearranged enthalpy equation to solve for SH:
            # SH = (h - 1.006*T) / (2501 + 1.805*T)
            denom = 2501 + 1.805 * t_db
            if denom > 0:
                sh = (h - 1.006 * t_db) / denom
                # Only plot physically meaningful values
                if sh > 0 and sh < 0.06:
                    sh_line.append(sh)
                else:
                    sh_line.append(np.nan)
            else:
                sh_line.append(np.nan)
        ax.plot(t_db_range, sh_line, linestyle=':', color='orange', alpha=0.7)
        # Label the line at the end (find last valid point)
        for i in range(len(sh_line)-1, -1, -1):
            if not np.isnan(sh_line[i]):
                ax.text(t_db_range[i], sh_line[i], f"{h} kJ/kg", color='orange', fontsize=8, va='bottom')
                break


    ax.set_xlabel("Dry Bulb Temperature (°C)")
    ax.set_ylabel("Specific Humidity (kg/kg)")
    ax.set_title("Psychrometric Chart (Simplified)")
    ax.legend()
    ax.grid(True)

    st.pyplot(fig)