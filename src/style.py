"""
Custom CSS theming and color constants for the CLO Dashboard.
"""
import streamlit as st


# ── Color Palette ─────────────────────────────────────────────────────

COLORS = {
    "pass": "#2ECC71",
    "warning": "#F39C12",
    "breach": "#E74C3C",
    "primary": "#1F4E79",
    "secondary": "#2980B9",
    "info": "#3498DB",
    "bg_card": "#262730",
    "bg_surface": "#1E1E2E",
    "text_muted": "#95A5A6",
    "border": "#3B3B4F",
}

TIER_COLORS = {
    "IG": "#2980B9",
    "BB": "#27AE60",
    "B": "#F39C12",
    "CCC": "#E74C3C",
    "NR": "#95A5A6",
}


def inject_custom_css() -> None:
    """Inject custom CSS for professional financial dashboard styling."""
    st.markdown("""
    <style>
    /* ── Header Bar ─────────────────────────────────────── */
    header[data-testid="stHeader"] {
        background-color: #0E1117;
        border-bottom: 2px solid #1F4E79;
    }

    /* ── Metric Cards ───────────────────────────────────── */
    div[data-testid="stMetric"] {
        background-color: #262730;
        border: 1px solid #3B3B4F;
        border-left: 4px solid #1F4E79;
        border-radius: 6px;
        padding: 12px 16px;
    }

    div[data-testid="stMetric"] label {
        font-size: 0.8rem;
        color: #95A5A6;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.4rem;
        font-weight: 700;
    }

    /* ── Sidebar ────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #0E1117;
        border-right: 1px solid #1F4E79;
    }

    section[data-testid="stSidebar"] div[data-testid="stMetric"] {
        border-left: 3px solid #2980B9;
        padding: 8px 12px;
        margin-bottom: 4px;
    }

    /* ── Tabs ───────────────────────────────────────────── */
    button[data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.9rem;
    }

    /* ── DataFrames / Tables ────────────────────────────── */
    div[data-testid="stDataFrame"] {
        border: 1px solid #3B3B4F;
        border-radius: 6px;
    }

    /* ── Expander ───────────────────────────────────────── */
    details[data-testid="stExpander"] {
        border: 1px solid #3B3B4F;
        border-radius: 6px;
        background-color: #262730;
    }

    /* ── Download Buttons ───────────────────────────────── */
    button[data-testid="stDownloadButton"] {
        border: 1px solid #1F4E79;
        border-radius: 4px;
    }

    /* ── Alert Banner Styles ────────────────────────────── */
    .alert-banner-critical {
        background-color: #3B1117;
        border: 1px solid #E74C3C;
        border-left: 5px solid #E74C3C;
        border-radius: 6px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }

    .alert-banner-warning {
        background-color: #3B2F11;
        border: 1px solid #F39C12;
        border-left: 5px solid #F39C12;
        border-radius: 6px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }

    .alert-banner-clear {
        background-color: #113B1E;
        border: 1px solid #2ECC71;
        border-left: 5px solid #2ECC71;
        border-radius: 6px;
        padding: 12px 18px;
        margin-bottom: 16px;
    }

    .alert-banner-critical h4, .alert-banner-warning h4, .alert-banner-clear h4 {
        margin: 0 0 4px 0;
        font-size: 1rem;
    }

    .alert-banner-critical p, .alert-banner-warning p, .alert-banner-clear p {
        margin: 0;
        font-size: 0.85rem;
        color: #BDC3C7;
    }

    /* ── Section Headers ────────────────────────────────── */
    .section-header {
        border-bottom: 2px solid #1F4E79;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }

    .section-header h3 {
        margin: 0;
        color: #ECF0F1;
    }

    .section-header p {
        margin: 2px 0 0 0;
        font-size: 0.8rem;
        color: #95A5A6;
    }

    /* ── Watchlist Severity Badges ──────────────────────── */
    .severity-critical {
        background-color: #E74C3C;
        color: white;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .severity-warning {
        background-color: #F39C12;
        color: white;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 700;
    }

    .severity-info {
        background-color: #3498DB;
        color: white;
        padding: 2px 8px;
        border-radius: 3px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    </style>
    """, unsafe_allow_html=True)
