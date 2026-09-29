from __future__ import annotations
import os
import pandas as pd
from supabase import create_client
from src.optimization.network import build_cost_matrix,build_road_cost_matrix
class ProductionData:
 def __init__(self):
  url=os.getenv("SUPABASE_URL","").rstrip("/"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY","")
  if not url or not key: raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for production data")
  self.sb=create_client(url,key)
 def fetch_all(self,table,select="*"):
  rows=[]; offset=0
  while True:
   batch=self.sb.table(table).select(select).range(offset,offset+999).execute().data; rows.extend(batch)
   if len(batch)<1000:return pd.DataFrame(rows)
   offset+=1000
 def load(self):
  hubs=self.fetch_all("logistics_hubs"); cap=self.fetch_all("logistics_hub_capacity"); fleet=self.fetch_all("logistics_fleet"); road=self.fetch_all("logistics_road_matrix")
  hubs=hubs.merge(cap[["hub_id","capacity_parcels"]],on="hub_id",how="left")
  forecast=self.fetch_all("logistics_forecast_predictions","forecast_date,origin_hub_id,destination_hub_id,xgb_pred,model_version")
  if forecast.empty: raise RuntimeError("No production forecast predictions available")
  forecast["forecast_date"]=pd.to_datetime(forecast.forecast_date); latest=forecast.forecast_date.max(); f=forecast[forecast.forecast_date==latest].copy()
  demand=f.rename(columns={"origin_hub_id":"origin_hub","destination_hub_id":"destination_hub","xgb_pred":"parcel_count"})[["origin_hub","destination_hub","parcel_count"]]
  cost=build_road_cost_matrix(road) if not road.empty else build_cost_matrix(hubs)
  return {"hubs":hubs,"fleet":fleet,"cost":cost,"demand":demand,"forecast_date":str(latest.date()),"model_version":str(f.iloc[0].model_version)}
