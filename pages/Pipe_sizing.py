import streamlit as st
import numpy as np
import CoolProp.CoolProp as CP
import math
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from utils.functions import (
    colebrook_white, convert_headtombar, darcy_weisbach,
    get_equivalent_length, calc_insulation_thickness
)
from utils.pipe_weight_calc import pipe_mass_per_m, china_elbow_mass
from utils.constants import PIPE_MATERIALS

# ----------------- Page Config -----------------
st.set_page_config(page_title="Pipe Sizing & Insulation", layout="wide")

st.markdown("<h1 style='color: red;'>Pipe Sizing & Insulation</h1>", unsafe_allow_html=True)
st.markdown(
    "<p font-size: 16px;'>"
    "Estimate pipe sizing, pressure drops, insulation requirements, and costs."
    "</p>", unsafe_allow_html=True
)

# ----------------- Load Catalogs -----------------
PIPE_CATALOG = pd.read_csv(Path("utils/pipe catalog.csv"))
ELBOW_CATALOG = pd.read_csv(Path("utils/elbow catalog.csv"))

pipe_cost_dict = dict(zip(PIPE_CATALOG["size"], PIPE_CATALOG["$/m"]))
elbow_cost_dict = dict(zip(ELBOW_CATALOG["size"], ELBOW_CATALOG["$/piece"]))

