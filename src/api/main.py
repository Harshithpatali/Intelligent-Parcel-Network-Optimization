import logging,time
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
from src.optimization.network import solve_network
from src.optimization.scenarios import Scenario,run_scenario
configure_logging(LOG_LEVEL); logger=logging.getLogger('parcel-api'); app=FastAPI(title='Intelligent Parcel Network Optimization',version='2.0.0',docs_url='/docs' if APP_ENV!='production' else None); app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=False,allow_methods=['GET','POST'],allow_headers=['*']); demand,parcels,hubs=generate_demo()
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
 checks={'demo_data':len(demand)>0 and len(hubs)>0,'optimizer_runtime':pywraplp is not None}
 if not all(checks.values()): raise HTTPException(503,{'status':'not_ready','checks':checks})
 return {'status':'ready','checks':checks}
@app.get('/metrics')
def metrics(): return Response(generate_latest(),media_type=CONTENT_TYPE_LATEST)
@app.get('/summary')
def summary(): return {'orders_demo':int(len(parcels)),'demand_rows':int(len(demand)),'hubs':int(len(hubs)),'model_version':MODEL_VERSION,'optimizer_version':OPTIMIZER_VERSION}
@app.get('/network')
def network(): return {'hubs':hubs.to_dict(orient='records'),'demand_rows':int(len(demand)),'model_version':MODEL_VERSION,'optimizer_version':OPTIMIZER_VERSION}
@app.post('/forecast')
def forecast(req:ForecastRequest):
 result=fit_forecaster(demand.tail(req.days*len(hubs)*(len(hubs)-1))); 
 if result.get('test_mae') is not None: FORECAST_MAE.set(result['test_mae'])
 return {**result,'model_version':MODEL_VERSION}
@app.post('/optimize')
def optimize(req:OptimizeRequest):
 try:
  d=demand.tail(7*len(hubs)*(len(hubs)-1)).copy(); d['parcel_count']=(d.parcel_count*req.demand_multiplier).round().astype(int); flows,m=solve_network(d.groupby(['origin_hub','destination_hub'],as_index=False).parcel_count.sum(),hubs,capacity_multiplier=req.capacity_multiplier,service_level_target=req.service_level_target); m.update({'optimizer_version':OPTIMIZER_VERSION,'request_id':request_id_ctx.get()}); UNMET_PARCELS.set(m['unmet_demand']); OPTIMIZATION_RUNS.labels(m['status']).inc(); return {'metrics':m,'flows':flows.to_dict(orient='records')}
 except Exception: OPTIMIZATION_RUNS.labels('error').inc(); logger.exception('optimization_failed'); raise HTTPException(400,{'detail':'Optimization request failed','request_id':request_id_ctx.get()})
@app.post('/scenario')
def scenario(req:ScenarioRequest):
 scenarios={'demand_surge':Scenario('demand_surge','demand_surge',demand_multiplier=1.30),'hub_outage':Scenario('hub_outage','hub_outage',capacity_multiplier=.60),'combined':Scenario('combined','combined',demand_multiplier=1.30,capacity_multiplier=.70)}
 try:
  d=demand.tail(7*len(hubs)*(len(hubs)-1)).groupby(['origin_hub','destination_hub'],as_index=False).parcel_count.sum(); flows,m=run_scenario(d,hubs,scenarios[req.scenario]); UNMET_PARCELS.set(m['unmet_demand']); OPTIMIZATION_RUNS.labels(m['status']).inc(); return {'metrics':m,'flows':flows.to_dict(orient='records')}
 except Exception: OPTIMIZATION_RUNS.labels('error').inc(); logger.exception('scenario_failed'); raise HTTPException(400,{'detail':'Scenario request failed','request_id':request_id_ctx.get()})
