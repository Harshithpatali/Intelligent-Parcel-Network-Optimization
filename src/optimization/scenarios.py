from dataclasses import dataclass, field
from typing import Iterable
import pandas as pd
from src.optimization.network import solve_network


@dataclass(frozen=True)
class Scenario:
    name: str
    scenario_type: str
    demand_multiplier: float = 1.0
    capacity_multiplier: float = 1.0
    fleet_multiplier: float = 1.0
    disabled_hubs: tuple[int, ...] = field(default_factory=tuple)
    disabled_routes: tuple[tuple[int, int], ...] = field(default_factory=tuple)


def apply_scenario(demand, hubs, fleet, cost, scenario: Scenario):
    d = demand.copy()
    d["parcel_count"] = (
        pd.to_numeric(d["parcel_count"]).clip(lower=0)
        * scenario.demand_multiplier
    )

    h = hubs.copy()
    f = fleet.copy()
    c = cost.copy()

    if scenario.disabled_hubs:
        disabled = set(scenario.disabled_hubs)
        # Keep affected demand so the optimizer records it as unmet.
        # Only remove the failed hub and its network connections.
        h = h[~h.hub_id.isin(disabled)].copy()
        c = c[
            ~c.origin_hub.isin(disabled)
            & ~c.destination_hub.isin(disabled)
        ].copy()

    if scenario.disabled_routes:
        disabled_routes = set(scenario.disabled_routes)
        mask = c.apply(
            lambda r: (int(r.origin_hub), int(r.destination_hub))
            in disabled_routes,
            axis=1,
        )
        c = c[~mask].copy()

    if scenario.fleet_multiplier != 1.0:
        f["vehicle_count"] = (
            f["vehicle_count"] * scenario.fleet_multiplier
        ).round().astype(int).clip(lower=0)

    return d, h, f, c


def run_scenario(demand, hubs, fleet, cost, scenario: Scenario):
    d, h, f, c = apply_scenario(demand, hubs, fleet, cost, scenario)

    flows, metrics = solve_network(
        demand=d,
        hubs=h,
        fleet=f,
        cost=c,
        capacity_multiplier=scenario.capacity_multiplier,
    )

    metrics.update({
        "scenario": scenario.name,
        "scenario_type": scenario.scenario_type,
        "demand_multiplier": scenario.demand_multiplier,
        "capacity_multiplier": scenario.capacity_multiplier,
        "fleet_multiplier": scenario.fleet_multiplier,
        "disabled_hubs": list(scenario.disabled_hubs),
        "disabled_routes": [list(x) for x in scenario.disabled_routes],
    })
    return flows, metrics


def standard_scenarios(hubs: pd.DataFrame, cost: pd.DataFrame) -> list[Scenario]:
    hub_ids = sorted(hubs.hub_id.astype(int).tolist())
    if not hub_ids:
        return []

    # Deterministic, transparent benchmark scenarios. These are scenario definitions,
    # not claims about actual carrier disruptions.
    outage_hub = hub_ids[0]
    routes = cost[
        (cost.origin_hub == outage_hub) | (cost.destination_hub == outage_hub)
    ].sort_values("distance_km")
    route = (
        int(routes.iloc[0].origin_hub),
        int(routes.iloc[0].destination_hub),
    ) if not routes.empty else None

    scenarios = [
        Scenario("baseline", "baseline"),
        Scenario("demand_surge_25pct", "demand_surge", demand_multiplier=1.25),
        Scenario("capacity_shock_minus_25pct", "capacity_shock", capacity_multiplier=0.75),
        Scenario("fleet_shortage_minus_30pct", "fleet_shortage", fleet_multiplier=0.70),
        Scenario("hub_outage", "hub_outage", disabled_hubs=(outage_hub,)),
    ]
    if route:
        scenarios.append(
            Scenario("road_disruption", "road_disruption", disabled_routes=(route,))
        )
    return scenarios
