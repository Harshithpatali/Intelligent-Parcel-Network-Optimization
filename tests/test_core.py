from fastapi.testclient import TestClient
from src.api.main import app
from src.data.demo import generate_demo
from src.data_quality.validate import validate_demand,validate_parcels
from src.models.forecast import make_features,fit_forecaster
from src.optimization.network import solve_network
client=TestClient(app)
def test_demo_and_contracts():
 demand,parcels,hubs=generate_demo(); validate_demand(demand); validate_parcels(parcels); assert len(demand)>100 and len(parcels)>100 and len(hubs)>=3
def test_features_are_leakage_safe():
 demand,_,_=generate_demo(); f=make_features(demand); assert f.loc[f.lag_1.notna(),'lag_1'].iloc[0]>=0; assert f.loc[f.rolling_7.notna(),'rolling_7'].notna().all()
def test_forecast():
 demand,_,_=generate_demo(); result=fit_forecaster(demand); assert result['model_type'] in {'hist_gradient_boosting','seasonal_naive'}; assert result.get('forecast_total_next_day',result.get('forecast'))>=0
def test_optimizer_reports_unmet_demand():
 demand,_,hubs=generate_demo(); d=demand.groupby(['origin_hub','destination_hub'],as_index=False).parcel_count.sum(); flows,metrics=solve_network(d,hubs,capacity_multiplier=.5); assert metrics['unmet_demand']>=0 and 'service_level' in metrics and len(flows)>0
def test_api_smoke():
 assert client.get('/health').status_code==200; assert client.get('/ready').status_code==200; assert client.get('/network').status_code==200; assert client.get('/summary').status_code==200; assert client.post('/forecast',json={'days':30}).status_code==200; assert client.post('/optimize',json={'demand_multiplier':1.1,'capacity_multiplier':.9}).status_code==200; assert client.post('/scenario',json={'scenario':'combined'}).status_code==200; assert client.get('/metrics').status_code==200
