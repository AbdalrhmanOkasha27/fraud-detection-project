import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import dash
from dash import dcc, html, Input, Output
import dash_bootstrap_components as dbc


# ════════════════════════════════════════════════════════════════
#  SECTION 1 — COLOR SYSTEM
# ════════════════════════════════════════════════════════════════

SIDEBAR_BG   = "#0A0C12"
PAGE_BG      = "#0F1117"
CARD_BG      = "#161B27"
CARD_BORDER  = "#252D3D"
CARD_BORDER2 = "#2E3A4E"

C_CRIMSON    = "#C0392B"
C_CRIMSON_B  = "#E84040"
C_CRIMSON_D  = "#7D1F1F"

TIER_LOW      = "#2A6B4A"
TIER_MODERATE = "#7A5B1E"
TIER_HIGH     = "#8B3A1A"
TIER_CRITICAL = "#C0392B"
TIER_COLORS   = {"Low": TIER_LOW, "Moderate": TIER_MODERATE,
                 "High": TIER_HIGH, "Critical": TIER_CRITICAL}

C_REF       = "#4A6380"
C_SILVER    = "#8B98A8"
C_GRAPHITE  = "#3D4A5C"
C_MUTED     = "#5A6478"
C_STEEL     = "#4A6380"

KPI_CRIMSON = "#C0392B"
KPI_STEEL   = "#4A6380"
KPI_WINE    = "#8B2252"
KPI_AMBER   = "#7A5B1E"

GRID_COLOR  = "#1C2333"
AXIS_COLOR  = "#252D3D"
TICK_COLOR  = "#5A6478"
FONT_FMLY   = "Inter, 'SF Pro Display', 'Segoe UI', system-ui, sans-serif"

HEATMAP_CS = [
    [0.00, "#0F1117"], [0.20, "#1C1418"],
    [0.45, "#4A1515"], [0.70, "#8B2020"],
    [0.88, "#C0392B"], [1.00, "#FF4040"],
]

LOLLIPOP_STEM  = "#3D4A5C"
DUMBBELL_LEFT  = "#4A6380"
DUMBBELL_LINE  = "#2E3A4E"

SB_TEXT   = "#8B98A8"
SB_BRIGHT = "#C8D0DB"
SB_MUTED  = "#4A5568"
SB_HR     = "#1C2333"

WEIGHTS = {
    "high_drain": 2.0, "top_amount": 2.0, "highrisk_state": 1.5,
    "highrisk_device": 1.5, "time_risk": 1.5, "irreversible": 1.0,
}

DOW_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
SEG_ORDER = ["Late Night","Evening","Afternoon","Morning"]


# ════════════════════════════════════════════════════════════════
#  SECTION 2 — HELPERS
# ════════════════════════════════════════════════════════════════

def fmt_number(n):
    if n is None or (isinstance(n, float) and np.isnan(n)): return "N/A"
    n = float(n)
    if abs(n) >= 1_000_000: return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:     return f"{n/1_000:.1f}K"
    return f"{n:.2f}"

def fmt_inr(n):
    if n is None or (isinstance(n, float) and np.isnan(n)): return "N/A"
    n = float(n)
    if abs(n) >= 10_000_000: return f"₹{n/10_000_000:.2f} Cr"
    if abs(n) >= 100_000:    return f"₹{n/100_000:.2f} L"
    if abs(n) >= 1_000:      return f"₹{n/1_000:.1f}K"
    return f"₹{n:.0f}"

def fmt_pct(n): return f"{n:.2f}%" if n is not None else "N/A"

def risk_color(rate, avg):
    if rate >= avg * 1.35: return C_CRIMSON
    if rate >= avg:        return TIER_HIGH
    return TIER_LOW

def lift_color(lift):
    if lift >= 1.5:  return C_CRIMSON_B
    if lift >= 1.2:  return TIER_HIGH
    if lift >= 1.0:  return TIER_MODERATE
    return TIER_LOW

def apply_chart_style(fig, height=340):
    fig.update_layout(
        height=height, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        font=dict(family=FONT_FMLY, size=11.5, color=C_SILVER),
        margin=dict(l=14, r=18, t=48, b=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, font=dict(size=10.5, color=C_SILVER),
                    bgcolor="rgba(0,0,0,0)", bordercolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#0A0C12", font_size=12, font_color=SB_BRIGHT,
                        bordercolor=CARD_BORDER2, font_family=FONT_FMLY),
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1,
                     linecolor=AXIS_COLOR, linewidth=0.5, zeroline=False,
                     tickfont=dict(size=10.5, color=TICK_COLOR),
                     title_font=dict(size=11, color=C_MUTED))
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, gridwidth=1,
                     linecolor=AXIS_COLOR, linewidth=0.5, zeroline=False,
                     tickfont=dict(size=10.5, color=TICK_COLOR),
                     title_font=dict(size=11, color=C_MUTED))
    return fig

def chart_title(text, sub=None):
    t = dict(text=text, font=dict(size=13, color=SB_BRIGHT))
    if sub:
        t["subtitle"] = dict(text=sub, font=dict(size=10, color=C_MUTED))
    return t

def kpi_children(label, value, sub, value_color=SB_BRIGHT):
    return [
        html.P(label, style={"fontSize":"10px","color":SB_TEXT,"textTransform":"uppercase",
                              "letterSpacing":".1em","marginBottom":"8px","fontWeight":"500"}),
        html.H3(value, style={"fontSize":"28px","fontWeight":"300","color":value_color,
                               "margin":"0 0 6px 0","lineHeight":"1","letterSpacing":"-.02em",
                               "fontFamily":FONT_FMLY}),
        html.P(sub, style={"fontSize":"11px","color":SB_MUTED,"margin":"0"}),
    ]

def loading_graph(graph_id, **kw):
    return dcc.Loading(type="dot", color=C_CRIMSON, parent_style={"minHeight":"60px"},
                       children=[dcc.Graph(id=graph_id,
                                           config={"displayModeBar": False}, **kw)])

def ref_line(fig, val, label, axis="y"):
    if axis == "y":
        fig.add_hline(y=val, line_dash="dot", line_color=C_REF, line_width=1.3,
                       annotation_text=label, annotation_position="top right",
                       annotation_font=dict(size=9, color=C_REF))
    else:
        fig.add_vline(x=val, line_dash="dot", line_color=C_REF, line_width=1.3,
                       annotation_text=label, annotation_position="top",
                       annotation_font=dict(size=9, color=C_REF))


# ════════════════════════════════════════════════════════════════
#  SECTION 3 — STATISTICAL HELPERS
# ════════════════════════════════════════════════════════════════

def compute_lift(group_rate, overall_rate):
    """Lift = segment fraud rate / overall fraud rate."""
    return round(group_rate / overall_rate, 3) if overall_rate > 0 else 0

def chi_square_test(df, col):
    """Chi-square test between a categorical column and Is_Fraud."""
    try:
        ct = pd.crosstab(df[col], df["Is_Fraud"])
        chi2, p, dof, _ = stats.chi2_contingency(ct)
        sig = "✓ Significant" if p < 0.05 else "✗ Not significant"
        return chi2, p, sig
    except Exception:
        return None, None, "N/A"

def zscore_outliers(series):
    """Return mask of Z-score outliers (|z| > 3)."""
    z = np.abs(stats.zscore(series.dropna()))
    return z > 3

def fraud_rate_by_group(df, col):
    """Return DataFrame: group, count, fraud_count, fraud_rate, lift."""
    overall = df["Is_Fraud"].mean() * 100
    g = (df.groupby(col)["Is_Fraud"]
           .agg(["sum","count","mean"])
           .reset_index())
    g.columns = [col, "fraud_count", "total", "rate"]
    g["fraud_rate"] = (g["rate"] * 100).round(2)
    g["lift"] = (g["fraud_rate"] / overall).round(3)
    return g.sort_values("fraud_rate", ascending=False)


# ════════════════════════════════════════════════════════════════
#  SECTION 4 — DATA LOADING & FEATURE ENGINEERING
# ════════════════════════════════════════════════════════════════

