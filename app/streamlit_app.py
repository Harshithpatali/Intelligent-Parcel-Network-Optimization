import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import folium
import streamlit.components.v1 as components

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

st.set_page_config(page_title="Parcel Network Control Tower", page_icon="📦", layout="wide")

st.markdown("""
<style>
:root { --fx-purple:#4D148C; --fx-orange:#FF6600; }
.block-container { padding-top:1.4rem; padding-bottom:2rem; }
.fx-header { background:linear-gradient(100deg,#4D148C 0%,#5d1aa0 72%,#FF6600 100%); border-radius:14px; padding:22px 28px; color:white; margin-bottom:10px; box-shadow:0 6px 22px rgba(77,20,140,.16); }
.fx-header h1 { margin:0; font-size:2rem; letter-spacing:-.02em; }
.fx-header p { margin:7px 0 0; opacity:.92; font-size:.95rem; }
.fx-accent { height:5px; background:#FF6600; border-radius:99px; margin:0 0 18px; }
.fx-note { background:#f6f3fa; border-left:4px solid #FF6600; padding:10px 14px; border-radius:6px; }
div.stButton > button[kind="primary"] { background:#4D148C; border-color:#4D148C; }
div.stButton > button[kind="primary"]:hover { background:#FF6600; border-color:#FF6600; }
[data-testid="stMetricValue"] { color:#4D148C; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="fx-header"><h1>Intelligent Parcel Network Control Tower</h1>
<p>Predictive demand · capacity-aware optimization · disruption resilience · multi-stop parcel consolidation</p></div>
<div class="fx-accent"></div>
""", unsafe_allow_html=True)
def get(path, timeout=15):
    return requests.get(f"{API_URL}{path}", headers=HEADERS, timeout=timeout)


def post(path, payload, timeout=60):
    return requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS, timeout=timeout)


try:
    summary = get("/summary").json()
    network = get("/network").json()
except Exception as e:
    st.error(f"API unavailable: {e}")
    st.stop()

prod = summary.get("production_mode", False)
if prod:
    st.success(
        f"Production analytics connected · forecast {summary.get('forecast_date')} · "
        f"model {summary.get('model_version')}"
    )
else:
    st.warning(
        "Demo mode. Set ENVIRONMENT=production and configure the Supabase service-role key on the API backend."
    )

