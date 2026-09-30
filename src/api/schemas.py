from typing import Literal
from pydantic import BaseModel,Field
class ForecastRequest(BaseModel): days:int=Field(30,ge=1,le=365)
class OptimizeRequest(BaseModel):
 demand_multiplier:float=Field(1.0,ge=.1,le=3.0); capacity_multiplier:float=Field(1.0,gt=.1,le=3.0); service_level_target:float=Field(.95,ge=0,le=1)
class ScenarioRequest(BaseModel): scenario:Literal['demand_surge','capacity_shock','fleet_shortage','hub_outage','road_disruption','combined']='demand_surge'
class RoutingRequest(BaseModel):
    demand_multiplier:float=Field(1.0,ge=.1,le=3.0)
    parcel_capacity:int=Field(40,ge=1,le=200)
    max_route_hours:float=Field(16.0,gt=0,le=48)
    max_stops:int=Field(5,ge=1,le=15)
    fixed_trip_cost:float=Field(45.0,ge=0)
    cost_per_km:float=Field(.075,ge=0)
    distance_weight:float=Field(.5,ge=0)
    time_weight:float=Field(.5,ge=0)
