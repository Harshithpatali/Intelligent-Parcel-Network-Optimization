from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

from src.optimization.scenarios import Scenario, run_scenario


@dataclass(frozen=True)
class SimulationConfig:
    n_simulations: int = 500
    seed: int = 42
    service_level_target: float = 0.95

    # Stochastic demand: lognormal around 1.0, clipped to avoid extreme tails.
    demand_sigma: float = 0.12
    demand_min: float = 0.70
    demand_max: float = 1.60

    # Network capacity shock.
    capacity_mean: float = 1.00
    capacity_std: float = 0.10
    capacity_min: float = 0.60
    capacity_max: float = 1.20

    # Fleet availability as a multiplicative random shock.
    fleet_mean: float = 1.00
    fleet_std: float = 0.12
    fleet_min: float = 0.60
    fleet_max: float = 1.20

    # Independent failure probabilities per simulation.
    hub_failure_probability: float = 0.05
    route_failure_probability: float = 0.02

    # Limit simultaneous failures to keep the scenario interpretable.
    max_hub_failures: int = 2
    max_route_failures: int = 5


def _sample_lognormal_multiplier(rng, sigma, low, high):
    # Median = 1.0, rather than mean = 1.0, which keeps the baseline intuitive.
    value = rng.lognormal(mean=-0.5 * sigma * sigma, sigma=sigma)
    return float(np.clip(value, low, high))


def _sample_truncated_normal(rng, mean, std, low, high):
    return float(np.clip(rng.normal(mean, std), low, high))


def generate_random_scenario(hubs, cost, rng, index, config):
    demand_multiplier = _sample_lognormal_multiplier(
        rng, config.demand_sigma, config.demand_min, config.demand_max
    )
    capacity_multiplier = _sample_truncated_normal(
        rng, config.capacity_mean, config.capacity_std,
        config.capacity_min, config.capacity_max
    )
    fleet_multiplier = _sample_truncated_normal(
        rng, config.fleet_mean, config.fleet_std,
        config.fleet_min, config.fleet_max
    )

    hub_ids = hubs.hub_id.astype(int).tolist()
    failed_hubs = tuple(
        int(h)
        for h in hub_ids
        if rng.random() < config.hub_failure_probability
    )
    failed_hubs = failed_hubs[:config.max_hub_failures]

    route_pairs = list(
        zip(cost.origin_hub.astype(int), cost.destination_hub.astype(int))
    )
    route_pairs = list(dict.fromkeys(route_pairs))
    failed_routes = tuple(
        pair for pair in route_pairs
        if pair[0] not in failed_hubs
        and pair[1] not in failed_hubs
        and rng.random() < config.route_failure_probability
    )[:config.max_route_failures]

    return Scenario(
        name=f"sim_{index:05d}",
        scenario_type="probabilistic_resilience",
        demand_multiplier=demand_multiplier,
        capacity_multiplier=capacity_multiplier,
        fleet_multiplier=fleet_multiplier,
        disabled_hubs=failed_hubs,
        disabled_routes=failed_routes,
    )


def run_probabilistic_simulation(
    demand,
    hubs,
    fleet,
    cost,
    config: Optional[SimulationConfig] = None,
):
    config = config or SimulationConfig()
    rng = np.random.default_rng(config.seed)
    rows = []

    for i in range(config.n_simulations):
        scenario = generate_random_scenario(
            hubs, cost, rng, i, config
        )
        _, metrics = run_scenario(
            demand=demand,
            hubs=hubs,
            fleet=fleet,
            cost=cost,
            scenario=scenario,
        )

        service = float(metrics["service_level"])
        rows.append({
            "simulation_index": i,
            "simulation_seed": config.seed,
            "scenario_name": scenario.name,
            "demand_multiplier": scenario.demand_multiplier,
            "capacity_multiplier": scenario.capacity_multiplier,
            "fleet_multiplier": scenario.fleet_multiplier,
            "hub_failures": len(scenario.disabled_hubs),
            "road_failures": len(scenario.disabled_routes),
            "service_level": service,
            "unmet_demand": float(metrics["unmet_demand"]),
            "total_transport_cost": float(metrics["total_transport_cost"]),
            "objective_with_unmet_penalty": float(
                metrics["objective_with_unmet_penalty"]
            ),
            "target_met": service >= config.service_level_target,
        })

    return pd.DataFrame(rows)


def summarize_risk(results, service_level_target=0.95):
    if results.empty:
        raise ValueError("Simulation produced no results.")

    cost = results["total_transport_cost"]
    service = results["service_level"]
    unmet = results["unmet_demand"]

    var95 = float(cost.quantile(0.95))
    tail = cost[cost >= var95]
    cvar95 = float(tail.mean()) if len(tail) else var95

    return {
        "n_simulations": int(len(results)),
        "target_service_level": float(service_level_target),
        "probability_target_met": float(
            (results["service_level"] >= service_level_target).mean()
        ),
        "service_level_p05": float(service.quantile(0.05)),
        "service_level_p50": float(service.quantile(0.50)),
        "service_level_p95": float(service.quantile(0.95)),
        "unmet_demand_p50": float(unmet.quantile(0.50)),
        "unmet_demand_p95": float(unmet.quantile(0.95)),
        "transport_cost_p50": float(cost.quantile(0.50)),
        "transport_cost_p95": float(cost.quantile(0.95)),
        "transport_cost_var95": var95,
        "transport_cost_cvar95": cvar95,
    }
