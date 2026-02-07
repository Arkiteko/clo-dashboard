"""
Risk analytics calculations for CLO Dashboard.

Provides portfolio-level metrics: WARF, Diversity Score, HHI,
Duration/DV01, single-name concentration, lien sublimits, coupon analytics.
"""
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from src.stress import RATING_ORDER, rating_to_tier


# ── Moody's Rating Factors ────────────────────────────────────────────

MOODY_RATING_FACTORS: Dict[str, int] = {
    "Aaa": 1, "Aa1": 10, "Aa2": 20, "Aa3": 40,
    "A1": 70, "A2": 120, "A3": 180,
    "Baa1": 260, "Baa2": 360, "Baa3": 610,
    "Ba1": 940, "Ba2": 1350, "Ba3": 1766,
    "B1": 2220, "B2": 2720, "B3": 3490,
    "Caa1": 4770, "Caa2": 6500, "Caa3": 8070,
    "Ca": 10000, "C": 10000,
}

# Moody's diversity table: maps (N issuers in industry) -> diversity units
# Simplified lookup (Moody's actual table varies by par concentration)
_DIVERSITY_TABLE = {
    1: 1.0, 2: 1.5, 3: 2.0, 4: 2.33, 5: 2.67,
    6: 3.0, 7: 3.25, 8: 3.5, 9: 3.75, 10: 4.0,
}

# S&P to Moody's rating equivalence
SP_TO_MOODYS = {
    "AAA": "Aaa", "AA+": "Aa1", "AA": "Aa2", "AA-": "Aa3",
    "A+": "A1", "A": "A2", "A-": "A3",
    "BBB+": "Baa1", "BBB": "Baa2", "BBB-": "Baa3",
    "BB+": "Ba1", "BB": "Ba2", "BB-": "Ba3",
    "B+": "B1", "B": "B2", "B-": "B3",
    "CCC+": "Caa1", "CCC": "Caa2", "CCC-": "Caa3",
    "CC": "Ca", "C": "C", "D": "C",
}


# ── WARF ──────────────────────────────────────────────────────────────

def compute_warf(
    df: pd.DataFrame,
    rating_col: str = "rating_moodys",
    weight_col: str = "par_amount",
) -> float:
    """Compute Weighted Average Rating Factor.

    WARF = sum(par_i * RF_i) / sum(par_i)
    Typical CLO range: 2200-3200.
    """
    if df.empty or weight_col not in df.columns or rating_col not in df.columns:
        return 0.0
    total_par = df[weight_col].sum()
    if total_par <= 0:
        return 0.0
    weighted_sum = 0.0
    for _, row in df.iterrows():
        rating = str(row[rating_col]).strip() if pd.notna(row[rating_col]) else ""
        factor = MOODY_RATING_FACTORS.get(rating, 3490)  # Default to B3 for NR
        weighted_sum += row[weight_col] * factor
    return weighted_sum / total_par


# ── Diversity Score ───────────────────────────────────────────────────

def compute_diversity_score(
    df: pd.DataFrame,
    industry_col: str = "industry_gics",
    issuer_col: str = "issuer_name",
    weight_col: str = "par_amount",
) -> float:
    """Compute simplified Moody's-style Diversity Score.

    For each industry group, count unique issuers and map to
    diversity units via the Moody's lookup table.
    Total score = sum of diversity units across all industries.
    Typical CLO target: 40-80.
    """
    if df.empty or industry_col not in df.columns or issuer_col not in df.columns:
        return 0.0

    total_score = 0.0
    for industry, group in df.groupby(industry_col):
        n_issuers = group[issuer_col].nunique()
        if n_issuers <= 0:
            continue
        if n_issuers <= 10:
            units = _DIVERSITY_TABLE.get(n_issuers, 4.0)
        else:
            # For >10 issuers: diminishing returns, approximate
            units = 4.0 + (n_issuers - 10) * 0.2
        total_score += units

    return round(total_score, 1)


# ── Portfolio Duration & DV01 ─────────────────────────────────────────

