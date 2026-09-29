"""Research-grade targeted hub intervention generation and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .interventions import Intervention, InterventionConfig, evaluate_interventions, pareto_frontier


@dataclass(frozen=True)
class TargetedInterventionConfig:
    top_hubs: int = 5
    capacity_steps: tuple[float, ...] = (0.10, 0.20, 0.30)
    backup_capacity: float = 0.25
    hub_capacity_unit_cost: float = 8.0
    backup_fixed_cost: float = 60.0


def rank_hubs(demand: pd.DataFrame, hubs: pd.DataFrame, top_n: int = 5) -> pd.DataFrame:
    outbound = demand.groupby("origin_hub")["demand"].sum().rename("outbound_demand")
    inbound = demand.groupby("destination_hub")["demand"].sum().rename("inbound_demand")

    ranked = hubs[["hub_id", "capacity_parcels"]].copy()
    ranked = ranked.join(outbound, on="hub_id").join(inbound, on="hub_id").fillna(0)
    ranked["throughput_exposure"] = ranked["outbound_demand"] + ranked["inbound_demand"]
    ranked["capacity_pressure"] = (
        ranked["throughput_exposure"] / ranked["capacity_parcels"].clip(lower=1)
    )

    for col in ("throughput_exposure", "capacity_pressure"):
        lo, hi = ranked[col].min(), ranked[col].max()
        ranked[f"{col}_score"] = (
            (ranked[col] - lo) / (hi - lo) if hi > lo else 0.0
        )

    ranked["criticality_score"] = (
        0.5 * ranked["throughput_exposure_score"]
        + 0.5 * ranked["capacity_pressure_score"]
    )
    return ranked.sort_values("criticality_score", ascending=False).head(top_n).reset_index(drop=True)


def build_targeted_interventions(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    config: TargetedInterventionConfig | None = None,
) -> list[Intervention]:
    config = config or TargetedInterventionConfig()
    ranked = rank_hubs(demand, hubs, config.top_hubs)
    candidates: list[Intervention] = []

    for row in ranked.itertuples(index=False):
        hub = int(row.hub_id)
        for uplift in config.capacity_steps:
            pct = int(round(uplift * 100))
            candidates.append(
                Intervention(
                    intervention_id=f"hub_{hub}_capacity_plus_{pct}pct",
                    intervention_type="targeted_hub_capacity",
                    variable_cost=config.hub_capacity_unit_cost * uplift,
                    capacity_uplift=uplift,
                    target_hub_id=hub,
                    description=f"Increase hub {hub} capacity by {pct}%.",
                )
            )
        candidates.append(
            Intervention(
                intervention_id=f"hub_{hub}_backup_capacity",
                intervention_type="backup_hub_capacity",
                fixed_cost=config.backup_fixed_cost,
                capacity_uplift=config.backup_capacity,
                target_hub_id=hub,
                description=f"Add backup capacity equivalent to {config.backup_capacity:.0%} at hub {hub}.",
            )
        )
    return candidates


def evaluate_targeted_interventions(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    fleet: pd.DataFrame,
    config: TargetedInterventionConfig | None = None,
    n_simulations: int = 500,
    seed: int = 42,
    service_target: float = 0.95,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = config or TargetedInterventionConfig()
    candidates = build_targeted_interventions(demand, hubs, config)
    results = evaluate_interventions(
        demand=demand,
        hubs=hubs,
        cost_matrix=cost_matrix,
        fleet=fleet,
        interventions=candidates,
        config=InterventionConfig(
            n_simulations=n_simulations,
            seed=seed,
            service_target=service_target,
        ),
    )
    return rank_hubs(demand, hubs, config.top_hubs), pareto_frontier(results)
