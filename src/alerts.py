"""
Alert engine for CLO Dashboard.

Evaluates portfolio state against configurable thresholds and returns
a list of Alert objects sorted by severity.
"""
import hashlib
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from src.models import Alert, AlertSeverity, AlertConfig
from src.config import WarehouseConfig
from src.risk_analytics import (
    compute_warf, compute_diversity_score, compute_single_name_concentration,
    compute_lien_breakdown, compute_hhi,
)
from src.stress import rating_to_tier


# ── Alert Rule Helpers ────────────────────────────────────────────────

def _alert_id(warehouse: str, rule_id: str) -> str:
    """Generate a deterministic alert ID."""
    return hashlib.md5(f"{warehouse}:{rule_id}".encode()).hexdigest()[:12]


def _is_enabled(rule_id: str, alert_config: AlertConfig) -> bool:
    return rule_id not in alert_config.disabled_rules


# ── Individual Alert Rules ────────────────────────────────────────────

def _check_oc_breach(
    df: pd.DataFrame, warehouse: str, config: WarehouseConfig,
    debt_outstanding: Optional[float] = None, cash_balance: float = 0.0,
) -> List[Alert]:
    """Check OC ratio breach and proximity."""
    alerts = []
    ac = config.alert_config
    funded = df["par_amount"].sum()
    if funded <= 0:
        return alerts

    if debt_outstanding is None:
        if "market_price" in df.columns:
            w_price = (df["par_amount"] * df["market_price"]).sum() / funded
            debt_outstanding = funded * (w_price / 100) * config.advance_rate
        else:
            return alerts

    if debt_outstanding <= 0:
        return alerts

    oc_ratio = (funded + cash_balance) / debt_outstanding
    trigger = config.oc_trigger_pct

    if _is_enabled("oc_breach", ac) and oc_ratio < trigger:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "oc_breach"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Compliance", title="OC Ratio Breach",
            detail=f"OC ratio {oc_ratio:.2%} is below trigger {trigger:.0%}",
            metric_name="oc_ratio", current_value=oc_ratio, threshold_value=trigger,
        ))
    elif _is_enabled("oc_proximity", ac) and oc_ratio < trigger * (1 + ac.proximity_margin):
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "oc_proximity"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Threshold Proximity", title="OC Ratio Near Trigger",
            detail=f"OC ratio {oc_ratio:.2%} is within {ac.proximity_margin:.0%} of trigger {trigger:.0%}",
            metric_name="oc_ratio", current_value=oc_ratio, threshold_value=trigger,
        ))
    return alerts


