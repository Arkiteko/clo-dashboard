"""
Plotly chart factory for the CLO Dashboard.

All charts use a consistent dark theme, brand colors, and
formatting conventions so the dashboard looks cohesive.
"""
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Optional, List, Dict

# Plotly display config — passed to every st.plotly_chart() call
# Hides the floating toolbar; keeps responsive sizing enabled so
# charts fill their Streamlit container without scrollbars.
PLOTLY_CONFIG = {"displayModeBar": False}

# ── Brand palette ────────────────────────────────────────────────────

BRAND = {
    "primary":   "#3B82F6",   # bright blue
    "secondary": "#6366F1",   # indigo
    "accent":    "#22D3EE",   # cyan
    "positive":  "#10B981",   # emerald
    "warning":   "#F59E0B",   # amber
    "negative":  "#EF4444",   # red
    "muted":     "#64748B",   # slate
    "bg":        "#0E1117",
    "card":      "#1E293B",
    "grid":      "#1E293B",
    "text":      "#E2E8F0",
    "text_muted":"#94A3B8",
}

SERIES_COLORS = [
    "#3B82F6", "#22D3EE", "#A78BFA", "#F472B6",
    "#34D399", "#FBBF24", "#FB923C", "#E879F9",
]

RATING_COLORS = {
    "Aaa": "#3B82F6", "Aa1": "#3B82F6", "Aa2": "#3B82F6", "Aa3": "#3B82F6",
    "A1": "#60A5FA", "A2": "#60A5FA", "A3": "#60A5FA",
    "Baa1": "#22D3EE", "Baa2": "#22D3EE", "Baa3": "#22D3EE",
    "Ba1": "#34D399", "Ba2": "#34D399", "Ba3": "#34D399",
    "B1": "#FBBF24", "B2": "#FBBF24", "B3": "#FBBF24",
    "Caa1": "#FB923C", "Caa2": "#FB923C", "Caa3": "#FB923C",
    "Ca": "#EF4444", "C": "#EF4444",
    "NR": "#64748B",
}


def _base_layout(**overrides) -> dict:
    """Common layout settings for every chart."""
    layout = dict(
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, sans-serif", color=BRAND["text"], size=12),
        margin=dict(l=0, r=10, t=28, b=8),
        xaxis=dict(
            gridcolor=BRAND["grid"],
            zerolinecolor=BRAND["grid"],
            tickfont=dict(size=10, color=BRAND["text_muted"]),
        ),
        yaxis=dict(
            gridcolor=BRAND["grid"],
            zerolinecolor=BRAND["grid"],
            tickfont=dict(size=10, color=BRAND["text_muted"]),
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=11, color=BRAND["text_muted"]),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
        hoverlabel=dict(
            bgcolor=BRAND["card"],
            font_size=12,
            font_color=BRAND["text"],
            bordercolor=BRAND["primary"],
        ),
    )
    layout.update(overrides)
    return layout


# ═══════════════════════════════════════════════════════════════════
# LINE CHARTS
# ═══════════════════════════════════════════════════════════════════

def line_chart(
    df: pd.DataFrame,
    y_cols: List[str],
    title: str = "",
    y_format: str = "",
    height: int = 300,
    show_area: bool = False,
    colors: Optional[List[str]] = None,
) -> go.Figure:
    """Multi-series line chart on a DateTimeIndex."""
    fig = go.Figure()
    palette = colors or SERIES_COLORS

    for i, col in enumerate(y_cols):
        color = palette[i % len(palette)]
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df[col],
            name=col,
            mode="lines",
            line=dict(color=color, width=2.5),
            fill="tozeroy" if show_area and i == 0 else None,
            fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.08)" if show_area and i == 0 else None,
            hovertemplate=f"<b>{col}</b><br>%{{x|%b %d, %Y}}<br>%{{y:{y_format or ',.2f'}}}<extra></extra>",
        ))

    layout_opts = _base_layout(height=height, title=dict(text=title, font=dict(size=14)))
    if y_format:
        layout_opts["yaxis"]["tickformat"] = y_format
    fig.update_layout(**layout_opts)
    return fig


def trend_chart(
    df: pd.DataFrame,
    col: str,
    title: str = "",
    y_format: str = "",
    color: str = "",
    height: int = 280,
) -> go.Figure:
    """Single-series trend line with area fill."""
    c = color or BRAND["primary"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[col],
        mode="lines",
        line=dict(color=c, width=2.5),
        fill="tozeroy",
        fillcolor=f"rgba({int(c[1:3],16)},{int(c[3:5],16)},{int(c[5:7],16)},0.10)",
        hovertemplate=f"<b>{title or col}</b><br>%{{x|%b %d}}<br>%{{y:{y_format or ',.2f'}}}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        height=height,
        title=dict(text=title, font=dict(size=13)),
        showlegend=False,
    ))
    if y_format:
        fig.update_yaxes(tickformat=y_format)
    return fig


# ═══════════════════════════════════════════════════════════════════
# BAR CHARTS
# ═══════════════════════════════════════════════════════════════════

