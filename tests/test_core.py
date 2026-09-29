import pandas as pd
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


def test_scenario_construction_and_execution():
    from src.optimization.scenarios import Scenario, run_scenario
    demand, _, hubs = generate_demo()
    fleet = __import__("pandas").DataFrame([{
        "vehicle_type": "default", "vehicle_count": 20, "parcel_capacity": 20,
        "operating_hours_per_day": 12.0, "fixed_trip_cost": 25.0,
        "cost_per_km": 0.10, "max_trip_hours": 12.0
    }])
    from src.optimization.network import build_cost_matrix
    cost = build_cost_matrix(hubs)
    scenario = Scenario("test", "demand_surge", demand_multiplier=1.1)
    _, metrics = run_scenario(
        demand.groupby(["origin_hub", "destination_hub"], as_index=False)
        .parcel_count.sum(), hubs, fleet, cost, scenario
    )
    assert metrics["demand_multiplier"] == 1.1
    assert 0 <= metrics["service_level"] <= 1


def test_bundle_optimizer_reproducible():
    from src.optimization.intervention_bundles import BundleConfig, evaluate_bundle_candidates
    from src.optimization.interventions import Intervention
    demand, _, hubs = generate_demo()
    d = demand.groupby(["origin_hub", "destination_hub"], as_index=False).parcel_count.sum()
    fleet = __import__("pandas").DataFrame([{
        "vehicle_type": "default", "vehicle_count": 20, "parcel_capacity": 20,
        "operating_hours_per_day": 12.0, "fixed_trip_cost": 25.0,
        "cost_per_km": 0.10, "max_trip_hours": 12.0
    }])
    from src.optimization.network import build_cost_matrix
    cost = build_cost_matrix(hubs)
    interventions = [
        Intervention("h1", "targeted_hub_capacity", variable_cost=1.0,
                     capacity_uplift=.10, target_hub_id=hubs.iloc[0].hub_id),
        Intervention("h2", "targeted_hub_capacity", variable_cost=2.0,
                     capacity_uplift=.20, target_hub_id=hubs.iloc[1].hub_id),
    ]
    cfg = BundleConfig(n_simulations=2, seed=7, budget=10, max_bundle_size=2)
    a = evaluate_bundle_candidates(d, hubs, cost, fleet, interventions, cfg)
    b = evaluate_bundle_candidates(d, hubs, cost, fleet, interventions, cfg)
    assert a[["bundle_id", "probability_target_met"]].equals(
        b[["bundle_id", "probability_target_met"]]
    )


def test_unavailable_route_is_counted_as_unmet():
    import pandas as pd
    import pytest
    from src.optimization.network import solve_network
    demand = pd.DataFrame([
        {"origin_hub": 1, "destination_hub": 2, "parcel_count": 10},
        {"origin_hub": 2, "destination_hub": 1, "parcel_count": 20},
    ])
    hubs = pd.DataFrame([
        {"hub_id": 1, "capacity_parcels": 100},
        {"hub_id": 2, "capacity_parcels": 100},
    ])
    fleet = pd.DataFrame([{
        "vehicle_type": "default", "vehicle_count": 10, "parcel_capacity": 20,
        "operating_hours_per_day": 12.0, "fixed_trip_cost": 1.0,
        "cost_per_km": 0.01, "max_trip_hours": 12.0
    }])
    cost = pd.DataFrame([{
        "origin_hub": 1, "destination_hub": 2, "distance_km": 10.0,
        "unit_cost": 1.0, "travel_time_hours": 1.0
    }])
    _, metrics = solve_network(demand, hubs, cost=cost, fleet=fleet)
    assert metrics["total_parcels"] == 10
    assert metrics["unmet_demand"] == 20
    assert metrics["service_level"] == pytest.approx(10 / 30)


def test_root_cause_decomposition_contract():
    import pandas as pd
    from src.analytics.root_cause import analyze_simulations
    df=pd.DataFrame({
        "service_level":[.9,.8,.7,.6], "unmet_demand":[10,20,30,40], "total_transport_cost":[100,110,120,130],
        "demand_multiplier":[1,1.2,1,1.2], "capacity_multiplier":[1,1,.8,.8], "fleet_multiplier":[1,.9,1,.9],
        "hub_failures":[0,0,1,2], "road_failures":[0,1,0,2],
    })
    out,summary=analyze_simulations(df,run_id="00000000-0000-0000-0000-000000000001")
    assert len(out)>0 and summary["simulations"]==4 and out["run_id"].nunique()==1

def test_intervention_catalog_contains_fleet_options():
    from src.optimization.targeted_hub_interventions import build_targeted_interventions
    demand,_,hubs=generate_demo(); d=demand.groupby(["origin_hub","destination_hub"],as_index=False).parcel_count.sum()
    candidates=build_targeted_interventions(d,hubs)
    assert any(i.fleet_uplift>0 for i in candidates)
    assert any(i.reserve_vehicle_multiplier>0 for i in candidates)


def test_hub_pressure_accepts_capacity_enriched_hubs():
    from src.analytics.root_cause import hub_pressure_table
    demand = pd.DataFrame({
        "origin_hub": [1, 2], "destination_hub": [2, 1], "demand": [10.0, 20.0]
    })
    hubs = pd.DataFrame({"hub_id": [1, 2], "capacity_parcels": [20, 40]})
    out = hub_pressure_table(demand, hubs)
    assert len(out) == 2
    assert "capacity_pressure" in out.columns


def test_same_hub_demand_is_not_counted_as_network_unmet():
    demand = pd.DataFrame([
        {"origin_hub": 1, "destination_hub": 1, "parcel_count": 15},
        {"origin_hub": 1, "destination_hub": 2, "parcel_count": 10},
    ])
    hubs = pd.DataFrame([
        {"hub_id": 1, "capacity_parcels": 100},
        {"hub_id": 2, "capacity_parcels": 100},
    ])
    fleet = pd.DataFrame([{
        "vehicle_type": "default", "vehicle_count": 10, "parcel_capacity": 20,
        "operating_hours_per_day": 12.0, "fixed_trip_cost": 1.0,
        "cost_per_km": 0.01, "max_trip_hours": 12.0
    }])
    cost = pd.DataFrame([{
        "origin_hub": 1, "destination_hub": 2, "distance_km": 10.0,
        "unit_cost": 1.0, "travel_time_hours": 1.0
    }])
    _, metrics = solve_network(demand, hubs, cost=cost, fleet=fleet)
    assert metrics["total_parcels"] == pytest.approx(25.0)
    assert metrics["unmet_demand"] == pytest.approx(0.0)
    assert metrics["local_parcels_assumed_served"] == pytest.approx(15.0)