def load_and_engineer(path="Bank_Transaction_Fraud_Detection.csv"):
    df = pd.read_csv(path)
    df = df.drop_duplicates()
    df.columns = df.columns.str.strip()
    df.drop(columns=["Customer_Name","Customer_Email","Customer_Contact",
                      "Transaction_Currency"], inplace=True, errors="ignore")

    df["Transaction_Date"] = pd.to_datetime(
        df["Transaction_Date"], errors="coerce", dayfirst=True)
    df["Hour"]   = pd.to_numeric(df["Transaction_Time"].str[:2], errors="coerce")
    df["Minute"] = pd.to_numeric(df["Transaction_Time"].str[3:5], errors="coerce")
    df["Age"]    = pd.to_numeric(df["Age"], errors="coerce")

    df = df[(df["Age"] >= 18) & (df["Age"] <= 90)].copy()
    df = df[(df["Transaction_Amount"] > 0) & (df["Account_Balance"] > 0)].copy()
    df["Is_Fraud"] = df["Is_Fraud"].astype(int)
    df["is_over_balance"] = (df["Transaction_Amount"] > df["Account_Balance"]).astype(int)

    def time_segment(h):
        if pd.isna(h):        return "Unknown"
        if h < 5 or h == 23:  return "Late Night"
        if h <= 11:           return "Morning"
        if h <= 16:           return "Afternoon"
        return "Evening"

    df["F2_time_segment"] = df["Hour"].apply(time_segment)
    df["F1_is_offhours"]  = df["Hour"].apply(
        lambda h: 1 if (not pd.isna(h) and (h < 6 or h > 22)) else 0)
    hour_risk = df.groupby("Hour")["Is_Fraud"].mean()
    df["F3_is_risky_hour"]  = df["Hour"].map(
        hour_risk > hour_risk.quantile(0.75)).fillna(0).astype(int)
    df["F_time_risk_score"] = 0.4*df["F1_is_offhours"] + 0.6*df["F3_is_risky_hour"]

    df["F4_balance_drain_ratio"] = df["Transaction_Amount"] / (df["Account_Balance"] + 1)
    df["F5_is_high_drain"] = (
        df["F4_balance_drain_ratio"] > df["F4_balance_drain_ratio"].quantile(0.90)).astype(int)
    df["F6_is_top_amount"] = (
        df["Transaction_Amount"] > df["Transaction_Amount"].quantile(0.90)).astype(int)

    state_risk  = df.groupby("State")["Is_Fraud"].mean()
    device_risk = df.groupby("Transaction_Device")["Is_Fraud"].mean()
    df["F7_is_highrisk_state"]  = df["State"].map(
        state_risk > state_risk.mean()).fillna(0).astype(int)
    df["F8_is_highrisk_device"] = df["Transaction_Device"].map(
        device_risk > device_risk.mean()).fillna(0).astype(int)
    df["F9_is_irreversible"] = df["Transaction_Type"].isin(
        ["Transfer","Bill Payment"]).astype(int)

    df["F12_risk_score"] = (
        WEIGHTS["high_drain"]       * df["F5_is_high_drain"]      +
        WEIGHTS["top_amount"]       * df["F6_is_top_amount"]      +
        WEIGHTS["highrisk_state"]   * df["F7_is_highrisk_state"]  +
        WEIGHTS["highrisk_device"]  * df["F8_is_highrisk_device"] +
        WEIGHTS["time_risk"]        * df["F_time_risk_score"]     +
        WEIGHTS["irreversible"]     * df["F9_is_irreversible"]
    )
    df["risk_tier"] = pd.cut(df["F12_risk_score"], bins=[-1,1,3,5,20],
                              labels=["Low","Moderate","High","Critical"])

    # ── Multi-dimensional combo features ─────────────────────────
    df["combo_offhours_highval"] = (
        (df["F1_is_offhours"] == 1) & (df["F6_is_top_amount"] == 1)).astype(int)
    df["combo_risky_device_irreversible"] = (
        (df["F8_is_highrisk_device"] == 1) & (df["F9_is_irreversible"] == 1)).astype(int)
    df["combo_risky_state_highval"] = (
        (df["F7_is_highrisk_state"] == 1) & (df["F6_is_top_amount"] == 1)).astype(int)
    df["combo_drain_offhours"] = (
        (df["F5_is_high_drain"] == 1) & (df["F1_is_offhours"] == 1)).astype(int)

    df["DayOfWeek"] = df["Transaction_Date"].dt.day_name()
    df["Age_Group"] = pd.cut(df["Age"], bins=[18,30,40,50,60,70],
                              labels=["18-30","31-40","41-50","51-60","61-70"])

    # Dynamic amount bins based on actual data distribution
    amt_p = [0, 20, 40, 60, 80, 100]
    amt_edges = [df["Transaction_Amount"].quantile(p/100) for p in amt_p]
    amt_edges[0] = 0
    amt_edges[-1] = df["Transaction_Amount"].max() + 1
    amt_labels = [f"Q{i+1}" for i in range(len(amt_edges)-1)]
    df["Amount_Bin"] = pd.cut(df["Transaction_Amount"],
                               bins=amt_edges, labels=amt_labels, duplicates="drop")
    # Also keep readable bins
    df["Amount_Bin_R"] = pd.cut(
        df["Transaction_Amount"],
        bins=[0,20000,40000,60000,80000, df["Transaction_Amount"].max()+1],
        labels=["0-20K","20-40K","40-60K","60-80K","80K+"])

    return df


try:
    DF_RAW = load_and_engineer("Bank_Transaction_Fraud_Detection.csv")
except FileNotFoundError:
    DF_RAW = pd.DataFrame()
    print("[ERROR] CSV not found.")

ALL_STATES   = sorted(DF_RAW["State"].dropna().unique()) if not DF_RAW.empty else []
ALL_GENDERS  = sorted(DF_RAW["Gender"].dropna().unique()) if not DF_RAW.empty else []
ALL_ACCTYPES = sorted(DF_RAW["Account_Type"].dropna().unique()) if not DF_RAW.empty else []
AMT_MIN      = float(DF_RAW["Transaction_Amount"].min()) if not DF_RAW.empty else 0
AMT_MAX      = float(DF_RAW["Transaction_Amount"].max()) if not DF_RAW.empty else 100000


# ════════════════════════════════════════════════════════════════
#  SECTION 5 — STYLES & LAYOUT COMPONENTS
# ════════════════════════════════════════════════════════════════

def kpi_style(accent):
    return {"backgroundColor": CARD_BG, "borderRadius": "8px",
            "padding": "16px 18px", "border": f"0.5px solid {CARD_BORDER}",
            "borderLeft": f"3px solid {accent}", "height": "100%",
            "boxShadow": "0 4px 24px rgba(0,0,0,0.4)"}

CARD_STYLE = {"backgroundColor": CARD_BG, "borderRadius": "8px",
              "padding": "16px", "border": f"0.5px solid {CARD_BORDER}",
              "marginBottom": "12px", "boxShadow": "0 4px 20px rgba(0,0,0,0.35)"}

TAB_ON  = {"backgroundColor": CARD_BG, "color": C_CRIMSON_B, "fontWeight": "400",
           "border": f"0.5px solid {CARD_BORDER}", "borderBottom": f"2px solid {C_CRIMSON}",
           "padding": "10px 20px", "borderRadius": "6px 6px 0 0", "fontSize": "12.5px",
           "letterSpacing": ".02em"}
TAB_OFF = {"backgroundColor": PAGE_BG, "color": C_MUTED, "fontWeight": "400",
           "border": f"0.5px solid {CARD_BORDER}", "borderBottom": "none",
           "padding": "10px 20px", "borderRadius": "6px 6px 0 0", "fontSize": "12.5px"}

EMPTY_FIG = go.Figure().update_layout(
    title="No data — adjust sidebar filters",
    plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
    font=dict(color=C_MUTED, family=FONT_FMLY),
    xaxis=dict(visible=False), yaxis=dict(visible=False))

def card(children, title=None):
    content = []
    if title:
        content.append(html.P(title, style={"fontSize":"10px","fontWeight":"500",
                                             "color":C_MUTED,"textTransform":"uppercase",
                                             "letterSpacing":".1em","marginBottom":"10px"}))
    content += children if isinstance(children, list) else [children]
    return html.Div(content, style=CARD_STYLE)

def sb_label(text):
    return html.P(text, style={"color":SB_MUTED,"fontSize":"10px","fontWeight":"500",
                                "letterSpacing":".1em","textTransform":"uppercase",
                                "marginBottom":"5px","marginTop":"16px"})

def stat_badge(text, color=C_MUTED):
    return html.Span(text, style={"fontSize":"9.5px","color":color,
                                   "backgroundColor":CARD_BORDER,
                                   "padding":"2px 7px","borderRadius":"4px",
                                   "marginLeft":"6px","letterSpacing":".04em"})


# ════════════════════════════════════════════════════════════════
#  SECTION 6 — SIDEBAR & APP
# ════════════════════════════════════════════════════════════════

