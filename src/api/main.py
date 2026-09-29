import logging,time,os
import pandas as pd
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import JSONResponse,Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import generate_latest,CONTENT_TYPE_LATEST
from src.core.config import API_KEY,APP_ENV,LOG_LEVEL,MODEL_VERSION,OPTIMIZER_VERSION,ALLOWED_ORIGINS
from src.core.logging import configure_logging,new_request_id,request_id_ctx
from src.core.observability import REQUESTS,LATENCY,OPTIMIZATION_RUNS,UNMET_PARCELS,FORECAST_MAE
from src.api.schemas import ForecastRequest,OptimizeRequest,ScenarioRequest
from src.data.demo import generate_demo
from src.models.forecast import fit_forecaster
from src.optimization.network import solve_network,build_cost_matrix
from src.optimization.scenarios import Scenario,run_scenario
configure_logging(LOG_LEVEL); logger=logging.getLogger('parcel-api')
app=FastAPI(title='Intelligent Parcel Network Optimization',version='3.0.0',docs_url='/docs' if APP_ENV!='production' else None)
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['*'])
demo_demand,demo_parcels,demo_hubs=generate_demo()
def get_data():
 if APP_ENV.lower() in {'production','prod'} and os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
  from src.api.production_data import ProductionData; return ProductionData().load(),True
 return {'demand':demo_demand.groupby(['origin_hub','destination_hub'],as_index=False).parcel_count.sum(),'hubs':demo_hubs,'fleet':None,'cost':build_cost_matrix(demo_hubs),'forecast_date':None,'model_version':MODEL_VERSION},False
def api_get_data():
 try:return get_data()
 except Exception: logger.exception('production_data_load_failed'); raise HTTPException(503,'Production data unavailable')
@app.middleware('http')
async def middleware(request:Request,call_next):
 rid=new_request_id(); token=request_id_ctx.set(rid); start=time.perf_counter()
 try:
  if API_KEY and request.url.path not in {'/health','/ready','/metrics'} and request.headers.get('x-api-key')!=API_KEY: response=JSONResponse({'detail':'Invalid API key','request_id':rid},status_code=401)
  else: response=await call_next(request)
 except Exception: logger.exception('unhandled_request_error'); response=JSONResponse({'detail':'Internal server error','request_id':rid},status_code=500)
 response.headers['X-Request-ID']=rid; REQUESTS.labels(request.method,request.url.path,str(response.status_code)).inc(); LATENCY.labels(request.url.path).observe(time.perf_counter()-start); request_id_ctx.reset(token); return response
@app.get('/health')
def health(): return {'status':'ok','service':'parcel-network-optimization','version':app.version}
@app.get('/ready')
def ready():
 from src.optimization.network import pywraplp
 checks={'optimizer_runtime':pywraplp is not None}
 if APP_ENV.lower() in {'production','prod'}:
  try: data,_=get_data(); checks.update({'production_data':True,'forecast_date':data['forecast_date'],'road_routes':len(data['cost'])})
  except Exception as exc: checks.update({'production_data':False,'error':str(exc)})
 else: checks['demo_data']=len(demo_demand)>0 and len(demo_hubs)>0
 if not checks.get('optimizer_runtime') or checks.get('production_data') is False: raise HTTPException(503,{'status':'not_ready','checks':checks})
 return {'status':'ready','checks':checks}
@app.get('/metrics')
def metrics(): return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.get('/summary')
def summary():
 data,prod=api_get_data(); return {'orders_demo':int(len(demo_parcels)),'demand_rows':int(len(data['demand'])),'hubs':int(len(data['hubs'])),'production_mode':prod,'forecast_date':data['forecast_date'],'model_version':data['model_version'],'optimizer_version':OPTIMIZER_VERSION}
@app.get('/network')
def network():
 data,prod=api_get_data(); return {'hubs':data['hubs'].to_dict(orient='records'),'routes':int(len(data['cost'])),'demand_rows':int(len(data['demand'])),'production_mode':prod,'forecast_date':data['forecast_date'],'model_version':data['model_version'],'optimizer_version':OPTIMIZER_VERSION}
