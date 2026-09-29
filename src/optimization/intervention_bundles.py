"""Step 10C: constrained intervention bundle optimization.

The bundle search uses a two-stage stochastic screening design:
1. deterministic dominance pruning for capacity-only intervention catalogs;
2. a pilot Monte Carlo sample to screen candidates;
3. full Monte Carlo evaluation (default 500 simulations) for finalists.

This keeps the final risk estimates at the requested simulation count while
avoiding thousands of unnecessary SCIP solves.
"""

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
    pilot_simulations: int = 30
    final_candidate_limit: int = 75


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


def _bundle_resource_signature(bundle, hub_ids):
    """Return effective per-hub capacity uplift for a capacity-only bundle."""
    multipliers = {hub_id: 1.0 for hub_id in hub_ids}
    fleet_multiplier = 1.0
    for intervention in bundle:
        if intervention.capacity_uplift:
            if intervention.target_hub_id is None:
                for hub_id in multipliers:
                    multipliers[hub_id] *= 1.0 + intervention.capacity_uplift
            elif intervention.target_hub_id in multipliers:
                multipliers[intervention.target_hub_id] *= 1.0 + intervention.capacity_uplift
        fleet_multiplier *= 1.0 + intervention.fleet_uplift + intervention.reserve_vehicle_multiplier
    return tuple(round(multipliers[hub_id] - 1.0, 12) for hub_id in hub_ids) + (round(fleet_multiplier - 1.0, 12),)


def _deterministically_non_dominated(bundles, hubs, budget):
    """Prune bundles dominated on all monotone resources at no greater cost."""
    candidates = [b for b in bundles if sum(i.total_cost(1) for i in b) <= budget]
    hub_ids = list(hubs.hub_id)
    scored = [(b, sum(i.total_cost(1) for i in b), _bundle_resource_signature(b, hub_ids)) for b in candidates]
    keep = []
    for bundle, cost, signature in scored:
        dominated = False
        for other_bundle, other_cost, other_signature in scored:
            if other_bundle == bundle:
                continue
            if other_cost <= cost and all(a >= b for a, b in zip(other_signature, signature)) and (other_cost < cost or other_signature != signature):
                dominated = True
                break
        if not dominated:
            keep.append(bundle)
    return keep

def _pareto_flags(out):
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
    return efficient


def _evaluate_bundles(demand, hubs, cost_matrix, fleet, bundles, scenarios,
                      target, required_reliability, unmet_weight, cvar_weight,
                      progress_label):
    results = []
    total = len(bundles)
    for idx, bundle in enumerate(bundles, start=1):
        cost = sum(i.total_cost(1) for i in bundle)
        rows = []
        for scenario in scenarios:
            s, h = _apply_bundle(scenario, hubs, bundle)
            _, metrics = run_scenario(demand, h, fleet, cost_matrix, s)
            rows.append(metrics)

        summary = _summary(rows, target)
        results.append({
            "bundle_id": "baseline" if not bundle else "+".join(i.intervention_id for i in bundle),
            "intervention_cost": cost,
            **summary,
            "objective_value": (
                cost
                + unmet_weight * summary["expected_unmet_demand"]
                + cvar_weight * summary["transport_cost_cvar95"]
            ),
            "feasible": summary["probability_target_met"] >= required_reliability,
            "selected_interventions": [i.intervention_id for i in bundle],
        })
        if idx == 1 or idx == total or idx % 10 == 0:
            print(f"{progress_label}: {idx}/{total}", flush=True)
    return results


def _select_final_candidates(pilot, limit):
    if len(pilot) <= limit:
        return pilot

    selected = {"baseline"}

    # Protect different notions of promise against pilot noise.
    ranked = [
        pilot.sort_values(["objective_value", "intervention_cost"]),
        pilot.sort_values(["probability_target_met", "service_level_p50"], ascending=[False, False]),
        pilot.sort_values(["expected_unmet_demand", "intervention_cost"]),
        pilot.sort_values(["intervention_cost", "probability_target_met"]),
    ]
    slice_size = max(1, limit // len(ranked))
    for frame in ranked:
        selected.update(frame.head(slice_size)["bundle_id"].tolist())

    # Feasible pilot candidates are retained first.
    feasible = pilot[pilot["feasible"]].sort_values(
        ["objective_value", "intervention_cost"]
    )
    selected.update(feasible["bundle_id"].tolist())

    if len(selected) > limit:
        # Keep baseline plus the strongest pilot candidates.
        chosen = pilot[pilot["bundle_id"].isin(selected)].sort_values(
            ["feasible", "objective_value", "probability_target_met"],
            ascending=[False, True, False],
        )
        selected = set(chosen.head(limit)["bundle_id"])

    if len(selected) < limit:
        for bundle_id in pilot.sort_values(
            ["objective_value", "intervention_cost"]
        )["bundle_id"]:
            selected.add(bundle_id)
            if len(selected) >= limit:
                break

    return pilot[pilot["bundle_id"].isin(selected)].copy()


def evaluate_bundle_candidates(
    demand, hubs, cost_matrix, fleet,
    interventions: Sequence[Intervention],
    config: BundleConfig | None = None,
) -> pd.DataFrame:
    config = config or BundleConfig()
    if (
        config.budget < 0
        or config.max_bundle_size < 0
        or config.n_simulations < 1
        or config.pilot_simulations < 1
        or config.final_candidate_limit < 1
    ):
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

    # Service and unmet-demand objectives are monotone in capacity and fleet.
    monotone_resources = config.cvar_weight == 0 and config.unmet_weight >= 0
    if monotone_resources:
        bundles = _deterministically_non_dominated(
            bundles, hubs, config.budget
        )
        print(f"Deterministic bundle pruning retained {len(bundles)} candidates.", flush=True)
    else:
        bundles = [
            b for b in bundles
            if sum(i.total_cost(1) for i in b) <= config.budget
        ]

    if not bundles:
        raise ValueError("No intervention bundle fits the configured budget.")

    pilot_n = min(config.pilot_simulations, config.n_simulations)
    pilot_scenarios = scenarios[:pilot_n]
    pilot_rows = _evaluate_bundles(
        demand, hubs, cost_matrix, fleet, bundles,
        pilot_scenarios,
        config.service_target,
        config.required_reliability,
        config.unmet_weight,
        config.cvar_weight,
        "Pilot bundle evaluation",
    )
    pilot = pd.DataFrame(pilot_rows)

    final_pilot = _select_final_candidates(
        pilot, config.final_candidate_limit
    )
    final_ids = set(final_pilot["bundle_id"])
    final_bundles = [
        b for b in bundles
        if ("baseline" if not b else "+".join(i.intervention_id for i in b)) in final_ids
    ]

    print(
        f"Full Monte Carlo evaluation: {len(final_bundles)} candidates × "
        f"{config.n_simulations} simulations.",
        flush=True,
    )
    final_rows = _evaluate_bundles(
        demand, hubs, cost_matrix, fleet, final_bundles,
        scenarios,
        config.service_target,
        config.required_reliability,
        config.unmet_weight,
        config.cvar_weight,
        "Full bundle evaluation",
    )

    out = pd.DataFrame(final_rows)
    out["pareto_efficient"] = _pareto_flags(out)
    out["pilot_candidates"] = len(bundles)
    out["final_candidates"] = len(final_bundles)
    out["pilot_simulations"] = pilot_n
    out["full_simulations"] = config.n_simulations

    return out.sort_values(
        ["feasible", "objective_value", "intervention_cost"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
