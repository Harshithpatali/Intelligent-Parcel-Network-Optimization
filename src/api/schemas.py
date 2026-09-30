from typing import Literal
from pydantic import BaseModel, Field

class ForecastRequest(BaseModel):
    days: int = Field(30, ge=1, le=365)

class OptimizeRequest(BaseModel):
    demand_multiplier: float = Field(1.0, ge=.1, le=3.0)
    capacity_multiplier: float = Field(1.0, gt=.1, le=3.0)
    service_level_target: float = Field(.95, ge=0, le=1)

class ScenarioRequest(BaseModel):
    scenario: Literal["demand_surge","capacity_shock","fleet_shortage","hub_outage","road_disruption","combined"] = "demand_surge"

class RoutingRequest(BaseModel):
    demand_multiplier: float = Field(1.0, ge=.1, le=3.0)

    vehicle_type: str = Field("linehaul_truck")
    parcel_capacity: int = Field(40, ge=1, le=500)
    parcel_capacity_overridden: bool = False

    max_route_hours: float = Field(16.0, gt=0, le=72)
    max_stops: int = Field(5, ge=1, le=15)

    fixed_trip_cost: float = Field(45.0, ge=0)
    cost_per_km: float = Field(.075, ge=0)

    distance_weight: float = Field(.4, ge=0)
    time_weight: float = Field(.4, ge=0)
    economic_weight: float = Field(.2, ge=0)

    service_time_minutes_per_stop: float = Field(15.0, ge=0, le=180)
    loading_minutes: float = Field(30.0, ge=0, le=240)
    unloading_minutes_per_parcel: float = Field(.5, ge=0, le=10)

    max_weight_kg: float = Field(12000.0, gt=0, le=100000)
    max_volume_m3: float = Field(65.0, gt=0, le=1000)

    driver_break_hours: float = Field(.5, ge=0, le=4)
    return_to_origin: bool = False
    empty_return_factor: float = Field(.35, ge=0, le=1)

    max_detour_pct: float = Field(25.0, ge=0, le=100)
    max_time_detour_pct: float = Field(25.0, ge=0, le=100)
    min_capacity_utilization: float = Field(.60, ge=0, le=1)

    staging_buffer_hours: float = Field(.5, ge=0, le=4)
