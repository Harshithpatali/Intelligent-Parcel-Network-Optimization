import pandas as pd
try: from ortools.linear_solver import pywraplp
except ImportError: pywraplp=None
from src.core.geo import haversine_km
UNMET_PENALTY=1000.0
def build_cost_matrix(hubs):
    rows=[]
    for _,a in hubs.iterrows():
        for _,b in hubs.iterrows():
            if a.hub_id==b.hub_id: continue
            km=haversine_km(a.lat,a.lon,b.lat,b.lon)*1.18; rows.append({'origin_hub':a.hub_id,'destination_hub':b.hub_id,'distance_km':km,'unit_cost':2.2+.075*km})
    return pd.DataFrame(rows)
def solve_network(demand,hubs,cost=None,capacity_multiplier=1.0,service_level_target=.95):
    d=demand.copy(); d['parcel_count']=pd.to_numeric(d.parcel_count).clip(lower=0); cost=cost if cost is not None else build_cost_matrix(hubs)
    c={(r.origin_hub,r.destination_hub):float(r.unit_cost) for _,r in cost.iterrows()}; dist={(r.origin_hub,r.destination_hub):float(r.distance_km) for _,r in cost.iterrows()}
    caps={h:float(hubs.loc[hubs.hub_id==h,'capacity_parcels'].iloc[0])*capacity_multiplier for h in hubs.hub_id}
    if pywraplp is None:
        used_out={h:0.0 for h in caps}; used_in={h:0.0 for h in caps}; out=[]
        for _,r in d.sort_values('parcel_count',ascending=False).iterrows():
            o,j=r.origin_hub,r.destination_hub; q=float(r.parcel_count); feasible=max(0,min(q,caps.get(o,0)-used_out.get(o,0),caps.get(j,0)-used_in.get(j,0))); used_out[o]+=feasible; used_in[j]+=feasible
            out.append({'origin_hub':o,'destination_hub':j,'requested_parcels':q,'parcels':feasible,'unmet_parcels':q-feasible,'distance_km':dist.get((o,j),0),'transport_cost':feasible*c.get((o,j),999)})
        out=pd.DataFrame(out); unmet=float(out.unmet_parcels.sum()); total=float(out.transport_cost.sum()); return out,{'status':'greedy_fallback','total_transport_cost':total,'unmet_demand':unmet,'service_level':float(1-unmet/max(float(d.parcel_count.sum()),1)),'service_level_target':service_level_target,'objective_with_unmet_penalty':total+unmet*UNMET_PENALTY,'total_parcels':float(out.parcels.sum())}
    solver=pywraplp.Solver.CreateSolver('SCIP');
    if not solver: raise RuntimeError('OR-Tools SCIP solver unavailable')
    x={};u={}
    for _,r in d.iterrows():
        k=(r.origin_hub,r.destination_hub); x[k]=solver.IntVar(0,solver.infinity(),f'x_{k[0]}_{k[1]}'); u[k]=solver.IntVar(0,solver.infinity(),f'u_{k[0]}_{k[1]}'); solver.Add(x[k]+u[k]>=float(r.parcel_count))
    for h,cap in caps.items(): solver.Add(sum(v for (o,j),v in x.items() if o==h)<=cap); solver.Add(sum(v for (o,j),v in x.items() if j==h)<=cap)
    obj=solver.Objective()
    for k,v in x.items(): obj.SetCoefficient(v,c.get(k,999)); obj.SetCoefficient(u[k],UNMET_PENALTY)
    obj.SetMinimization(); status=solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL,pywraplp.Solver.FEASIBLE): raise RuntimeError('Network optimization infeasible')
    rows=[]
    for k in x:
        q=x[k].solution_value(); unmet=u[k].solution_value(); rows.append({'origin_hub':k[0],'destination_hub':k[1],'requested_parcels':q+unmet,'parcels':q,'unmet_parcels':unmet,'distance_km':dist.get(k,0),'transport_cost':q*c.get(k,999)})
    out=pd.DataFrame(rows); unmet=float(out.unmet_parcels.sum()); total=float(out.transport_cost.sum()); return out,{'status':'optimal' if status==pywraplp.Solver.OPTIMAL else 'feasible','total_transport_cost':total,'unmet_demand':unmet,'service_level':float(1-unmet/max(float(d.parcel_count.sum()),1)),'service_level_target':service_level_target,'objective_with_unmet_penalty':total+unmet*UNMET_PENALTY,'total_parcels':float(out.parcels.sum())}