hubs = pd.DataFrame(network["hubs"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Candidate hubs", summary["hubs"])
c2.metric("OD demand rows", summary["demand_rows"])
c3.metric("Routes", network.get("routes", 0))
c4.metric("Mode", "Production" if prod else "Demo")

t1, t2, t3, t4, t5, t6 = st.tabs(
    ["Network", "Optimization", "Resilience", "Root Cause", "Interventions", "Routing"]
)

with t1:
    st.subheader("Network overview")
    st.markdown(
        '<div class="fx-note">The operational route map is intentionally kept on the final Routing page. This view focuses on network structure, capacity and fleet assumptions.</div>',
        unsafe_allow_html=True,
    )
    if not hubs.empty:
        left, right = st.columns([1.5, 1])
        with left:
            st.plotly_chart(
                px.scatter(
                    hubs,
                    x="lon",
                    y="lat",
                    size="capacity_parcels",
                    text="hub_id",
                    hover_name="city",
                    title="Candidate hub capacity footprint",
                    color_discrete_sequence=["#4D148C"],
                ),
                use_container_width=True,
            )
        with right:
            fleet_df = pd.DataFrame(network.get("fleet", []))
            if not fleet_df.empty:
                st.markdown("#### Fleet profile")
                st.dataframe(fleet_df, use_container_width=True, hide_index=True)
            st.markdown("#### Candidate hubs")
            st.dataframe(
                hubs[["hub_id", "city", "capacity_parcels", "handling_capacity"]],
                use_container_width=True,
                hide_index=True,
            )

with t2:
    a, b, c = st.columns(3)
    surge = a.slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05)
    cap = b.slider("Capacity multiplier", 0.5, 3.0, 1.0, 0.05)
    service = c.slider("Service target", 0.80, 0.99, 0.95, 0.01)
    if st.button("Run optimization", type="primary"):
        r = post(
            "/optimize",
            {
                "demand_multiplier": surge,
                "capacity_multiplier": cap,
                "service_level_target": service,
            },
        )
        if r.ok:
            m = r.json()["metrics"]
            x, y, z = st.columns(3)
            x.metric("Service level", f"{m['service_level']:.1%}")
            y.metric("Unmet parcels", f"{m['unmet_demand']:.1f}")
            z.metric("Transport cost", f"{m['total_transport_cost']:.2f}")
            st.dataframe(
                pd.DataFrame(r.json()["flows"]),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Trip cost is a fixed dispatch + distance charge. Low utilization is surfaced rather than hidden; "
                "unmet rows are not transportation with zero cost."
            )
        else:
            st.error(r.text)

    st.subheader("Disruption scenario")
    scenario = st.selectbox(
        "Scenario",
        [
            "demand_surge",
            "capacity_shock",
            "fleet_shortage",
            "hub_outage",
            "road_disruption",
            "combined",
        ],
    )
    if st.button("Run disruption"):
        r = post("/scenario", {"scenario": scenario})
        st.json(r.json()["metrics"] if r.ok else {"error": r.text})

with t3:
    if prod:
        r = get("/resilience")
        if r.ok:
            risk = r.json()["risk_summary"]
            st.dataframe(pd.DataFrame(risk), use_container_width=True, hide_index=True)
        else:
            st.error(r.text)
    else:
        st.info("Resilience analytics appear after the production pipeline populates Supabase.")

with t4:
    if prod:
        r = get("/root-cause")
        if r.ok:
            rc = pd.DataFrame(r.json()["rows"])
            st.dataframe(rc, use_container_width=True, hide_index=True)
            if not rc.empty and "analysis_type" in rc.columns:
                grouped = rc[rc["analysis_type"] == "grouped_factor"].copy()
                if not grouped.empty:
                    st.plotly_chart(
                        px.bar(
                            grouped,
                            x="factor",
                            y="contribution_score",
                            title="Service-level contribution by disruption factor",
                        ),
                        use_container_width=True,
                    )
        else:
            st.error(r.text)
    else:
        st.info("Root-cause analysis appears after the production pipeline runs Step 1.")

with t5:
    if prod:
        r = get("/interventions")
        if r.ok:
            it = pd.DataFrame(r.json()["rows"])
            st.dataframe(it, use_container_width=True, hide_index=True)
            if not it.empty:
                st.plotly_chart(
                    px.scatter(
                        it,
                        x="intervention_cost",
                        y="probability_target_met",
                        size="expected_unmet_demand",
                        hover_data=["bundle_id"],
                        title="Intervention cost vs reliability",
                    ),
                    use_container_width=True,
                )
                feasible = (
                    it[it.feasible == True] if "feasible" in it.columns else pd.DataFrame()
                )
                st.info(f"Feasible bundles in latest evaluation: {len(feasible)}")
        else:
            st.error(r.text)
    else:
        st.info("Intervention analytics appear after the production pipeline runs.")

with t6:
    st.subheader("Parcel consolidation + multi-stop routing")
    st.caption(
        "The route planner consolidates forecast hub-to-hub demand into physical linehaul tours "
        "using the real road-network distance/time matrix. Map lines connect hub coordinates; "
        "they are not turn-by-turn road geometry."
    )

    a, b, c, d, e = st.columns(5)
    parcel_capacity = a.number_input("Truck capacity", min_value=1, max_value=200, value=40, step=1)
    max_route_hours = b.number_input("Max route hours", min_value=1.0, max_value=48.0, value=16.0, step=1.0)
    max_stops = c.number_input("Max stops", min_value=1, max_value=15, value=5, step=1)
    demand_multiplier = d.slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05)
    cost_per_km = e.number_input("Cost / km", min_value=0.0, value=0.075, step=0.005, format="%.3f")
    w1, w2 = st.columns(2)
    distance_weight = w1.slider("Distance weight", 0.0, 1.0, 0.5, 0.05)
    time_weight = w2.slider("Time weight", 0.0, 1.0, 0.5, 0.05)
    if distance_weight + time_weight <= 0:
        st.error("At least one distance/time weight must be positive.")

    if st.button("Build consolidated routes", type="primary"):
        payload = {
            "parcel_capacity": int(parcel_capacity),
            "max_route_hours": float(max_route_hours),
            "max_stops": int(max_stops),
            "demand_multiplier": float(demand_multiplier),
            "fixed_trip_cost": 45.0,
            "cost_per_km": float(cost_per_km),
            "distance_weight": float(distance_weight),
            "time_weight": float(time_weight),
        }
        r = post("/routing", payload, timeout=120)

        if r.ok:
            body = r.json()
            metrics = body["metrics"]
            routes = pd.DataFrame(body["routes"])

            x, y, z, q = st.columns(4)
            x.metric("Consolidated routes", int(metrics["consolidated_routes"]))
            y.metric("Average stops", f"{metrics['average_stops']:.1f}")
            z.metric("Avg utilization", f"{metrics['average_capacity_utilization']:.1%}")
            q.metric("Cost savings", f"{metrics['estimated_cost_savings_pct']:.1f}%")
            st.metric("Service level", f"{metrics['service_level']:.1%}")

            if not routes.empty:
                coord = {
                    row.hub_id: (float(row.lat), float(row.lng))
                    for row in hubs.itertuples()
                }
                fmap = folium.Map(
                    location=[float(hubs["lat"].mean()), float(hubs["lng"].mean())],
                    zoom_start=4,
                    control_scale=True,
                )

                palette = [
                    "red", "blue", "green", "purple", "orange",
                    "darkred", "cadetblue", "darkgreen", "pink", "gray",
                ]

                for row in hubs.itertuples():
                    folium.CircleMarker(
                        location=[float(row.lat), float(row.lng)],
                        radius=6,
                        fill=True,
                        tooltip=f"Hub {row.hub_id}",
                    ).add_to(fmap)

                for idx, row in routes.iterrows():
                    sequence = [row["origin_hub"]] + list(row["destination_hubs"])
                    points = [coord[h] for h in sequence if h in coord]
                    color = palette[idx % len(palette)]

                    folium.PolyLine(
                        points,
                        color=color,
                        weight=5,
                        opacity=0.75,
                        tooltip=(
                            f"Route {int(row['route_id'])}: {int(row['parcels'])} parcels · "
                            f"{int(row['stops'])} stops · {row['capacity_utilization']:.1%} full"
                        ),
                        popup=(
                            f"Route {int(row['route_id'])}<br>"
                            f"Stops: {int(row['stops'])}<br>"
                            f"Parcels: {row['parcels']:.1f}<br>"
                            f"Distance: {row['distance_km']:.1f} km<br>"
                            f"Time: {row['travel_time_hours']:.1f} h<br>"
                            f"Cost: {row['transport_cost']:.2f}"
                        ),
                    ).add_to(fmap)

                    for stop_no, hub_id in enumerate(sequence, 1):
                        if hub_id in coord:
                            folium.Marker(
                                coord[hub_id],
                                tooltip=f"R{int(row['route_id'])} · stop {stop_no} · hub {hub_id}",
                            ).add_to(fmap)

                components.html(fmap.get_root().render(), height=720, scrolling=False)

                display = routes.copy()
                display["destination_hubs"] = display["destination_hubs"].astype(str)
                display["stop_parcels"] = display["stop_parcels"].astype(str)
                st.dataframe(display, use_container_width=True, hide_index=True)

                if metrics["estimated_cost_savings"] > 0:
                    st.success(
                        f"Consolidation reduces modeled transport cost by "
                        f"{metrics['estimated_cost_savings']:.2f} "
                        f"({metrics['estimated_cost_savings_pct']:.1f}%) versus direct dispatches."
                    )
                else:
                    st.info(
                        "The generated route set does not reduce modeled cost under the current "
                        "capacity, time, and stop constraints."
                    )
            else:
                st.warning("No feasible consolidated routes were generated.")
        else:
            st.error(r.text)

st.divider()
st.caption(
    f"Model: {summary.get('model_version')} · Optimizer: {summary.get('optimizer_version')} · "
    "Synthetic costs/disruption distributions are stress-test assumptions."
)