def _check_ccc(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check CCC % breach and proximity."""
    alerts = []
    ac = config.alert_config
    funded = df["par_amount"].sum()
    if funded <= 0 or "rating_moodys" not in df.columns:
        return alerts

    ccc_par = df[df["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
    ccc_pct = ccc_par / funded
    limit = config.max_ccc_pct

    if _is_enabled("ccc_breach", ac) and ccc_pct > limit:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "ccc_breach"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Compliance", title="CCC Bucket Breach",
            detail=f"CCC exposure {ccc_pct:.1%} exceeds limit {limit:.1%}",
            metric_name="ccc_pct", current_value=ccc_pct, threshold_value=limit,
        ))
    elif _is_enabled("ccc_proximity", ac) and ccc_pct > limit * (1 - ac.proximity_margin):
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "ccc_proximity"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Threshold Proximity", title="CCC % Near Limit",
            detail=f"CCC exposure {ccc_pct:.1%} approaching limit {limit:.1%}",
            metric_name="ccc_pct", current_value=ccc_pct, threshold_value=limit,
        ))
    return alerts


def _check_industry_concentration(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check industry concentration breach and proximity."""
    alerts = []
    ac = config.alert_config
    funded = df["par_amount"].sum()
    if funded <= 0 or "industry_gics" not in df.columns:
        return alerts

    ind_exp = df.groupby("industry_gics")["par_amount"].sum()
    limit = config.concentration_limit_industry

    for industry, par in ind_exp.items():
        pct = par / funded
        if _is_enabled("industry_breach", ac) and pct > limit:
            alerts.append(Alert(
                alert_id=_alert_id(warehouse, f"industry_breach_{industry}"),
                warehouse=warehouse, severity=AlertSeverity.CRITICAL,
                category="Concentration", title=f"Industry Limit Breach: {industry}",
                detail=f"{industry} at {pct:.1%} exceeds limit {limit:.0%}",
                metric_name="industry_concentration", current_value=pct, threshold_value=limit,
            ))
        elif _is_enabled("industry_proximity", ac) and pct > limit * (1 - ac.proximity_margin):
            alerts.append(Alert(
                alert_id=_alert_id(warehouse, f"industry_prox_{industry}"),
                warehouse=warehouse, severity=AlertSeverity.WARNING,
                category="Threshold Proximity", title=f"Industry Near Limit: {industry}",
                detail=f"{industry} at {pct:.1%} approaching limit {limit:.0%}",
                metric_name="industry_concentration", current_value=pct, threshold_value=limit,
            ))
    return alerts


def _check_single_name(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check single-name concentration."""
    alerts = []
    ac = config.alert_config
    sn = compute_single_name_concentration(df)
    limit = config.max_single_name_pct
    pct = sn["max_single_issuer_pct"]
    name = sn["max_single_issuer_name"]

    if _is_enabled("single_name_breach", ac) and pct > limit:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "single_name_breach"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Concentration", title=f"Single-Name Breach: {name}",
            detail=f"{name} at {pct:.1%} exceeds limit {limit:.1%}",
            metric_name="single_name_pct", current_value=pct, threshold_value=limit,
        ))
    elif _is_enabled("single_name_proximity", ac) and pct > limit * (1 - ac.proximity_margin):
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "single_name_proximity"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Threshold Proximity", title=f"Single-Name Near Limit: {name}",
            detail=f"{name} at {pct:.1%} approaching limit {limit:.1%}",
            metric_name="single_name_pct", current_value=pct, threshold_value=limit,
        ))
    return alerts


def _check_lien_sublimits(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check second lien and unsecured sublimits."""
    alerts = []
    ac = config.alert_config
    lien = compute_lien_breakdown(df)

    if _is_enabled("second_lien_breach", ac) and lien["2L_pct"] > config.max_second_lien_pct:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "second_lien_breach"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Compliance", title="Second Lien Sublimit Breach",
            detail=f"2L exposure {lien['2L_pct']:.1%} exceeds limit {config.max_second_lien_pct:.0%}",
            metric_name="second_lien_pct", current_value=lien["2L_pct"],
            threshold_value=config.max_second_lien_pct,
        ))

    if _is_enabled("unsecured_breach", ac) and lien["unsecured_pct"] > config.max_unsecured_pct:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "unsecured_breach"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Compliance", title="Unsecured Sublimit Breach",
            detail=f"Unsecured exposure {lien['unsecured_pct']:.1%} exceeds limit {config.max_unsecured_pct:.0%}",
            metric_name="unsecured_pct", current_value=lien["unsecured_pct"],
            threshold_value=config.max_unsecured_pct,
        ))
    return alerts


def _check_data_freshness(
    df: pd.DataFrame, warehouse: str, config: WarehouseConfig,
) -> List[Alert]:
    """Check data staleness."""
    alerts = []
    ac = config.alert_config
    if "data_date" not in df.columns or df.empty:
        return alerts

    latest = pd.to_datetime(df["data_date"]).max()
    days_old = (pd.to_datetime(datetime.now()) - latest).days

    if _is_enabled("data_stale", ac) and days_old >= ac.stale_critical_days:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "data_stale_critical"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Data Quality", title="Data Critically Stale",
            detail=f"Last tape is {days_old} days old (limit: {ac.stale_critical_days}d)",
            metric_name="data_freshness_days", current_value=float(days_old),
            threshold_value=float(ac.stale_critical_days),
        ))
    elif _is_enabled("data_stale", ac) and days_old >= ac.stale_warning_days:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "data_stale_warning"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Data Quality", title="Data Getting Stale",
            detail=f"Last tape is {days_old} days old (warning: {ac.stale_warning_days}d)",
            metric_name="data_freshness_days", current_value=float(days_old),
            threshold_value=float(ac.stale_warning_days),
        ))
    return alerts


