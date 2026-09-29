import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

st.set_page_config(page_title="Parcel Network Control Tower", layout="wide")
st.title("Intelligent Parcel Network Optimization")
st.caption("Predictive + prescriptive logistics prototype calibrated from Olist/open data; synthetic network layer.")


def api_get(path, timeout=5):
    return requests.get(f"{API_URL}{path}", headers=HEADERS, timeout=timeout)


def api_post(path, payload, timeout=20):
    return requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS, timeout=timeout)


try:
    api_get("/health", timeout=3).raise_for_status()
except Exception as exc:
    st.error(f"API unavailable: {exc}")
    st.stop()

m = api_get("/summary").json()
n = api_get("/network").json()

c1, c2, c3 = st.columns(3)
c1.metric("Demo parcels", m["orders_demo"])
c2.metric("Demand rows", m["demand_rows"])
c3.metric("Hubs", m["hubs"])

st.subheader("Network")
hubs = pd.DataFrame(n["hubs"])
st.dataframe(hubs, use_container_width=True, hide_index=True)
st.plotly_chart(
    px.scatter(
        hubs,
        x="lon",
        y="lat",
        size="capacity_parcels",
        text="hub_id",
        hover_name="city",
        title="Candidate logistics hubs",
    ),
    use_container_width=True,
)

st.subheader("Optimization")
a, b, c = st.columns(3)
surge = a.slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05)
cap = b.slider("Capacity multiplier", 0.5, 1.2, 1.0, 0.05)
service = c.slider("Service target", 0.80, 0.99, 0.95, 0.01)

if st.button("Run network optimization", type="primary"):
    r = api_post(
        "/optimize",
        {
            "demand_multiplier": surge,
            "capacity_multiplier": cap,
            "service_level_target": service,
        },
    )
    if r.ok:
        payload = r.json()
        st.json(payload["metrics"])
        st.dataframe(pd.DataFrame(payload["flows"]), use_container_width=True, hide_index=True)
    else:
        st.error(r.text)

st.subheader("Disruption simulator")
scenario = st.selectbox("Scenario", ["demand_surge", "hub_outage", "combined"])
if st.button("Run scenario"):
    r = api_post("/scenario", {"scenario": scenario})
    if r.ok:
        st.json(r.json()["metrics"])
        st.dataframe(pd.DataFrame(r.json()["flows"]), use_container_width=True, hide_index=True)
    else:
        st.error(r.text)

st.divider()
st.caption(
    f"Model: {m['model_version']} · Optimizer: {m['optimizer_version']} · "
    "Research prototype; synthetic hub/fleet assumptions are explicitly labeled."
)