@app.post('/forecast')
def forecast(req:ForecastRequest):
 if APP_ENV.lower() in {'production','prod'}:
  data,_=api_get_data(); return {'forecast_date':data['forecast_date'],'model_version':data['model_version'],'rows':data['demand'].to_dict(orient='records')}
 result=fit_forecaster(demo_demand.tail(req.days*len(demo_hubs)*(len(demo_hubs)-1)))
 if result.get('test_mae') is not None: FORECAST_MAE.set(result['test_mae'])
 return {**result,'model_version':MODEL_VERSION}
@app.post('/optimize')
def optimize(req:OptimizeRequest):
 try:
  data,prod=api_get_data(); d=data['demand'].copy(); d['parcel_count']=(pd.to_numeric(d.parcel_count)*req.demand_multiplier).round()
  flows,m=solve_network(d,data['hubs'],fleet=data['fleet'],cost=data['cost'],capacity_multiplier=req.capacity_multiplier,service_level_target=req.service_level_target)
  m.update({'optimizer_version':OPTIMIZER_VERSION,'production_mode':prod,'forecast_date':data['forecast_date'],'request_id':request_id_ctx.get()}); UNMET_PARCELS.set(m['unmet_demand']); OPTIMIZATION_RUNS.labels(m['status']).inc(); return {'metrics':m,'flows':flows.to_dict(orient='records')}
 except Exception: OPTIMIZATION_RUNS.labels('error').inc(); logger.exception('optimization_failed'); raise HTTPException(400,{'detail':'Optimization request failed','request_id':request_id_ctx.get()})
@app.post('/scenario')
def scenario(req:ScenarioRequest):
 try:
  data,prod=api_get_data(); scenarios={'demand_surge':Scenario('demand_surge','demand_surge',demand_multiplier=1.30),'capacity_shock':Scenario('capacity_shock','capacity_shock',capacity_multiplier=.75),'fleet_shortage':Scenario('fleet_shortage','fleet_shortage',fleet_multiplier=.70)}
  sc=scenarios.get(req.scenario)
  if req.scenario=='hub_outage': sc=Scenario('hub_outage','hub_outage',disabled_hubs=(data['hubs'].iloc[0].hub_id,))
  elif req.scenario=='road_disruption' and not data['cost'].empty:
   rr=data['cost'].sort_values('distance_km').iloc[0]; sc=Scenario('road_disruption','road_disruption',disabled_routes=((rr.origin_hub,rr.destination_hub),))
  elif req.scenario=='combined': sc=Scenario('combined','combined',demand_multiplier=1.30,capacity_multiplier=.70)
  if sc is None: raise ValueError('Unknown scenario')
  flows,m=run_scenario(data['demand'],data['hubs'],data['fleet'],data['cost'],sc); m.update({'production_mode':prod,'forecast_date':data['forecast_date']}); UNMET_PARCELS.set(m['unmet_demand']); OPTIMIZATION_RUNS.labels(m['status']).inc(); return {'metrics':m,'flows':flows.to_dict(orient='records')}
 except Exception: OPTIMIZATION_RUNS.labels('error').inc(); logger.exception('scenario_failed'); raise HTTPException(400,{'detail':'Scenario request failed','request_id':request_id_ctx.get()})
@app.get('/resilience')
def resilience():
 from src.api.production_data import ProductionData
 try:
  if APP_ENV.lower() not in {'production','prod'}: raise RuntimeError()
  return {'risk_summary':ProductionData().sb.table('logistics_resilience_risk_summary').select('*').execute().data}
 except Exception: raise HTTPException(503,'Resilience analytics unavailable')
@app.get('/root-cause')
def root_cause():
 from src.api.production_data import ProductionData
 try:
  if APP_ENV.lower() not in {'production','prod'}: raise RuntimeError()
  return {'rows':ProductionData().sb.table('logistics_resilience_root_cause').select('*').order('created_at',desc=True).limit(100).execute().data}
 except Exception: raise HTTPException(503,'Root-cause analysis unavailable')
@app.get('/interventions')
def interventions():
 from src.api.production_data import ProductionData
 try:
  if APP_ENV.lower() not in {'production','prod'}: raise RuntimeError()
  return {'rows':ProductionData().sb.table('logistics_intervention_bundles').select('*').order('created_at',desc=True).limit(75).execute().data}
 except Exception: raise HTTPException(503,'Intervention analytics unavailable')
