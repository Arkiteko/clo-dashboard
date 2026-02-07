"""
Reusable styled Streamlit components for the CLO Dashboard.

Provides alert banners, styled compliance tables, section headers,
and watchlist rendering with conditional formatting.
"""
import streamlit as st
import pandas as pd
from typing import List, Optional, Dict
from src.models import Alert, AlertSeverity
from src.style import COLORS


# ── Alert Banner ──────────────────────────────────────────────────────

def render_alert_banner(alerts: List[Alert]) -> None:
    """Render a prominent alert banner at the top of a tab.

    - CRITICAL alerts: red banner
    - WARNING only: amber banner
    - All clear: green banner (compact)
    """
    if not alerts:
        st.markdown(
            '<div class="alert-banner-clear">'
            '<h4>All Clear</h4>'
            '<p>No active alerts</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    n_critical = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL)
    n_warning = sum(1 for a in alerts if a.severity == AlertSeverity.WARNING)
    n_info = sum(1 for a in alerts if a.severity == AlertSeverity.INFO)

    if n_critical > 0:
        top_alert = next(a for a in alerts if a.severity == AlertSeverity.CRITICAL)
        st.markdown(
            f'<div class="alert-banner-critical">'
            f'<h4>{n_critical} Critical | {n_warning} Warning | {n_info} Info</h4>'
            f'<p>{top_alert.title}: {top_alert.detail}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
    elif n_warning > 0:
        top_alert = next(a for a in alerts if a.severity == AlertSeverity.WARNING)
        st.markdown(
            f'<div class="alert-banner-warning">'
            f'<h4>{n_warning} Warning | {n_info} Info</h4>'
            f'<p>{top_alert.title}: {top_alert.detail}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )
    else:
        top_alert = alerts[0]
        st.markdown(
            f'<div class="alert-banner-clear">'
            f'<h4>{n_info} Info Alert(s)</h4>'
            f'<p>{top_alert.title}: {top_alert.detail}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Expandable detail
    with st.expander(f"View All Alerts ({len(alerts)})"):
        for a in alerts:
            if a.severity == AlertSeverity.CRITICAL:
                icon = ":red_circle:"
            elif a.severity == AlertSeverity.WARNING:
                icon = ":large_orange_circle:"
            else:
                icon = ":large_blue_circle:"
            st.markdown(f"{icon} **[{a.warehouse}]** {a.title} — {a.detail}")


# ── Section Header ────────────────────────────────────────────────────

def section_header(title: str, subtitle: Optional[str] = None) -> None:
    """Render a visually distinct section header."""
    html = f'<div class="section-header"><h3>{title}</h3>'
    if subtitle:
        html += f'<p>{subtitle}</p>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ── Compliance Table with Conditional Formatting ──────────────────────

def _compliance_bg_color(val: float, limit: float, higher_is_worse: bool = True) -> str:
    """Return background color based on proximity to limit."""
    if higher_is_worse:
        ratio = val / limit if limit > 0 else 0
        if ratio > 1.0:
            return f"background-color: {COLORS['breach']}33"  # Red with alpha
        elif ratio > 0.85:
            return f"background-color: {COLORS['warning']}33"
        else:
            return f"background-color: {COLORS['pass']}22"
    else:
        # Lower is worse (e.g., OC ratio)
        ratio = val / limit if limit > 0 else 0
        if ratio < 1.0:
            return f"background-color: {COLORS['breach']}33"
        elif ratio < 1.0 + 0.10:
            return f"background-color: {COLORS['warning']}33"
        else:
            return f"background-color: {COLORS['pass']}22"


def style_compliance_table(
    compliance_data: List[Dict],
    configs: Dict,
) -> pd.DataFrame:
    """Build and style a compliance DataFrame with conditional formatting.

    Returns a styled DataFrame ready for st.dataframe().
    """
    if not compliance_data:
        return pd.DataFrame()

    df = pd.DataFrame(compliance_data)
    return df


def render_compliance_table(
    compliance_data: List[Dict],
    configs: Dict,
) -> None:
    """Render the compliance status table with color-coded status indicators."""
    if not compliance_data:
        st.info("No compliance data available.")
        return

    rows = []
    for item in compliance_data:
        wh = item["warehouse"]
        cfg = configs.get(wh)
        if cfg is None:
            continue

        oc = item.get("oc_ratio", 0)
        ccc = item.get("ccc_pct", 0)
        max_ind = item.get("max_industry_pct", 0)
        max_sn = item.get("max_single_name_pct", 0)
        lien_2l = item.get("second_lien_pct", 0)
        warf = item.get("warf", 0)

        def status_icon(val, limit, higher_is_worse=True):
            if higher_is_worse:
                if val > limit:
                    return ":red_circle:"
                elif val > limit * 0.85:
                    return ":large_orange_circle:"
                return ":white_check_mark:"
            else:
                if val < limit:
                    return ":red_circle:"
                elif val < limit * 1.10:
                    return ":large_orange_circle:"
                return ":white_check_mark:"

        rows.append({
            "Warehouse": wh,
            "OC Ratio": f"{oc:.2%}",
            "OC": status_icon(oc, cfg.oc_trigger_pct, higher_is_worse=False),
            "CCC %": f"{ccc:.1%}",
            "CCC": status_icon(ccc, cfg.max_ccc_pct),
            "Max Industry": f"{max_ind:.1%}",
            "Ind": status_icon(max_ind, cfg.concentration_limit_industry),
            "Max Issuer": f"{max_sn:.1%}",
            "SN": status_icon(max_sn, cfg.max_single_name_pct),
            "2L %": f"{lien_2l:.1%}",
            "2L": status_icon(lien_2l, cfg.max_second_lien_pct),
            "WARF": f"{warf:.0f}",
            "WF": status_icon(warf, cfg.alert_config.warf_warning),
        })

    df_display = pd.DataFrame(rows)
    st.dataframe(df_display, use_container_width=True, hide_index=True)


# ── Watchlist Table ───────────────────────────────────────────────────

def render_watchlist_table(df_watchlist: pd.DataFrame) -> None:
    """Render the asset watchlist with severity-based visual indicators."""
    if df_watchlist.empty:
        st.info("No assets currently on watchlist.")
        return

    st.dataframe(
        df_watchlist,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Par ($M)": st.column_config.NumberColumn(format="%.2f"),
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "Severity": st.column_config.TextColumn(),
        },
    )


# ── Alert Detail Table ────────────────────────────────────────────────

def render_alert_detail_table(alerts: List[Alert]) -> None:
    """Render a detailed table of alerts for the Watchlist & Alerts tab."""
    if not alerts:
        st.info("No active alerts.")
        return

    rows = []
    for a in alerts:
        rows.append({
            "Severity": a.severity.value,
            "Warehouse": a.warehouse,
            "Category": a.category,
            "Alert": a.title,
            "Detail": a.detail,
            "Current": f"{a.current_value:.2%}" if a.current_value < 10 else f"{a.current_value:.0f}",
            "Threshold": f"{a.threshold_value:.2%}" if a.threshold_value < 10 else f"{a.threshold_value:.0f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
