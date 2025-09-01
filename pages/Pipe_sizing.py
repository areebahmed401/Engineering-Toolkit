import streamlit as st
import numpy as np
import CoolProp.CoolProp as CP
import math
import matplotlib.pyplot as plt
import pandas as pd

from utils.functions import (
    colebrook_white, convert_headtombar, darcy_weisbach,
    get_equivalent_length, calc_insulation_thickness
)
from utils.constants import PIPE_MATERIALS
from utils.styling import apply_custom_css

# ----------------- Page Config -----------------
st.set_page_config(page_title="Pipe Sizing & Insulation", layout="wide")
# apply_custom_css()

st.markdown("<h1 style='color:red;'>Pipe Sizing & Insulation</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='color: red; font-size: 16px;'>"
    "Estimate pipe sizing, pressure drops, and insulation requirements."
    "</p>", unsafe_allow_html=True
)

# ----------------- Input Section -----------------
with st.expander("Fluid & Pipe Parameters", expanded=True,):
    c1, c2 = st.columns(2)
    with c1:
        mass_flow_rate_hr = st.number_input("Mass flow rate [kg/hr]", value=50.0)
        initial_pressure_bar = st.number_input("Initial pressure [bar a]", value=4.0)
        initial_temperature_c = st.number_input("Initial temperature [°C]", value=145.0)
        straight_length = st.number_input("Pipe length [m]", value=1.0)
    with c2:
        min_d = st.number_input("Min pipe diameter [mm]", value=20.0)
        max_d = st.number_input("Max pipe diameter [mm]", value=50.0)
        fluids = sorted(CP.get_global_param_string("fluids_list").split(","))
        fluid = st.selectbox("Fluid", fluids, index=fluids.index("Water"))
        material = st.selectbox("Pipe material", list(PIPE_MATERIALS.keys()))
        roughness = PIPE_MATERIALS[material]

with st.expander("Fittings"):
    fittings = {}
    fitting_labels = {
        "90_elbow": "90° Elbow", "45_elbow": "45° Elbow", "globe_valve": "Globe Valve",
        "gate_valve": "Gate Valve", "ball_valve": "Ball Valve", "check_valve": "Check Valve",
        "tee_run": "Tee (Run)", "tee_branch": "Tee (Branch)"
    }
    cols = st.columns(4)
    for i, (key, label) in enumerate(fitting_labels.items()):
        with cols[i % 4]:
            fittings[key] = st.number_input(label, min_value=0, value=0, step=1)

with st.expander("Constraints"):
    vmin = st.number_input("Min velocity [m/s]", value=20.0)
    vmax = st.number_input("Max velocity [m/s]", value=30.0)
    dpmax = st.number_input("Max pressure drop [mbar]", value=100.0)

with st.expander("Insulation"):
    use_insulation = st.checkbox("Include insulation calculation")
    if use_insulation:
        atm_temp = st.number_input("Atmospheric temperature [°C]", value=25.0)
        q_max = st.number_input("Acceptable heat loss [W/m]", value=30.0)
        k_ins = st.number_input("Insulation k [W/m·K]", value=0.04)
    else:
        atm_temp = q_max = k_ins = None

# ----------------- Run Button -----------------
if st.button("Run Calculation", use_container_width=True):
    try:
        mass_flow_rate = mass_flow_rate_hr / 3600.0
        P_pa = initial_pressure_bar * 1e5
        T_k = initial_temperature_c + 273.15
        pipe_diameters = np.arange(min_d, max_d + 5, 5)

        density = CP.PropsSI('D', 'T', T_k, 'P', P_pa, fluid)
        viscosity = CP.PropsSI('V', 'T', T_k, 'P', P_pa, fluid)

        results = []
        for d_mm in pipe_diameters:
            d = d_mm / 1000.0
            A = math.pi * (d / 2) ** 2
            v = mass_flow_rate / (A * density)
            Re = density * v * d / viscosity
            f = colebrook_white(Re, roughness, d)

            eq_len, _ = get_equivalent_length(fittings, d)
            total_len = straight_length + eq_len
            dp = convert_headtombar(darcy_weisbach(f, total_len, v, d), density)

            t_mm = calc_insulation_thickness(d, initial_temperature_c, atm_temp, q_max, k_ins) if use_insulation else None
            ins_display = "-" if t_mm is None else (f"{t_mm:.1f}" if math.isfinite(t_mm) else "Too thick")

            results.append({
                "Diameter (mm)": d_mm,
                "Velocity (m/s)": v,
                "Pressure Drop (mbar)": dp,
                "Eq. Length (m)": eq_len,
                "Total Length (m)": total_len,
                "Insulation (mm)": ins_display,
                "Acceptable": vmin <= v <= vmax and dp <= dpmax
            })

        df = pd.DataFrame(results)
        st.session_state["results_df"] = df

    except Exception as e:
        st.error(f"Error: {e}")

# ----------------- Results -----------------
if "results_df" in st.session_state:
    df = st.session_state["results_df"]
    
    st.markdown("<h3 style='color:red;'>Key Metric of Selected Pipe size</h3>", unsafe_allow_html=True)
    acceptable = df[df["Acceptable"]]
    if not acceptable.empty:
        row = acceptable.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Inner Diameter", f"{row['Diameter (mm)']} mm")
        c2.metric("Velocity", f"{row['Velocity (m/s)']:.2f} m/s")
        c3.metric("Pressure Drop", f"{row['Pressure Drop (mbar)']:.2f} mbar")
    else:
        st.warning("No acceptable designs found. Adjust your constraints.")

    st.markdown("<h3 style='color:red;'>Results Overview</h3>", unsafe_allow_html=True)
    def highlight_rows(row):
        return ['color: green; font-weight: bold' if row.Acceptable else 'color: gray'] * len(row)
    st.dataframe(df.style.apply(highlight_rows, axis=1), use_container_width=True)

    
    st.markdown("<h3 style='color:red;'>Velocity & PD vs Pipe Size Plot</h3>", unsafe_allow_html=True)
    fig, ax1 = plt.subplots()
    ax1.set_xlabel('Pipe Diameter (mm)')
    ax1.set_ylabel('Velocity [m/s]', color='blue')
    ax1.plot(df["Diameter (mm)"], df["Velocity (m/s)"], marker='o', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax2 = ax1.twinx()
    ax2.set_ylabel('Pressure Drop [mbar]', color='red')
    ax2.plot(df["Diameter (mm)"], df["Pressure Drop (mbar)"], marker='s', color='red')
    ax2.tick_params(axis='y', labelcolor='red')
    fig.tight_layout()
    st.pyplot(fig)