sidebar = html.Div([
    html.Div([
        html.Div(style={"width":"6px","height":"6px","borderRadius":"50%",
                         "backgroundColor":C_CRIMSON,"marginRight":"8px",
                         "flexShrink":"0","marginTop":"2px",
                         "boxShadow":f"0 0 8px {C_CRIMSON}"}),
        html.Div([
            html.P("FRAUD INTEL", style={"color":SB_BRIGHT,"fontWeight":"500",
                                          "fontSize":"12px","margin":"0",
                                          "letterSpacing":".12em","fontFamily":FONT_FMLY}),
            html.P("Analytics Platform", style={"color":SB_MUTED,"fontSize":"10px",
                                                  "margin":"0","letterSpacing":".04em"}),
        ]),
    ], style={"display":"flex","alignItems":"flex-start","marginBottom":"4px"}),
    html.Hr(style={"borderColor":SB_HR,"margin":"18px 0 6px 0"}),

    sb_label("Account Type"),
    dcc.Checklist(id="f-acct",
                  options=[{"label":f"  {a}","value":a} for a in ALL_ACCTYPES],
                  value=ALL_ACCTYPES,
                  labelStyle={"display":"block","color":SB_TEXT,
                               "fontSize":"11.5px","marginBottom":"5px"},
                  inputStyle={"marginRight":"8px","accentColor":C_CRIMSON}),

    sb_label("Gender"),
    dcc.Checklist(id="f-gender",
                  options=[{"label":f"  {g}","value":g} for g in ALL_GENDERS],
                  value=ALL_GENDERS,
                  labelStyle={"display":"block","color":SB_TEXT,
                               "fontSize":"11.5px","marginBottom":"5px"},
                  inputStyle={"marginRight":"8px","accentColor":C_CRIMSON}),

    sb_label("State"),
    dcc.Dropdown(id="f-state",
                 options=[{"label":s,"value":s} for s in ALL_STATES],
                 value=ALL_STATES, multi=True, placeholder="All states",
                 style={"fontSize":"11.5px","color":"#CCC",
                        "backgroundColor":CARD_BG,"border":f"0.5px solid {CARD_BORDER}"}),

    sb_label("Amount Range"),
    dcc.RangeSlider(id="f-amt", min=AMT_MIN, max=AMT_MAX,
                    value=[AMT_MIN, AMT_MAX], allowCross=False,
                    marks={int(AMT_MIN):{"label":fmt_inr(AMT_MIN),
                                         "style":{"color":SB_MUTED,"fontSize":"9.5px"}},
                           int(AMT_MAX):{"label":fmt_inr(AMT_MAX),
                                         "style":{"color":SB_MUTED,"fontSize":"9.5px"}}},
                    tooltip={"placement":"bottom","always_visible":False}),
    html.Div(id="amt-lbl", style={"color":SB_MUTED,"fontSize":"10.5px","marginTop":"5px"}),

    html.Hr(style={"borderColor":SB_HR,"margin":"18px 0 10px 0"}),
    html.P("All metrics computed dynamically from filtered data.",
           style={"color":SB_MUTED,"fontSize":"10px","fontStyle":"italic","lineHeight":"1.6"}),
], style={"position":"fixed","top":0,"left":0,"bottom":0,"width":"244px",
           "padding":"22px 15px","backgroundColor":SIDEBAR_BG,
           "overflowY":"auto","zIndex":1000,"borderRight":f"0.5px solid {CARD_BORDER}"})


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP],
                suppress_callback_exceptions=True,
                title="Fraud Intelligence Dashboard")
server = app.server

app.layout = html.Div([
    sidebar,
    html.Div([
        dcc.Tabs(id="tabs", value="tab-1", children=[
            dcc.Tab(label="OVERVIEW",         value="tab-1",
                    style=TAB_OFF, selected_style=TAB_ON),
            dcc.Tab(label="TIME & BEHAVIOR",  value="tab-2",
                    style=TAB_OFF, selected_style=TAB_ON),
            dcc.Tab(label="GEOGRAPHY & RISK", value="tab-3",
                    style=TAB_OFF, selected_style=TAB_ON),
        ], colors={"border":"transparent","primary":C_CRIMSON,"background":PAGE_BG}),
        html.Div(id="tab-content", style={"paddingTop":"16px"}),
    ], style={"marginLeft":"254px","padding":"20px 24px",
               "backgroundColor":PAGE_BG,"minHeight":"100vh"}),
], style={"backgroundColor":PAGE_BG})


# ════════════════════════════════════════════════════════════════
#  SECTION 7 — FILTER HELPER
# ════════════════════════════════════════════════════════════════

def apply_filters(acct, gender, states, amt):
    df = DF_RAW.copy()
    if acct:   df = df[df["Account_Type"].isin(acct)]
    if gender: df = df[df["Gender"].isin(gender)]
    if states: df = df[df["State"].isin(states)]
    if amt:
        df = df[(df["Transaction_Amount"] >= amt[0]) &
                (df["Transaction_Amount"] <= amt[1])]
    return df


# ════════════════════════════════════════════════════════════════
#  SECTION 8 — TAB LAYOUTS
# ════════════════════════════════════════════════════════════════

def dash_title(main, sub):
    return html.Div([
        html.Div([
            html.Div(style={"width":"2px","height":"18px","backgroundColor":C_CRIMSON,
                             "marginRight":"10px","borderRadius":"1px","flexShrink":"0"}),
            html.Div([
                html.H4(main, style={"fontWeight":"300","fontSize":"17px","color":SB_BRIGHT,
                                      "margin":"0 0 1px 0","letterSpacing":"-.01em",
                                      "fontFamily":FONT_FMLY}),
                html.P(sub, style={"color":C_MUTED,"fontSize":"11.5px","margin":"0"}),
            ]),
        ], style={"display":"flex","alignItems":"center"}),
    ], style={"marginBottom":"20px"})

def kpi_col(kid, accent):
    return dbc.Col(html.Div(id=kid, style=kpi_style(accent)), width=3)

def layout_tab1():
    return html.Div([
        dash_title("Executive Overview",
                   "Fraud detection intelligence · Statistical depth · All figures computed dynamically"),
        dbc.Row([kpi_col("k1-total",KPI_STEEL),  kpi_col("k1-rate",KPI_CRIMSON),
                 kpi_col("k1-loss",KPI_CRIMSON),  kpi_col("k1-avg",KPI_AMBER)],
                className="g-3 mb-4"),
        html.Hr(style={"borderColor":CARD_BORDER,"margin":"2px 0 16px 0"}),
        dbc.Row([
            dbc.Col(card([loading_graph("g1-tier")]),   width=7),
            dbc.Col(card([loading_graph("g1-combo")]),  width=5),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(card([loading_graph("g1-cat")]),    width=4),
            dbc.Col(card([loading_graph("g1-type")]),   width=4),
            dbc.Col(card([loading_graph("g1-acc")]),    width=4),
        ], className="g-3"),
    ])

def layout_tab2():
    return html.Div([
        dash_title("Time & Behavioral Patterns",
                   "Temporal fraud signals · Amount distribution · Feature impact analysis"),
        dbc.Row([kpi_col("k2-hour",KPI_CRIMSON), kpi_col("k2-day",KPI_CRIMSON),
                 kpi_col("k2-seg",KPI_AMBER),    kpi_col("k2-topamt",KPI_AMBER)],
                className="g-3 mb-4"),
        html.Hr(style={"borderColor":CARD_BORDER,"margin":"2px 0 16px 0"}),
        card([
            html.P("FRAUD RATE HEATMAP — HOUR × DAY OF WEEK",
                   style={"fontSize":"10px","color":C_MUTED,"marginBottom":"6px",
                          "fontWeight":"500","letterSpacing":".1em"}),
            loading_graph("g2-heatmap"),
        ]),
        dbc.Row([
            dbc.Col(card([loading_graph("g2-dow")]),    width=6),
            dbc.Col(card([loading_graph("g2-seg")]),    width=6),
        ], className="g-3 mb-3"),
        dbc.Row([
            dbc.Col(card([loading_graph("g2-amtdist")]),width=6),
            dbc.Col(card([loading_graph("g2-lift")]),   width=6),
        ], className="g-3"),
    ])

