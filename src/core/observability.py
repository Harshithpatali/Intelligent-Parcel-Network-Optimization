from prometheus_client import Counter,Histogram,Gauge
REQUESTS=Counter('parcel_api_requests_total','API requests',['method','path','status'])
LATENCY=Histogram('parcel_api_request_duration_seconds','API request latency',['path'])
OPTIMIZATION_RUNS=Counter('parcel_optimization_runs_total','Optimization runs',['status'])
UNMET_PARCELS=Gauge('parcel_unmet_demand','Unmet parcels from latest optimization')
FORECAST_MAE=Gauge('parcel_forecast_mae','Latest forecast validation MAE')
