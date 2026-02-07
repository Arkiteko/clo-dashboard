"""
Stress Loss / SVar Engine for CLO Warehouse Risk Management.

Implements 5 stress scenarios:
1. Price Shock (Market Risk)
2. Default Stress
3. Spread Widening
4. Downgrade Migration
5. Concentration Blow-up
"""
import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ── Moody's Rating Hierarchy ──────────────────────────────────────────

RATING_ORDER = {
    "Aaa": 1, "Aa1": 2, "Aa2": 3, "Aa3": 4,
    "A1": 5, "A2": 6, "A3": 7,
    "Baa1": 8, "Baa2": 9, "Baa3": 10,
    "Ba1": 11, "Ba2": 12, "Ba3": 13,
    "B1": 14, "B2": 15, "B3": 16,
    "Caa1": 17, "Caa2": 18, "Caa3": 19,
    "Ca": 20, "C": 21,
}

# Reverse lookup: ordinal -> rating string
ORDER_TO_RATING = {v: k for k, v in RATING_ORDER.items()}


def rating_to_tier(rating: str) -> str:
    """Map a Moody's rating string to a broad tier bucket."""
    if not rating or pd.isna(rating):
        return "NR"
    rating = str(rating).strip()
    order = RATING_ORDER.get(rating, None)
    if order is None:
        # Try partial match
        if "Caa" in rating or rating in ("Ca", "C"):
            return "CCC"
        if rating.startswith("B") and not rating.startswith("Ba"):
            return "B"
        if rating.startswith("Ba"):
            return "BB"
        if rating.startswith("Baa") or rating.startswith("A") or rating.startswith("Aa") or rating == "Aaa":
            return "IG"
        return "NR"
    if order <= 10:
        return "IG"
    if order <= 13:
        return "BB"
    if order <= 16:
        return "B"
    if order <= 21:
        return "CCC"
    return "NR"


def downgrade_one_notch(rating: str) -> str:
    """Return the rating one notch below the given rating."""
    order = RATING_ORDER.get(rating, None)
    if order is None or order >= 21:
        return rating  # already at bottom or unknown
    return ORDER_TO_RATING.get(order + 1, rating)


def get_recovery_rate(lien_type: str, stress_cfg) -> float:
    """Return recovery rate based on lien type."""
    if not lien_type or pd.isna(lien_type):
        return stress_cfg.recovery_1l  # default to 1L
    lien = str(lien_type).strip().upper()
    if "1" in lien:
        return stress_cfg.recovery_1l
    if "2" in lien:
        return stress_cfg.recovery_2l
    if "UN" in lien:
        return stress_cfg.recovery_unsecured
    return stress_cfg.recovery_1l


# ── Result Containers ─────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    name: str
    loss_dollars: float = 0.0
    loss_pct: float = 0.0
    detail: str = ""
    asset_level: Optional[pd.DataFrame] = None


@dataclass
class StressResults:
    warehouse_name: str
    total_par: float = 0.0
    base_mv: float = 0.0
    base_oc: float = 0.0
    scenarios: List[ScenarioResult] = field(default_factory=list)
    total_stressed_loss: float = 0.0
    stressed_oc: float = 0.0
    oc_trigger: float = 0.0
    oc_breach: bool = False
    stressed_ccc_pct: float = 0.0
    ccc_breach: bool = False


# ── Scenario 1: Price Shock ───────────────────────────────────────────

def scenario_price_shock(df: pd.DataFrame, stress_cfg) -> ScenarioResult:
    """Apply rating-tiered price haircuts."""
    haircuts = {
        "IG": stress_cfg.price_shock_ig,
        "BB": stress_cfg.price_shock_bb,
        "B": stress_cfg.price_shock_b,
        "CCC": stress_cfg.price_shock_ccc,
        "NR": stress_cfg.price_shock_b,  # treat NR like B
    }

    df_work = df.copy()
    df_work["tier"] = df_work["rating_moodys"].apply(rating_to_tier)
    df_work["haircut"] = df_work["tier"].map(haircuts).fillna(stress_cfg.price_shock_b)
    df_work["base_mv"] = df_work["par_amount"] * df_work["market_price"] / 100
    df_work["stressed_price"] = (df_work["market_price"] - df_work["haircut"]).clip(lower=0)
    df_work["stressed_mv"] = df_work["par_amount"] * df_work["stressed_price"] / 100
    df_work["loss"] = df_work["base_mv"] - df_work["stressed_mv"]

    total_loss = df_work["loss"].sum()
    total_base_mv = df_work["base_mv"].sum()
    loss_pct = total_loss / total_base_mv if total_base_mv > 0 else 0

    worst_tier = df_work.groupby("tier")["loss"].sum().idxmax() if not df_work.empty else "N/A"

    return ScenarioResult(
        name="Price Shock",
        loss_dollars=total_loss,
        loss_pct=loss_pct,
        detail=f"Worst tier: {worst_tier}",
        asset_level=df_work[["asset_id", "issuer_name", "tier", "market_price", "stressed_price", "loss"]].copy()
    )


