"""Research-grade targeted + network intervention catalog."""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .interventions import Intervention,InterventionConfig,evaluate_interventions,pareto_frontier
@dataclass(frozen=True)
class TargetedInterventionConfig:
 top_hubs:int=5
 capacity_steps:tuple[float,...]=(0.10,0.20,0.30,0.50,1.00)
 backup_capacity:float=0.50
 hub_capacity_unit_cost:float=8.0
 backup_fixed_cost:float=60.0
 fleet_steps:tuple[float,...]=(0.25,0.50,1.00)
 fleet_unit_cost:float=20.0
 reserve_fleet_steps:tuple[float,...]=(0.25,0.50)
 reserve_fixed_cost:float=50.0

def rank_hubs(demand,hubs,top_n=5):
 col="parcel_count" if "parcel_count" in demand.columns else "demand"
 if col not in demand.columns: raise ValueError("Demand frame must contain either 'parcel_count' or 'demand'.")
 outbound=demand.groupby("origin_hub")[col].sum().rename("outbound_demand"); inbound=demand.groupby("destination_hub")[col].sum().rename("inbound_demand")
 ranked=hubs[["hub_id","capacity_parcels"]].copy().join(outbound,on="hub_id").join(inbound,on="hub_id").fillna(0)
 ranked["throughput_exposure"]=ranked.outbound_demand+ranked.inbound_demand; ranked["capacity_pressure"]=ranked.throughput_exposure/ranked.capacity_parcels.clip(lower=1)
 for c in ("throughput_exposure","capacity_pressure"):
  lo,hi=ranked[c].min(),ranked[c].max(); ranked[f"{c}_score"]=(ranked[c]-lo)/(hi-lo) if hi>lo else 0.0
 ranked["criticality_score"]=0.5*ranked.throughput_exposure_score+0.5*ranked.capacity_pressure_score
 return ranked.sort_values("criticality_score",ascending=False).head(top_n).reset_index(drop=True)

def build_targeted_interventions(demand,hubs,config=None):
 config=config or TargetedInterventionConfig(); ranked=rank_hubs(demand,hubs,config.top_hubs); candidates=[]
 for row in ranked.itertuples(index=False):
  hub=row.hub_id
  for uplift in config.capacity_steps:
   pct=int(round(uplift*100)); candidates.append(Intervention(f"hub_{hub}_capacity_plus_{pct}pct","targeted_hub_capacity",variable_cost=config.hub_capacity_unit_cost*uplift,capacity_uplift=uplift,target_hub_id=hub,description=f"Increase hub {hub} handling capacity by {pct}%."))
  candidates.append(Intervention(f"hub_{hub}_backup_capacity","backup_hub_capacity",fixed_cost=config.backup_fixed_cost,capacity_uplift=config.backup_capacity,target_hub_id=hub,description=f"Add backup handling capacity equivalent to {config.backup_capacity:.0%} at hub {hub}."))
 for uplift in config.fleet_steps:
  pct=int(round(uplift*100)); candidates.append(Intervention(f"network_fleet_plus_{pct}pct","network_fleet_capacity",variable_cost=config.fleet_unit_cost*uplift,fleet_uplift=uplift,description=f"Increase network fleet availability by {pct}%."))
 for uplift in config.reserve_fleet_steps:
  pct=int(round(uplift*100)); candidates.append(Intervention(f"reserve_fleet_plus_{pct}pct","reserve_fleet",fixed_cost=config.reserve_fixed_cost*uplift,reserve_vehicle_multiplier=uplift,description=f"Hold {pct}% reserve fleet capacity."))
 return candidates

def evaluate_targeted_interventions(demand,hubs,cost_matrix,fleet,config=None,n_simulations=500,seed=42,service_target=.95):
 config=config or TargetedInterventionConfig(); candidates=build_targeted_interventions(demand,hubs,config)
 results=evaluate_interventions(demand,hubs,cost_matrix,fleet,candidates,InterventionConfig(n_simulations=n_simulations,seed=seed,service_target=service_target))
 return rank_hubs(demand,hubs,config.top_hubs),pareto_frontier(results)
