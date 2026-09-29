from dataclasses import dataclass
from itertools import product
from uuid import uuid4
import pandas as pd

from src.optimization.scenarios import Scenario, run_scenario


@dataclass(frozen=True)
class FrontierConfig:
    demand_levels: tuple[float, ...] = (1.00, 1.10, 1.20, 1.30, 1.40, 1.50)
    capacity_levels: tuple[float, ...] = (0.75, 0.85, 1.00, 1.10, 1.25)
    fleet_levels: tuple[float, ...] = (0.70, 0.85, 1.00, 1.15, 1.30)
    service_level_target: float = 0.95


def build_frontier_scenarios(config: FrontierConfig) -> list[Scenario]:
    scenarios = []
    for demand, capacity, fleet in product(
        config.demand_levels,
        config.capacity_levels,
        config.fleet_levels,
    ):
        name = (
            f"d{demand:.2f}_c{capacity:.2f}_f{fleet:.2f}"
        )
        scenarios.append(
            Scenario(
                name=name,
                scenario_type="resilience_grid",
                demand_multiplier=demand,
                capacity_multiplier=capacity,
                fleet_multiplier=fleet,
            )
        )
    return scenarios


def run_resilience_frontier(
    demand,
    hubs,
    fleet,
    cost,
    config: FrontierConfig | None = None,
):
    config = config or FrontierConfig()
    rows = []

    for scenario in build_frontier_scenarios(config):
        _, metrics = run_scenario(
            demand=demand,
            hubs=hubs,
            fleet=fleet,
            cost=cost,
            scenario=scenario,
        )

        service = float(metrics["service_level"])
        cost_value = float(metrics["total_transport_cost"])
        feasible = service >= config.service_level_target

        # Intervention score is a transparent normalized burden:
        # additional capacity + additional fleet relative to baseline.
        capacity_intervention = max(0.0, scenario.capacity_multiplier - 1.0)
        fleet_intervention = max(0.0, scenario.fleet_multiplier - 1.0)
        intervention_score = capacity_intervention + fleet_intervention

        rows.append({
            "run_id": str(uuid4()),
            "scenario_name": scenario.name,
            "demand_multiplier": scenario.demand_multiplier,
            "capacity_multiplier": scenario.capacity_multiplier,
            "fleet_multiplier": scenario.fleet_multiplier,
            "service_level": service,
            "unmet_demand": float(metrics["unmet_demand"]),
            "total_transport_cost": cost_value,
            "objective_with_unmet_penalty": float(
                metrics["objective_with_unmet_penalty"]
            ),
            "feasible_target": feasible,
            "service_level_target": config.service_level_target,
            "intervention_score": intervention_score,
        })

    result = pd.DataFrame(rows)

    # Pareto frontier: retain points for which no other point has both
    # lower/equal cost and higher/equal service, with at least one strict gain.
    frontier = []
    for i, row in result.iterrows():
        dominated = False
        for j, other in result.iterrows():
            if i == j:
                continue
            no_worse = (
                other.total_transport_cost <= row.total_transport_cost
                and other.service_level >= row.service_level
            )
            strictly_better = (
                other.total_transport_cost < row.total_transport_cost
                or other.service_level > row.service_level
            )
            if no_worse and strictly_better:
                dominated = True
                break
        frontier.append(not dominated)

    result["pareto_frontier"] = frontier
    return result.sort_values(
        ["feasible_target", "service_level", "total_transport_cost"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
