from dataclasses import dataclass
from src.optimization.network import solve_network
@dataclass(frozen=True)
class Scenario:
    name:str; demand_multiplier:float=1.0; capacity_multiplier:float=1.0
def run_scenario(demand,hubs,scenario):
    d=demand.copy(); d['parcel_count']=(d.parcel_count*scenario.demand_multiplier).round().astype(int)
    flows,metrics=solve_network(d,hubs,capacity_multiplier=scenario.capacity_multiplier)
    metrics.update({'scenario':scenario.name,'demand_multiplier':scenario.demand_multiplier,'capacity_multiplier':scenario.capacity_multiplier})
    return flows,metrics
