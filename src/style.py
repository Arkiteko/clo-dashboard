"""
Custom CSS theming and color constants for the CLO Dashboard.
"""
import streamlit as st


# ── Color Palette ─────────────────────────────────────────────────────

COLORS = {
    "pass": "#10B981",
    "warning": "#F59E0B",
    "breach": "#EF4444",
    "primary": "#3B82F6",
    "secondary": "#6366F1",
    "info": "#22D3EE",
    "bg_card": "#1E293B",
    "bg_surface": "#0F172A",
    "text_muted": "#94A3B8",
    "border": "#334155",
}

TIER_COLORS = {
    "IG": "#3B82F6",
    "BB": "#34D399",
    "B": "#FBBF24",
    "CCC": "#EF4444",
    "NR": "#64748B",
}


def inject_custom_css() -> None:
    """Inject custom CSS for professional financial dashboard styling."""
    st.markdown("""
    <style>
    /* ── Import font ─────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ── Global ──────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ── Header Bar ─────────────────────────────────────── */
    header[data-testid="stHeader"] {
        background-color: #0E1117;
        border-bottom: 1px solid #1E293B;
    }

    /* ── Metric Cards ───────────────────────────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-left: 3px solid #3B82F6;
        border-radius: 8px;
        padding: 14px 18px;
    }

    div[data-testid="stMetric"] label {
        font-family: 'Inter', sans-serif;
        font-size: 0.7rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.35rem;
        font-weight: 600;
        color: #F1F5F9;
    }

    div[data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.72rem;
    }

    /* ── Sidebar ────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F172A 0%, #0E1117 100%);
        border-right: 1px solid #1E293B;
    }

    section[data-testid="stSidebar"] div[data-testid="stMetric"] {
        border-left: 3px solid #6366F1;
        padding: 10px 14px;
        margin-bottom: 6px;
    }

    section[data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.15rem;
    }

    /* ── Tabs ───────────────────────────────────────────── */
    button[data-baseweb="tab"] {
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
        letter-spacing: 0.3px;
    }

    /* ── DataFrames / Tables ────────────────────────────── */
    div[data-testid="stDataFrame"] {
        border: 1px solid #334155;
        border-radius: 8px;
        overflow: hidden;
    }

    /* Monospace for numbers in tables */
    div[data-testid="stDataFrame"] td {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.82rem;
    }

    /* ── Expander ───────────────────────────────────────── */
    details[data-testid="stExpander"] {
        border: 1px solid #334155;
        border-radius: 8px;
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    }

    /* ── Download Buttons ───────────────────────────────── */
    button[data-testid="stDownloadButton"] {
        border: 1px solid #334155;
        border-radius: 6px;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
    }

    /* ── Plotly Charts Container ─────────────────────────── */
    div[data-testid="stPlotlyChart"] {
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 8px;
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        overflow: hidden !important;
    }

    div[data-testid="stPlotlyChart"] iframe,
    div[data-testid="stPlotlyChart"] > div,
    div[data-testid="stPlotlyChart"] > div > div {
        overflow: hidden !important;
    }

    /* ── Alert Banner Styles ────────────────────────────── */
    .alert-banner-critical {
        background: linear-gradient(135deg, #3B111780 0%, #1A060880 100%);
        border: 1px solid #EF444466;
        border-left: 4px solid #EF4444;
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(8px);
    }

    .alert-banner-warning {
        background: linear-gradient(135deg, #3B2F1180 0%, #1A170880 100%);
        border: 1px solid #F59E0B66;
        border-left: 4px solid #F59E0B;
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(8px);
    }

    .alert-banner-clear {
        background: linear-gradient(135deg, #113B1E80 0%, #081A0E80 100%);
        border: 1px solid #10B98166;
        border-left: 4px solid #10B981;
        border-radius: 8px;
        padding: 14px 20px;
        margin-bottom: 16px;
        backdrop-filter: blur(8px);
    }

    .alert-banner-critical h4, .alert-banner-warning h4, .alert-banner-clear h4 {
        margin: 0 0 4px 0;
        font-size: 0.95rem;
        font-weight: 600;
    }

    .alert-banner-critical p, .alert-banner-warning p, .alert-banner-clear p {
        margin: 0;
        font-size: 0.82rem;
        color: #CBD5E1;
    }

    /* ── Section Headers ────────────────────────────────── */
    .section-header {
        border-bottom: 2px solid #3B82F6;
        padding-bottom: 8px;
        margin-bottom: 20px;
    }

    .section-header h3 {
        margin: 0;
        font-weight: 600;
        color: #F1F5F9;
    }

    .section-header p {
        margin: 2px 0 0 0;
        font-size: 0.78rem;
        color: #94A3B8;
    }

    /* ── Severity Badges ──────────────────────────────── */
    .severity-critical {
        background-color: #EF4444;
        color: white;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .severity-warning {
        background-color: #F59E0B;
        color: white;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    .severity-info {
        background-color: #22D3EE;
        color: #0F172A;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.5px;
    }

    /* ── Sidebar Status Rows ────────────────────────────── */
    .sidebar-status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #1E293B;
        font-size: 0.82rem;
    }

    .sidebar-status-row .wh-name {
        font-weight: 500;
        color: #E2E8F0;
    }

    .sidebar-status-row .wh-age {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 4px;
    }

    .age-fresh { background-color: #10B98122; color: #10B981; }
    .age-stale { background-color: #F59E0B22; color: #F59E0B; }
    .age-old { background-color: #EF444422; color: #EF4444; }

    /* ── Alert Count Badges (sidebar) ─────────────────── */
    .alert-badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    .badge-critical { background: #EF444433; color: #EF4444; }
    .badge-warning  { background: #F59E0B33; color: #F59E0B; }
    .badge-info     { background: #22D3EE33; color: #22D3EE; }
    .badge-clear    { background: #10B98133; color: #10B981; }

    /* ── Dividers ────────────────────────────────────── */
    hr {
        border-color: #1E293B !important;
    }

    /* ── Progress bar ─────────────────────────────────── */
    div[data-testid="stProgress"] > div > div {
        background-color: #3B82F6;
    }

    </style>
    """, unsafe_allow_html=True)