def layout_tab3():
    return html.Div([
        dash_title("Geographic & Demographic Risk",
                   "State risk ranking · Device channels · Chi-square validation · Demographic segmentation"),
        dbc.Row([kpi_col("k3-state",KPI_CRIMSON), kpi_col("k3-device",KPI_CRIMSON),
                 kpi_col("k3-group",KPI_WINE),    kpi_col("k3-age",KPI_STEEL)],
                className="g-3 mb-4"),
        html.Hr(style={"borderColor":CARD_BORDER,"margin":"2px 0 16px 0"}),
        card([
            dbc.Row([
                dbc.Col([
                    html.P("STATES TO SHOW", style={"fontSize":"10px","color":C_MUTED,
                                                     "fontWeight":"500","letterSpacing":".1em",
                                                     "marginBottom":"6px"}),
                    dcc.Slider(id="sl-nstates", min=5, max=20, step=1, value=10,
                               marks={5:"5",10:"10",15:"15",20:"20"},
                               tooltip={"placement":"bottom","always_visible":False}),
                ], width=5),
                dbc.Col([
                    html.P("DEVICES TO SHOW", style={"fontSize":"10px","color":C_MUTED,
                                                      "fontWeight":"500","letterSpacing":".1em",
                                                      "marginBottom":"6px"}),
                    dcc.Slider(id="sl-ndevs", min=5, max=15, step=1, value=10,
                               marks={5:"5",10:"10",15:"15"},
                               tooltip={"placement":"bottom","always_visible":False}),
                ], width=5),
            ]),
        ]),
        dbc.Row([
            dbc.Col(card([loading_graph("g3-states")]),  width=6),
            dbc.Col(card([loading_graph("g3-devices")]), width=6),
        ], className="g-3 mb-3"),
        card([loading_graph("g3-cross")]),
        dbc.Row([
            dbc.Col(card([loading_graph("g3-gen")]),  width=5),
            dbc.Col(card([loading_graph("g3-age")]),  width=7),
        ], className="g-3"),
        html.P(id="footer", style={"color":SB_MUTED,"fontSize":"10.5px",
                                    "fontStyle":"italic","textAlign":"right",
                                    "marginTop":"14px","letterSpacing":".02em"}),
    ])


# ════════════════════════════════════════════════════════════════
#  SECTION 9 — CALLBACKS
# ════════════════════════════════════════════════════════════════

@app.callback(Output("amt-lbl","children"), Input("f-amt","value"))
def cb_amt(r): return f"{fmt_inr(r[0])} — {fmt_inr(r[1])}" if r else ""

@app.callback(Output("tab-content","children"), Input("tabs","value"))
def cb_tab(t):
    if t == "tab-1": return layout_tab1()
    if t == "tab-2": return layout_tab2()
    return layout_tab3()


# ── Dashboard 1 — Executive Overview ─────────────────────────────
@app.callback(
    [Output("k1-total","children"), Output("k1-rate","children"),
     Output("k1-loss","children"),  Output("k1-avg","children"),
     Output("g1-tier","figure"),    Output("g1-combo","figure"),
     Output("g1-cat","figure"),     Output("g1-type","figure"),
     Output("g1-acc","figure")],
    [Input("f-acct","value"), Input("f-gender","value"),
     Input("f-state","value"), Input("f-amt","value")],
)
def cb1(acct, gender, states, amt):
    df = apply_filters(acct, gender, states, amt)
    if df.empty:
        e = [html.P("—", style={"color":C_MUTED})]
        return e,e,e,e, EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG

    total    = len(df)
    fraud_n  = int(df["Is_Fraud"].sum())
    legit_n  = total - fraud_n
    avg_rate = df["Is_Fraud"].mean() * 100
    loss     = df[df["Is_Fraud"]==1]["Transaction_Amount"].sum()
    af       = df[df["Is_Fraud"]==1]["Transaction_Amount"].mean()
    al       = df[df["Is_Fraud"]==0]["Transaction_Amount"].mean()
    direction= "larger" if af >= al else "smaller"
    diff     = abs((af/al - 1)*100) if al else 0

    # ── Z-score on fraud rate vs expected ────────────────────────
    p0      = DF_RAW["Is_Fraud"].mean()    # overall baseline
    se      = np.sqrt(p0*(1-p0)/total) if total > 0 else 1
    z_score = (df["Is_Fraud"].mean() - p0) / se if se > 0 else 0
    z_sig   = f"Z={z_score:+.2f}" + (" ✓" if abs(z_score) > 1.96 else "")

    k1 = kpi_children("Total Transactions", fmt_number(total),
                       f"{fmt_number(legit_n)} legitimate · {fmt_number(fraud_n)} fraudulent")
    k2 = kpi_children("Fraud Rate", f"{avg_rate:.2f}%",
                       f"{fmt_number(fraud_n)} cases · {z_sig} vs baseline", C_CRIMSON_B)
    k3 = kpi_children("Total Fraud Losses", fmt_inr(loss),
                       f"Avg {fmt_inr(af)} per fraudulent transaction", C_CRIMSON_B)
    k4 = kpi_children("Avg Legitimate Txn", fmt_inr(al),
                       f"Fraud txns are {diff:.1f}% {direction} than legit avg", "#A08060")

    # ── Risk tier lollipop — with lift annotation ─────────────────
    tier_df = (df.groupby("risk_tier", observed=True)["Is_Fraud"]
                 .agg(["sum","count","mean"]).reset_index())
    tier_df.columns = ["Tier","Fraud","Total","Rate"]
    tier_df["Rate%"]    = (tier_df["Rate"]*100).round(2)
    tier_df["Capture%"] = (tier_df["Fraud"]/fraud_n*100).round(1) if fraud_n else 0
    tier_df["Lift"]     = (tier_df["Rate%"] / avg_rate).round(2)
    tier_df["dot_color"]= tier_df["Tier"].map(TIER_COLORS)

    fig_tier = go.Figure()
    for _, row in tier_df.iterrows():
        fig_tier.add_shape(type="line",
                            x0=row["Tier"], x1=row["Tier"], y0=0, y1=row["Rate%"],
                            line=dict(color=LOLLIPOP_STEM, width=1.5))
    fig_tier.add_trace(go.Scatter(
        x=tier_df["Tier"], y=tier_df["Rate%"], mode="markers+text",
        marker=dict(color=tier_df["dot_color"], size=18, line=dict(color=CARD_BG, width=2)),
        text=[f"{r:.1f}%" for r in tier_df["Rate%"]],
        textposition="top center", textfont=dict(size=10.5, color=SB_BRIGHT),
        hovertemplate=(
            "<b>%{x}</b><br>Fraud rate: %{customdata[0]:.2f}%<br>"
            "Lift vs avg: %{customdata[1]:.2f}×<br>"
            "Fraud capture: %{customdata[2]:.0f}%<extra></extra>"),
        customdata=tier_df[["Rate%","Lift","Capture%"]].values,
        showlegend=False))
    fig_tier.add_trace(go.Scatter(
        x=tier_df["Tier"], y=[0.1]*len(tier_df), mode="text",
        text=[f"Lift {l:.2f}× · {c:.0f}% of fraud" for l,c in
              zip(tier_df["Lift"], tier_df["Capture%"])],
        textfont=dict(size=9.5, color=C_MUTED),
        showlegend=False, hoverinfo="skip"))
    ref_line(fig_tier, avg_rate, f"Overall avg {avg_rate:.2f}%")
    fig_tier.update_layout(
        title=chart_title("Risk Score Tier Analysis",
                           "Lift = tier fraud rate ÷ overall fraud rate. Higher = more predictive."),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[0, tier_df["Rate%"].max()*1.55 if not tier_df.empty else 15]),
        showlegend=False)
    apply_chart_style(fig_tier, 330)

    # ── Multi-dimensional combo analysis — grouped bars ───────────
    combos = {
        "Off-hours\n+ High Value":    "combo_offhours_highval",
        "Risky Device\n+ Irreversible": "combo_risky_device_irreversible",
        "Risky State\n+ High Value":  "combo_risky_state_highval",
        "High Drain\n+ Off-hours":    "combo_drain_offhours",
    }
    combo_rows = []
    for label, col in combos.items():
        if col in df.columns and df[col].sum() > 0:
            rate = df[df[col]==1]["Is_Fraud"].mean() * 100
            cnt  = int(df[col].sum())
            lift = rate / avg_rate
            combo_rows.append({"Label": label, "Rate": round(rate,2),
                                "Count": cnt, "Lift": round(lift,2)})
    cb_df = pd.DataFrame(combo_rows).sort_values("Rate", ascending=True)

    fig_combo = go.Figure()
    if not cb_df.empty:
        c_colors = [lift_color(l) for l in cb_df["Lift"]]
        fig_combo.add_trace(go.Bar(
            x=cb_df["Rate"], y=cb_df["Label"],
            orientation="h",
            marker=dict(color=c_colors, line=dict(width=0)),
            text=[f"{r:.2f}%  ·  {l:.2f}× lift  (n={c:,})"
                  for r,l,c in zip(cb_df["Rate"],cb_df["Lift"],cb_df["Count"])],
            textposition="outside", textfont=dict(size=10, color=C_SILVER),
            hovertemplate="<b>%{y}</b><br>Fraud rate: %{x:.2f}%<br>Lift: %{customdata:.2f}×<extra></extra>",
            customdata=cb_df["Lift"].values, width=0.55,
        ))
        ref_line(fig_combo, avg_rate, f"Baseline {avg_rate:.2f}%", axis="x")
    fig_combo.update_layout(
        title=chart_title("Multi-Dimensional Fraud Combinations",
                           "Intersection of two risk signals. Bars above baseline = genuine risk amplification."),
        xaxis_title="Fraud Rate (%)",
        xaxis=dict(range=[0, cb_df["Rate"].max()*1.32] if not cb_df.empty else [0,10]),
        showlegend=False)
    apply_chart_style(fig_combo, 300)
    fig_combo.update_layout(margin=dict(l=14, r=155, t=52, b=14))

    # ── Category — fraud rate + chi-square significance ───────────
    cat_df = fraud_rate_by_group(df, "Merchant_Category").sort_values("fraud_rate", ascending=True)
    chi2_c, p_c, sig_c = chi_square_test(df, "Merchant_Category")
    p_label_c = f"χ²={chi2_c:.1f}, p={p_c:.3f} — {sig_c}" if chi2_c else ""

    fig_cat = go.Figure(go.Bar(
        x=cat_df["fraud_rate"], y=cat_df["Merchant_Category"],
        orientation="h",
        marker=dict(color=[risk_color(r, avg_rate) for r in cat_df["fraud_rate"]],
                    line=dict(width=0)),
        text=[f"{r:.2f}%  ·  {l:.2f}× lift"
              for r,l in zip(cat_df["fraud_rate"], cat_df["lift"])],
        textposition="outside", textfont=dict(size=10.5, color=C_SILVER),
        hovertemplate="<b>%{y}</b><br>Fraud rate: %{x:.2f}%<br>Lift: %{customdata:.2f}×<extra></extra>",
        customdata=cat_df["lift"].values, width=0.65,
    ))
    ref_line(fig_cat, avg_rate, f"Avg {avg_rate:.2f}%", axis="x")
    fig_cat.update_layout(
        title=chart_title("Fraud Rate by Merchant Category",
                           p_label_c if p_label_c else "Which categories are most exploited?"),
        xaxis_title="Fraud Rate (%)",
        xaxis=dict(range=[0, cat_df["fraud_rate"].max()*1.32]),
        yaxis=dict(automargin=True), showlegend=False)
    apply_chart_style(fig_cat, 300)
    fig_cat.update_layout(margin=dict(l=14, r=140, t=52, b=14))

    # ── Transaction type — fraud rate + lift ──────────────────────
    type_df = fraud_rate_by_group(df, "Transaction_Type").sort_values("fraud_rate", ascending=False)
    chi2_t, p_t, sig_t = chi_square_test(df, "Transaction_Type")

    fig_type = go.Figure(go.Bar(
        x=type_df["Transaction_Type"], y=type_df["fraud_rate"],
        marker=dict(color=[risk_color(r, avg_rate) for r in type_df["fraud_rate"]],
                    line=dict(width=0)),
        text=[f"{r:.2f}%<br>{l:.2f}×"
              for r,l in zip(type_df["fraud_rate"], type_df["lift"])],
        textposition="outside", textfont=dict(size=10, color=C_SILVER),
        hovertemplate="<b>%{x}</b><br>Fraud rate: %{y:.2f}%<br>Lift: %{customdata:.2f}×<extra></extra>",
        customdata=type_df["lift"].values, width=0.50,
    ))
    ref_line(fig_type, avg_rate, f"Avg {avg_rate:.2f}%")
    fig_type.update_layout(
        title=chart_title("Fraud by Transaction Type",
                           f"χ²={chi2_t:.1f}, p={p_t:.3f} — {sig_t}" if chi2_t else "Irreversible types carry highest risk"),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[0, type_df["fraud_rate"].max()*1.40]),
        xaxis=dict(tickangle=-20), showlegend=False)
    apply_chart_style(fig_type, 300)

    # ── Account type — fraud rate + chi-square ────────────────────
    acc_df = fraud_rate_by_group(df, "Account_Type").sort_values("fraud_rate", ascending=False)
    chi2_a, p_a, sig_a = chi_square_test(df, "Account_Type")

    fig_acc = go.Figure(go.Bar(
        x=acc_df["Account_Type"], y=acc_df["fraud_rate"],
        marker=dict(color=[risk_color(r, avg_rate) for r in acc_df["fraud_rate"]],
                    line=dict(width=0)),
        text=[f"{r:.2f}%<br>{l:.2f}×"
              for r,l in zip(acc_df["fraud_rate"], acc_df["lift"])],
        textposition="outside", textfont=dict(size=10.5, color=C_SILVER),
        hovertemplate="<b>%{x}</b><br>Fraud rate: %{y:.2f}%<br>Lift: %{customdata:.2f}×<extra></extra>",
        customdata=acc_df["lift"].values, width=0.46,
    ))
    ref_line(fig_acc, avg_rate, f"Avg {avg_rate:.2f}%")
    fig_acc.update_layout(
        title=chart_title("Fraud by Account Type",
                           f"χ²={chi2_a:.1f}, p={p_a:.3f} — {sig_a}" if chi2_a else ""),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[0, acc_df["fraud_rate"].max()*1.38]),
        showlegend=False)
    apply_chart_style(fig_acc, 300)

    return k1,k2,k3,k4, fig_tier,fig_combo,fig_cat,fig_type,fig_acc


