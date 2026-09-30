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

st.set_page_config(page_title="Parcel Network Control Tower", layout="wide")
st.title("Intelligent Parcel Network Control Tower")
st.caption("Olist-calibrated research network · predictive forecasting · stochastic resilience · intervention optimization")


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
    st.subheader("Candidate hub network")
    center = [float(hubs["lat"].mean()), float(hubs["lng"].mean())]
    fmap = folium.Map(location=center, zoom_start=4, control_scale=True)
    for row in hubs.itertuples():
        folium.CircleMarker(
            location=[float(row.lat), float(row.lng)],
            radius=7,
            fill=True,
            tooltip=f"Hub {row.hub_id} · capacity {row.capacity_parcels:.0f}",
            popup=f"ZIP {row.representative_zip} · capacity {row.capacity_parcels:.0f}",
        ).add_to(fmap)
    components.html(fmap.get_root().render(), height=620, scrolling=False)
    st.dataframe(hubs, use_container_width=True, hide_index=True)

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

    if st.button("Build consolidated routes", type="primary"):
        payload = {
            "parcel_capacity": int(parcel_capacity),
            "max_route_hours": float(max_route_hours),
            "max_stops": int(max_stops),
            "demand_multiplier": float(demand_multiplier),
            "fixed_trip_cost": 45.0,
            "cost_per_km": float(cost_per_km),
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
