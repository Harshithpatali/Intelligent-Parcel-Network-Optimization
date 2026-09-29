"""Resilience root-cause decomposition from Monte Carlo simulation results."""
from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
FACTORS={"hub_failures":"hub_failures","road_failures":"road_failures"}
def _summary(df,factor,level,contribution):
 s=df.service_level.astype(float); u=df.unmet_demand.astype(float); c=df.total_transport_cost.astype(float)
 return {"analysis_type":"grouped_factor","factor":factor,"factor_level":str(level),"observations":int(len(df)),"mean_service_level":float(s.mean()),"p05_service_level":float(s.quantile(.05)),"p50_service_level":float(s.quantile(.50)),"p95_service_level":float(s.quantile(.95)),"mean_unmet_demand":float(u.mean()),"mean_transport_cost":float(c.mean()),"contribution_score":float(contribution)}
def analyze_simulations(results:pd.DataFrame,run_id:str|None=None):
 if results.empty: raise ValueError("No simulation results supplied")
 req={"service_level","unmet_demand","total_transport_cost","demand_multiplier","capacity_multiplier","fleet_multiplier","hub_failures","road_failures"}; miss=req-set(results.columns)
 if miss: raise ValueError(f"Missing simulation columns: {sorted(miss)}")
 df=results.copy(); rows=[]; baseline=float(df.service_level.mean())
 for factor,col in FACTORS.items():
  for level,g in df.groupby(col,dropna=False): rows.append(_summary(g,factor,level,baseline-float(g.service_level.mean())))
 for factor,col,bins in [("demand_pressure","demand_multiplier",[0,.9,1,1.1,10]),("capacity_pressure","capacity_multiplier",[0,.9,1,1.1,10]),("fleet_pressure","fleet_multiplier",[0,.9,1,1.1,10])]:
  labels=["<0.90","0.90-0.99","1.00-1.09","1.10+"]; cats=pd.cut(df[col],bins=bins,labels=labels,right=False,include_lowest=True)
  for level,g in df.groupby(cats,observed=True): rows.append(_summary(g,factor,level,baseline-float(g.service_level.mean())))
 if run_id is None: run_id=str(uuid.uuid4())
 out=pd.DataFrame(rows); out.insert(0,"run_id",run_id)
 effects=(out[out.analysis_type.eq("grouped_factor")].groupby("factor",as_index=False)["contribution_score"].mean().sort_values("contribution_score",ascending=False))
 return out,{"run_id":run_id,"simulations":int(len(df)),"mean_service_level":baseline,"factor_effects":effects.to_dict("records")}
def hub_pressure_table(demand:pd.DataFrame,hubs:pd.DataFrame):
 d=demand.copy(); d["demand"]=pd.to_numeric(d["demand"],errors="coerce").fillna(0)
 out=d.groupby("origin_hub",as_index=False).demand.sum().rename(columns={"origin_hub":"hub_id","demand":"outbound_demand"}); inn=d.groupby("destination_hub",as_index=False).demand.sum().rename(columns={"destination_hub":"hub_id","demand":"inbound_demand"})
 out=out.merge(inn,on="hub_id",how="outer").fillna(0).merge(hubs[["hub_id","capacity_parcels"]],on="hub_id",how="left"); out["throughput_demand"]=out.outbound_demand+out.inbound_demand; out["capacity_pressure"]=out.throughput_demand/(2*out.capacity_parcels.clip(lower=1)); return out.sort_values("capacity_pressure",ascending=False)
