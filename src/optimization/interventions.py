"""Step 10: resilience intervention optimization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .probabilistic import SimulationConfig, generate_random_scenario
from .scenarios import run_scenario


@dataclass(frozen=True)
class Intervention:
    intervention_id: str
    intervention_type: str
    fixed_cost: float = 0.0
    variable_cost: float = 0.0
    capacity_uplift: float = 0.0
    target_hub_id: Optional[object] = None
    fleet_uplift: float = 0.0
    reserve_vehicle_multiplier: float = 0.0
    description: str = ""

    def total_cost(self, horizon_days: int = 1) -> float:
        return self.fixed_cost + self.variable_cost * horizon_days


@dataclass(frozen=True)
class InterventionConfig:
    n_simulations: int = 500
    seed: int = 42
    service_target: float = 0.95
    horizon_days: int = 1


def _apply_intervention(scenario, hubs, intervention):
    from .scenarios import Scenario

    hubs_out = hubs.copy()
    # Intervention multipliers can be fractional (e.g. +25%), so make the
    # capacity column explicitly float before applying them. This avoids
    # pandas incompatible-dtype warnings while preserving the model's
    # continuous capacity representation.
    hubs_out["capacity_parcels"] = hubs_out["capacity_parcels"].astype(float)
    capacity_multiplier = 1.0 + intervention.capacity_uplift
    fleet_multiplier = (
        1.0 + intervention.fleet_uplift + intervention.reserve_vehicle_multiplier
    )

    if intervention.target_hub_id is not None and intervention.capacity_uplift:
        mask = hubs_out["hub_id"] == intervention.target_hub_id
        hubs_out.loc[mask, "capacity_parcels"] *= capacity_multiplier
        capacity_multiplier = 1.0

    scenario_out = Scenario(
        name=scenario.name,
        scenario_type=scenario.scenario_type,
        demand_multiplier=scenario.demand_multiplier,
        capacity_multiplier=scenario.capacity_multiplier * capacity_multiplier,
        fleet_multiplier=scenario.fleet_multiplier * fleet_multiplier,
        disabled_hubs=list(scenario.disabled_hubs),
        disabled_routes=list(scenario.disabled_routes),
    )
    return scenario_out, hubs_out


def _q(values, q):
    values = np.asarray(values, dtype=float)
    return float(np.quantile(values, q)) if values.size else float("nan")


def _summary(rows, intervention, target, horizon_days):
    service = np.asarray([r["service_level"] for r in rows], dtype=float)
    unmet = np.asarray([r["unmet_demand"] for r in rows], dtype=float)
    costs = np.asarray([r["total_transport_cost"] for r in rows], dtype=float)
    var95 = _q(costs, 0.95)
    tail = costs[costs >= var95]
    cvar95 = float(tail.mean()) if tail.size else var95
    return {
        "intervention_id": intervention.intervention_id,
        "intervention_cost": intervention.total_cost(horizon_days),
        "probability_target_met": float(np.mean(service >= target)),
        "service_level_p05": _q(service, .05),
        "service_level_p50": _q(service, .50),
        "service_level_p95": _q(service, .95),
        "unmet_demand_p50": _q(unmet, .50),
        "unmet_demand_p95": _q(unmet, .95),
        "transport_cost_p50": _q(costs, .50),
        "transport_cost_cvar95": cvar95,
    }


def evaluate_interventions(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    fleet: pd.DataFrame,
    interventions: Sequence[Intervention],
    config: InterventionConfig | None = None,
    base_simulation_config: SimulationConfig | None = None,
) -> pd.DataFrame:
    """Evaluate interventions on identical Monte Carlo scenarios.

    Common random numbers make paired intervention comparisons less noisy.
    """
    config = config or InterventionConfig()
    base_simulation_config = base_simulation_config or SimulationConfig(
        n_simulations=config.n_simulations,
        seed=config.seed,
        service_level_target=config.service_target,
    )

    rng = np.random.default_rng(config.seed)
    scenarios = [
        generate_random_scenario(
            hubs, cost_matrix, rng, i, base_simulation_config
        )
        for i in range(config.n_simulations)
    ]

    baseline_rows = []
    intervention_rows = {i.intervention_id: [] for i in interventions}

    for scenario in scenarios:
        baseline_rows.append(run_scenario(demand, hubs, fleet, cost_matrix, scenario)[1])
        for intervention in interventions:
            modified_scenario, modified_hubs = _apply_intervention(
                scenario, hubs, intervention
            )
            intervention_rows[intervention.intervention_id].append(
                run_scenario(
                    demand, modified_hubs, fleet, cost_matrix, modified_scenario
                )[1]
            )

    baseline = _summary(
        baseline_rows,
        Intervention("baseline", "baseline"),
        config.service_target,
        config.horizon_days,
    )
    baseline["intervention_cost"] = 0.0
    baseline["risk_reduction"] = 0.0
    baseline["service_p50_uplift"] = 0.0
    baseline["cost_delta_p50"] = 0.0
    baseline["feasible"] = baseline["probability_target_met"] >= config.service_target

    rows = [baseline]
    for intervention in interventions:
        row = _summary(
            intervention_rows[intervention.intervention_id],
            intervention,
            config.service_target,
            config.horizon_days,
        )
        row["risk_reduction"] = (
            row["probability_target_met"] - baseline["probability_target_met"]
        )
        row["service_p50_uplift"] = (
            row["service_level_p50"] - baseline["service_level_p50"]
        )
        row["cost_delta_p50"] = (
            row["transport_cost_p50"] - baseline["transport_cost_p50"]
        )
        row["feasible"] = row["probability_target_met"] >= config.service_target
        rows.append(row)

    return pd.DataFrame(rows)


def pareto_frontier(results: pd.DataFrame) -> pd.DataFrame:
    """Flag non-dominated points on intervention cost vs reliability."""
    out = results.copy()
    efficient = []
    for i, row in out.iterrows():
        dominated = False
        for j, other in out.iterrows():
            if i == j:
                continue
            no_worse = (
                other["intervention_cost"] <= row["intervention_cost"]
                and other["probability_target_met"] >= row["probability_target_met"]
            )
            strict = (
                other["intervention_cost"] < row["intervention_cost"]
                or other["probability_target_met"] > row["probability_target_met"]
            )
            if no_worse and strict:
                dominated = True
                break
        efficient.append(not dominated)
    out["pareto_efficient"] = efficient
    return out
