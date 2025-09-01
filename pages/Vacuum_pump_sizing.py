import streamlit as st
from utils.functions import pumpdown_sizing, continuous_operation_sizing

st.set_page_config(page_title="Vacuum Pump Sizing", layout="wide")

st.markdown("<h1 style='color:red;'>Vacuum Pump Sizing</h1>", unsafe_allow_html=True)

# Tabs for Pumpdown and Continuous modes
tab1, tab2 = st.tabs(["🔻 Pump-down Sizing", "♻ Continuous Operation Sizing"])

# ---------------- Pump-down Section ----------------
with tab1:
    st.subheader("Pump-down Sizing")

    col1, col2, col3 = st.columns(3)
    with col1:
        fluid1 = st.text_input("Fluid 1", "Air")
        mf1 = st.number_input("Mass ratio Fluid 1", value=1.0, step=0.1)
    with col2:
        fluid2 = st.text_input("Fluid 2", "")
        mf2 = st.number_input("Mass ratio Fluid 2", value=0.0, step=0.1)
    with col3:
        fluid3 = st.text_input("Fluid 3", "")
        mf3 = st.number_input("Mass ratio Fluid 3", value=0.0, step=0.1)

    st.markdown("### Conditions")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        V = st.number_input("Vessel Volume [m³]", value=1.0, step=0.1)
    with c2:
        Pi_mbar = st.number_input("Initial Pressure [mbar]", value=830.0, step=10.0)
    with c3:
        Pf_mbar = st.number_input("Final Pressure [mbar]", value=50.0, step=5.0)
    with c4:
        t = st.number_input("Pump Down Time [s]", value=60.0, step=5.0)

    T_C = st.number_input("Fluid Temperature [°C]", value=25.0, step=1.0)

    if st.button("Calculate Pump-down Size", use_container_width=True):
        try:
            fluids = [f for f in [fluid1, fluid2, fluid3] if f.strip() != ""]
            mass_fracs = [mf1, mf2, mf3]

            result = pumpdown_sizing(fluids, mass_fracs, V, Pi_mbar, Pf_mbar, T_C, t)

            st.success("✅ Pump-down Results")
            st.write(f"**Pumpdown Classical Flow:** {result['Q_m3hr']:.2f} m³/hr  ({result['Q_Nm3hr']:.2f} Nm³/hr)")
            st.write(f"**Mixture Temperature:** {result['T_C']} °C")
            st.write(f"**M_mix:** {result['M_mix']:.3f} kg/kmol")
            st.write(f"**Density (at Pi):** {result['density']:.3f} kg/m³")
            st.write(f"**Viscosity (at Pi):** {result['viscosity']:.3e} Pa·s")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# ---------------- Continuous Operation Section ----------------
with tab2:
    st.subheader("Continuous Operation Sizing")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        P_mbar = st.number_input("Vessel Pressure [mbar]", value=200.0, step=5.0)
    with c2:
        T_C = st.number_input("Temperature [°C]", value=100.0, step=1.0)
    with c3:
        mdot_steam = st.number_input("Steam Flow [kg/h]", value=50.0, step=1.0)
    with c4:
        mdot_co2 = st.number_input("CO2 Flow [kg/h]", value=2.0, step=0.1)

    if st.button("Calculate Continuous Operation Size", use_container_width=True):
        try:
            result = continuous_operation_sizing(P_mbar, T_C, mdot_steam, mdot_co2)

            st.success("✅ Continuous Operation Results")
            st.write(f"**Required Pump Capacity:** {result['Vdot_m3hr']:.2f} m³/hr  ({result['Vdot_Nm3hr']:.2f} Nm³/hr)")
            st.write(f"**Mole Fractions:** Steam {result['y_steam']:.3f}, CO2 {result['y_co2']:.3f}")
            st.write(f"**Mixture Density:** {result['density']:.3f} kg/m³")
            st.write(f"**Mixture Viscosity:** {result['viscosity']:.3e} Pa·s")

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