# ── Dashboard 2 — Time & Behavior ────────────────────────────────
@app.callback(
    [Output("k2-hour","children"),     Output("k2-day","children"),
     Output("k2-seg","children"),      Output("k2-topamt","children"),
     Output("g2-heatmap","figure"),    Output("g2-dow","figure"),
     Output("g2-seg","figure"),        Output("g2-amtdist","figure"),
     Output("g2-lift","figure")],
    [Input("f-acct","value"), Input("f-gender","value"),
     Input("f-state","value"), Input("f-amt","value")],
)
def cb2(acct, gender, states, amt):
    df = apply_filters(acct, gender, states, amt)
    if df.empty:
        e = [html.P("—", style={"color":C_MUTED})]
        return e,e,e,e, EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG

    avg_rate = df["Is_Fraud"].mean() * 100
    hr_r = df.groupby("Hour")["Is_Fraud"].mean() * 100
    ph   = hr_r.idxmax() if not hr_r.empty else "N/A"
    phr  = hr_r.max()    if not hr_r.empty else 0
    dw_r = df.groupby("DayOfWeek")["Is_Fraud"].mean() * 100
    pd_  = dw_r.idxmax() if not dw_r.empty else "N/A"
    pdr  = dw_r.max()    if not dw_r.empty else 0
    sg_r = df.groupby("F2_time_segment")["Is_Fraud"].mean() * 100
    ws   = sg_r.idxmax() if not sg_r.empty else "N/A"
    bs   = sg_r.idxmin() if not sg_r.empty else "N/A"

    # High-value threshold dynamic
    p90_thresh = df["Transaction_Amount"].quantile(0.90)
    tar  = (df[df["F6_is_top_amount"]==1]["Is_Fraud"].mean()*100
            if "F6_is_top_amount" in df.columns and df["F6_is_top_amount"].sum()>0 else 0)
    tar_lift = tar / avg_rate if avg_rate > 0 else 0

    k1 = kpi_children("Peak Risk Hour",
                       f"{int(ph):02d}:00" if ph!="N/A" else "N/A",
                       f"{phr:.2f}% fraud rate — {phr/avg_rate:.2f}× the average", C_CRIMSON_B)
    k2 = kpi_children("Riskiest Day",
                       str(pd_)[:3], f"{pdr:.2f}% fraud rate on this day", C_CRIMSON_B)
    k3 = kpi_children("Riskiest Time Segment", str(ws),
                       f"{sg_r.get(ws,0):.2f}% vs {sg_r.get(bs,0):.2f}% safest ({bs})", "#A08060")
    k4 = kpi_children("Top-10% Amount Fraud Rate", fmt_pct(tar),
                       f"Above {fmt_inr(p90_thresh)} · {tar_lift:.2f}× lift vs baseline", "#A08060")

    # ── Heatmap ───────────────────────────────────────────────────
    hm  = df.groupby(["DayOfWeek","Hour"])["Is_Fraud"].mean().reset_index()
    hm["rate"] = (hm["Is_Fraud"]*100).round(2)
    hmp = hm.pivot(index="DayOfWeek", columns="Hour", values="rate")
    vd  = [d for d in DOW_ORDER if d in hmp.index]
    hmp = hmp.reindex(vd).reindex(columns=list(range(24)), fill_value=None)
    zv  = hmp.values
    zmax = min(float(np.nanmax(zv[~np.isnan(zv)]))*1.05, 15) if not np.all(np.isnan(zv)) else 10
    ot   = [[f"{v:.1f}%" if (not np.isnan(v) and v >= avg_rate*1.35) else ""
              for v in row] for row in zv]

    fig_hm = go.Figure(go.Heatmap(
        z=zv, x=[f"{h:02d}h" for h in range(24)], y=vd,
        colorscale=HEATMAP_CS, text=ot, texttemplate="%{text}",
        textfont=dict(size=8, color="#FFCCCC"),
        hovertemplate="<b>%{y} at %{x}</b><br>Fraud rate: %{z:.2f}%<extra></extra>",
        colorbar=dict(title=dict(text="Fraud %", side="right",
                                  font=dict(size=10, color=C_MUTED)),
                      thickness=12, len=0.9,
                      tickfont=dict(size=9, color=TICK_COLOR),
                      bgcolor="rgba(0,0,0,0)",
                      bordercolor=CARD_BORDER, borderwidth=0.5),
        xgap=2, ygap=2, zmin=0, zmax=zmax))
    fig_hm.update_layout(
        height=300, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=12, r=60, t=14, b=30),
        font=dict(family=FONT_FMLY, color=C_SILVER),
        xaxis=dict(title="Hour of Day (0 = midnight)",
                   tickfont=dict(size=9, color=TICK_COLOR),
                   title_font=dict(size=10, color=C_MUTED)),
        yaxis=dict(tickfont=dict(size=10, color=TICK_COLOR)),
        hoverlabel=dict(bgcolor="#0A0C12", font_color=SB_BRIGHT,
                        font_size=11, font_family=FONT_FMLY, bordercolor=CARD_BORDER2))

    # ── Day of week — smooth line ─────────────────────────────────
    vdow = [d for d in DOW_ORDER if d in dw_r.index]
    dv   = dw_r.reindex(vdow).values

    fig_dow = go.Figure()
    fig_dow.add_trace(go.Scatter(
        x=[d[:3] for d in vdow], y=dv, mode="lines+markers",
        line=dict(color=C_CRIMSON, width=2.5, shape="spline", smoothing=0.8),
        marker=dict(size=10, color=dv,
                    colorscale=[[0,TIER_LOW],[0.5,TIER_HIGH],[1,C_CRIMSON_B]],
                    cmin=min(dv) if len(dv) else 0, cmax=max(dv) if len(dv) else 10,
                    line=dict(color=CARD_BG, width=2)),
        text=[f"{r:.2f}%" for r in dv],
        textposition="top center", textfont=dict(size=9.5, color=C_SILVER),
        hovertemplate="<b>%{x}</b><br>Fraud rate: %{y:.2f}%<extra></extra>",
        fill="tozeroy", fillcolor="rgba(192,57,43,0.07)", showlegend=False))
    ref_line(fig_dow, avg_rate, f"Avg {avg_rate:.2f}%")
    fig_dow.update_layout(
        title=chart_title("Fraud Rate by Day of Week",
                           "Weekend spike reflects reduced fraud monitoring coverage."),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[max(0, min(dv)*0.6) if len(dv) else 0,
                          max(dv)*1.35 if len(dv) else 10]),
        showlegend=False)
    apply_chart_style(fig_dow, 310)

    # ── Time segment — polished bars + lift labels ────────────────
    sg = (df.groupby("F2_time_segment")["Is_Fraud"]
            .agg(["sum","count","mean"]).reset_index())
    sg.columns = ["Seg","Fraud","Total","Rate"]
    sg["Rate%"] = (sg["Rate"]*100).round(2)
    sg["Lift"]  = (sg["Rate%"] / avg_rate).round(2)
    sg = sg.set_index("Seg").reindex(
        [s for s in SEG_ORDER if s in sg.index]).reset_index()

    def seg_color(r, avg):
        if r >= avg*1.3:  return C_CRIMSON_B
        if r >= avg:      return "#8B3A1A"
        if r >= avg*0.9:  return TIER_MODERATE
        return "#2A4A3A"

    sc = [seg_color(r, avg_rate) for r in sg["Rate%"]]

    fig_seg = go.Figure(go.Bar(
        x=sg["Seg"], y=sg["Rate%"],
        marker=dict(color=sc, line=dict(width=0)),
        text=[f"{r:.2f}%  ·  {l:.2f}× lift"
              for r,l in zip(sg["Rate%"], sg["Lift"])],
        textposition="outside", textfont=dict(size=10.5, color=C_SILVER),
        hovertemplate=(
            "<b>%{x}</b><br>Fraud rate: %{y:.2f}%<br>"
            "Lift vs avg: %{customdata[0]:.2f}×<br>"
            "Fraud cases: %{customdata[1]}<extra></extra>"),
        customdata=sg[["Lift","Fraud"]].values, width=0.55))
    ref_line(fig_seg, avg_rate, f"Overall avg {avg_rate:.2f}%")
    fig_seg.update_layout(
        title=chart_title("Fraud Rate by Time of Day",
                           "Late Night (11 PM–4 AM) carries highest lift — automated bot attacks."),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[0, sg["Rate%"].max()*1.42 if not sg.empty else 10]),
        xaxis=dict(categoryorder="array", categoryarray=SEG_ORDER),
        showlegend=False)
    apply_chart_style(fig_seg, 310)

    # ── Amount distribution — fraud vs legit overlay histogram ────
    fraud_amts = df[df["Is_Fraud"]==1]["Transaction_Amount"]
    legit_amts = df[df["Is_Fraud"]==0]["Transaction_Amount"]
    bin_max    = df["Transaction_Amount"].quantile(0.99)   # clip at 99th pct

    fig_amtdist = go.Figure()
    fig_amtdist.add_trace(go.Histogram(
        x=legit_amts.clip(upper=bin_max), name="Legitimate",
        nbinsx=40, histnorm="probability density",
        marker=dict(color=C_STEEL, opacity=0.55, line=dict(width=0)),
        hovertemplate="Amount: %{x:,.0f}<br>Density: %{y:.4f}<extra>Legitimate</extra>"))
    fig_amtdist.add_trace(go.Histogram(
        x=fraud_amts.clip(upper=bin_max), name="Fraudulent",
        nbinsx=40, histnorm="probability density",
        marker=dict(color=C_CRIMSON_B, opacity=0.65, line=dict(width=0)),
        hovertemplate="Amount: %{x:,.0f}<br>Density: %{y:.4f}<extra>Fraudulent</extra>"))

    # Median lines
    med_fraud = fraud_amts.median()
    med_legit = legit_amts.median()
    fig_amtdist.add_vline(x=med_fraud, line_dash="dot", line_color=C_CRIMSON_B,
                           line_width=1.3,
                           annotation_text=f"Fraud median {fmt_inr(med_fraud)}",
                           annotation_font=dict(size=9, color=C_CRIMSON_B))
    fig_amtdist.add_vline(x=med_legit, line_dash="dot", line_color=C_STEEL,
                           line_width=1.3,
                           annotation_text=f"Legit median {fmt_inr(med_legit)}",
                           annotation_font=dict(size=9, color=C_STEEL),
                           annotation_position="top left")

    # Mann-Whitney U test
    try:
        u_stat, p_mw = stats.mannwhitneyu(fraud_amts.dropna(), legit_amts.dropna(),
                                           alternative="two-sided")
        mw_label = f"Mann-Whitney p={p_mw:.3f} — {'significant' if p_mw<0.05 else 'not significant'}"
    except Exception:
        mw_label = "Amount distributions"

    fig_amtdist.update_layout(
        barmode="overlay",
        title=chart_title("Transaction Amount Distribution",
                           mw_label),
        xaxis_title="Transaction Amount (INR)",
        yaxis_title="Density",
        legend=dict(font=dict(size=10.5, color=C_SILVER), bgcolor="rgba(0,0,0,0)"))
    apply_chart_style(fig_amtdist, 310)

    # ── Feature lift — dumbbell plot ─────────────────────────────
    fm = {"F6 Top Amount":       "F6_is_top_amount",
          "F7 High-Risk State":  "F7_is_highrisk_state",
          "F5 High Drain":       "F5_is_high_drain",
          "F8 High-Risk Device": "F8_is_highrisk_device",
          "F1 Off-Hours":        "F1_is_offhours",
          "F9 Irreversible":     "F9_is_irreversible",
          "combo: Off-hrs+HighVal":  "combo_offhours_highval",
          "combo: Dev+Irreversible": "combo_risky_device_irreversible"}
    rows = []
    for name, col in fm.items():
        if col in df.columns and df[col].sum() > 0:
            r = df[df[col]==1]["Is_Fraud"].mean() * 100
            rows.append({"Feature":name,"Rate":round(r,2),
                          "Lift":round(r/avg_rate,2)})
    ld = pd.DataFrame(rows).sort_values("Lift", ascending=True) if rows else pd.DataFrame()

    if not ld.empty:
        fig_lift = go.Figure()
        for _, row in ld.iterrows():
            fig_lift.add_shape(type="line",
                                x0=1.0, x1=row["Lift"],
                                y0=row["Feature"], y1=row["Feature"],
                                line=dict(color=DUMBBELL_LINE, width=1.5))
        fig_lift.add_trace(go.Scatter(
            x=[1.0]*len(ld), y=ld["Feature"], mode="markers",
            marker=dict(color=DUMBBELL_LEFT, size=10,
                        line=dict(color=CARD_BG, width=1.5)),
            name="Baseline 1.0×",
            hovertemplate="<b>%{y}</b><br>Baseline: 1.0×<extra></extra>"))
        fig_lift.add_trace(go.Scatter(
            x=ld["Lift"], y=ld["Feature"], mode="markers+text",
            marker=dict(color=[lift_color(l) for l in ld["Lift"]],
                        size=13, line=dict(color=CARD_BG, width=2)),
            text=[f"{l:.2f}×" for l in ld["Lift"]],
            textposition="middle right", textfont=dict(size=10, color=C_SILVER),
            name="Feature lift",
            hovertemplate="<b>%{y}</b><br>Lift: %{x:.2f}×<br>Fraud rate: %{customdata:.2f}%<extra></extra>",
            customdata=ld["Rate"].values))
        ref_line(fig_lift, 1.0, "baseline", axis="x")
        fig_lift.update_layout(
            title=chart_title("Feature Lift — Dumbbell Plot",
                               "Right dot = fraud rate when flagged ÷ overall rate. Combo features appear at bottom."),
            xaxis_title="Lift (×)",
            xaxis=dict(range=[0.80, ld["Lift"].max()*1.22]),
            showlegend=True,
            legend=dict(font=dict(size=10, color=C_SILVER), bgcolor="rgba(0,0,0,0)"))
        apply_chart_style(fig_lift, 340)
    else:
        fig_lift = EMPTY_FIG

    return k1,k2,k3,k4, fig_hm,fig_dow,fig_seg,fig_amtdist,fig_lift