def compute_portfolio_duration(
    df: pd.DataFrame,
    as_of_date: Optional[datetime] = None,
    weight_col: str = "par_amount",
) -> Dict[str, float]:
    """Compute portfolio-level duration and DV01.

    For floating-rate loans: Modified Duration ~ WAL * 0.9 (reset risk only).
    DV01 = Market Value * Modified Duration * 0.0001

    Returns dict with weighted_avg_duration, portfolio_dv01, dv01_per_million.
    """
    if as_of_date is None:
        as_of_date = datetime.now()
    as_of = pd.to_datetime(as_of_date)

    result = {"weighted_avg_duration": 0.0, "portfolio_dv01": 0.0, "dv01_per_million": 0.0}
    if df.empty or "maturity_date" not in df.columns or "market_price" not in df.columns:
        return result

    total_par = df[weight_col].sum()
    if total_par <= 0:
        return result

    df_calc = df.copy()
    df_calc["years_to_mat"] = (pd.to_datetime(df_calc["maturity_date"]) - as_of).dt.days / 365.0
    df_calc["years_to_mat"] = df_calc["years_to_mat"].clip(lower=0)
    df_calc["est_duration"] = df_calc["years_to_mat"] * 0.9  # Floating rate approximation
    df_calc["mv"] = df_calc[weight_col] * (df_calc["market_price"] / 100.0)
    df_calc["asset_dv01"] = df_calc["mv"] * df_calc["est_duration"] * 0.0001

    wavg_duration = (df_calc[weight_col] * df_calc["est_duration"]).sum() / total_par
    total_dv01 = df_calc["asset_dv01"].sum()
    total_mv = df_calc["mv"].sum()

    result["weighted_avg_duration"] = round(wavg_duration, 2)
    result["portfolio_dv01"] = round(total_dv01, 0)
    result["dv01_per_million"] = round(total_dv01 / (total_mv / 1e6), 0) if total_mv > 0 else 0.0
    return result


# ── Single-Name Concentration ─────────────────────────────────────────

def compute_single_name_concentration(
    df: pd.DataFrame,
    issuer_col: str = "issuer_name",
    weight_col: str = "par_amount",
    top_n: int = 10,
) -> Dict:
    """Compute single-name concentration metrics.

    Returns dict with max_pct, max_name, top_n_table, top_n_total_pct.
    """
    result = {
        "max_single_issuer_pct": 0.0,
        "max_single_issuer_name": "",
        "top_n_table": pd.DataFrame(),
        "top_n_total_pct": 0.0,
    }
    if df.empty or issuer_col not in df.columns:
        return result

    total_par = df[weight_col].sum()
    if total_par <= 0:
        return result

    issuer_exp = df.groupby(issuer_col)[weight_col].sum().sort_values(ascending=False)
    issuer_pct = issuer_exp / total_par

    result["max_single_issuer_pct"] = issuer_pct.iloc[0] if len(issuer_pct) > 0 else 0.0
    result["max_single_issuer_name"] = issuer_pct.index[0] if len(issuer_pct) > 0 else ""

    top = issuer_exp.head(top_n)
    top_df = pd.DataFrame({
        "Issuer": top.index,
        "Par ($M)": (top.values / 1e6).round(2),
        "% of Portfolio": (top.values / total_par * 100).round(2),
    }).reset_index(drop=True)
    top_df["Cumulative %"] = top_df["% of Portfolio"].cumsum().round(2)
    result["top_n_table"] = top_df
    result["top_n_total_pct"] = top.sum() / total_par

    return result


# ── Lien Breakdown ────────────────────────────────────────────────────

def compute_lien_breakdown(
    df: pd.DataFrame,
    weight_col: str = "par_amount",
) -> Dict:
    """Compute lien type breakdown with percentages.

    Returns dict with pct values per lien type and a breakdown_table DataFrame.
    """
    result = {
        "1L_pct": 0.0, "2L_pct": 0.0, "unsecured_pct": 0.0, "other_pct": 0.0,
        "breakdown_table": pd.DataFrame(),
    }
    if df.empty or "lien_type" not in df.columns:
        return result

    total_par = df[weight_col].sum()
    if total_par <= 0:
        return result

    lien_exp = df.groupby("lien_type")[weight_col].sum()

    for lien_type, par in lien_exp.items():
        pct = par / total_par
        lt = str(lien_type).strip().upper()
        if lt in ("1L", "FIRST LIEN", "1ST LIEN", "SENIOR SECURED"):
            result["1L_pct"] += pct
        elif lt in ("2L", "SECOND LIEN", "2ND LIEN"):
            result["2L_pct"] += pct
        elif lt in ("UNSECURED", "SUBORDINATED", "MEZZANINE"):
            result["unsecured_pct"] += pct
        else:
            result["other_pct"] += pct

    breakdown = lien_exp.reset_index()
    breakdown.columns = ["Lien Type", "Par Amount"]
    breakdown["% of Portfolio"] = (breakdown["Par Amount"] / total_par * 100).round(2)
    breakdown = breakdown.sort_values("Par Amount", ascending=False)
    result["breakdown_table"] = breakdown

    return result


# ── Herfindahl-Hirschman Index ────────────────────────────────────────