# ── Scenario 2: Default Stress ────────────────────────────────────────

def scenario_default_stress(df: pd.DataFrame, stress_cfg) -> ScenarioResult:
    """Apply conditional default rates by rating, recovery by lien."""
    cdrs = {
        "IG": stress_cfg.cdr_ig,
        "BB": stress_cfg.cdr_bb,
        "B": stress_cfg.cdr_b,
        "CCC": stress_cfg.cdr_ccc,
        "NR": stress_cfg.cdr_b,
    }

    df_work = df.copy()
    df_work["tier"] = df_work["rating_moodys"].apply(rating_to_tier)
    df_work["cdr"] = df_work["tier"].map(cdrs).fillna(stress_cfg.cdr_b)
    df_work["recovery"] = df_work["lien_type"].apply(lambda x: get_recovery_rate(x, stress_cfg))
    df_work["expected_default_par"] = df_work["par_amount"] * df_work["cdr"]
    df_work["loss"] = df_work["expected_default_par"] * (1 - df_work["recovery"])

    total_loss = df_work["loss"].sum()
    total_par = df_work["par_amount"].sum()
    loss_pct = total_loss / total_par if total_par > 0 else 0
    n_defaulting = (df_work["expected_default_par"] > 0).sum()

    return ScenarioResult(
        name="Default Stress",
        loss_dollars=total_loss,
        loss_pct=loss_pct,
        detail=f"{n_defaulting} assets with default exposure",
        asset_level=df_work[["asset_id", "issuer_name", "tier", "cdr", "recovery", "expected_default_par", "loss"]].copy()
    )


# ── Scenario 3: Spread Widening ───────────────────────────────────────

def scenario_spread_widening(df: pd.DataFrame, stress_cfg) -> ScenarioResult:
    """Spread shock with duration-based MV impact."""
    spread_shocks = {
        "IG": stress_cfg.spread_shock_ig,
        "BB": stress_cfg.spread_shock_bb,
        "B": stress_cfg.spread_shock_b,
        "CCC": stress_cfg.spread_shock_ccc,
        "NR": stress_cfg.spread_shock_b,
    }

    df_work = df.copy()
    df_work["tier"] = df_work["rating_moodys"].apply(rating_to_tier)
    df_work["spread_shock_bps"] = df_work["tier"].map(spread_shocks).fillna(stress_cfg.spread_shock_b)

    # Estimate duration from years to maturity (simplified: duration ~ WAL * 0.9 for floating rate loans)
    today = pd.to_datetime(datetime.now())
    if "maturity_date" in df_work.columns:
        df_work["years_to_mat"] = (pd.to_datetime(df_work["maturity_date"]) - today).dt.days / 365.0
        df_work["years_to_mat"] = df_work["years_to_mat"].clip(lower=0)
    else:
        df_work["years_to_mat"] = 3.0  # fallback

    df_work["est_duration"] = df_work["years_to_mat"] * 0.9

    # MV impact = par * (price/100) * duration * spread_shock_bps / 10000
    df_work["base_mv"] = df_work["par_amount"] * df_work["market_price"] / 100
    df_work["loss"] = df_work["base_mv"] * df_work["est_duration"] * df_work["spread_shock_bps"] / 10000

    total_loss = df_work["loss"].sum()
    total_base_mv = df_work["base_mv"].sum()
    loss_pct = total_loss / total_base_mv if total_base_mv > 0 else 0

    avg_shock = df_work["spread_shock_bps"].mean()

    return ScenarioResult(
        name="Spread Widening",
        loss_dollars=total_loss,
        loss_pct=loss_pct,
        detail=f"Avg shock: +{avg_shock:.0f}bps",
        asset_level=df_work[["asset_id", "issuer_name", "tier", "spread_shock_bps", "est_duration", "loss"]].copy()
    )