def _check_warf(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check WARF thresholds."""
    alerts = []
    ac = config.alert_config
    warf = compute_warf(df)

    if _is_enabled("warf_high", ac) and warf >= ac.warf_critical:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "warf_critical"),
            warehouse=warehouse, severity=AlertSeverity.CRITICAL,
            category="Risk", title="WARF Critical",
            detail=f"WARF {warf:.0f} exceeds critical threshold {ac.warf_critical:.0f}",
            metric_name="warf", current_value=warf, threshold_value=ac.warf_critical,
        ))
    elif _is_enabled("warf_high", ac) and warf >= ac.warf_warning:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "warf_warning"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Risk", title="WARF Elevated",
            detail=f"WARF {warf:.0f} exceeds warning threshold {ac.warf_warning:.0f}",
            metric_name="warf", current_value=warf, threshold_value=ac.warf_warning,
        ))
    return alerts


def _check_diversity(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check diversity score threshold."""
    alerts = []
    ac = config.alert_config
    score = compute_diversity_score(df)

    if _is_enabled("diversity_low", ac) and score < ac.diversity_warning and score > 0:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "diversity_low"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Risk", title="Low Diversity Score",
            detail=f"Diversity score {score:.1f} below threshold {ac.diversity_warning:.0f}",
            metric_name="diversity_score", current_value=score,
            threshold_value=ac.diversity_warning,
        ))
    return alerts


