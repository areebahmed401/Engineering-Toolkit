import streamlit as st
import numpy as np
import CoolProp.CoolProp as CP
import math
import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    ELECTRIC_VALVE_CATALOG = pd.read_csv(Path("utils/electric_valve_catalog.csv"))
    PNEUMATIC_VALVE_CATALOG = pd.read_csv(Path("utils/pneumatic_valve_catalog.csv"))

    pipe_cost_dict = dict(zip(PIPE_CATALOG["size"], PIPE_CATALOG["$/m"]))
    elbow_cost_dict = dict(zip(ELBOW_CATALOG["size"], ELBOW_CATALOG["$/piece"]))
    electric_valve_cost_dict = {}
    pneumatic_valve_cost_dict = {}
    
    # Create dictionaries for valve costs with DN size as key
    for size, cost in zip(ELECTRIC_VALVE_CATALOG["size"], ELECTRIC_VALVE_CATALOG["cost"]):
        dn = int(size.split("_")[0].replace("DN", ""))
        material = size.split("_")[1]
        if material == "CS":  # Using carbon steel costs as default
            electric_valve_cost_dict[dn] = cost
    
    for size, cost in zip(PNEUMATIC_VALVE_CATALOG["size"], PNEUMATIC_VALVE_CATALOG["cost"]):
        dn = int(size.split("_")[0].replace("DN", ""))
        material = size.split("_")[1]
        if material == "CS":  # Using carbon steel costs as default
            pneumatic_valve_cost_dict[dn] = cost

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
            valve_type = st.radio("Valve Type", ["Pneumatic", "Electric"], horizontal=True)

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
                painting_labour = st.number_input("Painting Labour [$/m²]", value=3.0)
            with c3:
                painting_cost = st.number_input("Painting Cost [$/m²]", value=3.70)

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

                # Calculate surface area and surface treatment costs
                extras_total = 0
                if use_costing and use_insulation and t_mm not in [None, "Too thick"]:
                    try:
                        thickness_ratio = float(t_mm) / 100.0
                        
                        # Get pipe OD
                        pipe_od_mm = float(PIPE_CATALOG[PIPE_CATALOG["size"] == d_mm]["OD (mm)"].values[0]) if "OD (mm)" in PIPE_CATALOG else d_mm
                        
                        # Calculate outer diameter with insulation
                        outer_diameter_m = (pipe_od_mm + 2 * float(t_mm)) / 1000.0
                        surface_area_m2 = math.pi * outer_diameter_m * straight_length
                        
                        # Apply 6/10th rule for insulation and cladding
                        insulation_material_cost = insulation_cost * (thickness_ratio ** 0.6)
                        cladding_material_cost = cladding_cost * (thickness_ratio ** 0.6)
                        insulation_labor_scaled = insulation_labour * (thickness_ratio ** 0.3)
                        
                        # Calculate total costs
                        insulation_total = (insulation_material_cost + insulation_labor_scaled) * straight_length
                        cladding_total = cladding_material_cost * straight_length
                        painting_total = (painting_cost + painting_labour) * surface_area_m2
                        
                        extras_total = insulation_total + cladding_total + painting_total
                    except:
                        extras_total = 0

                # Costing
                pipe_cost_m = elbow_cost = valve_cost = total_cost = "-"
                if use_costing:
                    if source == "Local":
                        pipe_cost_m = pipe_cost_dict.get(d_mm, 0)
                        elbow_cost = elbow_cost_dict.get(d_mm, 0) * elbows_total
                        
                        # Calculate valve costs based on valve type
                        total_valves = (
                            fittings_for_calc.get("globe_valve", 0) +
                            fittings_for_calc.get("gate_valve", 0) +
                            fittings_for_calc.get("ball_valve", 0) +
                            fittings_for_calc.get("check_valve", 0)
                        )
                        
                        if valve_type == "Electric":
                            valve_unit_cost = electric_valve_cost_dict.get(d_mm, 0)
                        else:  # Pneumatic
                            valve_unit_cost = pneumatic_valve_cost_dict.get(d_mm, 0)
                            
                        valve_cost = valve_unit_cost * total_valves
                        base_cost = (pipe_cost_m * straight_length) + elbow_cost + valve_cost
                    else:  # China
                        pipe_cost_m = (pipe_mass / 1000.0) * steel_cost_per_ton
                        elbow_cost = china_elbow_mass(d_mm) * elbows_total
                        
                        # Calculate valve costs based on valve type
                        total_valves = (
                            fittings_for_calc.get("globe_valve", 0) +
                            fittings_for_calc.get("gate_valve", 0) +
                            fittings_for_calc.get("ball_valve", 0) +
                            fittings_for_calc.get("check_valve", 0)
                        )
                        
                        if valve_type == "Electric":
                            valve_unit_cost = electric_valve_cost_dict.get(d_mm, 0)
                        else:  # Pneumatic
                            valve_unit_cost = pneumatic_valve_cost_dict.get(d_mm, 0)
                            
                        valve_cost = valve_unit_cost * total_valves
                        base_cost = pipe_cost_m * straight_length + elbow_cost + valve_cost
                        if include_customs:
                            base_cost *= 1.4

                # Calculate surface area and surface treatment costs
                extras_total = 0
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
                    "Valve Cost [USD]": f"{valve_cost:.2f}" if valve_cost != "-" else "-",
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

        # Calculate costs
        pipe_cost = float(row["Pipe Cost [USD/m]"]) * straight_length if row["Pipe Cost [USD/m]"] != "-" else 0
        elbow_cost = float(row["Elbow Cost [USD]"]) if row["Elbow Cost [USD]"] != "-" else 0
        valve_cost = float(row["Valve Cost [USD]"]) if row["Valve Cost [USD]"] != "-" else 0
        equipment_cost = pipe_cost + elbow_cost + valve_cost
        
            # Calculate scaled insulation and cladding costs using 6/10th rule
            # Base costs are for 100mm thickness
        insulation_total = 0
        cladding_total = 0
        painting_total = 0

        if row["Insulation (mm)"] not in ["-", "Too thick"]:
            try:
                actual_thickness = float(row["Insulation (mm)"])
                thickness_ratio = actual_thickness / 100.0  # ratio to base thickness of 100mm

                # Apply 6/10th rule for material costs
                insulation_material_cost = insulation_cost * (thickness_ratio ** 0.6)
                cladding_material_cost = cladding_cost * (thickness_ratio ** 0.6)

                # Labor costs scale less aggressively - using 0.3 exponent
                insulation_labor_scaled = insulation_labour * (thickness_ratio ** 0.3)

                insulation_total = (insulation_material_cost + insulation_labor_scaled) * straight_length
                cladding_total = cladding_material_cost * straight_length

                # --- Painting cost per m2 of insulated pipe ---
                # Get pipe OD for selected DN
                d_mm = float(selected_dn.replace("DN", ""))
                pipe_row = PIPE_CATALOG[PIPE_CATALOG["size"] == d_mm]
                if not pipe_row.empty and "OD (mm)" in pipe_row:
                    pipe_od_mm = float(pipe_row["OD (mm)"].values[0])
                else:
                    # Approximate OD as DN if not found
                    pipe_od_mm = d_mm

                # Calculate outer diameter of insulation (in meters)
                outer_diameter_m = (pipe_od_mm + 2 * actual_thickness) / 1000.0

                # Surface area of insulated pipe (π * D * L)
                surface_area_m2 = math.pi * outer_diameter_m * straight_length

                painting_total = (painting_cost + painting_labour) * surface_area_m2

            except ValueError:
                pass  # Keep default zero values if conversion fails

        surface_treatment_total = insulation_total + cladding_total + painting_total
        total_cost = equipment_cost + surface_treatment_total
        if source == "China" and include_customs:
            customs_cost = equipment_cost * 0.4
            total_cost += customs_cost
        else:
            customs_cost = 0

        # Calculate total valves
        total_valves = sum(fittings.get(key, 0) for key in ["globe_valve", "gate_valve", "ball_valve", "check_valve"])

        with st.expander("Key Output Parameters", expanded=True):
            # Flow Parameters
            st.markdown("##### Flow Parameters")
            cols = st.columns(5)
            # Color velocity based on constraints
            if row['Velocity (m/s)'] < vmin:
                cols[0].metric(
                    label="Velocity",
                    value=f"{row['Velocity (m/s)']:.2f} m/s",
                    delta="⚠️ Below min",
                    delta_color="inverse"
                )
            elif row['Velocity (m/s)'] > vmax:
                cols[0].metric(
                    label="Velocity",
                    value=f"{row['Velocity (m/s)']:.2f} m/s",
                    delta="⚠️ Above max",
                    delta_color="inverse"
                )
            else:
                cols[0].metric(
                    label="Velocity",
                    value=f"{row['Velocity (m/s)']:.2f} m/s"
                )

            # Color pressure drop based on max constraint
            if row['Pressure Drop (mbar)'] > dpmax:
                cols[1].metric(
                    label="Pressure Drop",
                    value=f"{row['Pressure Drop (mbar)']:.1f} mbar",
                    delta="⚠️ Above max",
                    delta_color="inverse"
                )
            else:
                cols[1].metric(
                    label="Pressure Drop",
                    value=f"{row['Pressure Drop (mbar)']:.1f} mbar"
                )

            # Show steam loss with percentage change
            steam_loss_hr = st.session_state.get('steam_loss_hr', 0)
            steam_loss_pct = st.session_state.get('steam_loss_pct', 0)
            cols[2].metric(
                label="Steam Loss",
                value=f"{steam_loss_hr:.1f} kg/hr",
                delta=f"-{steam_loss_pct:.1f}% of flow",
                delta_color="inverse"
            )

            # Color insulation based on existence
            insulation_value = row["Insulation (mm)"]
            if insulation_value == "-":
                cols[3].metric(
                    label="Insulation",
                    value=f"{insulation_value} mm",
                    delta="Not applied",
                    delta_color="off"
                )
            elif insulation_value == "Too thick":
                cols[3].metric(
                    label="Insulation",
                    value=f"{insulation_value}",
                    delta="⚠️ Review needed",
                    delta_color="off"
                )
            else:
                cols[3].metric(
                    label="Insulation",
                    value=f"{insulation_value} mm"
                )

            # Weight indicator
            cols[4].metric(
                label="Total Weight",
                value=f"{row['Total Weight (kg)']} kg",
                delta="Including fittings",
                delta_color="off"
            )

            # Physical Parameters
            st.markdown("##### Physical Parameters")
            cols = st.columns(5)
            
            # Show total length with equivalent length addition
            eq_length = float(row['Eq. Length (m)'])
            total_length = float(row['Total Length (m)'])
            
                # Calculate surface area and treatment costs per meter for display
            surface_area_per_m = 0
            if use_insulation and row["Insulation (mm)"] not in ["-", "Too thick"]:
                try:
                    actual_thickness = float(row["Insulation (mm)"])
                    d_mm = float(selected_dn.replace("DN", ""))
                    pipe_row = PIPE_CATALOG[PIPE_CATALOG["size"] == d_mm]
                    if not pipe_row.empty and "OD (mm)" in pipe_row:
                        pipe_od_mm = float(pipe_row["OD (mm)"].values[0])
                    else:
                        pipe_od_mm = d_mm
                    outer_diameter_m = (pipe_od_mm + 2 * actual_thickness) / 1000.0
                    surface_area_per_m = math.pi * outer_diameter_m
                except ValueError:
                    pass
                    
            cols[0].metric(
                label="Total Length",
                value=f"{total_length:.1f} m",
                delta=f"Surface area: {surface_area_per_m:.2f} m²/m" if surface_area_per_m > 0 else None,
                delta_color="off"
            )

            # Show fittings with their counts
            cols[1].metric(
                label="90° Elbows",
                value=f"{row['Num 90° Elbows']} pcs",
                delta=f"{min_90_elbows} from loops" if include_loops else None
            )
            
            # Show valve count and type
            if total_valves > 0:
                cols[2].metric(
                    label="Total Valves",
                    value=f"{total_valves} pcs",
                    delta=f"{valve_type} type"
                )
            else:
                cols[2].metric(
                    label="Total Valves",
                    value=f"{total_valves} pcs"
                )

            # Show expansion loops
            cols[3].metric(
                label="Exp. Loops",
                value=f"{math.floor(straight_length / 100) if include_loops else 0} pcs",
                delta="Every 100m" if include_loops else "None"
            )
            
            # Calculate pipe sections
            pipe_sections = math.ceil(straight_length / 6)  # Assuming 6m pipe sections
            cols[4].metric(
                label="Pipe Sections",
                value=f"{pipe_sections} pcs",
                delta="6m each",
                delta_color="off"
            )

        with st.expander("Cost Breakdown", expanded=True):
            # Equipment Costs
            st.markdown("##### Equipment Costs")
            cols = st.columns(4)
            cols[0].metric(
                label="Pipe Cost",
                value=f"${pipe_cost:,.0f}",
                delta=f"${pipe_cost/straight_length:,.1f}/m"
            )
            cols[1].metric(
                label="Elbow Cost",
                value=f"${elbow_cost:,.0f}",
                delta=f"${elbow_cost/max(1,row['Num 90° Elbows']):,.1f}/pc"
            )
            
            if total_valves > 0:
                cols[2].metric(
                    label="Valve Cost",
                    value=f"${valve_cost:,.0f}",
                    delta=f"${valve_cost/total_valves:,.1f}/pc"
                )
            else:
                cols[2].metric(
                    label="Valve Cost",
                    value=f"${valve_cost:,.0f}"
                )
                
            cols[3].metric(
                label="Equipment Total",
                value=f"${equipment_cost:,.0f}",
                delta=f"{(equipment_cost/total_cost*100):.1f}% of total"
            )

            # Surface Treatment Costs
            st.markdown("##### Surface Treatment")
            cols = st.columns(4)
            cols[0].metric(
                label="Insulation",
                value=f"${insulation_total:,.0f}",
                delta=f"${(insulation_cost + insulation_labour):.1f}/m"
            )
            cols[1].metric(
                label="Cladding",
                value=f"${cladding_total:,.0f}",
                delta=f"${cladding_cost:.1f}/m"
            )
            # Calculate cost per meter for display
            if surface_area_per_m > 0:
                painting_cost_per_m = (painting_cost + painting_labour) * surface_area_per_m
                cols[2].metric(
                    label="Painting",
                    value=f"${painting_total:,.0f}",
                    delta=f"${painting_cost_per_m:.2f}/m"
                )
            cols[3].metric(
                label="Surface Total",
                value=f"${surface_treatment_total:,.0f}",
                delta=f"{(surface_treatment_total/total_cost*100):.1f}% of total"
            )

            # Total Project Cost with custom styling
            st.markdown("##### Project Total")
            cols = st.columns(3)
            cols[0].metric(
                label="Equipment Cost",
                value=f"${equipment_cost:,.0f}",
                delta=f"{(equipment_cost/total_cost*100):.1f}%",
                delta_color="off"
            )
            cols[1].metric(
                label="Surface Treatment",
                value=f"${surface_treatment_total:,.0f}",
                delta=f"{(surface_treatment_total/total_cost*100):.1f}%",
                delta_color="off"
            )
            
            if customs_cost > 0:
                cols[2].metric(
                    label="Customs (40%)",
                    value=f"${customs_cost:,.0f}",
                    delta=f"{(customs_cost/total_cost*100):.1f}%",
                    delta_color="off"
                )
            
            # Grand Total with custom styling
            st.metric(
                label="Total Project Cost",
                value=f"${total_cost:,.0f}",
                delta=f"${total_cost/straight_length:,.0f} per meter",
                delta_color="off"
            )

    # ----------------- Cost Visualization -----------------
    if "results_df" in st.session_state:
        with st.expander("Cost Breakdown Visualization", expanded=False):
            # Create tabs for different visualization types
            viz_tab1, viz_tab2, viz_tab3 = st.tabs(["Main Breakdown", "Equipment Details", "Size Comparison"])
            
            with viz_tab1:
                # Main cost breakdown in two columns
                col1, col2 = st.columns(2)
                
                with col1:
                    # Overall project breakdown pie chart
                    project_labels = []
                    project_values = []
                    
                    if equipment_cost > 0:
                        project_labels.append('Equipment')
                        project_values.append(equipment_cost)
                    if surface_treatment_total > 0:
                        project_labels.append('Surface Treatment')
                        project_values.append(surface_treatment_total)
                    if customs_cost > 0:
                        project_labels.append('Customs Duty')
                        project_values.append(customs_cost)
                    
                    if project_values:
                        fig_project = px.pie(
                            values=project_values,
                            names=project_labels,
                            title=f"Project Total: ${sum(project_values):,.0f}",
                            color_discrete_sequence=['#FF6B6B', '#4ECDC4', '#F0A500']
                        )
                        fig_project.update_traces(
                            textposition='inside', 
                            textinfo='percent+label',
                            hovertemplate='<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>'
                        )
                        fig_project.update_layout(
                            height=300,
                            margin=dict(t=50, b=0, l=0, r=0),
                            showlegend=True,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5
                            )
                        )
                        st.plotly_chart(fig_project, use_container_width=True)
                
                with col2:
                    # Detailed donut chart
                    if total_cost > 0:
                        detailed_labels = []
                        detailed_values = []
                        detailed_colors = []
                        
                        # Equipment components
                        if pipe_cost > 0:
                            detailed_labels.append('Pipe')
                            detailed_values.append(pipe_cost)
                            detailed_colors.append('#FF6B6B')
                        if elbow_cost > 0:
                            detailed_labels.append('Elbows')
                            detailed_values.append(elbow_cost)
                            detailed_colors.append('#FF8E53')
                        if valve_cost > 0:
                            detailed_labels.append('Valves')
                            detailed_values.append(valve_cost)
                            detailed_colors.append('#FF4757')
                        
                        # Surface treatment components
                        if insulation_total > 0:
                            detailed_labels.append('Insulation')
                            detailed_values.append(insulation_total)
                            detailed_colors.append('#4ECDC4')
                        if cladding_total > 0:
                            detailed_labels.append('Cladding')
                            detailed_values.append(cladding_total)
                            detailed_colors.append('#45B7D1')
                        if painting_total > 0:
                            detailed_labels.append('Painting')
                            detailed_values.append(painting_total)
                            detailed_colors.append('#3742FA')
                        
                        # Customs
                        if customs_cost > 0:
                            detailed_labels.append('Customs')
                            detailed_values.append(customs_cost)
                            detailed_colors.append('#F0A500')
                        
                        if detailed_values:
                            fig_donut = go.Figure(data=[go.Pie(
                                labels=detailed_labels,
                                values=detailed_values,
                                hole=0.5,
                                marker_colors=detailed_colors
                            )])
                            
                            fig_donut.update_traces(
                                textposition='inside',
                                textinfo='percent',
                                hovertemplate='<b>%{label}</b><br>$%{value:,.0f} (%{percent})<extra></extra>'
                            )
                            
                            fig_donut.update_layout(
                                title="Detailed Breakdown",
                                height=300,
                                margin=dict(t=50, b=0, l=0, r=0),
                                annotations=[dict(
                                    text=f'${sum(detailed_values):,.0f}',
                                    x=0.5, y=0.5,
                                    font_size=14,
                                    showarrow=False
                                )],
                                showlegend=True,
                                legend=dict(
                                    orientation="v",
                                    yanchor="middle",
                                    y=0.5,
                                    xanchor="left",
                                    x=1.02
                                )
                            )
                            
                            st.plotly_chart(fig_donut, use_container_width=True)
            
            with viz_tab2:
                # Equipment and surface treatment breakdown
                col1, col2 = st.columns(2)
                
                with col1:
                    # Equipment breakdown
                    equipment_labels = []
                    equipment_values = []
                    
                    if pipe_cost > 0:
                        equipment_labels.append('Pipe')
                        equipment_values.append(pipe_cost)
                    if elbow_cost > 0:
                        equipment_labels.append('Elbows')
                        equipment_values.append(elbow_cost)
                    if valve_cost > 0:
                        equipment_labels.append('Valves')
                        equipment_values.append(valve_cost)
                    
                    if equipment_values:
                        fig_equipment = px.pie(
                            values=equipment_values,
                            names=equipment_labels,
                            title=f"Equipment: ${sum(equipment_values):,.0f}",
                            color_discrete_sequence=['#FF6B6B', '#FF8E53', '#FF4757']
                        )
                        fig_equipment.update_traces(
                            textposition='inside', 
                            textinfo='percent+label',
                            hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>'
                        )
                        fig_equipment.update_layout(
                            height=300,
                            margin=dict(t=50, b=0, l=0, r=0),
                            showlegend=True,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=-0.3,
                                xanchor="center",
                                x=0.5
                            )
                        )
                        st.plotly_chart(fig_equipment, use_container_width=True)
                
                with col2:
                    # Surface treatment breakdown
                    if surface_treatment_total > 0:
                        surface_labels = []
                        surface_values = []
                        
                        if insulation_total > 0:
                            surface_labels.append('Insulation')
                            surface_values.append(insulation_total)
                        if cladding_total > 0:
                            surface_labels.append('Cladding')
                            surface_values.append(cladding_total)
                        if painting_total > 0:
                            surface_labels.append('Painting')
                            surface_values.append(painting_total)
                        
                        if surface_values:
                            fig_surface = px.pie(
                                values=surface_values,
                                names=surface_labels,
                                title=f"Surface Treatment: ${sum(surface_values):,.0f}",
                                color_discrete_sequence=['#4ECDC4', '#45B7D1', '#3742FA']
                            )
                            fig_surface.update_traces(
                                textposition='inside', 
                                textinfo='percent+label',
                                hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>'
                            )
                            fig_surface.update_layout(
                                height=300,
                                margin=dict(t=50, b=0, l=0, r=0),
                                showlegend=True,
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=-0.3,
                                    xanchor="center",
                                    x=0.5
                                )
                            )
                            st.plotly_chart(fig_surface, use_container_width=True)
            
            with viz_tab3:
                # Cost comparison across pipe sizes
                df_costs = st.session_state["results_df"].copy()
                
                cost_data = []
                for _, row in df_costs.iterrows():
                    dn = row["Diameter (DN)"]
                    total_cost_str = row["Total Cost [USD]"]
                    
                    if total_cost_str != "-" and isinstance(total_cost_str, str):
                        cost_value = float(total_cost_str.replace("$", "").replace(",", ""))
                        cost_data.append({"DN": dn, "Total Cost": cost_value})
                
                if cost_data:
                    cost_df = pd.DataFrame(cost_data)
                    
                    fig_comparison = px.bar(
                        cost_df,
                        x="DN",
                        y="Total Cost",
                        title="Total Project Cost by Pipe Size",
                        color="Total Cost",
                        color_continuous_scale="viridis",
                        text="Total Cost"
                    )
                    fig_comparison.update_traces(
                        texttemplate='$%{text:,.0f}',
                        textposition='outside',
                        hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
                    )
                    fig_comparison.update_layout(
                        height=350,
                        margin=dict(t=50, b=50, l=50, r=50),
                        xaxis_title="Pipe Diameter",
                        yaxis_title="Total Cost (USD)",
                        showlegend=True,
                        legend=dict(
                            title="Cost Range",
                            orientation="v",
                            yanchor="top",
                            y=0.98,
                            xanchor="left",
                            x=1.02
                        )
                    )
                    
                    st.plotly_chart(fig_comparison, use_container_width=True)

    # ----------------- Results -----------------
    if "results_df_display" in st.session_state:
        with st.expander("Output Details", expanded=False):
            df_display = st.session_state["results_df_display"]
            
            # Create tabs for results organization
            results_tab1, results_tab2 = st.tabs(["Performance Charts", "Data Table"])
            
            with results_tab1:
                st.markdown("##### Velocity, Pressure Drop & Cost vs Pipe Size")
                
                fig, ax1 = plt.subplots(figsize=(10, 6))
                ax1.set_xlabel('Pipe Diameter (DN)')

                ax1.set_ylabel('Velocity [m/s]', color='blue')
                line1 = ax1.plot(df_display["Diameter (DN)"], df_display["Velocity (m/s)"], marker='o', color='blue', label='Velocity [m/s]')
                ax1.tick_params(axis='y', labelcolor='blue')

                ax2 = ax1.twinx()
                ax2.set_ylabel('Pressure Drop [mbar]', color='red')
                line2 = ax2.plot(df_display["Diameter (DN)"], df_display["Pressure Drop (mbar)"], marker='s', color='red', label='Pressure Drop [mbar]')
                ax2.tick_params(axis='y', labelcolor='red')

                ax3 = ax1.twinx()
                ax3.spines["right"].set_position(("outward", 60))
                ax3.set_ylabel('Total Cost [USD]', color='green')

                line3 = []
                try:
                    total_cost_values = df_display["Total Cost [USD]"].replace('[\\$,]', '', regex=True).astype(float)
                    line3 = ax3.plot(df_display["Diameter (DN)"], total_cost_values, marker='^', color='green', label='Total Cost [USD]')
                    ax3.tick_params(axis='y', labelcolor='green')
                except Exception:
                    pass

                # Add combined legend
                lines = line1 + line2 + line3
                labels = [l.get_label() for l in lines]
                ax1.legend(lines, labels, loc='upper left', bbox_to_anchor=(0, 1))
                
                fig.tight_layout()
                st.pyplot(fig)
            
            with results_tab2:
                st.markdown("##### Complete Results Summary")
                st.dataframe(
                    df_display.style.set_properties(**{"text-align": "center"}).set_table_styles(
                        [{"selector": "th", "props": [("text-align", "center")]}]
                    ),
                    width='stretch'
                )
        
        
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