# ── Scenario 4: Downgrade Migration ───────────────────────────────────

def scenario_downgrade_migration(df: pd.DataFrame, stress_cfg) -> ScenarioResult:
    """Simulate migration of X% of each tier one notch down."""
    migration_rate = stress_cfg.migration_rate
    haircuts = {
        "IG": stress_cfg.price_shock_ig,
        "BB": stress_cfg.price_shock_bb,
        "B": stress_cfg.price_shock_b,
        "CCC": stress_cfg.price_shock_ccc,
        "NR": stress_cfg.price_shock_b,
    }

    df_work = df.copy()
    df_work["tier"] = df_work["rating_moodys"].apply(rating_to_tier)
    df_work["original_tier"] = df_work["tier"]

    # Randomly select migration_rate fraction of assets for downgrade
    # Deterministic: take the top X% by par within each tier
    migrated_indices = []
    for tier, g in df_work.groupby("tier"):
        n_migrate = max(1, int(len(g) * migration_rate))
        top_by_par = g.nlargest(n_migrate, "par_amount").index
        migrated_indices.extend(top_by_par.tolist())

    df_work["migrated"] = False
    df_work.loc[migrated_indices, "migrated"] = True

    # Apply downgrade to migrated assets
    df_work["stressed_rating"] = df_work["rating_moodys"]
    df_work.loc[df_work["migrated"], "stressed_rating"] = df_work.loc[df_work["migrated"], "rating_moodys"].apply(downgrade_one_notch)
    df_work["stressed_tier"] = df_work["stressed_rating"].apply(rating_to_tier)

    # Price impact: migrated assets get the haircut of their NEW tier minus their OLD tier
    df_work["old_haircut"] = df_work["original_tier"].map(haircuts).fillna(0)
    df_work["new_haircut"] = df_work["stressed_tier"].map(haircuts).fillna(0)
    df_work["incremental_haircut"] = 0.0
    df_work.loc[df_work["migrated"], "incremental_haircut"] = (
        df_work.loc[df_work["migrated"], "new_haircut"] - df_work.loc[df_work["migrated"], "old_haircut"]
    ).clip(lower=0)

    df_work["base_mv"] = df_work["par_amount"] * df_work["market_price"] / 100
    df_work["loss"] = df_work["par_amount"] * df_work["incremental_haircut"] / 100

    total_loss = df_work["loss"].sum()
    total_par = df_work["par_amount"].sum()
    loss_pct = total_loss / total_par if total_par > 0 else 0

    # Compute stressed CCC %
    ccc_par_stressed = df_work[df_work["stressed_tier"] == "CCC"]["par_amount"].sum()
    new_ccc_pct = ccc_par_stressed / total_par if total_par > 0 else 0

    return ScenarioResult(
        name="Downgrade Migration",
        loss_dollars=total_loss,
        loss_pct=loss_pct,
        detail=f"Stressed CCC: {new_ccc_pct:.1%}",
        asset_level=df_work[["asset_id", "issuer_name", "original_tier", "stressed_tier", "migrated", "loss"]].copy()
    )


# ── Scenario 5: Concentration Blow-up ─────────────────────────────────

def scenario_concentration(df: pd.DataFrame, stress_cfg) -> ScenarioResult:
    """Default the top N obligors by par exposure."""
    top_n = stress_cfg.concentration_top_n

    df_work = df.copy()

    # Find top N obligors by total par
    obligor_par = df_work.groupby("issuer_name")["par_amount"].sum().nlargest(top_n)
    top_obligors = set(obligor_par.index.tolist())

    df_work["is_top_n"] = df_work["issuer_name"].isin(top_obligors)
    df_work["recovery"] = df_work["lien_type"].apply(lambda x: get_recovery_rate(x, stress_cfg))

    df_work["loss"] = 0.0
    mask = df_work["is_top_n"]
    df_work.loc[mask, "loss"] = df_work.loc[mask, "par_amount"] * (1 - df_work.loc[mask, "recovery"])

    total_loss = df_work["loss"].sum()
    total_par = df_work["par_amount"].sum()
    loss_pct = total_loss / total_par if total_par > 0 else 0

    obligor_names = ", ".join(list(top_obligors)[:3])

    return ScenarioResult(
        name="Concentration",
        loss_dollars=total_loss,
        loss_pct=loss_pct,
        detail=f"Top {top_n}: {obligor_names}",
        asset_level=df_work[df_work["is_top_n"]][["asset_id", "issuer_name", "par_amount", "recovery", "loss"]].copy()
    )


