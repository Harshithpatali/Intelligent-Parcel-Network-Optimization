from typing import Literal
from pydantic import BaseModel,Field
class ForecastRequest(BaseModel): days:int=Field(30,ge=1,le=365)
class OptimizeRequest(BaseModel):
    demand_multiplier:float=Field(1.0,ge=.1,le=3.0); capacity_multiplier:float=Field(1.0,gt=.1,le=1.5); service_level_target:float=Field(.95,ge=0,le=1)
class ScenarioRequest(BaseModel): scenario:Literal['demand_surge','hub_outage','combined']='demand_surge'
