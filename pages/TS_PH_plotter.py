import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import CoolProp.CoolProp as CP
from utils.styling import apply_custom_css

# Page setup
st.set_page_config(page_title="TS & PH Diagram Plotter", page_icon="📊", layout="wide")
# apply_custom_css()

st.markdown("<h1 style='color:red;'>T-S & P-H Diagram Plotter </h1>", unsafe_allow_html=True)

# --- Inputs ---
fluids_list = CP.get_global_param_string("fluids_list").split(',')

col1, col2, col3 = st.columns(3)

with col1:
    fluid = st.selectbox("Select Fluid", options=fluids_list, index=fluids_list.index("Water") if "Water" in fluids_list else 0)
    T_in = st.number_input("Temperature [°C]", value=150.0)
    
with col2:
    P_in = st.number_input("Pressure [bar]", value=5.0)
    process_type = st.selectbox("Process Type", ["Isobaric", "Isoenthalpic", "Isothermal"])
    
with col3:
    end_value = st.number_input(
        "End Value", 
        value=200.0, 
        help="For isobaric: end T [°C]; For isothermal: end P [bar]; For isoenthalpic: end P [bar]"
    )

# Centered Generate button
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
generate_button = st.button("Generate Diagrams")
st.markdown("</div>", unsafe_allow_html=True)

if generate_button:
    try:
        # --- Critical & triple points ---
        T_crit = CP.PropsSI("Tcrit", fluid)
        T_trip = CP.PropsSI("Ttriple", fluid)

        # --- Saturation curves ---
        T_range = np.linspace(T_trip + 1, T_crit - 1, 400)
        s_liq = [CP.PropsSI("S", "T", T, "Q", 0, fluid) for T in T_range]
        s_vap = [CP.PropsSI("S", "T", T, "Q", 1, fluid) for T in T_range]
        h_liq = [CP.PropsSI("H", "T", T, "Q", 0, fluid) for T in T_range]
        h_vap = [CP.PropsSI("H", "T", T, "Q", 1, fluid) for T in T_range]

        # --- Starting state ---
        T_K = T_in + 273.15
        P_Pa = P_in * 1e5
        s_in = CP.PropsSI("S", "T", T_K, "P", P_Pa, fluid)
        h_in = CP.PropsSI("H", "T", T_K, "P", P_Pa, fluid)

        # --- Process path ---
        s_proc, T_proc, h_proc, P_proc = [], [], [], []
        n_points = 50

        if process_type == "Isobaric":
            T_end = end_value + 273.15
            T_list = np.linspace(T_K, T_end, n_points)
            for T in T_list:
                s_proc.append(CP.PropsSI("S", "T", T, "P", P_Pa, fluid))
                h_proc.append(CP.PropsSI("H", "T", T, "P", P_Pa, fluid))
                T_proc.append(T)
                P_proc.append(P_Pa)
        elif process_type == "Isothermal":
            P_end = end_value * 1e5
            P_list = np.linspace(P_Pa, P_end, n_points)
            for P in P_list:
                s_proc.append(CP.PropsSI("S", "T", T_K, "P", P, fluid))
                h_proc.append(CP.PropsSI("H", "T", T_K, "P", P, fluid))
                T_proc.append(T_K)
                P_proc.append(P)
        elif process_type == "Isoenthalpic":
            P_end = end_value * 1e5
            P_list = np.linspace(P_Pa, P_end, n_points)
            for P in P_list:
                T = CP.PropsSI("T", "P", P, "H", h_in, fluid)
                s_proc.append(CP.PropsSI("S", "P", P, "H", h_in, fluid))
                h_proc.append(h_in)
                T_proc.append(T)
                P_proc.append(P)

        # --- Build diagrams ---
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

        # T-s Diagram
        ax1.plot(s_liq, T_range, "r-", label="Saturated Liquid")
        ax1.plot(s_vap, T_range, "b-", label="Saturated Vapor")
        ax1.plot(s_proc, T_proc, "k-", lw=2, label=f"{process_type} process")
        ax1.plot(s_in, T_K, "go", markersize=6, label="Start")
        ax1.set_xlabel("Entropy [J/kg·K]")
        ax1.set_ylabel("Temperature [K]")
        ax1.set_title(f"T-s Diagram: {fluid}", fontsize=10)
        ax1.legend(fontsize=8)
        ax1.grid(True, ls="--", alpha=0.5)

        # P-h Diagram
        ax2.semilogy(h_liq, [CP.PropsSI("P", "T", T, "Q", 0, fluid) for T in T_range], "r-")
        ax2.semilogy(h_vap, [CP.PropsSI("P", "T", T, "Q", 1, fluid) for T in T_range], "b-")
        ax2.semilogy(h_proc, P_proc, "k-", lw=2, label=f"{process_type} process")
        ax2.plot(h_in, P_Pa, "go", markersize=6, label="Start")
        ax2.set_xlabel("Enthalpy [J/kg]")
        ax2.set_ylabel("Pressure [Pa]")
        ax2.set_title(f"P-h Diagram: {fluid}", fontsize=10)
        ax2.legend(fontsize=8)
        ax2.grid(True, which="both", ls="--", alpha=0.5)

        st.pyplot(fig, use_container_width=True)

        # --- End state summary ---
        h_end = h_proc[-1]
        T_end = T_proc[-1]
        P_end = P_proc[-1]
        rho_end = CP.PropsSI("D", "H", h_end, "P", P_end, fluid)
        v_end = 1 / rho_end

        st.markdown("### End Point Conditions")
        st.write({
            "Temperature [deg C]": T_end-273.15,
            "Pressure [bar]": P_end/1e5,
            "Enthalpy [kJ/kg]": h_end/1000,
            "Density [kg/m³]": rho_end,
            "Specific Volume [m³/kg]": v_end
        })

    except Exception as e:
        st.error(f"Error generating diagrams: {str(e)}")
