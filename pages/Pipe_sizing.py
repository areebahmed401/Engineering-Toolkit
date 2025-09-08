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

st.markdown("<h1>Pipe Sizing & Insulation</h1>", unsafe_allow_html=True)
st.markdown(
    "<p font-size: 16px;'>"
    "Estimate pipe sizing, pressure drops, insulation requirements, steam losses, and costs."
    "</p>", unsafe_allow_html=True
)

# ----------------- Tab Selection -----------------
tab1, tab2 = st.tabs(["Pipe Sizing", "Insulation Optimization"])

with tab1:
    # ----------------- Load Catalogs -----------------
    PIPE_CATALOG = pd.read_csv(Path("utils/pipe catalog.csv"))
    ELBOW_CATALOG = pd.read_csv(Path("utils/elbow catalog.csv"))

    pipe_cost_dict = dict(zip(PIPE_CATALOG["size"], PIPE_CATALOG["$/m"]))
    elbow_cost_dict = dict(zip(ELBOW_CATALOG["size"], ELBOW_CATALOG["$/piece"]))

    # ----------------- Input Section -----------------
    with st.expander("Fluid & Pipe Parameters", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            mass_flow_rate_hr = st.number_input("Mass flow rate [kg/hr]", value=3600.0)
            initial_pressure_bar = st.number_input("Initial pressure [bar a]", value=5.0)
            initial_temperature_c = st.number_input("Initial temperature [°C]", value=160.0)
            straight_length = st.number_input("Pipe length [m]", value=2500.0)
            include_loops = st.checkbox("Include expansion loops (every 100 m)", value=True)
        with c2:
            # Standard Sch 40 DN sizes
            standard_dn = [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300]

            min_dn = st.selectbox("Minimum DN size", standard_dn, index=standard_dn.index(100))
            max_dn = st.selectbox("Maximum DN size", standard_dn, index=standard_dn.index(300))

            if standard_dn.index(min_dn) > standard_dn.index(max_dn):
                st.warning("⚠️ Minimum DN cannot be larger than Maximum DN. Please adjust.")

            fluids = sorted(CP.get_global_param_string("fluids_list").split(","))
            fluid = st.selectbox("Fluid", fluids, index=fluids.index("Water"))
            material = st.selectbox("Pipe material", list(PIPE_MATERIALS.keys()))
            roughness = PIPE_MATERIALS[material]

    with st.expander("Fittings"):
        fitting_labels = {
            "90_elbow": "90° Elbow", "45_elbow": "45° Elbow", "globe_valve": "Globe Valve",
            "gate_valve": "Gate Valve", "ball_valve": "Ball Valve", "check_valve": "Check Valve",
            "tee_run": "Tee (Run)", "tee_branch": "Tee (Branch)"
        }
        cols = st.columns(4)

        # Calculate minimum number of 90° elbows required for expansion loops
        min_90_elbows = math.floor(straight_length / 100.0) * 4 if include_loops else 0

        fittings = {}
        for i, (key, label) in enumerate(fitting_labels.items()):
            with cols[i % 4]:
                if key == "90_elbow":
                    fittings[key] = st.number_input(
                        label,
                        min_value=min_90_elbows,
                        value=min_90_elbows,
                        step=1,
                        key=key
                    )
                    if fittings[key] == min_90_elbows and min_90_elbows > 0:
                        st.info(
                            f"Minimum {min_90_elbows} elbows required for expansion loops. "
                            "Increase this value if you have additional elbows in the system."
                        )
                else:
                    fittings[key] = st.number_input(label, min_value=0, value=0, step=1, key=key)

    with st.expander("Constraints"):
        c1, c2, c3 = st.columns(3)
        vmin = c1.number_input("Min velocity [m/s]", value=10.0)
        vmax = c2.number_input("Max velocity [m/s]", value=30.0)
        dpmax = c3.number_input("Max pressure drop [mbar]", value=1000.0)

    with st.expander("Insulation"):
        
        use_insulation = st.checkbox("Include insulation calculation", value=True)
        
        c1, c2, c3 = st.columns(3)
        if use_insulation:
            atm_temp = c1.number_input("Atmospheric temperature [°C]", value=25.0)
            q_max = c2.number_input("Acceptable heat loss [W/m]", value=30.0)
            k_ins = c3.number_input("Insulation k [W/m·K]", value=0.04)
        else:
            atm_temp = q_max = k_ins = None

    with st.expander("Costing"):
        use_costing = st.checkbox("Include pipe costing", value=True)

        if use_costing:
            source = st.radio("Select Source", ["China", "Local"], horizontal=True)

            if source == "China":
                steel_cost_per_ton = st.number_input("Steel Cost [$/ton]", value=640.0)
                include_customs = st.checkbox("Apply 40% Customs Duty (China only)", value=True)

            st.markdown("### Insulation, Cladding & Painting (applies to both sources)")
            c1, c2, c3 = st.columns(3)
            with c1:
                insulation_cost = st.number_input("Fiberglass 100mm [$/m]", value=16.9)
                cladding_cost = st.number_input("Aluminum Cladding [$/m]", value=17.6)
            with c2:
                insulation_labour = st.number_input("Insulation Labour [$/m]", value=2.69)
                painting_labour = st.number_input("Painting Labour [$/m]", value=2.40)
            with c3:
                painting_cost = st.number_input("Painting Cost [$/m]", value=3.70)

    # ----------------- Run Button -----------------
    if st.button("Run Calculation", width="stretch"):
        try:
            mass_flow_rate = mass_flow_rate_hr / 3600.0  # kg/s
            P_pa = initial_pressure_bar * 1e5
            T_k = initial_temperature_c + 273.15

            density = CP.PropsSI('D', 'T', T_k, 'P', P_pa, fluid)
            viscosity = CP.PropsSI('V', 'T', T_k, 'P', P_pa, fluid)

            results = []
            dn_range = standard_dn[standard_dn.index(min_dn): standard_dn.index(max_dn) + 1]

            total_len_ref = 0.0
            eq_len_ref = 0.0
            total_cost_ref = 0.0

            for d_mm in dn_range:
                d = d_mm / 1000.0
                A = math.pi * (d / 2) ** 2
                v = mass_flow_rate / (A * density)
                Re = density * v * d / viscosity
                f = colebrook_white(Re, roughness, d)

                # Expansion loops
                loops_count = math.floor(straight_length / 100.0) if include_loops else 0
                loop_length = loops_count * (21 * d)
                extra_elbows = loops_count * 4

                # Calculate total number of 90° elbows for this DN
                elbows_user = fittings.get("90_elbow", 0)
                elbows_total = elbows_user + extra_elbows if include_loops else elbows_user

                eq_len, _ = get_equivalent_length(fittings, d)
                total_len = straight_length + eq_len + loop_length

                # Ensure fittings dict reflects the correct number for calculation
                fittings_for_calc = fittings.copy()
                fittings_for_calc["90_elbow"] = elbows_total

                dp = convert_headtombar(darcy_weisbach(f, total_len, v, d), density)

                pipe_mass = pipe_mass_per_m(d_mm)
                total_weight = pipe_mass * total_len

                t_mm = calc_insulation_thickness(d, initial_temperature_c, atm_temp, q_max, k_ins,material) if use_insulation else None
                ins_display = "-" if t_mm is None else (f"{t_mm:.1f}" if math.isfinite(t_mm) else "Too thick")

                # Costing
                pipe_cost_m = elbow_cost = total_cost = "-"
                if use_costing:
                    if source == "Local":
                        pipe_cost_m = pipe_cost_dict.get(d_mm, 0)
                        elbow_cost = elbow_cost_dict.get(d_mm, 0) * elbows_total
                        base_cost = (pipe_cost_m * straight_length) + elbow_cost
                    else:  # China
                        pipe_cost_m = (pipe_mass / 1000.0) * steel_cost_per_ton
                        elbow_cost = china_elbow_mass(d_mm) * elbows_total
                        base_cost = pipe_cost_m * straight_length + elbow_cost
                        if include_customs:
                            base_cost *= 1.4

                    extras_per_m = insulation_cost + cladding_cost + insulation_labour + painting_labour + painting_cost
                    extras_total = extras_per_m * straight_length
                    total_cost = base_cost + extras_total

                results.append({
                    "Diameter (DN)": f"DN{d_mm}",
                    "Pipe Mass (kg/m)": f"{pipe_mass:.2f}",
                    "Velocity (m/s)": v,
                    "Pressure Drop (mbar)": dp,
                    "Eq. Length (m)": f"{(eq_len + loop_length):.2f}",
                    "Total Length (m)": f"{total_len:.2f}",
                    "Insulation (mm)": ins_display,
                    "Pipe Cost [USD/m]": f"{pipe_cost_m:.2f}" if pipe_cost_m != "-" else "-",
                    "Elbow Cost [USD]": f"{elbow_cost:.2f}" if elbow_cost != "-" else "-",
                    "Total Cost [USD]": "${:,.2f}".format(total_cost) if total_cost != "-" else "-",
                    "Total Weight (kg)": f"{total_weight:.2f}",
                    "Num 90° Elbows": elbows_total,
                    "Acceptable": vmin <= v <= vmax and dp <= dpmax
                })

                # Save ref values for cards (use mid-size DN as representative)
                if d_mm == dn_range[len(dn_range)//2]:
                    total_len_ref = total_len
                    eq_len_ref = eq_len + loop_length
                    total_cost_ref = total_cost if total_cost != "-" else 0

            df = pd.DataFrame(results)
            df_display = df.drop(columns=["Acceptable"]) if "Acceptable" in df.columns else df

            st.session_state["results_df"] = df
            st.session_state["results_df_display"] = df_display

            # ---------- Steam Loss Calculation (once only) ----------
            steam_loss_pct = steam_loss_hr = None
            if use_insulation and q_max and q_max > 0:
                try:
                    h_vap = CP.PropsSI('H', 'T', T_k, 'Q', 1, fluid)
                    h_liq = CP.PropsSI('H', 'T', T_k, 'Q', 0, fluid)
                    h_fg = h_vap - h_liq

                    Q_total = q_max * straight_length  # W
                    m_loss = Q_total / h_fg  # kg/s
                    steam_loss_pct = (m_loss / mass_flow_rate) * 100
                    steam_loss_hr = m_loss * 3600  # kg/hr

                    st.session_state["steam_loss_pct"] = steam_loss_pct
                    st.session_state["steam_loss_hr"] = steam_loss_hr
                except Exception:
                    st.session_state["steam_loss_pct"] = None
                    st.session_state["steam_loss_hr"] = None

            # Save global stats
            st.session_state["summary"] = {
                "Total Length": total_len_ref,
                "Eq Length": eq_len_ref,
                "Total Cost": total_cost_ref
            }

        except Exception as e:
            st.error(f"Error: {e}")


    # ----------------- Key Parameters -----------------
    st.markdown("### Key Parameters")

    if "results_df" in st.session_state:
        df = st.session_state["results_df"]

        # Pipe size selector
        selected_dn = st.selectbox("Select Pipe Size (DN):", df["Diameter (DN)"].unique())

        # Extract row for selected DN
        row = df[df["Diameter (DN)"] == selected_dn].iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Velocity", f"{row['Velocity (m/s)']:.2f}", "m/s")
        col2.metric("Pressure Drop", f"{row['Pressure Drop (mbar)']:.1f}", "mbar")
        col3.metric("Total Length", f"{float(row['Total Length (m)']):.1f}", "m")
        col4.metric("Pipe Mass", f"{row['Pipe Mass (kg/m)']}", "kg/m")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Total Weight", f"{row['Total Weight (kg)']}", "kg")
        col6.metric("Insulation", row["Insulation (mm)"], "mm")
        col7.metric("Eq. Length", f"{float(row['Eq. Length (m)']):.1f}", "m")
        col8.metric("Number of 90° Elbows", f"{row['Num 90° Elbows']}", "pieces")

        # Steam loss (calculated once globally)
        if "steam_loss_pct" in st.session_state:
            col9, col10, col11, col12 = st.columns(4)
            col9.metric("Steam Loss (%)", f"{st.session_state['steam_loss_pct']:.2f}", "%")
            col10.metric("Steam Loss", f"{st.session_state['steam_loss_hr']:.1f}", "kg/hr")
            col11.metric("Total Cost", f"${st.session_state['summary']['Total Cost']:.2f}", "USD")
            col12.metric("Number of Expansion Loops", f"{math.floor(straight_length / 100) if include_loops else 0}", "loops")

    # ----------------- Results -----------------
    if "results_df_display" in st.session_state:
        df_display = st.session_state["results_df_display"]

        st.markdown("<h3>Results Details</h3>", unsafe_allow_html=True)
        st.dataframe(
            df_display.style.set_properties(**{"text-align": "center"}).set_table_styles(
                [{"selector": "th", "props": [("text-align", "center")]}]
            ),
            width='stretch'
        )

        st.markdown("<h3>Velocity, Pressure Drop & Cost vs Pipe Size</h3>", unsafe_allow_html=True)

        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.set_xlabel('Pipe Diameter (DN)')

        ax1.set_ylabel('Velocity [m/s]', color='blue')
        ax1.plot(df_display["Diameter (DN)"], df_display["Velocity (m/s)"], marker='o', color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')

        ax2 = ax1.twinx()
        ax2.set_ylabel('Pressure Drop [mbar]', color='red')
        ax2.plot(df_display["Diameter (DN)"], df_display["Pressure Drop (mbar)"], marker='s', color='red')
        ax2.tick_params(axis='y', labelcolor='red')

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        ax3.set_ylabel('Total Cost [USD]', color='green')

        try:
            total_cost_values = df_display["Total Cost [USD]"].replace('[\\$,]', '', regex=True).astype(float)
            ax3.plot(df_display["Diameter (DN)"], total_cost_values, marker='^', color='green')
            ax3.tick_params(axis='y', labelcolor='green')
        except Exception:
            pass

        fig.tight_layout()
        st.pyplot(fig)
        
        
# ----------------- Insulation Optimization ----------------- 

with tab2:
    st.markdown("<h3>Insulation Optimization</h3>", unsafe_allow_html=True)

    if "results_df" in st.session_state:
        # Parameters for optimization
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_dn = st.selectbox(
                "Select Pipe Size (DN):", 
                df["Diameter (DN)"].unique(),
                key="insulation_opt"
            )
            thickness_step = st.number_input("Thickness Step [mm]", value=5.0, min_value=1.0)
        
        with col2:
            heat_loss_threshold = st.number_input(
                "Heat Loss Reduction Threshold [W/m]", 
                value=3.0,
                help="Minimum reduction in heat loss per thickness step to continue adding insulation"
            )
            max_thickness = st.number_input("Maximum Thickness [mm]", value=500.0)
        
        with col3:
            safety_margin = st.number_input(
                "Safety Margin [%]", 
                value=10.0,
                help="Additional thickness as percentage of optimal"
            )

        if st.button("Optimize Insulation", width="stretch"):
            # Extract diameter in meters
            d_mm = float(selected_dn.replace("DN", ""))
            d = d_mm / 1000.0

            # Generate range of insulation thicknesses
            thicknesses = np.arange(thickness_step, max_thickness + thickness_step, thickness_step)
            heat_losses = []
            heat_loss_diffs = []
            
            # Calculate heat losses for each thickness
            for t in thicknesses:
                t_m = t / 1000  # Convert to meters
                dT = initial_temperature_c - atm_temp
                r1 = d/2
                r2 = r1 + t_m
                q = 2 * math.pi * k_ins * dT / math.log(r2/r1)  # W/m
                heat_losses.append(q)
            
            # Calculate reduction in heat loss for each step increase
            heat_loss_diffs = [heat_losses[i] - heat_losses[i+1] for i in range(len(heat_losses)-1)]
            
            # Find optimal thickness
            optimal_idx = next((i for i, diff in enumerate(heat_loss_diffs) 
                              if diff < heat_loss_threshold), len(heat_losses)-1)
            optimal_thickness = thicknesses[optimal_idx]
            
            # Apply safety margin
            final_thickness = optimal_thickness * (1 + safety_margin/100)
            
            # Display results
            st.markdown("### Optimization Results")
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Base Optimal Thickness", 
                f"{optimal_thickness:.1f}", 
                "mm"
            )
            col2.metric(
                "Final Thickness (with safety)", 
                f"{final_thickness:.1f}",
                f"+{(final_thickness - optimal_thickness):.1f} mm"
            )
            col3.metric(
                "Heat Loss at Optimum", 
                f"{heat_losses[optimal_idx]:.1f}", 
                "W/m"
            )
            
            # Plot results
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
            
            # Heat loss vs thickness
            ax1.set_xlabel('Insulation Thickness [mm]')
            ax1.set_ylabel('Heat Loss [W/m]')
            ax1.plot(thicknesses, heat_losses, color='red', label='Heat Loss')
            ax1.axvline(x=optimal_thickness, color='green', linestyle='--', 
                       label=f'Optimal ({optimal_thickness:.1f} mm)')
            ax1.axvline(x=final_thickness, color='blue', linestyle='--',
                       label=f'With Safety ({final_thickness:.1f} mm)')
            ax1.grid(True)
            ax1.legend()
            
            # Heat loss reduction vs thickness
            ax2.set_xlabel('Insulation Thickness [mm]')
            ax2.set_ylabel(f'Heat Loss Reduction [W/m per {thickness_step:.0f}mm]')
            ax2.plot(thicknesses[:-1], heat_loss_diffs, color='blue', 
                    label='Incremental Benefit')
            ax2.axhline(y=heat_loss_threshold, color='red', linestyle='--', 
                       label=f'{heat_loss_threshold} W/m threshold')
            ax2.axvline(x=optimal_thickness, color='green', linestyle='--')
            ax2.axvline(x=final_thickness, color='blue', linestyle='--')
            ax2.grid(True)
            ax2.legend()
            
            fig.tight_layout()
            st.pyplot(fig)
    else:
        st.warning("Please run pipe sizing calculation first to enable insulation optimization.")


