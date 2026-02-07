import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
from src.etl import ETLPipeline
from src.utils import ingest_file
from src.config import get_warehouse_config, save_warehouse_config, WarehouseConfig, StressConfig
from src.stress import run_all_scenarios, run_historical_stress, PRESET_SCENARIOS, RATING_ORDER
from src.reports import generate_global_report, generate_warehouse_report, generate_stress_report
from src.style import inject_custom_css, TIER_COLORS
from src.risk_analytics import (
    compute_warf, compute_diversity_score, compute_portfolio_duration,
    compute_single_name_concentration, compute_lien_breakdown, compute_hhi,
    compute_compliance_status, compute_coupon_analytics,
)
from src.alerts import evaluate_all_alerts, evaluate_global_alerts, build_watchlist
from src.models import AlertSeverity, AlertConfig
from src.ui_components import (
    render_alert_banner, section_header, render_compliance_table,
    render_watchlist_table, render_alert_detail_table,
)


# Config
DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "0_raw"
STAGING_DIR = DATA_DIR / "1_staging"
STANDARD_DIR = DATA_DIR / "2_standard"
PUBLISHED_DIR = DATA_DIR / "3_published"

# Ensure dirs exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="CLO Warehouse Platform", layout="wide")

# Inject custom CSS
inject_custom_css()

# Load all published data globally for use in tabs
files = list(PUBLISHED_DIR.glob("*.parquet"))
df_all = pd.DataFrame()

if files:
    dfs = []
    for f in files:
        d = pd.read_parquet(f)
        name = f.stem

        parts = name.split("_")

        # Default fallback
        data_date = datetime.now()
        upload_ts = "000000"
        warehouse_name = "Unknown"

        # New Format: YYYYMMDD_HHMMSS_Name...
        if len(parts) >= 3 and len(parts[0])==8 and len(parts[1])==6:
             try:
                 data_date = datetime.strptime(parts[0], "%Y%m%d")
                 upload_ts = parts[1]
                 warehouse_name = "_".join(parts[2:]).replace(".parquet", "")
                 warehouse_name = warehouse_name.replace("_Tape", "")
             except:
                 pass
        else:
             try:
                 ts_str = parts[0]
                 if len(ts_str) == 8:
                      data_date = datetime.strptime(ts_str, "%Y%m%d")
                 if "Warehouse" in parts:
                     idx = parts.index("Warehouse")
                     warehouse_name = "_".join(parts[idx:idx+2])
             except:
                 pass

        d["warehouse_source"] = warehouse_name
        d["data_date"] = data_date
        d["upload_ts"] = upload_ts
        d["data_date"] = pd.to_datetime(d["data_date"])

        dfs.append(d)

    if dfs:
        df_raw = pd.concat(dfs, ignore_index=True)
        versions = df_raw[["warehouse_source", "data_date", "upload_ts"]].drop_duplicates()
        latest_versions = versions.sort_values("upload_ts").groupby(["warehouse_source", "data_date"]).tail(1)
        df_all = df_raw.merge(latest_versions, on=["warehouse_source", "data_date", "upload_ts"], how="inner")


# ── Precompute global metrics for sidebar and tabs ────────────────────

df_latest = pd.DataFrame()
all_alerts = []
all_configs = {}

if not df_all.empty:
    latest_dates = df_all.groupby("warehouse_source")["data_date"].transform("max")
    df_latest = df_all[df_all["data_date"] == latest_dates].copy()

    # Load configs for all warehouses
    for wh in df_latest["warehouse_source"].unique():
        all_configs[wh] = get_warehouse_config(wh)

    # Evaluate global alerts
    all_alerts = evaluate_global_alerts(df_latest, all_configs)


# ── Sidebar ───────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### CLO Warehouse Platform")
    st.caption("Portfolio Snapshot")

    if not df_latest.empty:
        global_par = df_latest["par_amount"].sum()
        n_warehouses = df_latest["warehouse_source"].nunique()
        global_warf = compute_warf(df_latest)
        global_diversity = compute_diversity_score(df_latest)
        global_duration = compute_portfolio_duration(df_latest)

        st.metric("Total AUM", f"${global_par/1e6:,.0f}M")
        st.metric("Active Warehouses", n_warehouses)
        st.metric("WARF", f"{global_warf:,.0f}")
        st.metric("Diversity Score", f"{global_diversity:.1f}")
        st.metric("Portfolio Duration", f"{global_duration['weighted_avg_duration']:.2f} yrs")

        st.divider()
        st.caption("Alert Summary")
        n_critical = sum(1 for a in all_alerts if a.severity == AlertSeverity.CRITICAL)
        n_warning = sum(1 for a in all_alerts if a.severity == AlertSeverity.WARNING)
        n_info = sum(1 for a in all_alerts if a.severity == AlertSeverity.INFO)

        if n_critical > 0:
            st.markdown(f"\U0001F534 **{n_critical} Critical**")
        if n_warning > 0:
            st.markdown(f"\U0001F7E0 **{n_warning} Warning**")
        if n_info > 0:
            st.markdown(f"\U0001F535 **{n_info} Info**")
        if n_critical == 0 and n_warning == 0 and n_info == 0:
            st.markdown("\u2705 **All Clear**")

        st.divider()
        st.caption("Data Freshness")
        today_ts = pd.to_datetime(datetime.now())
        for wh_name in sorted(df_latest["warehouse_source"].unique()):
            wh_data = df_latest[df_latest["warehouse_source"] == wh_name]
            latest_dt = wh_data["data_date"].max()
            days_old = (today_ts - latest_dt).days
            if days_old >= 14:
                st.markdown(f"\U0001F534 **{wh_name}**: {days_old}d ago")
            elif days_old >= 7:
                st.markdown(f"\U0001F7E0 **{wh_name}**: {days_old}d ago")
            else:
                st.markdown(f"\u2705 **{wh_name}**: {days_old}d ago")
    else:
        st.info("No data loaded.")


# ── Main Title + Tabs ─────────────────────────────────────────────────

st.title("CLO Warehouse Platform")

tabs = st.tabs([
    "Global Portfolio", "Warehouse Analytics", "Stress Testing",
    "Tape Ingestion", "Watchlist & Alerts", "Admin Settings",
])


