"""Step 10C: constrained intervention bundle optimization."""

from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

import numpy as np
import pandas as pd

from .interventions import Intervention, _apply_intervention
from .probabilistic import SimulationConfig, generate_random_scenario
from .scenarios import run_scenario


@dataclass(frozen=True)
class BundleConfig:
    n_simulations: int = 500
    seed: int = 42
    budget: float = 100.0
    service_target: float = 0.95
    required_reliability: float = 0.90
    max_bundle_size: int = 3
    unmet_weight: float = 1.0
    cvar_weight: float = 0.0


def _q(values, q):
    values = np.asarray(values, dtype=float)
    return float(np.quantile(values, q)) if values.size else float("nan")


def _summary(rows, target):
    service = np.asarray([r["service_level"] for r in rows], dtype=float)
    unmet = np.asarray([r["unmet_demand"] for r in rows], dtype=float)
    costs = np.asarray([r["total_transport_cost"] for r in rows], dtype=float)
    var95 = _q(costs, .95)
    tail = costs[costs >= var95]
    return {
        "probability_target_met": float(np.mean(service >= target)),
        "service_level_p05": _q(service, .05),
        "service_level_p50": _q(service, .50),
        "unmet_demand_p95": _q(unmet, .95),
        "expected_unmet_demand": float(unmet.mean()),
        "transport_cost_p50": _q(costs, .50),
        "transport_cost_cvar95": float(tail.mean()) if tail.size else var95,
    }


def _apply_bundle(scenario, hubs, interventions):
    modified_scenario = scenario
    modified_hubs = hubs.copy()
    for intervention in interventions:
        modified_scenario, modified_hubs = _apply_intervention(
            modified_scenario, modified_hubs, intervention
        )
    return modified_scenario, modified_hubs


def _deduplicate_interventions(interventions):
    by_id = {}
    for intervention in interventions:
        if intervention.intervention_id in by_id:
            raise ValueError(f"Duplicate intervention_id: {intervention.intervention_id}")
        by_id[intervention.intervention_id] = intervention
    return list(by_id.values())


def evaluate_bundle_candidates(demand, hubs, cost_matrix, fleet,
                               interventions: Sequence[Intervention],
                               config: BundleConfig | None = None) -> pd.DataFrame:
    config = config or BundleConfig()
    if config.budget < 0 or config.max_bundle_size < 0 or config.n_simulations < 1:
        raise ValueError("Invalid bundle configuration.")
    interventions = _deduplicate_interventions(interventions)

    sim_cfg = SimulationConfig(
        n_simulations=config.n_simulations,
        seed=config.seed,
        service_level_target=config.service_target,
    )
    rng = np.random.default_rng(config.seed)
    scenarios = [
        generate_random_scenario(hubs, cost_matrix, rng, i, sim_cfg)
        for i in range(config.n_simulations)
    ]

    bundles = [()]
    for size in range(1, min(config.max_bundle_size, len(interventions)) + 1):
        bundles.extend(combinations(interventions, size))

    results = []
    for bundle in bundles:
        cost = sum(i.total_cost(1) for i in bundle)
        if cost > config.budget:
            continue

        rows = []
        for scenario in scenarios:
            s, h = _apply_bundle(scenario, hubs, bundle)
            _, metrics = run_scenario(demand, h, fleet, cost_matrix, s)
            rows.append(metrics)

        summary = _summary(rows, config.service_target)
        objective = (
            cost
            + config.unmet_weight * summary["expected_unmet_demand"]
            + config.cvar_weight * summary["transport_cost_cvar95"]
        )
        results.append({
            "bundle_id": "baseline" if not bundle else "+".join(i.intervention_id for i in bundle),
            "intervention_cost": cost,
            **summary,
            "objective_value": objective,
            "feasible": summary["probability_target_met"] >= config.required_reliability,
            "selected_interventions": [i.intervention_id for i in bundle],
        })

    if not results:
        raise ValueError("No intervention bundle fits the configured budget.")

    out = pd.DataFrame(results)
    efficient = []
    for i, row in out.iterrows():
        dominated = (
            (out["intervention_cost"] <= row["intervention_cost"])
            & (out["probability_target_met"] >= row["probability_target_met"])
            & (
                (out["intervention_cost"] < row["intervention_cost"])
                | (out["probability_target_met"] > row["probability_target_met"])
            )
        )
        efficient.append(not bool(dominated.any()))
    out["pareto_efficient"] = efficient
    return out.sort_values(
        ["feasible", "objective_value", "intervention_cost"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
