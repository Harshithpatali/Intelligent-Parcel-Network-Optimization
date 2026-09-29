from pathlib import Path
import numpy as np
import pandas as pd
HUBS=pd.DataFrame([['H01','Sao Paulo',-23.5505,-46.6333,7000,4500],['H02','Rio de Janeiro',-22.9068,-43.1729,5000,3200],['H03','Belo Horizonte',-19.9167,-43.9345,4200,2700],['H04','Curitiba',-25.4284,-49.2733,3500,2200],['H05','Brasilia',-15.7939,-47.8828,3200,2000]],columns=['hub_id','city','lat','lon','capacity_parcels','handling_capacity'])
def generate_demo(n_days=140,seed=42):
 rng=np.random.default_rng(seed); dates=pd.date_range('2018-01-01',periods=n_days,freq='D'); rows=[]
 for d in dates:
  for o in HUBS.hub_id:
   for dest in HUBS.hub_id:
    if o==dest: continue
    base=45+18*(d.dayofweek in [0,1])+10*(d.month in [11,12]); rows.append([d,o,dest,max(1,int(rng.poisson(base*rng.uniform(.65,1.45))))])
 demand=pd.DataFrame(rows,columns=['date','origin_hub','destination_hub','parcel_count']); rng=np.random.default_rng(seed+1); n=len(demand)*2
 parcels=pd.DataFrame({'parcel_id':[f'D{i:07d}' for i in range(n)],'shipment_id':[f'D{i:07d}' for i in range(n)],'order_id':[f'O{i:07d}' for i in range(n)],'purchase_date':rng.choice(dates,n),'origin_hub':rng.choice(HUBS.hub_id,n),'destination_hub':rng.choice(HUBS.hub_id,n),'weight_kg':rng.gamma(2,1.7,n).clip(.1,25)})
 parcels['volume_m3']=(parcels.weight_kg*rng.uniform(.0015,.004,n)).clip(.0002,.08); return demand,parcels,HUBS.copy()
def write_demo(root:Path):
 d=root/'data'; d.mkdir(exist_ok=True); demand,parcels,hubs=generate_demo(); demand.to_csv(d/'demo_demand.csv',index=False); parcels.to_csv(d/'demo_parcels.csv',index=False); hubs.to_csv(d/'hubs.csv',index=False); return demand,parcels,hubs