# ----------------- Input Section -----------------
with st.expander("Fluid & Pipe Parameters", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        mass_flow_rate_hr = st.number_input("Mass flow rate [kg/hr]", value=50.0)
        initial_pressure_bar = st.number_input("Initial pressure [bar a]", value=4.0)
        initial_temperature_c = st.number_input("Initial temperature [°C]", value=145.0)
        straight_length = st.number_input("Pipe length [m]", value=1.0)
    with c2:
        # Standard Sch 40 DN sizes
        standard_dn = [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300]

        min_dn = st.selectbox("Minimum DN size", standard_dn, index=standard_dn.index(25))
        max_dn = st.selectbox("Maximum DN size", standard_dn, index=standard_dn.index(100))

        if standard_dn.index(min_dn) > standard_dn.index(max_dn):
            st.warning("⚠️ Minimum DN cannot be larger than Maximum DN. Please adjust.")

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

with st.expander("Costing"):
    use_costing = st.checkbox("Include pipe costing")

    if use_costing:
        source = st.radio("Select Source", ["Local", "China"], horizontal=True)

        if source == "China":
            steel_cost_per_ton = st.number_input("Steel Cost [$/ton]", value=640.0)
            include_customs = st.checkbox("Apply 40% Customs Duty (China only)", value=True)

        st.markdown("### Insulation, Cladding & Painting (applies to both sources)")
        insulation_cost = st.number_input("Fiberglass 100mm [$/m]", value=16.9)
        cladding_cost = st.number_input("Aluminum Cladding [$/m]", value=17.6)
        insulation_labour = st.number_input("Insulation Labour [$/m]", value=2.69)
        painting_labour = st.number_input("Painting Labour [$/m]", value=2.40)
        painting_cost = st.number_input("Painting Cost [$/m]", value=3.70)

# ----------------- Run Button -----------------
if st.button("Run Calculation", use_container_width=True):
    try:
        mass_flow_rate = mass_flow_rate_hr / 3600.0
        P_pa = initial_pressure_bar * 1e5
        T_k = initial_temperature_c + 273.15

        density = CP.PropsSI('D', 'T', T_k, 'P', P_pa, fluid)
        viscosity = CP.PropsSI('V', 'T', T_k, 'P', P_pa, fluid)

        results = []
        dn_range = standard_dn[standard_dn.index(min_dn): standard_dn.index(max_dn) + 1]

        for d_mm in dn_range:
            d = d_mm / 1000.0
            A = math.pi * (d / 2) ** 2
            v = mass_flow_rate / (A * density)
            Re = density * v * d / viscosity
            f = colebrook_white(Re, roughness, d)

            eq_len, _ = get_equivalent_length(fittings, d)
            total_len = straight_length + eq_len
            dp = convert_headtombar(darcy_weisbach(f, total_len, v, d), density)

            # Pipe mass
            pipe_mass = pipe_mass_per_m(d_mm)  # kg/m

            # Insulation thickness
            t_mm = calc_insulation_thickness(d, initial_temperature_c, atm_temp, q_max, k_ins) if use_insulation else None
            ins_display = "-" if t_mm is None else (f"{t_mm:.1f}" if math.isfinite(t_mm) else "Too thick")

            # Costing
            pipe_cost_m = elbow_cost = total_cost = "-"
            if use_costing:
                if source == "Local":
                    pipe_cost_m = pipe_cost_dict.get(d_mm, 0)
                    elbow_cost = elbow_cost_dict.get(d_mm, 0) * fittings.get("90_elbow", 0)
                    base_cost = (pipe_cost_m * straight_length) + elbow_cost

                else:  # China
                    pipe_cost_m = (pipe_mass / 1000.0) * steel_cost_per_ton
                    elbow_cost = china_elbow_mass(d_mm) * fittings.get("90_elbow", 0)
                    base_cost = pipe_cost_m * straight_length + elbow_cost
                    if include_customs:
                        base_cost *= 1.4

                # Add insulation, cladding, labour, painting
                extras_per_m = insulation_cost + cladding_cost + insulation_labour + painting_labour + painting_cost
                extras_total = extras_per_m * straight_length
                total_cost = base_cost + extras_total

            results.append({
                "Diameter (DN)": f"DN{d_mm}",
                "Pipe Mass (kg/m)": pipe_mass,
                "Velocity (m/s)": v,
                "Pressure Drop (mbar)": dp,
                "Eq. Length (m)": eq_len,
                "Total Length (m)": total_len,
                "Insulation (mm)": ins_display,
                "Pipe Cost [USD/m]": pipe_cost_m,
                "Elbow Cost [USD]": elbow_cost,
                "Total Cost [USD]": "${:,.2f}".format(total_cost) if total_cost != "-" else "-",
                "Acceptable": vmin <= v <= vmax and dp <= dpmax
            })

        df = pd.DataFrame(results)
        df_display = df.drop(columns=["Acceptable"]) if "Acceptable" in df.columns else df

        st.session_state["results_df"] = df
        st.session_state["results_df_display"] = df_display

    except Exception as e:
        st.error(f"Error: {e}")

# ----------------- Results -----------------
if "results_df_display" in st.session_state:
    df_display = st.session_state["results_df_display"]

    st.markdown("<h3 style='color:red;'>Results Overview</h3>", unsafe_allow_html=True)
    st.dataframe(df_display, use_container_width=True)

    st.markdown("<h3 style='color:red;'>Velocity, Pressure Drop & Cost vs Pipe Size</h3>", unsafe_allow_html=True)

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.set_xlabel('Pipe Diameter (DN)')

    # Velocity plot
    ax1.set_ylabel('Velocity [m/s]', color='blue')
    ax1.plot(df_display["Diameter (DN)"], df_display["Velocity (m/s)"], marker='o', color='blue', label="Velocity")
    ax1.tick_params(axis='y', labelcolor='blue')

    # Pressure drop plot
    ax2 = ax1.twinx()
    ax2.set_ylabel('Pressure Drop [mbar]', color='red')
    ax2.plot(df_display["Diameter (DN)"], df_display["Pressure Drop (mbar)"], marker='s', color='red', label="Pressure Drop")
    ax2.tick_params(axis='y', labelcolor='red')

    # Total cost plot (3rd axis, shifted right)
    ax3 = ax1.twinx()
    ax3.spines["right"].set_position(("outward", 60))
    ax3.set_ylabel('Total Cost [USD]', color='green')

    # Convert formatted cost strings back to numeric
    try:
        total_cost_values = df_display["Total Cost [USD]"].replace('[\$,]', '', regex=True).astype(float)
        ax3.plot(df_display["Diameter (DN)"], total_cost_values, marker='^', color='green', label="Total Cost")
        ax3.tick_params(axis='y', labelcolor='green')
    except Exception:
        pass

    fig.tight_layout()
    st.pyplot(fig)
