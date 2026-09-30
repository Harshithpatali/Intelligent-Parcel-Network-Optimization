import os,requests,pandas as pd,streamlit as st,plotly.express as px,plotly.graph_objects as go
API_URL=os.getenv("API_URL","http://127.0.0.1:8000").rstrip("/"); API_KEY=os.getenv("API_KEY",""); HEADERS={"x-api-key":API_KEY} if API_KEY else {}
st.set_page_config(page_title="Parcel Network Control Tower",layout="wide"); st.title("Intelligent Parcel Network Control Tower"); st.caption("Olist-calibrated research network · predictive forecasting · stochastic resilience · intervention optimization")
def get(path,timeout=15): return requests.get(f"{API_URL}{path}",headers=HEADERS,timeout=timeout)
def post(path,payload,timeout=60): return requests.post(f"{API_URL}{path}",json=payload,headers=HEADERS,timeout=timeout)
try:
 summary=get("/summary").json(); network=get("/network").json()
except Exception as e: st.error(f"API unavailable: {e}"); st.stop()
prod=summary.get("production_mode",False)
if prod: st.success(f"Production analytics connected · forecast {summary.get('forecast_date')} · model {summary.get('model_version')}")
else: st.warning("Demo mode. Set ENVIRONMENT=production and configure the Supabase service-role key on the API backend.")
hubs=pd.DataFrame(network["hubs"]); c1,c2,c3,c4=st.columns(4); c1.metric("Candidate hubs",summary["hubs"]); c2.metric("OD demand rows",summary["demand_rows"]); c3.metric("Routes",network.get("routes",0)); c4.metric("Mode","Production" if prod else "Demo")
t1,t2,t3,t4,t5=st.tabs(["Network","Optimization","Resilience","Root Cause","Interventions"])
with t1:
 st.subheader("Candidate hub network"); st.plotly_chart(px.scatter(hubs,x="lng",y="lat",size="capacity_parcels",text="hub_id",hover_name="representative_zip",title="Olist-calibrated candidate hubs"),use_container_width=True); st.dataframe(hubs,use_container_width=True,hide_index=True)
with t2:
 a,b,c=st.columns(3); surge=a.slider("Demand multiplier",.5,2.,1.,.05); cap=b.slider("Capacity multiplier",.5,3.,1.,.05); service=c.slider("Service target",.80,.99,.95,.01)
 if st.button("Run optimization",type="primary"):
  r=post("/optimize",{"demand_multiplier":surge,"capacity_multiplier":cap,"service_level_target":service});
  if r.ok:
   m=r.json()["metrics"]; x,y,z=st.columns(3); x.metric("Service level",f"{m['service_level']:.1%}"); y.metric("Unmet parcels",f"{m['unmet_demand']:.1f}"); z.metric("Transport cost",f"{m['total_transport_cost']:.2f}"); st.dataframe(pd.DataFrame(r.json()["flows"]),use_container_width=True,hide_index=True)
  else: st.error(r.text)
 st.subheader("Disruption scenario"); scenario=st.selectbox("Scenario",["demand_surge","capacity_shock","fleet_shortage","hub_outage","road_disruption","combined"])
 if st.button("Run disruption"):
  r=post("/scenario",{"scenario":scenario}); st.json(r.json()["metrics"] if r.ok else {"error":r.text})
with t3:
 if prod:
  r=get("/resilience");
  if r.ok:
   risk=r.json()["risk_summary"]; st.dataframe(pd.DataFrame(risk),use_container_width=True,hide_index=True)
   if risk:
    rr=pd.DataFrame(risk); st.bar_chart(rr.set_index("metric")["value"] if "metric" in rr.columns and "value" in rr.columns else pd.Series(dtype=float))
  else: st.error(r.text)
 else: st.info("Resilience analytics appear after the production pipeline populates Supabase.")
with t4:
 if prod:
  r=get("/root-cause");
  if r.ok:
   rc=pd.DataFrame(r.json()["rows"]); st.dataframe(rc,use_container_width=True,hide_index=True)
   grouped=rc[rc["analysis_type"]=="grouped_factor"].copy()
   if not grouped.empty: st.plotly_chart(px.bar(grouped,x="factor",y="contribution_score",title="Service-level contribution by disruption factor"),use_container_width=True)
  else: st.error(r.text)
 else: st.info("Root-cause analysis appears after the production pipeline runs Step 1.")
with t5:
 if prod:
  r=get("/interventions");
  if r.ok:
   it=pd.DataFrame(r.json()["rows"]); st.dataframe(it,use_container_width=True,hide_index=True)
   if not it.empty:
    st.plotly_chart(px.scatter(it,x="intervention_cost",y="probability_target_met",size="expected_unmet_demand",hover_data=["bundle_id"],title="Intervention cost vs reliability"),use_container_width=True)
    feasible=it[it.feasible==True] if "feasible" in it.columns else pd.DataFrame()
    st.info(f"Feasible bundles in latest evaluation: {len(feasible)}")
  else: st.error(r.text)
 else: st.info("Intervention analytics appear after the production pipeline runs.")
st.divider(); st.caption(f"Model: {summary.get('model_version')} · Optimizer: {summary.get('optimizer_version')} · Synthetic costs/disruption distributions are stress-test assumptions.")
