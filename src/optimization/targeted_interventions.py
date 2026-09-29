"""Targeted resilience intervention optimization.

Generates interventions from observed network exposure rather than a fixed
network-wide catalog. Candidate locations are selected from demand, capacity
and route criticality; intervention effects remain explicit assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .interventions import Intervention, evaluate_interventions, pareto_frontier


@dataclass(frozen=True)
class TargetedInterventionConfig:
    top_hubs: int = 5
    top_routes: int = 10
    capacity_steps: tuple[float, ...] = (0.10, 0.20, 0.30)
    fleet_steps: tuple[float, ...] = (0.10, 0.20)
    backup_hub_capacity: float = 0.25
    reserve_fleet_steps: tuple[float, ...] = (0.10, 0.20)
    hub_capacity_unit_cost: float = 8.0
    fleet_unit_cost: float = 18.0
    reserve_fixed_cost: float = 30.0
    backup_hub_fixed_cost: float = 60.0


def rank_hubs(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    top_n: int = 5,
) -> pd.DataFrame:
    """Rank hubs by combined demand exposure and capacity pressure."""

    d = demand.copy()
    out = d.groupby("origin_hub", as_index=False)["demand"].sum()
    inn = d.groupby("destination_hub", as_index=False)["demand"].sum()
    out = out.rename(columns={"origin_hub": "hub_id", "demand": "outbound_demand"})
    inn = inn.rename(columns={"destination_hub": "hub_id", "demand": "inbound_demand"})

    ranked = hubs[["hub_id", "capacity_parcels_per_day"]].merge(
        out, on="hub_id", how="left"
    ).merge(inn, on="hub_id", how="left").fillna(0)

    ranked["throughput_exposure"] = (
        ranked["outbound_demand"] + ranked["inbound_demand"]
    )
    ranked["capacity_pressure"] = (
        ranked["throughput_exposure"]
        / ranked["capacity_parcels_per_day"].clip(lower=1)
    )

    # Equal-weight normalized exposure and pressure avoids making units
    # incomparable while retaining a transparent ranking.
    for col in ["throughput_exposure", "capacity_pressure"]:
        lo, hi = ranked[col].min(), ranked[col].max()
        ranked[f"{col}_score"] = (
            (ranked[col] - lo) / (hi - lo) if hi > lo else 0.0
        )

    ranked["criticality_score"] = (
        0.5 * ranked["throughput_exposure_score"]
        + 0.5 * ranked["capacity_pressure_score"]
    )
    return ranked.sort_values("criticality_score", ascending=False).head(top_n)


def rank_routes(
    demand: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """Rank observed routes by demand exposure and route cost."""

    r = demand.groupby(
        ["origin_hub", "destination_hub"], as_index=False
    )["demand"].sum().rename(columns={"demand": "route_demand"})

    c = cost_matrix[
        ["origin_hub", "destination_hub", "distance_km", "unit_cost"]
    ].drop_duplicates(["origin_hub", "destination_hub"])

    ranked = r.merge(c, on=["origin_hub", "destination_hub"], how="left")
    ranked["route_cost_exposure"] = (
        ranked["route_demand"] * ranked["unit_cost"].fillna(0)
    )

    for col in ["route_demand", "route_cost_exposure"]:
        lo, hi = ranked[col].min(), ranked[col].max()
        ranked[f"{col}_score"] = (
            (ranked[col] - lo) / (hi - lo) if hi > lo else 0.0
        )

    ranked["criticality_score"] = (
        0.6 * ranked["route_demand_score"]
        + 0.4 * ranked["route_cost_exposure_score"]
    )
    return ranked.sort_values("criticality_score", ascending=False).head(top_n)


def build_targeted_interventions(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    config: TargetedInterventionConfig | None = None,
) -> list[Intervention]:
    """Create targeted candidate interventions from current network exposure."""

    config = config or TargetedInterventionConfig()
    hub_rank = rank_hubs(demand, hubs, config.top_hubs)
    route_rank = rank_routes(demand, cost_matrix, config.top_routes)

    candidates: list[Intervention] = []

    for row in hub_rank.itertuples(index=False):
        hub = int(row.hub_id)
        for uplift in config.capacity_steps:
            pct = int(round(uplift * 100))
            candidates.append(
                Intervention(
                    intervention_id=f"hub_{hub}_capacity_plus_{pct}pct",
                    intervention_type="targeted_hub_capacity",
                    variable_cost=config.hub_capacity_unit_cost * uplift,
                    capacity_uplift=uplift,
                    description=f"Increase capacity at critical hub {hub} by {pct}%.",
                )
            )

        for uplift in config.reserve_fleet_steps:
            pct = int(round(uplift * 100))
            candidates.append(
                Intervention(
                    intervention_id=f"hub_{hub}_reserve_fleet_{pct}pct",
                    intervention_type="targeted_hub_reserve_fleet",
                    fixed_cost=config.reserve_fixed_cost * uplift,
                    reserve_vehicle_multiplier=uplift,
                    description=f"Reserve fleet allocation associated with critical hub {hub}: {pct}%.",
                )
            )

        candidates.append(
            Intervention(
                intervention_id=f"hub_{hub}_backup_capacity",
                intervention_type="backup_hub_capacity",
                fixed_cost=config.backup_hub_fixed_cost,
                capacity_uplift=config.backup_hub_capacity,
                description=f"Backup capacity equivalent to {config.backup_hub_capacity:.0%} at hub {hub}.",
            )
        )

    for row in route_rank.itertuples(index=False):
        o, d = int(row.origin_hub), int(row.destination_hub)
        candidates.append(
            Intervention(
                intervention_id=f"route_{o}_{d}_redundancy",
                intervention_type="route_redundancy",
                fixed_cost=config.backup_hub_fixed_cost * 0.75,
                description=f"Protect critical route {o}->{d} with an alternate path.",
            )
        )

    return candidates


def build_targeted_catalog_report(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    config: TargetedInterventionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[Intervention]]:
    """Return ranked hubs, ranked routes and generated intervention candidates."""
    config = config or TargetedInterventionConfig()
    hubs_ranked = rank_hubs(demand, hubs, config.top_hubs)
    routes_ranked = rank_routes(demand, cost_matrix, config.top_routes)
    candidates = build_targeted_interventions(demand, hubs, cost_matrix, config)
    return hubs_ranked, routes_ranked, candidates


def evaluate_targeted_interventions(
    demand: pd.DataFrame,
    hubs: pd.DataFrame,
    cost_matrix: pd.DataFrame,
    fleet: pd.DataFrame,
    config: TargetedInterventionConfig | None = None,
    n_simulations: int = 500,
    seed: int = 42,
    service_target: float = 0.95,
    horizon_days: int = 1,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate, evaluate and frontier-filter targeted interventions."""

    candidates = build_targeted_interventions(demand, hubs, cost_matrix, config)
    from .interventions import InterventionConfig

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
            horizon_days=horizon_days,
        ),
    )
    results = pareto_frontier(results)

    hub_rank = rank_hubs(
        demand,
        hubs,
        (config or TargetedInterventionConfig()).top_hubs,
    )
    route_rank = rank_routes(
        demand,
        cost_matrix,
        (config or TargetedInterventionConfig()).top_routes,
    )
    return hub_rank, route_rank, results