def _check_defaulted_assets(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check for defaulted assets."""
    alerts = []
    ac = config.alert_config
    if "is_defaulted" not in df.columns:
        return alerts

    defaulted = df[df["is_defaulted"] == True]
    if _is_enabled("defaulted_assets", ac) and len(defaulted) > 0:
        total_par = defaulted["par_amount"].sum()
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "defaulted_assets"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Risk", title=f"{len(defaulted)} Defaulted Asset(s)",
            detail=f"{len(defaulted)} assets in default totaling ${total_par/1e6:,.1f}M par",
            metric_name="defaulted_count", current_value=float(len(defaulted)),
            threshold_value=0.0,
        ))
    return alerts


def _check_price_outliers(df: pd.DataFrame, warehouse: str, config: WarehouseConfig) -> List[Alert]:
    """Check for price outliers."""
    alerts = []
    ac = config.alert_config
    if "market_price" not in df.columns:
        return alerts

    distressed = df[df["market_price"] < 70]
    if _is_enabled("price_outlier", ac) and len(distressed) > 0:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "price_outlier"),
            warehouse=warehouse, severity=AlertSeverity.INFO,
            category="Data Quality", title=f"{len(distressed)} Distressed Price Asset(s)",
            detail=f"{len(distressed)} assets priced below 70 (potential distress/data issue)",
            metric_name="price_outlier_count", current_value=float(len(distressed)),
            threshold_value=70.0,
        ))
    return alerts


def _check_utilization(
    df: pd.DataFrame, warehouse: str, config: WarehouseConfig,
    debt_outstanding: Optional[float] = None,
) -> List[Alert]:
    """Check facility utilization."""
    alerts = []
    ac = config.alert_config
    funded = df["par_amount"].sum()

    if debt_outstanding is None:
        if "market_price" in df.columns and funded > 0:
            w_price = (df["par_amount"] * df["market_price"]).sum() / funded
            debt_outstanding = funded * (w_price / 100) * config.advance_rate
        else:
            return alerts

    if config.max_facility_amount <= 0:
        return alerts

    utilization = debt_outstanding / config.max_facility_amount
    if _is_enabled("facility_utilization_high", ac) and utilization > ac.utilization_warning:
        alerts.append(Alert(
            alert_id=_alert_id(warehouse, "utilization_high"),
            warehouse=warehouse, severity=AlertSeverity.WARNING,
            category="Compliance", title="High Facility Utilization",
            detail=f"Utilization {utilization:.1%} exceeds warning {ac.utilization_warning:.0%}",
            metric_name="facility_utilization", current_value=utilization,
            threshold_value=ac.utilization_warning,
        ))
    return alerts


# ── Main Alert Evaluation ─────────────────────────────────────────────

def evaluate_all_alerts(
    df: pd.DataFrame,
    warehouse_name: str,
    config: WarehouseConfig,
    debt_outstanding: Optional[float] = None,
    cash_balance: float = 0.0,
) -> List[Alert]:
    """Run all alert rules against a warehouse's current data.

    Returns list of Alert objects sorted by severity (CRITICAL first).
    """
    alerts: List[Alert] = []

    alerts.extend(_check_oc_breach(df, warehouse_name, config, debt_outstanding, cash_balance))
    alerts.extend(_check_ccc(df, warehouse_name, config))
    alerts.extend(_check_industry_concentration(df, warehouse_name, config))
    alerts.extend(_check_single_name(df, warehouse_name, config))
    alerts.extend(_check_lien_sublimits(df, warehouse_name, config))
    alerts.extend(_check_data_freshness(df, warehouse_name, config))
    alerts.extend(_check_warf(df, warehouse_name, config))
    alerts.extend(_check_diversity(df, warehouse_name, config))
    alerts.extend(_check_defaulted_assets(df, warehouse_name, config))
    alerts.extend(_check_price_outliers(df, warehouse_name, config))
    alerts.extend(_check_utilization(df, warehouse_name, config, debt_outstanding))

    # Sort: CRITICAL first, then WARNING, then INFO
    severity_order = {AlertSeverity.CRITICAL: 0, AlertSeverity.WARNING: 1, AlertSeverity.INFO: 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
    return alerts


def evaluate_global_alerts(
    df_all_latest: pd.DataFrame,
    configs: Dict[str, WarehouseConfig],
) -> List[Alert]:
    """Run alerts across all warehouses and return aggregated list."""
    all_alerts: List[Alert] = []
    for wh_name, group in df_all_latest.groupby("warehouse_source"):
        config = configs.get(wh_name, WarehouseConfig())
        all_alerts.extend(evaluate_all_alerts(group, wh_name, config))
    severity_order = {AlertSeverity.CRITICAL: 0, AlertSeverity.WARNING: 1, AlertSeverity.INFO: 2}
    all_alerts.sort(key=lambda a: severity_order.get(a.severity, 3))
    return all_alerts


# ── Watchlist Builder ─────────────────────────────────────────────────

def build_watchlist(
    df: pd.DataFrame,
    warehouse_name: str,
    config: WarehouseConfig,
) -> pd.DataFrame:
    """Identify assets that should be on the watchlist.

    Criteria:
    - is_defaulted == True
    - Rating is Caa1 or worse
    - Price < 80 (distressed)
    - Rating downgraded from original
    - Single-name concentration > 1.5% of portfolio
    """
    if df.empty:
        return pd.DataFrame()

    total_par = df["par_amount"].sum()
    if total_par <= 0:
        return pd.DataFrame()

    rows = []
    for _, asset in df.iterrows():
        reasons = []
        severity = "INFO"

        # Defaulted
        if asset.get("is_defaulted") == True:
            reasons.append("Defaulted")
            severity = "CRITICAL"

        # CCC-rated
        if pd.notna(asset.get("rating_moodys")):
            tier = rating_to_tier(str(asset["rating_moodys"]))
            if tier == "CCC":
                reasons.append(f"CCC-rated ({asset['rating_moodys']})")
                if severity != "CRITICAL":
                    severity = "WARNING"

        # Distressed price
        if pd.notna(asset.get("market_price")) and asset["market_price"] < 80:
            reasons.append(f"Distressed price ({asset['market_price']:.1f})")
            if severity != "CRITICAL":
                severity = "WARNING"

        # Rating migration
        if (pd.notna(asset.get("original_rating_moodys")) and
                pd.notna(asset.get("rating_moodys")) and
                str(asset["original_rating_moodys"]) != str(asset["rating_moodys"])):
            from src.stress import RATING_ORDER
            orig_order = RATING_ORDER.get(str(asset["original_rating_moodys"]), 99)
            curr_order = RATING_ORDER.get(str(asset["rating_moodys"]), 99)
            if curr_order > orig_order:
                reasons.append(f"Downgraded ({asset['original_rating_moodys']} -> {asset['rating_moodys']})")
                if severity == "INFO":
                    severity = "WARNING"

        # Concentrated single name
        if "issuer_name" in df.columns and pd.notna(asset.get("issuer_name")):
            issuer_par = df[df["issuer_name"] == asset["issuer_name"]]["par_amount"].sum()
            issuer_pct = issuer_par / total_par
            if issuer_pct > 0.015:
                reasons.append(f"Concentrated ({issuer_pct:.1%} of portfolio)")

        if reasons:
            rows.append({
                "Warehouse": warehouse_name,
                "Asset ID": asset.get("asset_id", ""),
                "Issuer": asset.get("issuer_name", ""),
                "Par ($M)": round(asset.get("par_amount", 0) / 1e6, 2),
                "Price": round(asset.get("market_price", 0), 2) if pd.notna(asset.get("market_price")) else None,
                "Rating": asset.get("rating_moodys", ""),
                "Flags": " | ".join(reasons),
                "Severity": severity,
            })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    sev_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    result["_sev_sort"] = result["Severity"].map(sev_order)
    result = result.sort_values(["_sev_sort", "Par ($M)"], ascending=[True, False]).drop(columns=["_sev_sort"])
    return result.reset_index(drop=True)