# ══════════════════════════════════════════════════════════════════════
# TAB 0: GLOBAL PORTFOLIO
# ══════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.header("Global Portfolio Overview")

    if df_latest.empty:
        st.info("No published data found. Please ingest some tapes.")
    else:
        # Alert banner
        global_tab_alerts = [a for a in all_alerts if a.category != "Data Quality"]
        render_alert_banner(global_tab_alerts)

        # Enrich with Strategy Type from Config
        def get_type(row):
            c = all_configs.get(row["warehouse_source"], WarehouseConfig())
            return c.warehouse_type
        df_latest["Strategy"] = df_latest.apply(get_type, axis=1)

        # Overall Metrics (Latest)
        total_funded = df_latest["par_amount"].sum()
        global_par = total_funded
        weighted_avg_price = (df_latest["par_amount"] * df_latest["market_price"]).sum() / global_par if global_par > 0 else 0

        if "spread" in df_latest.columns:
            weighted_avg_spread = (df_latest["par_amount"] * df_latest["spread"]).sum() / global_par if global_par > 0 else 0
        else:
            weighted_avg_spread = 0

        if "maturity_date" in df_latest.columns:
            today_date = pd.to_datetime(datetime.now())
            df_latest["years_to_mat"] = (df_latest["maturity_date"] - today_date).dt.days / 365.0
            weighted_avg_life = (df_latest["par_amount"] * df_latest["years_to_mat"]).sum() / global_par if global_par > 0 else 0
        else:
            weighted_avg_life = 0

        ccc_exposure = 0
        if "rating_moodys" in df_latest.columns:
             ccc_exposure = df_latest[df_latest["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
        ccc_pct = ccc_exposure / total_funded if total_funded > 0 else 0

        # Row 1: Core metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Funded Exposure", f"${total_funded/1_000_000:,.1f}M")
        c2.metric("Portfolio W.Avg Price", f"{weighted_avg_price:.2f}")
        c3.metric("W.Avg Spread (WAS)", f"{weighted_avg_spread:.0f} bps")
        c4.metric("W.Avg Life (WAL)", f"{weighted_avg_life:.2f} yrs")

        # Row 2: Risk metrics
        global_warf_val = compute_warf(df_latest)
        global_div_val = compute_diversity_score(df_latest)
        global_dur = compute_portfolio_duration(df_latest)
        issuer_hhi = compute_hhi(df_latest, "issuer_name")

        c5, c6, c7, c8 = st.columns(4)
        c5.metric("WARF", f"{global_warf_val:,.0f}")
        c6.metric("Diversity Score", f"{global_div_val:.1f}")
        c7.metric("Global CCC %", f"{ccc_pct:.2%}")
        c8.metric("Portfolio DV01", f"${global_dur['portfolio_dv01']:,.0f}")

        c9, c10, c11, c12 = st.columns(4)
        c9.metric("Total Assets", len(df_latest))
        c10.metric("Active Warehouses", df_latest["warehouse_source"].nunique())
        c11.metric("Issuer HHI", f"{issuer_hhi:.4f}")
        industry_hhi = compute_hhi(df_latest, "industry_gics") if "industry_gics" in df_latest.columns else 0
        c12.metric("Industry HHI", f"{industry_hhi:.4f}")

        st.divider()
        st.subheader("Exposure by Strategy")

        strat_stats = []
        if "Strategy" in df_latest.columns:
            for strat, g in df_latest.groupby("Strategy"):
                s_fund = g["par_amount"].sum()
                s_price = (g["par_amount"] * g["market_price"]).sum() / s_fund if s_fund > 0 else 0
                s_was = (g["par_amount"] * g["spread"]).sum() / s_fund if s_fund > 0 else 0
                s_count = g["warehouse_source"].nunique()
                strat_stats.append({
                    "Strategy": strat,
                    "Funded Exposure": s_fund,
                    "W.Avg Price": s_price,
                    "WAS": s_was,
                    "Warehouses": s_count
                })

        if strat_stats:
            df_strat = pd.DataFrame(strat_stats)
            cols = st.columns(len(strat_stats))
            for idx, row in df_strat.iterrows():
                with cols[idx]:
                    st.metric(f"{row['Strategy']}", f"${row['Funded Exposure']/1e6:,.1f}M", f"WAS: {row['WAS']:.0f} bps")

        st.divider()

        col_charts1, col_charts2 = st.columns(2)

        with col_charts1:
            st.subheader("Global Industry Concentration")
            if "industry_gics" in df_latest.columns:
                ind_exp = df_latest.groupby("industry_gics")["par_amount"].sum().sort_values(ascending=False).head(10)
                st.bar_chart(ind_exp)

        with col_charts2:
            st.subheader("Global Rating Distribution")
            if "rating_moodys" in df_latest.columns:
                rtg_exp = df_latest.groupby("rating_moodys")["par_amount"].sum()
                rtg_exp = rtg_exp.reindex(sorted(rtg_exp.index, key=lambda r: RATING_ORDER.get(r, 99)))
                st.bar_chart(rtg_exp)

        st.subheader("Top 20 Issuers (Global)")
        if "issuer_name" in df_latest.columns:
            sn_data = compute_single_name_concentration(df_latest, top_n=20)
            if not sn_data["top_n_table"].empty:
                st.dataframe(sn_data["top_n_table"], use_container_width=True, hide_index=True)
                st.download_button(
                    "Download Top Issuers CSV", sn_data["top_n_table"].to_csv(index=False).encode("utf-8"),
                    file_name="top_20_issuers.csv", mime="text/csv", key="dl_top_issuers"
                )

        # ────────────────────────────────────────────────────────────
        # WAREHOUSE SUMMARY TABLE (with data freshness + risk metrics)
        # ────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Warehouse Comparison")

        wh_summary_rows = []
        today_dt = pd.to_datetime(datetime.now())
        for wh_name, g in df_latest.groupby("warehouse_source"):
            cfg = all_configs.get(wh_name, WarehouseConfig())
            funded = g["par_amount"].sum()
            w_price = (g["par_amount"] * g["market_price"]).sum() / funded if funded > 0 else 0
            w_was = (g["par_amount"] * g["spread"]).sum() / funded if funded > 0 else 0 if "spread" in g.columns else 0

            if "maturity_date" in g.columns:
                g_wal = (g["par_amount"] * ((pd.to_datetime(g["maturity_date"]) - today_dt).dt.days / 365.0)).sum() / funded if funded > 0 else 0
            else:
                g_wal = 0

            est_debt = funded * (w_price / 100) * cfg.advance_rate
            est_oc = funded / est_debt if est_debt > 0 else 0
            util = est_debt / cfg.max_facility_amount if cfg.max_facility_amount > 0 else 0

            if "rating_moodys" in g.columns:
                ccc_par = g[g["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
            else:
                ccc_par = 0
            ccc = ccc_par / funded if funded > 0 else 0

            wh_warf = compute_warf(g)
            wh_hhi = compute_hhi(g, "issuer_name")

            latest_data_date = g["data_date"].max()
            days_ago = (today_dt - latest_data_date).days

            wh_summary_rows.append({
                "Warehouse": wh_name,
                "Type": cfg.warehouse_type,
                "Funded ($M)": round(funded / 1e6, 2),
                "W.Avg Price": round(w_price, 2),
                "WAS (bps)": round(w_was, 0),
                "WAL (yrs)": round(g_wal, 2),
                "Est. OC": f"{est_oc:.2%}",
                "Util.": f"{util:.1%}",
                "CCC %": f"{ccc:.1%}",
                "WARF": round(wh_warf, 0),
                "Issuer HHI": round(wh_hhi, 4),
                "Assets": len(g),
                "Last Updated": f"{days_ago}d ago",
            })

        if wh_summary_rows:
            df_wh_summary = pd.DataFrame(wh_summary_rows)
            st.dataframe(df_wh_summary, use_container_width=True, hide_index=True)

        # ────────────────────────────────────────────────────────────
        # COMPLIANCE HEATMAP (enhanced with new metrics)
        # ────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Compliance Status")

        compliance_data = []
        compliance_rows_legacy = []
        for wh_name, g in df_latest.groupby("warehouse_source"):
            cfg = all_configs.get(wh_name, WarehouseConfig())
            status = compute_compliance_status(g, cfg)
            status["warehouse"] = wh_name
            compliance_data.append(status)

            # Legacy rows for report generation
            compliance_rows_legacy.append({
                "Warehouse": wh_name,
                "OC Ratio": f"{status['oc_ratio']:.2%}",
                "OC Trigger": f"{cfg.oc_trigger_pct:.0%}",
                "CCC %": f"{status['ccc_pct']:.1%}",
                "CCC Limit": f"{cfg.max_ccc_pct:.1%}",
                "Max Industry": f"{status['max_industry_pct']:.1%}",
                "Ind. Limit": f"{cfg.concentration_limit_industry:.0%}",
            })

        render_compliance_table(compliance_data, all_configs)

        # ── Excel Report Download ──
        st.divider()
        report_bytes = generate_global_report(
            df_latest, wh_summary_rows, compliance_rows_legacy,
            configs=all_configs, alerts=all_alerts,
        )
        st.download_button(
            "Download Global Portfolio Report (Excel)", report_bytes,
            file_name=f"global_portfolio_{datetime.now():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_global_report"
        )

        # ────────────────────────────────────────────────────────────
        # LIEN TYPE & FACILITY MIX
        # ────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Portfolio Composition")

        col_lien, col_flags = st.columns(2)

        with col_lien:
            st.markdown("**Lien Type Breakdown**")
            global_lien = compute_lien_breakdown(df_latest)
            if not global_lien["breakdown_table"].empty:
                st.dataframe(global_lien["breakdown_table"], use_container_width=True, hide_index=True)
                if "lien_type" in df_latest.columns:
                    lien_by_wh = df_latest.groupby(["warehouse_source", "lien_type"])["par_amount"].sum().unstack(fill_value=0)
                    st.bar_chart(lien_by_wh)
            else:
                st.info("Lien type data not available.")

        with col_flags:
            st.markdown("**Portfolio Flags**")
            total_par = df_latest["par_amount"].sum()
            if total_par > 0:
                cov_lite_pct = df_latest[df_latest["is_cov_lite"] == True]["par_amount"].sum() / total_par if "is_cov_lite" in df_latest.columns else 0
                pik_pct = df_latest[df_latest["is_pik"] == True]["par_amount"].sum() / total_par if "is_pik" in df_latest.columns else 0
                default_pct = df_latest[df_latest["is_defaulted"] == True]["par_amount"].sum() / total_par if "is_defaulted" in df_latest.columns else 0

                f1, f2, f3 = st.columns(3)
                f1.metric("Cov-Lite %", f"{cov_lite_pct:.1%}")
                f2.metric("PIK %", f"{pik_pct:.1%}")
                f3.metric("Defaulted %", f"{default_pct:.1%}", delta_color="inverse" if default_pct > 0 else "off")

            # Coupon analytics
            coupon_data = compute_coupon_analytics(df_latest)
            if coupon_data["wavg_coupon"] > 0:
                st.markdown("**Coupon Analytics**")
                cp1, cp2, cp3 = st.columns(3)
                cp1.metric("W.Avg Coupon", f"{coupon_data['wavg_coupon']:.2%}")
                cp2.metric("W.Avg Floor", f"{coupon_data['wavg_floor']:.2%}")
                cp3.metric("% with Floor", f"{coupon_data['pct_with_floor']:.1%}")

        # ────────────────────────────────────────────────────────────
        # MATURITY PROFILE
        # ────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("Maturity Profile")

        if "maturity_date" in df_latest.columns:
            df_mat = df_latest.copy()
            df_mat["maturity_year"] = pd.to_datetime(df_mat["maturity_date"]).dt.year
            current_year = datetime.now().year
            df_mat["maturity_bucket"] = df_mat["maturity_year"].apply(
                lambda y: str(y) if y <= current_year + 5 else f"{current_year + 6}+"
            )
            mat_exp = df_mat.groupby("maturity_bucket")["par_amount"].sum().sort_index()
            st.bar_chart(mat_exp)
        else:
            st.info("Maturity date data not available.")


# ══════════════════════════════════════════════════════════════════════
# TAB 1: WAREHOUSE ANALYTICS
# ══════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.header("Warehouse Analytics")

    if df_all.empty:
        st.info("No data available.")
    else:
        wh_list = sorted(df_all["warehouse_source"].unique())
        selected_wh = st.selectbox("Select Warehouse", wh_list, key="wh_select_analytics")

        df_wh_history = df_all[df_all["warehouse_source"] == selected_wh].copy().sort_values("data_date")

        latest_date = df_wh_history["data_date"].max()
        df_wh = df_wh_history[df_wh_history["data_date"] == latest_date].copy()

        config = all_configs.get(selected_wh, get_warehouse_config(selected_wh))

        # Warehouse-level alerts
        wh_alerts = [a for a in all_alerts if a.warehouse == selected_wh]
        render_alert_banner(wh_alerts)

        wh_funded = df_wh["par_amount"].sum()
        wh_price = (df_wh["par_amount"] * df_wh["market_price"]).sum() / wh_funded if wh_funded > 0 else 0
        wh_was = (df_wh["par_amount"] * df_wh["spread"]).sum() / wh_funded if wh_funded > 0 else 0

        today_date = pd.to_datetime(latest_date)
        df_wh["years_to_mat"] = (df_wh["maturity_date"] - today_date).dt.days / 365.0
        wh_wal = (df_wh["par_amount"] * df_wh["years_to_mat"]).sum() / wh_funded if wh_funded > 0 else 0

        st.markdown(f"#### Compliance & Metrics (As of {latest_date.date()}) [{config.warehouse_type}]")

        implied_debt = wh_funded * (wh_price/100) * config.advance_rate

        c_snap1, c_snap2 = st.columns(2)
        debt_outstanding = c_snap1.number_input("Debt Outstanding (Snapshot)", value=implied_debt, help="Enter actual debt from report")
        cash_balance = c_snap2.number_input("Cash Balance", value=0.0)

        total_collateral_par = wh_funded
        numerator = total_collateral_par + cash_balance
        denominator = debt_outstanding if debt_outstanding > 0 else 1.0

        current_oc = numerator / denominator

        # Row 1: Core compliance
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Facility Utilization", f"{(debt_outstanding / config.max_facility_amount)*100:.1f}%", f"Limit: ${config.max_facility_amount/1e6:.0f}M")
        oc_delta = current_oc - config.oc_trigger_pct
        m2.metric("OC Ratio", f"{current_oc:.2%}", f"{oc_delta:.2%} vs Trig ({config.oc_trigger_pct:.0%})", delta_color="normal" if oc_delta >= 0 else "inverse")
        m3.metric("Equity (NAV)", f"${(numerator - debt_outstanding)/1e6:,.2f}M")
        m4.metric("W.Avg Price", f"{wh_price:.2f}")

        # Row 2: Spread, WAL, CCC, Asset Count
        m5, m6, m7, m8 = st.columns(4)
        m5.metric("W.Avg Spread (WAS)", f"{wh_was:.0f} bps")
        m6.metric("W.Avg Life (WAL)", f"{wh_wal:.2f} yrs")

        ccc_exposure_wh = df_wh[df_wh["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
        ccc_pct_wh = ccc_exposure_wh / wh_funded if wh_funded > 0 else 0
        m7.metric("CCC Exposure", f"{ccc_pct_wh:.1%}", f"Limit: {config.max_ccc_pct:.1%}", delta_color="inverse" if ccc_pct_wh > config.max_ccc_pct else "normal")
        m8.metric("Asset Count", len(df_wh))

        # Row 3: Risk analytics
        wh_warf = compute_warf(df_wh)
        wh_div = compute_diversity_score(df_wh)
        wh_dur = compute_portfolio_duration(df_wh, as_of_date=latest_date)
        wh_sn = compute_single_name_concentration(df_wh)

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("WARF", f"{wh_warf:,.0f}")
        r2.metric("Diversity Score", f"{wh_div:.1f}")
        r3.metric("Portfolio DV01", f"${wh_dur['portfolio_dv01']:,.0f}")
        r4.metric("Max Single Name", f"{wh_sn['max_single_issuer_pct']:.1%}",
                   f"Limit: {config.max_single_name_pct:.1%}",
                   delta_color="inverse" if wh_sn["max_single_issuer_pct"] > config.max_single_name_pct else "off")

        # ── Warehouse Excel Report Download ──
        wh_report = generate_warehouse_report(df_wh, config, selected_wh, alerts=wh_alerts)
        st.download_button(
            "Download Warehouse Report (Excel)", wh_report,
            file_name=f"{selected_wh}_{datetime.now():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_wh_report"
        )

        st.divider()

        # ── Subtabs ──
        subtabs = st.tabs(["Asset Quality", "Trends", "Concentration & Composition", "Trade Blotter"])

        with subtabs[0]:
            st.subheader("Credit Quality")

            c_qual1, c_qual2 = st.columns(2)

            with c_qual1:
                st.markdown("**Rating Distribution**")
                if "rating_moodys" in df_wh.columns:
                    rtg_exp = df_wh.groupby("rating_moodys")["par_amount"].sum()
                    rtg_exp = rtg_exp.reindex(sorted(rtg_exp.index, key=lambda r: RATING_ORDER.get(r, 99)))
                    st.bar_chart(rtg_exp)

            with c_qual2:
                st.markdown("**Rating Migration (vs Original)**")
                if "original_rating_moodys" in df_wh.columns:
                    df_mig = df_wh[["asset_id", "issuer_name", "original_rating_moodys", "rating_moodys", "par_amount"]].copy()
                    df_mig["Downgraded"] = df_mig.apply(lambda x: x["rating_moodys"] != x["original_rating_moodys"], axis=1)
                    df_mig_filtered = df_mig[df_mig["Downgraded"]]
                    st.dataframe(df_mig_filtered, hide_index=True)
                    if not df_mig_filtered.empty:
                        st.download_button(
                            "Download Migration CSV", df_mig_filtered.to_csv(index=False).encode("utf-8"),
                            file_name=f"{selected_wh}_rating_migration.csv", mime="text/csv", key="dl_mig"
                        )

        with subtabs[1]:
            st.subheader("Historical Trends")
            trend_data = []
            for d, g in df_wh_history.groupby("data_date"):
                 fnd = g["par_amount"].sum()
                 px = (g["par_amount"] * g["market_price"]).sum() / fnd if fnd > 0 else 0
                 est_debt_t = fnd * (px/100) * config.advance_rate
                 est_oc_t = fnd / est_debt_t if est_debt_t > 0 else 0
                 t_warf = compute_warf(g)
                 trend_data.append({
                     "Date": d,
                     "Funded Exposure": fnd,
                     "W.Avg Price": px,
                     "Est. OC%": est_oc_t,
                     "WARF": t_warf,
                 })

            df_trend = pd.DataFrame(trend_data).set_index("Date")

            t1, t2 = st.columns(2)
            with t1:
                st.markdown("**Funded Exposure**")
                st.line_chart(df_trend["Funded Exposure"])
            with t2:
                st.markdown("**W.Avg Price**")
                st.line_chart(df_trend["W.Avg Price"])

            t3, t4 = st.columns(2)
            with t3:
                st.markdown("**Est. OC Ratio**")
                st.line_chart(df_trend["Est. OC%"])
            with t4:
                st.markdown("**WARF Trend**")
                st.line_chart(df_trend["WARF"])

            # ── Ramp Tracker ──
            if config.target_ramp_amount and config.target_close_date:
                st.divider()
                st.markdown("**Ramp Tracker: Actual vs Target**")
                try:
                    target_date = pd.to_datetime(config.target_close_date)
                    target_amount = config.target_ramp_amount

                    if not df_trend.empty:
                        first_date = df_trend.index.min()
                        date_range = pd.date_range(first_date, target_date, periods=50)
                        days_total = (target_date - first_date).days

                        if days_total > 0:
                            target_vals = [target_amount * min(1.0, (d - first_date).days / days_total) for d in date_range]
                        else:
                            target_vals = [target_amount] * len(date_range)

                        df_ramp = pd.DataFrame({"Target Ramp": target_vals}, index=date_range)
                        df_actual = df_trend[["Funded Exposure"]].copy()
                        df_combined = df_ramp.join(df_actual, how="outer").sort_index()
                        df_combined["Funded Exposure"] = df_combined["Funded Exposure"].ffill()
                        st.line_chart(df_combined)
                except Exception:
                    st.info("Could not generate ramp chart. Check target dates in Admin Settings.")

        with subtabs[2]:
            st.subheader("Concentration & Composition")

            # HHI and Single-Name metrics
            wh_issuer_hhi = compute_hhi(df_wh, "issuer_name")
            wh_ind_hhi = compute_hhi(df_wh, "industry_gics") if "industry_gics" in df_wh.columns else 0
            h1, h2 = st.columns(2)
            h1.metric("Issuer HHI", f"{wh_issuer_hhi:.4f}", "Diversified" if wh_issuer_hhi < 0.01 else "Moderate" if wh_issuer_hhi < 0.025 else "Concentrated")
            h2.metric("Industry HHI", f"{wh_ind_hhi:.4f}", "Diversified" if wh_ind_hhi < 0.10 else "Moderate" if wh_ind_hhi < 0.20 else "Concentrated")

            c_conc1, c_conc2 = st.columns(2)
            with c_conc1:
                 st.markdown("**Top Industries**")
                 if "industry_gics" in df_wh.columns:
                     ind_exp = df_wh.groupby("industry_gics")["par_amount"].sum().sort_values(ascending=False).head(5)
                     st.bar_chart(ind_exp)

            with c_conc2:
                 st.markdown("**Top Obligors**")
                 if "issuer_name" in df_wh.columns:
                     iss_exp = df_wh.groupby("issuer_name")["par_amount"].sum().sort_values(ascending=False).head(5)
                     st.bar_chart(iss_exp)

            # Single-name concentration table
            st.divider()
            st.markdown("**Single-Name Concentration (Top 10)**")
            sn_wh = compute_single_name_concentration(df_wh)
            if not sn_wh["top_n_table"].empty:
                st.dataframe(sn_wh["top_n_table"], use_container_width=True, hide_index=True)

            # Lien breakdown
            st.divider()
            st.markdown("**Lien Type Breakdown**")
            lien_wh = compute_lien_breakdown(df_wh)
            l1, l2, l3 = st.columns(3)
            l1.metric("First Lien", f"{lien_wh['1L_pct']:.1%}")
            l2.metric("Second Lien", f"{lien_wh['2L_pct']:.1%}", f"Limit: {config.max_second_lien_pct:.0%}",
                       delta_color="inverse" if lien_wh["2L_pct"] > config.max_second_lien_pct else "off")
            l3.metric("Unsecured", f"{lien_wh['unsecured_pct']:.1%}", f"Limit: {config.max_unsecured_pct:.0%}",
                       delta_color="inverse" if lien_wh["unsecured_pct"] > config.max_unsecured_pct else "off")

            # Coupon analytics
            coupon = compute_coupon_analytics(df_wh)
            if coupon["wavg_coupon"] > 0:
                st.divider()
                st.markdown("**Coupon Analytics**")
                cp1, cp2, cp3 = st.columns(3)
                cp1.metric("W.Avg Coupon", f"{coupon['wavg_coupon']:.2%}")
                cp2.metric("W.Avg Floor", f"{coupon['wavg_floor']:.2%}")
                cp3.metric("% with Floor", f"{coupon['pct_with_floor']:.1%}")

            st.divider()
            asset_cols = [c for c in ["asset_id", "issuer_name", "par_amount", "market_price", "spread",
                                       "maturity_date", "rating_moodys", "lien_type"] if c in df_wh.columns]
            st.dataframe(df_wh[asset_cols], use_container_width=True, hide_index=True)
            st.download_button(
                "Download Asset Detail CSV", df_wh[asset_cols].to_csv(index=False).encode("utf-8"),
                file_name=f"{selected_wh}_assets.csv", mime="text/csv", key="dl_wh_assets"
            )

        # ── Trade Blotter ──
        with subtabs[3]:
            st.subheader("Trade Blotter (Tape Diff)")

            avail_dates = sorted(df_wh_history["data_date"].unique(), reverse=True)

            if len(avail_dates) < 2:
                st.info("Need at least 2 tape dates for comparison.")
            else:
                col_d1, col_d2 = st.columns(2)
                date_new = col_d1.selectbox("Current Date", avail_dates, index=0, key="blotter_new")
                date_old = col_d2.selectbox("Previous Date", avail_dates, index=1, key="blotter_old")

                df_new = df_wh_history[df_wh_history["data_date"] == date_new].drop_duplicates(subset=["asset_id"], keep="last").set_index("asset_id")
                df_old = df_wh_history[df_wh_history["data_date"] == date_old].drop_duplicates(subset=["asset_id"], keep="last").set_index("asset_id")

                new_ids = set(df_new.index) - set(df_old.index)
                removed_ids = set(df_old.index) - set(df_new.index)
                common_ids = set(df_new.index) & set(df_old.index)

                b1, b2, b3 = st.columns(3)
                b1.metric("Assets Added", len(new_ids))
                b2.metric("Assets Removed", len(removed_ids))

                new_par = df_new.loc[list(new_ids)]["par_amount"].sum() if new_ids else 0
                removed_par = df_old.loc[list(removed_ids)]["par_amount"].sum() if removed_ids else 0
                b3.metric("Net Par Change", f"${(new_par - removed_par)/1e6:+,.2f}M")

                if new_ids:
                    st.markdown("**New Assets Added:**")
                    st.dataframe(df_new.loc[list(new_ids)][["issuer_name", "par_amount", "market_price", "rating_moodys"]].reset_index(), hide_index=True)

                if removed_ids:
                    st.markdown("**Assets Removed:**")
                    st.dataframe(df_old.loc[list(removed_ids)][["issuer_name", "par_amount", "market_price", "rating_moodys"]].reset_index(), hide_index=True)

                if common_ids:
                    changes = []
                    for aid in common_ids:
                        row_new = df_new.loc[aid]
                        row_old = df_old.loc[aid]
                        par_chg = row_new["par_amount"] - row_old["par_amount"]
                        px_chg = row_new["market_price"] - row_old["market_price"]
                        rtg_chg = str(row_new["rating_moodys"]) != str(row_old["rating_moodys"])
                        if abs(par_chg) > 0.01 or abs(px_chg) > 0.01 or rtg_chg:
                            changes.append({
                                "Asset ID": aid,
                                "Issuer": row_new["issuer_name"],
                                "Par Change": round(par_chg, 2),
                                "Price Change": round(px_chg, 2),
                                "Rating (Old)": row_old["rating_moodys"],
                                "Rating (New)": row_new["rating_moodys"],
                                "Rating Changed": "Yes" if rtg_chg else "",
                            })
                    if changes:
                        st.markdown(f"**Modified Assets:** {len(changes)}")
                        st.dataframe(pd.DataFrame(changes), use_container_width=True, hide_index=True)
                    elif not new_ids and not removed_ids:
                        st.info("No changes detected between selected dates.")


# ══════════════════════════════════════════════════════════════════════
# TAB 2: STRESS TESTING
# ══════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.header("Stress Testing / SVar")

    if df_all.empty:
        st.info("No data available. Please ingest tapes first.")
    else:
        wh_list_stress = sorted(df_all["warehouse_source"].unique())
        selected_wh_stress = st.selectbox("Select Warehouse", wh_list_stress, key="wh_select_stress")

        df_wh_stress_all = df_all[df_all["warehouse_source"] == selected_wh_stress].copy()
        latest_date_stress = df_wh_stress_all["data_date"].max()
        df_wh_stress = df_wh_stress_all[df_wh_stress_all["data_date"] == latest_date_stress].copy()

        config_stress = all_configs.get(selected_wh_stress, get_warehouse_config(selected_wh_stress))
        s_cfg = config_stress.stress_config

        wh_funded_stress = df_wh_stress["par_amount"].sum()
        wh_price_stress = (df_wh_stress["par_amount"] * df_wh_stress["market_price"]).sum() / wh_funded_stress if wh_funded_stress > 0 else 100
        implied_debt_stress = wh_funded_stress * (wh_price_stress / 100) * config_stress.advance_rate

        col_debt, col_cash = st.columns(2)
        debt_input = col_debt.number_input("Debt Outstanding", value=implied_debt_stress, key="stress_debt")
        cash_input = col_cash.number_input("Cash Balance", value=0.0, key="stress_cash")

        run_stress = st.button("Run Stress Analysis", type="primary")

        if run_stress:
            with st.spinner("Running stress scenarios..."):
                results = run_all_scenarios(
                    df_wh_stress, config_stress, s_cfg,
                    debt_outstanding=debt_input, cash_balance=cash_input
                )

            st.divider()
            st.subheader("Aggregate Stress Summary")

            a1, a2, a3, a4 = st.columns(4)
            a1.metric(
                "Total Stressed Loss",
                f"${results.total_stressed_loss / 1e6:,.2f}M",
                f"-{results.total_stressed_loss / results.total_par:.1%} of par" if results.total_par > 0 else ""
            )
            a2.metric(
                "Stressed OC Ratio",
                f"{results.stressed_oc:.2%}",
                f"{results.stressed_oc - results.base_oc:.2%} vs base",
                delta_color="inverse"
            )
            if results.oc_breach:
                a3.metric("OC Breach", "YES", f"Trigger: {results.oc_trigger:.0%}", delta_color="inverse")
            else:
                a3.metric("OC Breach", "NO", f"Trigger: {results.oc_trigger:.0%}", delta_color="off")
            a4.metric(
                "Stressed CCC %",
                f"{results.stressed_ccc_pct:.1%}",
                "BREACH" if results.ccc_breach else "Within limit",
                delta_color="inverse" if results.ccc_breach else "off"
            )

            st.divider()
            st.subheader("Scenario Breakdown")

            scenario_rows = []
            for s in results.scenarios:
                scenario_rows.append({
                    "Scenario": s.name,
                    "Loss ($M)": round(s.loss_dollars / 1e6, 2),
                    "Loss (%)": f"{s.loss_pct:.2%}",
                    "Key Detail": s.detail,
                })
            df_scenario = pd.DataFrame(scenario_rows)
            st.dataframe(df_scenario, use_container_width=True, hide_index=True)

            st.divider()
            col_chart, col_compare = st.columns(2)

            with col_chart:
                st.markdown("**Loss by Scenario**")
                chart_data = pd.DataFrame({
                    "Scenario": [s.name for s in results.scenarios],
                    "Loss ($M)": [s.loss_dollars / 1e6 for s in results.scenarios]
                }).set_index("Scenario")
                st.bar_chart(chart_data)

            with col_compare:
                st.markdown("**Stressed vs Unstressed**")
                c1, c2 = st.columns(2)
                c1.metric("Base OC", f"{results.base_oc:.2%}")
                c2.metric("Stressed OC", f"{results.stressed_oc:.2%}", f"{results.stressed_oc - results.base_oc:.2%}", delta_color="inverse")

                base_ccc_par = df_wh_stress[df_wh_stress["rating_moodys"].str.contains("Caa|Ca|^C$", na=False, regex=True)]["par_amount"].sum()
                base_ccc_pct = base_ccc_par / results.total_par if results.total_par > 0 else 0
                c3, c4 = st.columns(2)
                c3.metric("Base CCC %", f"{base_ccc_pct:.1%}")
                c4.metric("Stressed CCC %", f"{results.stressed_ccc_pct:.1%}", f"{results.stressed_ccc_pct - base_ccc_pct:+.1%}", delta_color="inverse" if results.ccc_breach else "off")

                base_nav = (results.total_par + cash_input) - debt_input
                stressed_nav = (results.total_par - results.total_stressed_loss + cash_input) - debt_input
                c5, c6 = st.columns(2)
                c5.metric("Base NAV", f"${base_nav / 1e6:,.2f}M")
                c6.metric("Stressed NAV", f"${stressed_nav / 1e6:,.2f}M", f"${(stressed_nav - base_nav) / 1e6:,.2f}M", delta_color="inverse")

            st.divider()
            st.subheader("Asset-Level Stress Detail")

            for s in results.scenarios:
                if s.asset_level is not None and not s.asset_level.empty:
                    with st.expander(f"{s.name} - Asset Detail"):
                        display_df = s.asset_level.copy()
                        if "loss" in display_df.columns:
                            display_df = display_df.sort_values("loss", ascending=False)
                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                        st.download_button(
                            f"Download {s.name} CSV", display_df.to_csv(index=False).encode("utf-8"),
                            file_name=f"stress_{s.name.lower().replace(' ', '_')}.csv", mime="text/csv",
                            key=f"dl_stress_{s.name}"
                        )

            # ── Stress Report Download ──
            st.divider()
            stress_report = generate_stress_report(results, scenario_rows, selected_wh_stress)
            st.download_button(
                "Download Stress Report (Excel)", stress_report,
                file_name=f"stress_report_{selected_wh_stress}_{datetime.now():%Y%m%d}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_stress_report"
            )

        # ── Scenario Comparison (outside run_stress block) ──
        st.divider()
        st.subheader("Scenario Comparison")

        selected_presets = st.multiselect(
            "Select Preset Scenarios to Compare",
            list(PRESET_SCENARIOS.keys()),
            default=["Base", "Moderate", "Severe"],
            key="preset_select"
        )

        if st.button("Run Comparison", key="run_comparison"):
            comparison_rows = []
            for name in selected_presets:
                preset_cfg = PRESET_SCENARIOS[name]
                res = run_all_scenarios(df_wh_stress, config_stress, preset_cfg,
                                       debt_outstanding=debt_input, cash_balance=cash_input)
                comparison_rows.append({
                    "Scenario": name,
                    "Base OC": f"{res.base_oc:.2%}",
                    "Stressed OC": f"{res.stressed_oc:.2%}",
                    "Total Loss ($M)": f"{res.total_stressed_loss/1e6:,.2f}",
                    "Loss %": f"{res.total_stressed_loss/res.total_par:.2%}" if res.total_par > 0 else "0%",
                    "OC Breach": "YES" if res.oc_breach else "No",
                    "Stressed CCC %": f"{res.stressed_ccc_pct:.1%}",
                    "CCC Breach": "YES" if res.ccc_breach else "No",
                })
            if comparison_rows:
                df_compare = pd.DataFrame(comparison_rows)
                st.dataframe(df_compare, use_container_width=True, hide_index=True)

        # ── Historical Stress Trends ──
        st.divider()
        st.subheader("Historical Stress Trends")

        if st.button("Run Historical Stress", key="run_hist_stress"):
            with st.spinner("Computing stress across all historical snapshots..."):
                df_hist_stress = run_historical_stress(df_wh_stress_all, config_stress, s_cfg)

            if not df_hist_stress.empty:
                df_plot = df_hist_stress.set_index("Date")
                h1, h2 = st.columns(2)
                with h1:
                    st.markdown("**OC Ratio Over Time**")
                    st.line_chart(df_plot[["Base OC", "Stressed OC"]])
                with h2:
                    st.markdown("**Stressed CCC % Over Time**")
                    st.line_chart(df_plot[["Stressed CCC %"]])
                st.markdown("**Total Stressed Loss Over Time**")
                st.line_chart(df_plot[["Total Loss ($M)"]])
            else:
                st.info("No historical data available for stress trends.")


# ══════════════════════════════════════════════════════════════════════
# TAB 3: TAPE INGESTION
# ══════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.markdown("### Data Tape Ingestion & Validation")

    uploaded_file = st.file_uploader("Drop Standard Template (Excel)", type=["xlsx"])
    warehouse_name = st.selectbox("Select Warehouse Name for Ingestion", ["Warehouse_Alpha", "Warehouse_Beta", "Warehouse_Gamma"])
    as_of_date = st.date_input("As Of Date")

    process_btn = st.button("Process Tape")

    if uploaded_file and process_btn:
        with st.spinner("Ingesting and Validating..."):
            raw_path = ingest_file(uploaded_file, RAW_DIR, warehouse_name)
            st.success(f"File saved: {raw_path.name}")

            pipeline = ETLPipeline(RAW_DIR, STAGING_DIR, STANDARD_DIR)
            df, issues = pipeline.process_tape(raw_path)

            if df is not None:
                st.divider()
                st.subheader("Validation Report")

                hard_errors = [i for i in issues if i.severity == "HARD"]
                soft_warns = [i for i in issues if i.severity == "SOFT"]

                c1, c2 = st.columns(2)
                c1.metric("Hard Errors", len(hard_errors), delta_color="inverse" if hard_errors else "off")
                c2.metric("Warnings", len(soft_warns), delta_color="normal")

                if hard_errors:
                    st.error("Blocking Issues Found - Data NOT Published:")
                    for e in hard_errors:
                        st.write(f"- {e.message} (Row IDs: {e.row_id})")

                if soft_warns:
                    st.warning("Warnings:")
                    for w in soft_warns:
                         st.write(f"- {w.message}")

                if not hard_errors:
                    st.success("Published Successfully!")
                    st.cache_data.clear()
            else:
                st.error("Failed to parse file.")

    st.divider()
    st.markdown("### Load History")

    if df_all.empty:
        st.info("No load history.")
    else:
        hist_df = df_all.groupby(["warehouse_source", "data_date"]).agg(
            Assets=("asset_id", "count"),
            Total_Funded=("par_amount", "sum"),
            Last_Updated=("data_date", "max")
        ).reset_index().sort_values(["warehouse_source", "data_date"], ascending=[True, False])

        hist_df["Total_Funded"] = hist_df["Total_Funded"].apply(lambda x: f"${x/1e6:,.2f}M")

        st.dataframe(hist_df, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 4: WATCHLIST & ALERTS
# ══════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.header("Watchlist & Alerts")

    if df_latest.empty:
        st.info("No data available. Please ingest tapes first.")
    else:
        # Alert summary metrics
        n_crit = sum(1 for a in all_alerts if a.severity == AlertSeverity.CRITICAL)
        n_warn = sum(1 for a in all_alerts if a.severity == AlertSeverity.WARNING)
        n_info_a = sum(1 for a in all_alerts if a.severity == AlertSeverity.INFO)

        al1, al2, al3, al4 = st.columns(4)
        al1.metric("Total Alerts", len(all_alerts))
        al2.metric("Critical", n_crit)
        al3.metric("Warning", n_warn)
        al4.metric("Info", n_info_a)

        # Active alerts detail
        st.divider()
        st.subheader("Active Alerts")

        if all_alerts:
            # Group by warehouse
            alert_wh_filter = st.selectbox(
                "Filter by Warehouse",
                ["All"] + sorted(df_latest["warehouse_source"].unique().tolist()),
                key="alert_wh_filter"
            )
            if alert_wh_filter == "All":
                filtered_alerts = all_alerts
            else:
                filtered_alerts = [a for a in all_alerts if a.warehouse == alert_wh_filter]

            render_alert_detail_table(filtered_alerts)
        else:
            st.success("No active alerts. All compliance checks passed.")

        # Watchlist
        st.divider()
        st.subheader("Asset Watchlist")
        st.caption("Assets flagged for review: defaulted, CCC-rated, distressed price, downgraded, or concentrated")

        watchlist_frames = []
        for wh_name in sorted(df_latest["warehouse_source"].unique()):
            wh_data = df_latest[df_latest["warehouse_source"] == wh_name]
            cfg = all_configs.get(wh_name, WarehouseConfig())
            wl = build_watchlist(wh_data, wh_name, cfg)
            if not wl.empty:
                watchlist_frames.append(wl)

        if watchlist_frames:
            df_watchlist = pd.concat(watchlist_frames, ignore_index=True)

            wl_filter = st.selectbox(
                "Filter by Severity",
                ["All", "CRITICAL", "WARNING", "INFO"],
                key="wl_severity_filter"
            )
            if wl_filter != "All":
                df_watchlist = df_watchlist[df_watchlist["Severity"] == wl_filter]

            render_watchlist_table(df_watchlist)

            st.download_button(
                "Download Watchlist CSV", df_watchlist.to_csv(index=False).encode("utf-8"),
                file_name=f"watchlist_{datetime.now():%Y%m%d}.csv", mime="text/csv",
                key="dl_watchlist"
            )
        else:
            st.success("No assets currently flagged for watchlist.")

        # Per-warehouse alert breakdown
        st.divider()
        st.subheader("Alert Breakdown by Warehouse")
        for wh_name in sorted(df_latest["warehouse_source"].unique()):
            wh_alerts_list = [a for a in all_alerts if a.warehouse == wh_name]
            n_c = sum(1 for a in wh_alerts_list if a.severity == AlertSeverity.CRITICAL)
            n_w = sum(1 for a in wh_alerts_list if a.severity == AlertSeverity.WARNING)
            n_i = sum(1 for a in wh_alerts_list if a.severity == AlertSeverity.INFO)
            summary = f"{n_c} Critical, {n_w} Warning, {n_i} Info" if wh_alerts_list else "All Clear"
            with st.expander(f"{wh_name} — {summary}"):
                if wh_alerts_list:
                    for a in wh_alerts_list:
                        if a.severity == AlertSeverity.CRITICAL:
                            icon = "\U0001F534"
                        elif a.severity == AlertSeverity.WARNING:
                            icon = "\U0001F7E0"
                        else:
                            icon = "\U0001F535"
                        st.markdown(f"{icon} **{a.title}** — {a.detail}")
                else:
                    st.markdown("\u2705 All compliance checks passed.")


# ══════════════════════════════════════════════════════════════════════
# TAB 5: ADMIN SETTINGS
# ══════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.header("Admin Settings")
    st.info("Configure Limits, Triggers, and Alert Thresholds for each warehouse.")

    if df_all.empty:
         st.warning("No warehouses found. Please ingest data first.")
    else:
        wh_list = sorted(df_all["warehouse_source"].unique())
        selected_wh_admin = st.selectbox("Select Warehouse to Configure", wh_list, key="wh_select_admin")

        config = all_configs.get(selected_wh_admin, get_warehouse_config(selected_wh_admin))

        with st.form("admin_config_form"):
            st.subheader(f"Configuration for: {selected_wh_admin}")

            new_type = st.selectbox("Warehouse Type", ["BSL", "Middle Market"], index=0 if config.warehouse_type=="BSL" else 1)

            c_adm1, c_adm2 = st.columns(2)

            with c_adm1:
                st.markdown("#### Facility Limits")
                new_max = st.number_input("Max Facility Size ($)", value=float(config.max_facility_amount))
                new_adv = st.slider("Advance Rate", 0.0, 1.0, value=float(config.advance_rate))

            with c_adm2:
                st.markdown("#### Compliance Triggers")
                new_oc = st.number_input("Min OC Ratio Trigger (decimal)", value=float(config.oc_trigger_pct), step=0.01, help="e.g. 1.25 for 125%")
                new_conc = st.slider("Max Industry Concentration", 0.0, 1.0, value=float(config.concentration_limit_industry))

            # ── Compliance Sublimits ──
            st.divider()
            st.subheader("Compliance Sublimits")
            sub_col1, sub_col2, sub_col3 = st.columns(3)
            with sub_col1:
                new_max_sn = st.number_input("Max Single Name %", value=float(config.max_single_name_pct), step=0.005, format="%.3f", help="e.g. 0.02 for 2%")
            with sub_col2:
                new_max_2l = st.number_input("Max Second Lien %", value=float(config.max_second_lien_pct), step=0.01, format="%.2f")
            with sub_col3:
                new_max_unsec = st.number_input("Max Unsecured %", value=float(config.max_unsecured_pct), step=0.01, format="%.2f")
            new_max_ccc = st.number_input("Max CCC %", value=float(config.max_ccc_pct), step=0.005, format="%.3f", help="e.g. 0.075 for 7.5%")

            # ── Alert Settings ──
            st.divider()
            st.subheader("Alert Settings")
            ac = config.alert_config
            alert_col1, alert_col2, alert_col3 = st.columns(3)
            with alert_col1:
                new_prox_margin = st.number_input("Proximity Warning Margin", value=float(ac.proximity_margin), step=0.05, format="%.2f", help="e.g. 0.10 for 10%")
                new_stale_warn = st.number_input("Data Stale Warning (days)", value=int(ac.stale_warning_days), step=1)
                new_stale_crit = st.number_input("Data Stale Critical (days)", value=int(ac.stale_critical_days), step=1)
            with alert_col2:
                new_warf_warn = st.number_input("WARF Warning Threshold", value=float(ac.warf_warning), step=100.0)
                new_warf_crit = st.number_input("WARF Critical Threshold", value=float(ac.warf_critical), step=100.0)
            with alert_col3:
                new_div_warn = st.number_input("Diversity Score Warning", value=float(ac.diversity_warning), step=5.0)
                new_util_warn = st.number_input("Utilization Warning", value=float(ac.utilization_warning), step=0.05, format="%.2f")

            # ── Ramp Schedule ──
            st.divider()
            st.subheader("Ramp Schedule")
            ramp_col1, ramp_col2 = st.columns(2)
            with ramp_col1:
                new_ramp_target = st.number_input(
                    "Target Ramp Amount ($)",
                    value=float(config.target_ramp_amount or config.max_facility_amount),
                    key="ramp_target"
                )
            with ramp_col2:
                default_close = datetime.strptime(config.target_close_date, "%Y-%m-%d").date() if config.target_close_date else datetime.now().date()
                new_close_date = st.date_input("Target Close Date", value=default_close, key="close_date")

            # ── Stress Parameters ──
            st.divider()
            st.subheader("Stress Test Parameters")
            sc = config.stress_config

            st_col1, st_col2, st_col3 = st.columns(3)

            with st_col1:
                st.markdown("**Price Shock Haircuts (pts)**")
                sp_ig = st.number_input("IG", value=float(sc.price_shock_ig), step=0.5, key="sp_ig")
                sp_bb = st.number_input("BB", value=float(sc.price_shock_bb), step=0.5, key="sp_bb")
                sp_b = st.number_input("B", value=float(sc.price_shock_b), step=0.5, key="sp_b")
                sp_ccc = st.number_input("CCC", value=float(sc.price_shock_ccc), step=1.0, key="sp_ccc")

            with st_col2:
                st.markdown("**Default Rates (CDR)**")
                cdr_ig = st.number_input("IG CDR", value=float(sc.cdr_ig), step=0.005, format="%.3f", key="cdr_ig")
                cdr_bb = st.number_input("BB CDR", value=float(sc.cdr_bb), step=0.01, format="%.3f", key="cdr_bb")
                cdr_b = st.number_input("B CDR", value=float(sc.cdr_b), step=0.01, format="%.3f", key="cdr_b")
                cdr_ccc = st.number_input("CCC CDR", value=float(sc.cdr_ccc), step=0.01, format="%.3f", key="cdr_ccc")

                st.markdown("**Recovery Rates**")
                rec_1l = st.number_input("1L Recovery", value=float(sc.recovery_1l), step=0.05, format="%.2f", key="rec_1l")
                rec_2l = st.number_input("2L Recovery", value=float(sc.recovery_2l), step=0.05, format="%.2f", key="rec_2l")
                rec_un = st.number_input("Unsecured Recovery", value=float(sc.recovery_unsecured), step=0.05, format="%.2f", key="rec_un")

            with st_col3:
                st.markdown("**Spread Shocks (bps)**")
                ss_ig = st.number_input("IG Spread", value=float(sc.spread_shock_ig), step=10.0, key="ss_ig")
                ss_bb = st.number_input("BB Spread", value=float(sc.spread_shock_bb), step=25.0, key="ss_bb")
                ss_b = st.number_input("B Spread", value=float(sc.spread_shock_b), step=25.0, key="ss_b")
                ss_ccc = st.number_input("CCC Spread", value=float(sc.spread_shock_ccc), step=50.0, key="ss_ccc")

                st.markdown("**Migration & Concentration**")
                mig_rate = st.number_input("Migration Rate", value=float(sc.migration_rate), step=0.05, format="%.2f", key="mig_rate")
                conc_n = st.number_input("Top N Obligors", value=int(sc.concentration_top_n), step=1, key="conc_n")

            if st.form_submit_button("Save Configuration"):
                new_alert_config = AlertConfig(
                    proximity_margin=new_prox_margin,
                    stale_warning_days=int(new_stale_warn),
                    stale_critical_days=int(new_stale_crit),
                    warf_warning=new_warf_warn,
                    warf_critical=new_warf_crit,
                    diversity_warning=new_div_warn,
                    utilization_warning=new_util_warn,
                )
                new_stress = StressConfig(
                    price_shock_ig=sp_ig, price_shock_bb=sp_bb,
                    price_shock_b=sp_b, price_shock_ccc=sp_ccc,
                    cdr_ig=cdr_ig, cdr_bb=cdr_bb, cdr_b=cdr_b, cdr_ccc=cdr_ccc,
                    recovery_1l=rec_1l, recovery_2l=rec_2l, recovery_unsecured=rec_un,
                    spread_shock_ig=ss_ig, spread_shock_bb=ss_bb,
                    spread_shock_b=ss_b, spread_shock_ccc=ss_ccc,
                    migration_rate=mig_rate, concentration_top_n=int(conc_n),
                )
                new_cfg = WarehouseConfig(
                    max_facility_amount=new_max,
                    advance_rate=new_adv,
                    oc_trigger_pct=new_oc,
                    concentration_limit_industry=new_conc,
                    warehouse_type=new_type,
                    stress_config=new_stress,
                    max_single_name_pct=new_max_sn,
                    max_second_lien_pct=new_max_2l,
                    max_unsecured_pct=new_max_unsec,
                    max_ccc_pct=new_max_ccc,
                    alert_config=new_alert_config,
                    target_ramp_amount=new_ramp_target,
                    target_close_date=new_close_date.isoformat(),
                )
                save_warehouse_config(selected_wh_admin, new_cfg)
                st.success(f"Settings saved for {selected_wh_admin}")
                st.rerun()