def bar_chart(
    data: pd.Series,
    title: str = "",
    color: str = "",
    horizontal: bool = False,
    height: int = 300,
    y_format: str = "",
    color_map: Optional[Dict[str, str]] = None,
) -> go.Figure:
    """Styled bar chart from a Series (index = categories)."""
    if color_map:
        colors = [color_map.get(idx, color or BRAND["primary"]) for idx in data.index]
    else:
        colors = color or BRAND["primary"]

    if horizontal:
        fig = go.Figure(go.Bar(
            y=data.index,
            x=data.values,
            orientation="h",
            marker_color=colors,
            hovertemplate="<b>%{y}</b><br>%{x:,.0f}<extra></extra>",
        ))
        fig.update_layout(**_base_layout(
            height=height,
            title=dict(text=title, font=dict(size=13)),
            yaxis=dict(autorange="reversed", gridcolor=BRAND["grid"], tickfont=dict(size=10, color=BRAND["text_muted"])),
        ))
    else:
        fig = go.Figure(go.Bar(
            x=data.index,
            y=data.values,
            marker_color=colors,
            marker_line=dict(width=0),
            hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
        ))
        layout_opts = _base_layout(
            height=height,
            title=dict(text=title, font=dict(size=13)),
        )
        # Give x-axis labels room — auto-rotate long labels
        layout_opts["margin"]["b"] = 40
        layout_opts["xaxis"]["tickangle"] = -35 if len(data) > 8 else 0
        fig.update_layout(**layout_opts)
        if y_format:
            fig.update_yaxes(tickformat=y_format)

    return fig


def grouped_bar_chart(
    df: pd.DataFrame,
    title: str = "",
    height: int = 350,
) -> go.Figure:
    """Grouped bar chart from a DataFrame (index=categories, columns=groups)."""
    fig = go.Figure()
    for i, col in enumerate(df.columns):
        fig.add_trace(go.Bar(
            name=col,
            x=df.index,
            y=df[col],
            marker_color=SERIES_COLORS[i % len(SERIES_COLORS)],
            hovertemplate=f"<b>{col}</b><br>%{{x}}<br>%{{y:,.0f}}<extra></extra>",
        ))
    fig.update_layout(**_base_layout(
        height=height,
        title=dict(text=title, font=dict(size=13)),
        barmode="group",
    ))
    return fig


# ═══════════════════════════════════════════════════════════════════
# DONUT / PIE CHARTS
# ═══════════════════════════════════════════════════════════════════

def donut_chart(
    data: pd.Series,
    title: str = "",
    height: int = 300,
    colors: Optional[List[str]] = None,
    color_map: Optional[Dict[str, str]] = None,
) -> go.Figure:
    """Donut chart from a Series (index = labels, values = sizes)."""
    if color_map:
        clrs = [color_map.get(idx, BRAND["muted"]) for idx in data.index]
    else:
        clrs = colors or SERIES_COLORS[: len(data)]

    fig = go.Figure(go.Pie(
        labels=data.index,
        values=data.values,
        hole=0.55,
        marker=dict(colors=clrs, line=dict(color=BRAND["bg"], width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, color=BRAND["text"]),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        height=height,
        title=dict(text=title, font=dict(size=13)),
        showlegend=False,
        margin=dict(l=0, r=0, t=32, b=0),
    ))
    return fig


# ═══════════════════════════════════════════════════════════════════
# SPECIALTY CHARTS
# ═══════════════════════════════════════════════════════════════════

def waterfall_chart(
    categories: List[str],
    values: List[float],
    title: str = "",
    height: int = 320,
) -> go.Figure:
    """Waterfall chart for showing contributions."""
    fig = go.Figure(go.Waterfall(
        orientation="v",
        x=categories,
        y=values,
        increasing=dict(marker_color=BRAND["positive"]),
        decreasing=dict(marker_color=BRAND["negative"]),
        totals=dict(marker_color=BRAND["primary"]),
        connector=dict(line=dict(color=BRAND["muted"], width=1)),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**_base_layout(
        height=height,
        title=dict(text=title, font=dict(size=13)),
    ))
    return fig


def ramp_chart(
    df_combined: pd.DataFrame,
    title: str = "Ramp Tracker: Actual vs Target",
    height: int = 340,
) -> go.Figure:
    """Dual-line ramp tracker chart."""
    fig = go.Figure()

    if "Target Ramp" in df_combined.columns:
        fig.add_trace(go.Scatter(
            x=df_combined.index, y=df_combined["Target Ramp"],
            name="Target Ramp",
            mode="lines",
            line=dict(color=BRAND["muted"], width=2, dash="dash"),
            hovertemplate="<b>Target</b><br>%{x|%b %d}<br>$%{y:,.0f}<extra></extra>",
        ))

    if "Funded Exposure" in df_combined.columns:
        fig.add_trace(go.Scatter(
            x=df_combined.index, y=df_combined["Funded Exposure"],
            name="Actual",
            mode="lines+markers",
            line=dict(color=BRAND["primary"], width=2.5),
            marker=dict(size=4),
            fill="tozeroy",
            fillcolor=f"rgba(59,130,246,0.08)",
            hovertemplate="<b>Actual</b><br>%{x|%b %d}<br>$%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(**_base_layout(
        height=height,
        title=dict(text=title, font=dict(size=13)),
    ))
    return fig