def compute_hhi(
    df: pd.DataFrame,
    group_col: str,
    weight_col: str = "par_amount",
) -> float:
    """Compute HHI for concentration measurement.

    HHI = sum(s_i^2) where s_i is the share of group i.
    HHI ranges: <0.01 highly diversified, 0.01-0.025 moderate, >0.025 high.
    """
    if df.empty or group_col not in df.columns:
        return 0.0

    total = df[weight_col].sum()
    if total <= 0:
        return 0.0

    shares = df.groupby(group_col)[weight_col].sum() / total
    return float((shares ** 2).sum())


# ── Compliance Status (Unified) ───────────────────────────────────────

def compute_compliance_status(df: pd.DataFrame, config) -> Dict:
    """Compute all compliance metrics for a warehouse.

    Returns dict with raw numeric values for every compliance dimension.
    """
    result = {
        "oc_ratio": 0.0,
        "ccc_pct": 0.0,
        "max_industry_pct": 0.0,
        "max_industry_name": "",
        "max_single_name_pct": 0.0,
        "max_single_name": "",
        "second_lien_pct": 0.0,
        "unsecured_pct": 0.0,
        "warf": 0.0,
        "diversity_score": 0.0,
        "issuer_hhi": 0.0,
        "industry_hhi": 0.0,
    }
    if df.empty:
        return result

    funded = df["par_amount"].sum()
    if funded <= 0:
        return result

    # OC Ratio (estimated)
    if "market_price" in df.columns:
        w_price = (df["par_amount"] * df["market_price"]).sum() / funded
        est_debt = funded * (w_price / 100) * config.advance_rate
        result["oc_ratio"] = funded / est_debt if est_debt > 0 else 0.0

    # CCC %
    if "rating_moodys" in df.columns:
        ccc_par = df[df["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
        result["ccc_pct"] = ccc_par / funded

    # Industry concentration
    if "industry_gics" in df.columns:
        ind_exp = df.groupby("industry_gics")["par_amount"].sum()
        if not ind_exp.empty:
            max_ind = ind_exp.max()
            result["max_industry_pct"] = max_ind / funded
            result["max_industry_name"] = ind_exp.idxmax()

    # Single-name concentration
    sn = compute_single_name_concentration(df)
    result["max_single_name_pct"] = sn["max_single_issuer_pct"]
    result["max_single_name"] = sn["max_single_issuer_name"]

    # Lien sublimits
    lien = compute_lien_breakdown(df)
    result["second_lien_pct"] = lien["2L_pct"]
    result["unsecured_pct"] = lien["unsecured_pct"]

    # WARF
    result["warf"] = compute_warf(df)

    # Diversity Score
    result["diversity_score"] = compute_diversity_score(df)

    # HHI
    result["issuer_hhi"] = compute_hhi(df, "issuer_name")
    if "industry_gics" in df.columns:
        result["industry_hhi"] = compute_hhi(df, "industry_gics")

    return result


# ── Coupon Analytics ──────────────────────────────────────────────────

def compute_coupon_analytics(
    df: pd.DataFrame,
    weight_col: str = "par_amount",
) -> Dict:
    """Compute coupon-related analytics.

    Returns dict with wavg_coupon, wavg_floor, pct_with_floor, index_breakdown.
    """
    result = {
        "wavg_coupon": 0.0,
        "wavg_floor": 0.0,
        "pct_with_floor": 0.0,
        "index_breakdown": pd.DataFrame(),
    }
    if df.empty:
        return result

    total_par = df[weight_col].sum()
    if total_par <= 0:
        return result

    if "coupon" in df.columns:
        result["wavg_coupon"] = (df[weight_col] * df["coupon"].fillna(0)).sum() / total_par

    if "floor" in df.columns:
        result["wavg_floor"] = (df[weight_col] * df["floor"].fillna(0)).sum() / total_par
        result["pct_with_floor"] = df[df["floor"].fillna(0) > 0][weight_col].sum() / total_par

    if "index" in df.columns:
        idx_exp = df.groupby("index")[weight_col].sum()
        idx_df = idx_exp.reset_index()
        idx_df.columns = ["Index", "Par Amount"]
        idx_df["% of Portfolio"] = (idx_df["Par Amount"] / total_par * 100).round(2)
        result["index_breakdown"] = idx_df.sort_values("Par Amount", ascending=False)

    return result


# ── Country Concentration ─────────────────────────────────────────────

def compute_country_concentration(
    df: pd.DataFrame,
    weight_col: str = "par_amount",
) -> pd.DataFrame:
    """Compute country-level exposure breakdown."""
    if df.empty or "country" not in df.columns:
        return pd.DataFrame()

    total_par = df[weight_col].sum()
    if total_par <= 0:
        return pd.DataFrame()

    country_exp = df.groupby("country")[weight_col].sum().sort_values(ascending=False)
    result = country_exp.reset_index()
    result.columns = ["Country", "Par Amount"]
    result["% of Portfolio"] = (result["Par Amount"] / total_par * 100).round(2)
    return result