# ── Aggregation ───────────────────────────────────────────────────────

def run_all_scenarios(
    df: pd.DataFrame,
    warehouse_config,
    stress_cfg,
    debt_outstanding: float = 0.0,
    cash_balance: float = 0.0,
) -> StressResults:
    """
    Run all 5 stress scenarios and compute aggregate stressed metrics.

    Args:
        df: DataFrame of assets for a single warehouse (latest snapshot)
        warehouse_config: WarehouseConfig instance
        stress_cfg: StressConfig instance
        debt_outstanding: Current debt drawn (if 0, estimated from par * price * advance_rate)
        cash_balance: Current cash
    """
    total_par = df["par_amount"].sum()
    base_mv = (df["par_amount"] * df["market_price"] / 100).sum() if "market_price" in df.columns else total_par

    # Estimate debt if not provided
    if debt_outstanding <= 0:
        w_price = (df["par_amount"] * df["market_price"]).sum() / total_par if total_par > 0 else 100
        debt_outstanding = total_par * (w_price / 100) * warehouse_config.advance_rate

    base_oc = (total_par + cash_balance) / debt_outstanding if debt_outstanding > 0 else 0

    # Run each scenario
    s1 = scenario_price_shock(df, stress_cfg)
    s2 = scenario_default_stress(df, stress_cfg)
    s3 = scenario_spread_widening(df, stress_cfg)
    s4 = scenario_downgrade_migration(df, stress_cfg)
    s5 = scenario_concentration(df, stress_cfg)

    scenarios = [s1, s2, s3, s4, s5]

    # Aggregate: sum the worst-case across price shock + default + spread
    # (concentration and migration are tail scenarios, not additive)
    # Use max of (price_shock, spread) + default as combined market+credit loss
    market_loss = max(s1.loss_dollars, s3.loss_dollars)
    credit_loss = s2.loss_dollars
    total_stressed_loss = market_loss + credit_loss

    # Stressed OC
    stressed_par = total_par - total_stressed_loss
    stressed_oc = (stressed_par + cash_balance) / debt_outstanding if debt_outstanding > 0 else 0

    # Stressed CCC % (from migration scenario)
    # Parse from s4 detail
    stressed_ccc_pct = 0.0
    if s4.asset_level is not None and "stressed_tier" in s4.asset_level.columns:
        ccc_par = df.copy()
        ccc_par["tier"] = ccc_par["rating_moodys"].apply(rating_to_tier)
        # Merge migration results
        if not s4.asset_level.empty:
            migrated = s4.asset_level[["asset_id", "stressed_tier"]].drop_duplicates("asset_id")
            ccc_par = ccc_par.merge(migrated, on="asset_id", how="left")
            ccc_par["final_tier"] = ccc_par["stressed_tier"].fillna(ccc_par["tier"])
        else:
            ccc_par["final_tier"] = ccc_par["tier"]
        stressed_ccc_par = ccc_par[ccc_par["final_tier"] == "CCC"]["par_amount"].sum()
        stressed_ccc_pct = stressed_ccc_par / total_par if total_par > 0 else 0

    return StressResults(
        warehouse_name="",
        total_par=total_par,
        base_mv=base_mv,
        base_oc=base_oc,
        scenarios=scenarios,
        total_stressed_loss=total_stressed_loss,
        stressed_oc=stressed_oc,
        oc_trigger=warehouse_config.oc_trigger_pct,
        oc_breach=stressed_oc < warehouse_config.oc_trigger_pct,
        stressed_ccc_pct=stressed_ccc_pct,
        ccc_breach=stressed_ccc_pct > 0.075,
    )