# ── Dashboard 3 — Geography & Demographics ───────────────────────
@app.callback(
    [Output("k3-state","children"),  Output("k3-device","children"),
     Output("k3-group","children"),  Output("k3-age","children"),
     Output("g3-states","figure"),   Output("g3-devices","figure"),
     Output("g3-cross","figure"),    Output("g3-gen","figure"),
     Output("g3-age","figure")],
    [Input("f-acct","value"), Input("f-gender","value"),
     Input("f-state","value"), Input("f-amt","value"),
     Input("sl-nstates","value"), Input("sl-ndevs","value")],
)
def cb3(acct, gender, states, amt, ns, nd):
    df = apply_filters(acct, gender, states, amt)
    if df.empty:
        e = [html.P("—", style={"color":C_MUTED})]
        return e,e,e,e, EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG,EMPTY_FIG

    avg_rate = df["Is_Fraud"].mean() * 100
    sr   = df.groupby("State")["Is_Fraud"].mean() * 100
    dr   = df.groupby("Transaction_Device")["Is_Fraud"].mean() * 100
    ga   = df.groupby(["Gender","Account_Type"])["Is_Fraud"].mean() * 100
    ar   = df.groupby("Age_Group", observed=True)["Is_Fraud"].mean() * 100

    rs = sr.idxmax() if not sr.empty else "N/A"
    rd = dr.idxmax() if not dr.empty else "N/A"
    rc = ga.idxmax() if not ga.empty else ("N/A","N/A")
    sa = ar.idxmin() if not ar.empty else "N/A"

    rs_lift = sr.get(rs,0)/avg_rate if avg_rate > 0 else 0

    k1 = kpi_children("Highest-Risk State", str(rs)[:14],
                       f"{sr.get(rs,0):.2f}% · {rs_lift:.2f}× the overall average", C_CRIMSON_B)
    k2 = kpi_children("Riskiest Channel", str(rd)[:14],
                       f"{dr.get(rd,0):.2f}% fraud rate on this device", C_CRIMSON_B)
    k3 = kpi_children("Riskiest Demographic",
                       f"{str(rc[0])[:1]}·{str(rc[1])[:3]}" if isinstance(rc,tuple) else "N/A",
                       f"{rc[0]} × {rc[1]}: {ga.get(rc,0):.2f}%" if isinstance(rc,tuple) else "",
                       "#C06080")
    k4 = kpi_children("Safest Age Group", str(sa),
                       f"Lowest exposure at {ar.get(sa,0):.2f}% fraud rate", C_REF)

    # ── States — horizontal bar + lift ───────────────────────────
    st_df = (df.groupby("State")["Is_Fraud"]
               .agg(["sum","count","mean"]).reset_index()
               .sort_values("mean", ascending=False).head(ns)
               .sort_values("mean", ascending=True))
    st_df["rate"] = (st_df["mean"]*100).round(2)
    st_df["lift"] = (st_df["rate"] / avg_rate).round(2)
    st_df["color"] = st_df["rate"].apply(
        lambda r: "#FF4040" if r>=avg_rate*1.7
                  else C_CRIMSON_B if r>=avg_rate*1.3
                  else TIER_HIGH if r>=avg_rate else TIER_LOW)

    fig_st = go.Figure(go.Bar(
        x=st_df["rate"], y=st_df["State"],
        orientation="h",
        marker=dict(color=st_df["color"], line=dict(width=0)),
        text=[f"{r:.2f}%  ·  {l:.2f}× lift  ({c} fraud)"
              for r,l,c in zip(st_df["rate"],st_df["lift"],st_df["sum"])],
        textposition="outside", textfont=dict(size=10, color=C_SILVER),
        hovertemplate=(
            "<b>%{y}</b><br>Fraud rate: %{x:.2f}%<br>"
            "Lift: %{customdata[0]:.2f}×<br>"
            "Fraud cases: %{customdata[1]}<extra></extra>"),
        customdata=st_df[["lift","sum"]].values, width=0.65))
    ref_line(fig_st, avg_rate, f"National avg {avg_rate:.2f}%", axis="x")
    fig_st.update_layout(
        title=chart_title(f"Top {ns} Highest-Risk States",
                           "States where fraud rate significantly exceeds the national average."),
        xaxis_title="Fraud Rate (%)",
        xaxis=dict(range=[0, st_df["rate"].max()*1.32]),
        yaxis=dict(automargin=True), showlegend=False)
    apply_chart_style(fig_st, min(max(340, ns*36), 520))
    fig_st.update_layout(margin=dict(l=14, r=165, t=52, b=14))

    # ── Devices — horizontal bars + lift ─────────────────────────
    dv_df = (df.groupby("Transaction_Device")["Is_Fraud"]
               .agg(["sum","count","mean"]).reset_index()
               .sort_values("mean", ascending=False).head(nd)
               .sort_values("mean", ascending=True))
    dv_df["rate"] = (dv_df["mean"]*100).round(2)
    dv_df["lift"] = (dv_df["rate"] / avg_rate).round(2)
    dv_df["color"] = dv_df["rate"].apply(lambda r: risk_color(r, avg_rate))

    fig_dv = go.Figure(go.Bar(
        x=dv_df["rate"], y=dv_df["Transaction_Device"],
        orientation="h",
        marker=dict(color=dv_df["color"], line=dict(width=0)),
        text=[f"{r:.2f}%  ·  {l:.2f}× lift"
              for r,l in zip(dv_df["rate"], dv_df["lift"])],
        textposition="outside", textfont=dict(size=10, color=C_SILVER),
        hovertemplate="<b>%{y}</b><br>%{x:.2f}%<br>Lift: %{customdata:.2f}×<extra></extra>",
        customdata=dv_df["lift"].values, width=0.62))
    ref_line(fig_dv, avg_rate, f"Avg {avg_rate:.2f}%", axis="x")
    chi2_d, p_d, sig_d = chi_square_test(df, "Transaction_Device")
    fig_dv.update_layout(
        title=chart_title(f"Top {nd} Highest-Risk Channels",
                           f"χ²={chi2_d:.1f}, p={p_d:.3f} — {sig_d}" if chi2_d else "QR & mobile most exploited"),
        xaxis_title="Fraud Rate (%)",
        xaxis=dict(range=[0, dv_df["rate"].max()*1.30]),
        yaxis=dict(automargin=True), showlegend=False)
    apply_chart_style(fig_dv, min(max(340, nd*36), 520))
    fig_dv.update_layout(margin=dict(l=14, r=135, t=52, b=14))

    # ── Cross heatmap — merchant × txn type ──────────────────────
    cross = df.pivot_table(index="Merchant_Category", columns="Transaction_Type",
                            values="Is_Fraud", aggfunc="mean") * 100
    cross_lift = cross / avg_rate
    zmax_c = float(cross.values[~np.isnan(cross.values)].max())*1.05 if cross.size else 10

    text_cross = [[f"{v:.1f}%\n{(v/avg_rate):.2f}×" for v in row]
                  for row in cross.values]

    fig_cross = go.Figure(go.Heatmap(
        z=cross.values, x=cross.columns.tolist(), y=cross.index.tolist(),
        colorscale=HEATMAP_CS,
        text=text_cross, texttemplate="%{text}",
        textfont=dict(size=10, color="#FFCCCC"),
        hovertemplate="<b>%{y} × %{x}</b><br>Fraud rate: %{z:.2f}%<extra></extra>",
        colorbar=dict(title=dict(text="Fraud %", side="right",
                                  font=dict(size=10, color=C_MUTED)),
                      thickness=12, len=0.9,
                      tickfont=dict(size=9, color=TICK_COLOR),
                      bgcolor="rgba(0,0,0,0)",
                      bordercolor=CARD_BORDER, borderwidth=0.5),
        xgap=3, ygap=3, zmin=0, zmax=zmax_c))
    fig_cross.update_layout(
        title=chart_title("Fraud Rate — Merchant × Transaction Type",
                           "Each cell shows fraud rate % and lift (×). Darker = higher risk."),
        height=345, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=14, r=60, t=52, b=40),
        font=dict(family=FONT_FMLY, size=11.5, color=C_SILVER),
        xaxis=dict(title="Transaction Type",
                   tickfont=dict(size=11, color=TICK_COLOR),
                   title_font=dict(size=11, color=C_MUTED)),
        yaxis=dict(tickfont=dict(size=11, color=TICK_COLOR)),
        hoverlabel=dict(bgcolor="#0A0C12", font_color=SB_BRIGHT,
                        font_size=11, font_family=FONT_FMLY, bordercolor=CARD_BORDER2))

    # ── Gender × Account — heatmap + lift ────────────────────────
    gp = ga.unstack(fill_value=0).round(2)
    gp_lift = (gp / avg_rate).round(2)
    text_gen = [[f"{v:.2f}%\n{(v/avg_rate):.2f}×" for v in row] for row in gp.values]

    fig_gen = go.Figure(go.Heatmap(
        z=gp.values, x=gp.columns.tolist(), y=gp.index.tolist(),
        colorscale=HEATMAP_CS,
        text=text_gen, texttemplate="%{text}",
        textfont=dict(size=13, color="#FFCCCC"),
        hovertemplate="<b>%{y} × %{x}</b><br>%{z:.2f}%<extra></extra>",
        colorbar=dict(title=dict(text="Fraud %", side="right",
                                  font=dict(size=10, color=C_MUTED)),
                      thickness=12, tickfont=dict(size=9, color=TICK_COLOR),
                      bgcolor="rgba(0,0,0,0)"),
        xgap=4, ygap=4))
    fig_gen.update_layout(
        title=chart_title("Fraud Rate — Gender × Account Type",
                           "Each cell shows fraud % and lift. Identifies highest-risk demographic combinations."),
        height=295, plot_bgcolor=CARD_BG, paper_bgcolor=CARD_BG,
        margin=dict(l=14, r=60, t=52, b=22),
        font=dict(family=FONT_FMLY, size=11.5, color=C_SILVER),
        xaxis=dict(title="Account Type",
                   tickfont=dict(size=11, color=TICK_COLOR),
                   title_font=dict(size=11, color=C_MUTED)),
        yaxis=dict(tickfont=dict(size=11, color=TICK_COLOR)),
        hoverlabel=dict(bgcolor="#0A0C12", font_color=SB_BRIGHT,
                        font_size=11, font_family=FONT_FMLY, bordercolor=CARD_BORDER2))

    # ── Age group — dot trend + lift annotations ──────────────────
    ag_df = (df.groupby("Age_Group", observed=True)["Is_Fraud"]
               .agg(["sum","count","mean"]).reset_index())
    ag_df.columns = ["AgeG","Fraud","Total","Rate"]
    ag_df["Rate%"] = (ag_df["Rate"]*100).round(2)
    ag_df["Lift"]  = (ag_df["Rate%"] / avg_rate).round(2)
    agc = [risk_color(r, avg_rate) for r in ag_df["Rate%"]]

    # Kruskal-Wallis test across age groups
    groups = [df[df["Age_Group"]==g]["Is_Fraud"].values
               for g in ag_df["AgeG"] if len(df[df["Age_Group"]==g]) > 0]
    try:
        kw_stat, kw_p = stats.kruskal(*groups) if len(groups) >= 2 else (None, None)
        kw_label = f"Kruskal-Wallis p={kw_p:.3f} — {'significant' if kw_p<0.05 else 'not significant'}" if kw_p else ""
    except Exception:
        kw_label = ""

    fig_age = go.Figure()
    fig_age.add_trace(go.Scatter(
        x=ag_df["AgeG"], y=ag_df["Rate%"],
        fill="tozeroy", fillcolor="rgba(192,57,43,0.07)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, hoverinfo="skip"))
    fig_age.add_trace(go.Scatter(
        x=ag_df["AgeG"], y=ag_df["Rate%"], mode="lines",
        line=dict(color=C_GRAPHITE, width=1.5, shape="spline",
                  smoothing=0.7, dash="dot"),
        showlegend=False, hoverinfo="skip"))
    fig_age.add_trace(go.Scatter(
        x=ag_df["AgeG"], y=ag_df["Rate%"], mode="markers+text",
        marker=dict(color=agc, size=14, line=dict(color=CARD_BG, width=2)),
        text=[f"{r:.2f}%<br>{l:.2f}×" for r,l in zip(ag_df["Rate%"], ag_df["Lift"])],
        textposition="top center", textfont=dict(size=9.5, color=C_SILVER),
        hovertemplate="<b>%{x}</b><br>%{y:.2f}%  (%{customdata[0]} cases) · Lift %{customdata[1]:.2f}×<extra></extra>",
        customdata=ag_df[["Fraud","Lift"]].values, showlegend=False))
    ref_line(fig_age, avg_rate, f"Avg {avg_rate:.2f}%")
    fig_age.update_layout(
        title=chart_title("Fraud Rate by Age Group",
                           kw_label if kw_label else "31–40 typically most targeted — higher balances, more transactions."),
        yaxis_title="Fraud Rate (%)",
        yaxis=dict(range=[ag_df["Rate%"].min()*0.75 if not ag_df.empty else 0,
                          ag_df["Rate%"].max()*1.45 if not ag_df.empty else 10]),
        showlegend=False)
    apply_chart_style(fig_age, 295)

    return k1,k2,k3,k4, fig_st,fig_dv,fig_cross,fig_gen,fig_age


@app.callback(
    Output("footer","children"),
    [Input("f-acct","value"), Input("f-gender","value"),
     Input("f-state","value"), Input("f-amt","value")],
)
def cb_footer(acct, gender, states, amt):
    df = apply_filters(acct, gender, states, amt)
    fr = df["Is_Fraud"].mean()*100 if not df.empty else 0
    return (f"All metrics computed dynamically  ·  "
            f"{fmt_number(len(df))} transactions in view  ·  "
            f"Fraud rate: {fr:.2f}%")


# ════════════════════════════════════════════════════════════════
#  SECTION 10 — RUN
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)