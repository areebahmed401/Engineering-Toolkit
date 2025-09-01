# pages/Pump_sizing.py
import streamlit as st
import CoolProp.CoolProp as CP
import math
import matplotlib.pyplot as plt

st.set_page_config(page_title="Pump Sizing Tool", layout="wide")
st.title("🛠 Pump Sizing Tool")

# ----------------- Pump Sizing Function -----------------
def size_pump(fluid, demand_flow, distance, pump_pressure, pump_max_flow, T_C, P_bar, elevations, D, plot=False):
    flow_m3s = demand_flow / 1000 / 60
    T = T_C + 273.15
    P = P_bar * 1e5
    rho = CP.PropsSI("D", "T", T, "P", P, fluid)
    mu = CP.PropsSI("V", "T", T, "P", P, fluid)
    A = math.pi * D**2 / 4
    v = flow_m3s / A
    Re = rho * v * D / mu
    f = 64 / Re if Re < 2000 else 0.316 / (Re**0.25)

    # Segments
    segments = len(elevations) - 1
    seg_length = distance / segments if segments > 0 else distance
    total_head = total_dp = 0
    for i in range(segments):
        dp = f * (seg_length / D) * (rho * v**2 / 2)
        head_loss = dp / (rho * 9.81)
        elev_diff = elevations[i+1] - elevations[i]
        total_head += head_loss + elev_diff
        total_dp += dp + elev_diff*rho*9.81

    required_head = total_head
    required_pressure = total_dp
    can_deliver_flow = demand_flow <= pump_max_flow
    can_deliver_pressure = required_pressure <= pump_pressure*1e5

    # System & pump curves
    flow_rates = [q for q in range(0, int(pump_max_flow)+1, max(1,int(pump_max_flow/20)))]
    system_heads = []
    elev_diff_total = elevations[-1] - elevations[0] if len(elevations)>1 else 0
    for q in flow_rates:
        if q == 0:
            system_heads.append(float('inf'))
            continue
        q_m3s = q / 1000 / 60
        vq = q_m3s / A
        Req = rho * vq * D / mu
        fq = 64 / Req if Req < 2000 else 0.316 / (Req**0.25)
        dpq = fq * (distance / D) * (rho * vq**2 / 2)
        system_heads.append(dpq/(rho*9.81) + elev_diff_total)

    # Quadratic pump curve: max head at zero flow, zero head at max flow
    pump_heads = [(pump_pressure*1e5)/(rho*9.81) * (1 - (q/pump_max_flow)**2) for q in flow_rates]


    if plot:
        fig, ax1 = plt.subplots(figsize=(6,4))  # Reduced figure size
        ax1.plot(flow_rates, system_heads, label="System Curve", color="blue", linewidth=2)
        ax1.plot(flow_rates, pump_heads, label="Pump Curve", color="red", linewidth=2)

       
        ax1.set_xlabel("Flow (L/min)")
        ax1.set_ylabel("Head (m)")
        ax1.grid(True)
        ax2 = ax1.twinx()
        yticks = ax1.get_yticks()
        ax2.set_ylim(ax1.get_ylim())
        ax2.set_yticks(yticks)
        ax2.set_yticklabels([f"{(rho*9.81*h)/1e5:.2f}" for h in yticks])
        ax2.set_ylabel("Pressure (bar)")
        ax1.legend(loc="best")
        st.pyplot(fig, use_container_width=True)

    result = {
        "Density [kg/m³]": rho,
        "Viscosity [Pa.s]": mu,
        "Reynolds Number": Re,
        "Friction Factor": f,
        "Velocity [m/s]": v,
        "Total Head Loss + Elevation [m]": required_head,
        "Total Pressure Drop [bar]": required_pressure/1e5,
        "Pump Flow OK": can_deliver_flow,
        "Pump Pressure OK": can_deliver_pressure
    }

    return result

# ----------------- Inputs -----------------
st.subheader("Fluid & Operating Conditions")
col1, col2, col3 = st.columns(3)
with col1:
    fluid_list = CP.get_global_param_string("fluids_list").split(',')
    fluid = st.selectbox("Fluid", options=fluid_list, index=fluid_list.index("Water") if "Water" in fluid_list else 0)
    T_C = st.number_input("Fluid Temperature (°C)", value=25.0)
    P_bar = st.number_input("Fluid Pressure at Suction (bar a)", value=1.0)
with col2:
    demand_flow = st.number_input("Demand Flow (L/min)", value=10.0)
    distance = st.number_input("Pipe Length (m)", value=50.0)
    pump_pressure = st.number_input("Pump Max Pressure (bar)", value=3.9)
with col3:
    pump_max_flow = st.number_input("Pump Max Flow (L/min)", value=35.0)
    elevations_str = st.text_input("Elevation Points (m, comma-separated)", value="0,0")
    D_mm = st.number_input("Pipe Diameter (mm)", value=25.4)

if st.button("Calculate & Plot"):
    try:
        elevations = [float(x) for x in elevations_str.split(',')]
        D = D_mm / 1000
        result = size_pump(fluid, demand_flow, distance, pump_pressure, pump_max_flow, T_C, P_bar, elevations, D, plot=True)
        st.subheader("Pump Sizing Results")
        st.table(result)

        # ✅ Green alert if both flow and pressure are OK
        if result["Pump Flow OK"] and result["Pump Pressure OK"]:
            st.success("✅ Pump can deliver the required flow and pressure.")
        else:
            st.warning("⚠️ Pump may not meet the required flow or pressure.")

    except Exception as e:
        st.error(f"Error: {e}")
