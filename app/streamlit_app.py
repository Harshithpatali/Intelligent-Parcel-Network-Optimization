import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import folium
import streamlit.components.v1 as components

# ──────────────────────────────────────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────────────────────────────────────
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "")
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}

st.set_page_config(
    page_title="Parcel Network Control Tower",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
#  THEME TOKENS
# ──────────────────────────────────────────────────────────────────────────────
FX_PURPLE = "#4D148C"
FX_PURPLE_2 = "#6F2DBD"
FX_PURPLE_3 = "#8B5CF6"
FX_ORANGE = "#FF6600"
FX_ORANGE_2 = "#FF8A45"
INK = "#12141F"
MUTED = "#6B7280"
LINE = "#E6E7EE"
SURFACE = "#FFFFFF"
PLOT_BG = "rgba(255,255,255,0.85)"
GRID = "#EDEEF4"
FONT = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
PALETTE = [FX_PURPLE, FX_ORANGE, "#6B2BA8", "#D95700", "#7E57C2", "#E87500", "#3F0D73", "#C44D00"]


# ──────────────────────────────────────────────────────────────────────────────
#  GLOBAL CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root{{
  --fx-purple:{FX_PURPLE};
  --fx-purple-2:{FX_PURPLE_2};
  --fx-orange:{FX_ORANGE};
  --ink:{INK};
  --muted:{MUTED};
  --surface:{SURFACE};
  --surface-2:#F7F8FC;
  --line:{LINE};
  --success:#0E9F6E;
  --warning:#D97706;
  --danger:#DC2626;
}}

html, body, [class*="css"], .stApp {{ font-family:{FONT}; }}

.stApp{{
  background:
    radial-gradient(circle at 6% -4%, rgba(77,20,140,.10), transparent 30%),
    radial-gradient(circle at 98% 2%, rgba(255,102,0,.08), transparent 26%),
    linear-gradient(180deg,#F6F7FB 0%,#F2F3F9 100%);
  color:{INK};
}}
.block-container{{ max-width:1560px; padding:1.4rem 2.25rem 3.5rem; }}
header[data-testid="stHeader"]{{ background:transparent; height:0; }}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"]{{
  background:linear-gradient(180deg,#16182A 0%,#211442 100%);
  border-right:1px solid rgba(255,255,255,.07);
}}
section[data-testid="stSidebar"] *{{ color:#F3F1FA !important; }}

/* ── Hero shell ──────────────────────────────────────────────────────── */
.fx-shell{{
  background:
    radial-gradient(circle at 88% 8%, rgba(255,102,0,.20), transparent 42%),
    linear-gradient(118deg,#12141F 0%,#241041 52%,#4D148C 100%);
  border:1px solid rgba(255,255,255,.10);
  border-radius:24px;
  padding:34px 38px 30px;
  color:#fff;
  box-shadow:0 22px 60px rgba(18,20,31,.24);
  position:relative;
  overflow:hidden;
}}
.fx-shell::after{{
  content:"";position:absolute;right:-110px;top:-140px;width:380px;height:380px;
  border:74px solid rgba(255,102,0,.13);border-radius:50%;pointer-events:none;
}}
.fx-shell::before{{
  content:"";position:absolute;left:-60px;bottom:-120px;width:240px;height:240px;
  border:52px solid rgba(255,255,255,.05);border-radius:50%;pointer-events:none;
}}
.fx-kicker{{
  font-size:.70rem;letter-spacing:.18em;text-transform:uppercase;
  font-weight:800;color:#FFB58C;margin-bottom:10px;
  display:flex;align-items:center;gap:8px;
}}
.fx-shell h1{{
  margin:0;font-size:2.45rem;line-height:1.06;letter-spacing:-.045em;
  font-weight:900;color:#fff;max-width:960px;
}}
.fx-shell p{{
  margin:13px 0 0;color:rgba(255,255,255,.78);
  font-size:.97rem;line-height:1.55;max-width:820px;
}}
.fx-status{{
  display:inline-flex;align-items:center;gap:9px;margin-top:20px;
  padding:8px 14px;border-radius:999px;background:rgba(255,255,255,.10);
  border:1px solid rgba(255,255,255,.16);font-size:.76rem;font-weight:700;
  color:#fff;backdrop-filter:blur(6px);
}}
.fx-dot{{
  width:8px;height:8px;border-radius:50%;background:#28D17C;
  box-shadow:0 0 0 4px rgba(40,209,124,.18);
  animation:fxpulse 2.2s ease-in-out infinite;
}}
@keyframes fxpulse{{
  0%,100%{{ box-shadow:0 0 0 4px rgba(40,209,124,.18); }}
  50%{{ box-shadow:0 0 0 8px rgba(40,209,124,.06); }}
}}
.fx-accent-line{{
  height:4px;border-radius:99px;margin:16px 0 22px;
  background:linear-gradient(90deg,{FX_ORANGE} 0%,{FX_ORANGE_2} 28%,{FX_PURPLE_2} 68%,{FX_PURPLE} 100%);
}}

/* ── Section headers ─────────────────────────────────────────────────── */
.fx-section{{ margin:26px 0 14px; }}
.fx-section-title{{
  font-size:1.06rem;font-weight:800;color:{INK};
  letter-spacing:-.02em;display:flex;align-items:center;gap:9px;
}}
.fx-section-title::before{{
  content:"";width:4px;height:18px;border-radius:99px;
  background:linear-gradient(180deg,{FX_ORANGE},{FX_PURPLE});
  display:inline-block;
}}
.fx-section-sub{{ font-size:.79rem;color:{MUTED};margin-top:5px;margin-left:13px; }}

/* ── KPI cards ───────────────────────────────────────────────────────── */
.fx-card{{
  background:{SURFACE};border:1px solid {LINE};border-radius:16px;
  padding:18px 19px;box-shadow:0 8px 26px rgba(18,20,31,.055);
  position:relative;overflow:hidden;height:100%;
  transition:transform .18s ease, box-shadow .18s ease;
}}
.fx-card:hover{{ transform:translateY(-2px); box-shadow:0 14px 34px rgba(77,20,140,.13); }}
.fx-card::after{{
  content:"";position:absolute;left:0;top:0;bottom:0;width:4px;
  background:linear-gradient(180deg,{FX_ORANGE},{FX_PURPLE});
}}
.fx-card-label{{
  font-size:.70rem;color:{MUTED};font-weight:800;
  text-transform:uppercase;letter-spacing:.09em;
  white-space:normal;word-break:break-word;
}}
.fx-card-value{{
  font-size:1.85rem;color:{FX_PURPLE};font-weight:900;
  letter-spacing:-.045em;margin-top:6px;line-height:1.15;
  white-space:normal;word-break:break-word;
}}
.fx-card-meta{{
  font-size:.73rem;color:#8A90A0;margin-top:4px;font-weight:500;
  white-space:normal;word-break:break-word;
}}

/* ── Note / callout ──────────────────────────────────────────────────── */
.fx-note{{
  background:linear-gradient(90deg,#F5F0FB 0%,#FFF7F2 100%);
  border:1px solid #E9DEF3;border-left:4px solid {FX_ORANGE};
  padding:13px 16px;border-radius:11px;color:#43485A;
  font-size:.86rem;line-height:1.55;
}}
.fx-note b{{ color:{FX_PURPLE}; }}

/* ── Tabs ────────────────────────────────────────────────────────────── */
div[data-testid="stTabs"] > div:first-child{{
  gap:6px;border-bottom:1px solid {LINE};flex-wrap:wrap;
}}
div[data-testid="stTabs"] button{{
  border:0 !important;border-radius:11px 11px 0 0 !important;
  color:#707687 !important;font-weight:700 !important;
  padding:12px 17px !important;background:transparent !important;
  font-size:.88rem !important;white-space:nowrap !important;
  transition:all .15s ease !important;
}}
div[data-testid="stTabs"] button:hover{{
  color:{FX_PURPLE} !important;background:#F1EDF7 !important;
}}
div[data-testid="stTabs"] button[aria-selected="true"]{{
  color:{FX_PURPLE} !important;background:#EDE7F6 !important;
  box-shadow:inset 0 -3px 0 {FX_ORANGE} !important;
}}

/* ── Buttons ─────────────────────────────────────────────────────────── */
div.stButton > button{{
  border-radius:11px !important;font-weight:750 !important;
  min-height:44px !important;font-size:.88rem !important;
  transition:all .16s ease !important;white-space:normal !important;
  word-break:break-word !important;line-height:1.3 !important;
}}
div.stButton > button[kind="primary"]{{
  background:linear-gradient(100deg,{FX_PURPLE} 0%,{FX_PURPLE_2} 100%) !important;
  border:1px solid {FX_PURPLE} !important;color:#fff !important;
  box-shadow:0 8px 22px rgba(77,20,140,.24) !important;
}}
div.stButton > button[kind="primary"]:hover{{
  background:linear-gradient(100deg,{FX_ORANGE} 0%,#E94F00 100%) !important;
  border-color:{FX_ORANGE} !important;transform:translateY(-1px);
  box-shadow:0 10px 26px rgba(255,102,0,.28) !important;
}}
div.stButton > button[kind="secondary"]{{
  background:#fff !important;border:1px solid {LINE} !important;color:{INK} !important;
}}
div.stButton > button[kind="secondary"]:hover{{
  border-color:{FX_PURPLE} !important;color:{FX_PURPLE} !important;
}}

/* ── Metrics ─────────────────────────────────────────────────────────── */
div[data-testid="stMetric"]{{
  background:#fff;border:1px solid {LINE};border-radius:14px;
  padding:14px 16px;box-shadow:0 6px 20px rgba(18,20,31,.05);
  overflow:visible;
}}
[data-testid="stMetricLabel"]{{
  font-size:.71rem !important;text-transform:uppercase;letter-spacing:.07em;
  font-weight:800 !important;color:#747B8D !important;
  white-space:normal !important;word-break:break-word !important;
}}
[data-testid="stMetricValue"]{{
  color:{FX_PURPLE} !important;font-weight:900 !important;
  letter-spacing:-.04em;white-space:normal !important;word-break:break-word !important;
}}
[data-testid="stMetricDelta"]{{ font-weight:700 !important; }}

/* ── Tables / inputs / expanders ─────────────────────────────────────── */
[data-testid="stDataFrame"]{{
  border:1px solid {LINE};border-radius:13px;overflow:hidden;
  box-shadow:0 6px 20px rgba(18,20,31,.045);
}}
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div{{
  border-radius:10px !important;border-color:#DADCE5 !important;
}}
div[data-testid="stExpander"]{{
  border:1px solid {LINE};border-radius:13px;background:#fff;
  box-shadow:0 4px 16px rgba(18,20,31,.04);overflow:hidden;
}}
div[data-testid="stExpander"] summary{{ font-weight:700;color:{FX_PURPLE}; }}
hr{{ border-color:{LINE} !important; }}

/* ── Misc ────────────────────────────────────────────────────────────── */
.small-muted{{ font-size:.75rem;color:{MUTED}; }}
.stAlert{{ border-radius:12px; }}
h2, h3, h4 {{ color:{INK}; letter-spacing:-.02em; }}
.stSlider label, .stSelectbox label, .stNumberInput label, .stCheckbox label{{
  font-weight:700 !important;color:#3C4050 !important;font-size:.83rem !important;
  white-space:normal !important;word-break:break-word !important;
}}
.stCaption, [data-testid="stCaptionContainer"]{{
  color:{MUTED} !important;font-size:.78rem !important;line-height:1.5 !important;
}}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
#  PLOTLY THEME HELPER  — guarantees nothing is clipped
# ──────────────────────────────────────────────────────────────────────────────
def style_fig(fig, height=430, title=None, showlegend=False):
    fig.update_layout(
        height=height,
        margin=dict(l=70, r=50, t=80 if (title or fig.layout.title.text) else 40, b=70),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PLOT_BG,
        font=dict(family=FONT, size=13, color="#2A2D3A"),
        title=dict(
            text=title or fig.layout.title.text,
            font=dict(size=16, color=INK, family=FONT),
            x=0.01, xanchor="left", y=0.97, yanchor="top",
        ),
        hoverlabel=dict(
            bgcolor="#FFFFFF", bordercolor=LINE,
            font=dict(family=FONT, size=13, color=INK),
        ),
        legend=dict(
            bgcolor="rgba(255,255,255,.92)", bordercolor=LINE, borderwidth=1,
            font=dict(size=12, family=FONT), orientation="h",
            yanchor="bottom", y=1.02, xanchor="left", x=0,
        ),
        showlegend=showlegend,
        separators=".,",
    )
    fig.update_xaxes(
        automargin=True, gridcolor=GRID, zeroline=False,
        title_font=dict(size=12.5, color="#565B6E"), tickfont=dict(size=11.5),
        linecolor=LINE, showline=True, ticks="outside", tickcolor=LINE,
    )
    fig.update_yaxes(
        automargin=True, gridcolor=GRID, zeroline=False,
        title_font=dict(size=12.5, color="#565B6E"), tickfont=dict(size=11.5),
        linecolor=LINE, showline=True, ticks="outside", tickcolor=LINE,
    )
    return fig


def empty_fig(message, height=300):
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=14, color=MUTED, family=FONT),
        align="center",
    )
    fig.update_layout(
        height=height, margin=dict(l=40, r=40, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=PLOT_BG,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def section(title, sub=""):
    st.markdown(
        f'<div class="fx-section"><div class="fx-section-title">{title}</div>'
        f'<div class="fx-section-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def kpi_row(cards):
    cols = st.columns(len(cards))
    for col, (label, value, meta) in zip(cols, cards):
        col.markdown(
            f'<div class="fx-card">'
            f'<div class="fx-card-label">{label}</div>'
            f'<div class="fx-card-value">{value}</div>'
            f'<div class="fx-card-meta">{meta}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
#  HERO
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="fx-shell">
  <div class="fx-kicker">Parcel Intelligence Platform · Network Operations</div>
  <h1>Intelligent Parcel Network<br>Control Tower</h1>
  <p>Predictive demand · capacity-aware optimization · disruption resilience · multi-stop consolidation</p>
  <div class="fx-status"><span class="fx-dot"></span> Network analytics online · decision layer ready</div>
</div>
<div class="fx-accent-line"></div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
#  API HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def get(path, timeout=15):
    return requests.get(f"{API_URL}{path}", headers=HEADERS, timeout=timeout)


def post(path, payload, timeout=60):
    return requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS, timeout=timeout)


try:
    summary = get("/summary").json()
    network = get("/network").json()
except Exception as e:
    st.error(f"API unavailable: {e}")
    st.stop()

prod = summary.get("production_mode", False)
if prod:
    st.success(
        f"Production analytics connected · forecast {summary.get('forecast_date')} · "
        f"model {summary.get('model_version')}"
    )
else:
    st.warning(
        "Demo mode. Set ENVIRONMENT=production and configure the Supabase service-role key on the API backend."
    )


# ──────────────────────────────────────────────────────────────────────────────
#  HUB DATA NORMALIZATION
# ──────────────────────────────────────────────────────────────────────────────
hubs = pd.DataFrame(network.get("hubs", [])).copy()

_hub_aliases = {
    "latitude": "lat",
    "longitude": "lon",
    "lng": "lon",
    "capacity": "capacity_parcels",
    "handling_capacity_parcels": "handling_capacity",
}
for _src, _dst in _hub_aliases.items():
    if _src in hubs.columns and _dst not in hubs.columns:
        hubs[_dst] = hubs[_src]

for _col, _default in {
    "hub_id": "UNKNOWN",
    "city": "Unknown",
    "lat": float("nan"),
    "lon": float("nan"),
    "capacity_parcels": 0.0,
    "handling_capacity": 0.0,
}.items():
    if _col not in hubs.columns:
        hubs[_col] = _default

hubs["hub_id"] = hubs["hub_id"].astype(str)
hubs["city"] = hubs["city"].astype(str)
hubs["lat"] = pd.to_numeric(hubs["lat"], errors="coerce")
hubs["lon"] = pd.to_numeric(hubs["lon"], errors="coerce")
hubs["capacity_parcels"] = pd.to_numeric(hubs["capacity_parcels"], errors="coerce").fillna(0)
hubs["handling_capacity"] = pd.to_numeric(hubs["handling_capacity"], errors="coerce").fillna(0)


# ──────────────────────────────────────────────────────────────────────────────
#  COMMAND SUMMARY
# ──────────────────────────────────────────────────────────────────────────────
section("Network command summary", "Current model coverage and operational topology")
kpi_row([
    ("Candidate hubs", f"{summary.get('hubs', 0):,}", "network nodes"),
    ("OD demand", f"{summary.get('demand_rows', 0):,}", "origin–destination rows"),
    ("Road routes", f"{network.get('routes', 0):,}", "road-network links"),
    ("Operating mode", "PRODUCTION" if prod else "DEMO", "data connection"),
])

st.write("")

t1, t2, t3, t4, t5, t6 = st.tabs([
    "⌂  Network", "◈  Optimization", "◌  Resilience",
    "⌁  Root Cause", "✦  Interventions", "◉  Routing",
])


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 1 — NETWORK
# ──────────────────────────────────────────────────────────────────────────────
with t1:
    section("Network overview", "Capacity footprint, geographic spread and fleet assumptions")
    st.markdown(
        '<div class="fx-note">The operational route map is intentionally kept on the final '
        '<b>Routing</b> page. This view focuses on network structure, capacity and fleet assumptions.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if not hubs.empty:
        left, right = st.columns([1.55, 1], gap="large")

        with left:
            network_plot = hubs.loc[hubs["lat"].notna() & hubs["lon"].notna()].copy()

            if not network_plot.empty:
                network_plot["capacity_parcels"] = pd.to_numeric(
                    network_plot["capacity_parcels"], errors="coerce"
                ).fillna(0).clip(lower=1)

                try:
                    _plot_lon = "lon" if "lon" in network_plot.columns else "lng"
                    if _plot_lon not in network_plot.columns:
                        raise ValueError("No longitude column found in hub data")

                    fig = px.scatter(
                        network_plot,
                        x=_plot_lon,
                        y="lat",
                        size="capacity_parcels",
                        text="hub_id",
                        hover_name="city",
                        color="capacity_parcels",
                        color_continuous_scale=[[0, "#B9A6DC"], [0.5, FX_PURPLE_2], [1, FX_PURPLE]],
                        custom_data=["capacity_parcels", "handling_capacity"],
                    )
                    fig.update_traces(
                        marker=dict(line=dict(width=1.6, color=FX_ORANGE), opacity=0.9),
                        textposition="top center",
                        textfont=dict(size=10.5, color=INK, family=FONT),
                        cliponaxis=False,
                        hovertemplate=(
                            "<b>%{hovertext}</b><br>"
                            "Hub: %{text}<br>"
                            "Longitude: %{x:.4f}<br>"
                            "Latitude: %{y:.4f}<br>"
                            "Capacity: %{customdata[0]:,.0f} parcels<br>"
                            "Handling: %{customdata[1]:,.0f}"
                            "<extra></extra>"
                        ),
                    )
                    fig.update_layout(coloraxis_showscale=False)
                    fig.update_xaxes(title_text="Longitude")
                    fig.update_yaxes(title_text="Latitude")
                    st.plotly_chart(
                        style_fig(fig, height=440, title="Candidate hub capacity footprint"),
                        width="stretch",
                    )
                except (ValueError, TypeError, KeyError) as exc:
                    st.warning(
                        "The production hub coordinates could not be plotted. "
                        "The underlying network data is still available below."
                    )
                    st.caption(f"Chart validation: {type(exc).__name__}")
            else:
                st.info(
                    "No valid hub coordinates are available for the overview chart. "
                    "The operational map remains available on the Routing page."
                )

            # Top hubs by capacity — always visible, always labelled
            if not hubs.empty and hubs["capacity_parcels"].sum() > 0:
                top = (
                    hubs.sort_values("capacity_parcels", ascending=False)
                    .head(12)
                    .sort_values("capacity_parcels")
                )
                fig_bar = px.bar(
                    top,
                    x="capacity_parcels",
                    y="hub_id",
                    orientation="h",
                    text="capacity_parcels",
                    color="capacity_parcels",
                    color_continuous_scale=[[0, "#C4B0E2"], [1, FX_PURPLE]],
                    hover_data={"city": True, "handling_capacity": ":,.0f"},
                )
                fig_bar.update_traces(
                    texttemplate="%{text:,.0f}",
                    textposition="outside",
                    textfont=dict(size=11, color=INK, family=FONT),
                    cliponaxis=False,
                    marker_line_width=0,
                )
                fig_bar.update_layout(coloraxis_showscale=False, bargap=0.35)
                fig_bar.update_xaxes(title_text="Parcels")
                fig_bar.update_yaxes(title_text="")
                st.plotly_chart(
                    style_fig(fig_bar, height=390, title="Top hubs by parcel capacity"),
                    width="stretch",
                )

        with right:
            fleet_df = pd.DataFrame(network.get("fleet", []))
            if not fleet_df.empty:
                st.markdown("#### 🚚 Fleet profile")
                st.dataframe(fleet_df, width="stretch", hide_index=True)

                if "vehicle_type" in fleet_df.columns and "parcel_capacity" in fleet_df.columns:
                    fdf = fleet_df.copy()
                    fdf["parcel_capacity"] = pd.to_numeric(fdf["parcel_capacity"], errors="coerce").fillna(0)
                    fig_fleet = px.bar(
                        fdf,
                        x="vehicle_type",
                        y="parcel_capacity",
                        text="parcel_capacity",
                        color="parcel_capacity",
                        color_continuous_scale=[[0, "#FFD1B0"], [1, FX_ORANGE]],
                    )
                    fig_fleet.update_traces(
                        texttemplate="%{text:,.0f}",
                        textposition="outside",
                        textfont=dict(size=11, color=INK, family=FONT),
                        cliponaxis=False,
                        marker_line_width=0,
                    )
                    fig_fleet.update_layout(coloraxis_showscale=False, bargap=0.4)
                    fig_fleet.update_xaxes(title_text="")
                    fig_fleet.update_yaxes(title_text="Parcels")
                    st.plotly_chart(
                        style_fig(fig_fleet, height=300, title="Fleet parcel capacity"),
                        width="stretch",
                    )

            st.markdown("#### 📍 Candidate hubs")
            st.dataframe(
                hubs[["hub_id", "city", "capacity_parcels", "handling_capacity"]],
                width="stretch",
                hide_index=True,
            )


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 2 — OPTIMIZATION
# ──────────────────────────────────────────────────────────────────────────────
with t2:
    section("Capacity-aware optimization", "Tune demand, capacity and service target, then solve the flow model")

    a, b, c = st.columns(3, gap="large")
    surge = a.slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05, key="optimization_demand_multiplier")
    cap = b.slider("Capacity multiplier", 0.5, 3.0, 1.0, 0.05, key="optimization_capacity_multiplier")
    service = c.slider("Service target", 0.80, 0.99, 0.95, 0.01, key="optimization_service_target")

    st.write("")
    if st.button("▶  Run optimization", type="primary", key="run_optimization"):
        r = post("/optimize", {
            "demand_multiplier": surge,
            "capacity_multiplier": cap,
            "service_level_target": service,
        })
        if r.ok:
            m = r.json()["metrics"]

            kpi_row([
                ("Service level", f"{m['service_level']:.1%}", "parcels served on time"),
                ("Unmet parcels", f"{m['unmet_demand']:.1f}", "unserved demand"),
                ("Transport cost", f"{m['total_transport_cost']:.2f}", "modelled total"),
            ])
            st.write("")

            g1, g2, g3 = st.columns(3, gap="large")
            with g1:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=m["service_level"] * 100,
                    number={"suffix": "%", "font": {"size": 34, "color": FX_PURPLE, "family": FONT}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": LINE,
                                 "tickfont": {"size": 11, "color": MUTED}},
                        "bar": {"color": FX_PURPLE, "thickness": 0.32},
                        "bgcolor": "#F3F4F9",
                        "borderwidth": 0,
                        "steps": [
                            {"range": [0, 70], "color": "#FDE8E8"},
                            {"range": [70, 90], "color": "#FEF3C7"},
                            {"range": [90, 100], "color": "#DCFCE7"},
                        ],
                        "threshold": {
                            "line": {"color": FX_ORANGE, "width": 4},
                            "thickness": 0.8,
                            "value": service * 100,
                        },
                    },
                    title={"text": "Service level", "font": {"size": 14, "color": MUTED, "family": FONT}},
                ))
                st.plotly_chart(
                    style_fig(fig_gauge, height=300, title="Service attainment"),
                    width="stretch",
                )

            with g2:
                flows_df = pd.DataFrame(r.json()["flows"])
                if not flows_df.empty:
                    num_cols = [c for c in ["parcels", "cost", "distance_km", "utilization"] if c in flows_df.columns]
                    label_col = next((c for c in ["origin_hub", "origin", "from_hub"] if c in flows_df.columns), None)
                    if label_col and num_cols:
                        val_col = num_cols[0]
                        top_flows = (
                            flows_df.assign(_v=pd.to_numeric(flows_df[val_col], errors="coerce").fillna(0))
                            .sort_values("_v", ascending=False).head(10)
                            .sort_values("_v")
                        )
                        fig_flow = px.bar(
                            top_flows, x="_v", y=label_col, orientation="h",
                            text="_v", color="_v",
                            color_continuous_scale=[[0, "#C4B0E2"], [1, FX_PURPLE]],
                        )
                        fig_flow.update_traces(
                            texttemplate="%{text:,.1f}", textposition="outside",
                            textfont=dict(size=11, color=INK, family=FONT),
                            cliponaxis=False, marker_line_width=0,
                        )
                        fig_flow.update_layout(coloraxis_showscale=False, bargap=0.35)
                        fig_flow.update_xaxes(title_text=val_col.replace("_", " ").title())
                        fig_flow.update_yaxes(title_text="")
                        st.plotly_chart(
                            style_fig(fig_flow, height=300, title=f"Top flows by {val_col.replace('_',' ')}"),
                            width="stretch",
                        )
                    else:
                        st.plotly_chart(empty_fig("Flow chart fields unavailable"), width="stretch")
                else:
                    st.plotly_chart(empty_fig("No flows returned"), width="stretch")

            with g3:
                if not flows_df.empty:
                    cost_col = next((c for c in ["cost", "transport_cost", "total_cost"] if c in flows_df.columns), None)
                    if cost_col:
                        cost_vals = pd.to_numeric(flows_df[cost_col], errors="coerce").fillna(0)
                        fig_donut = go.Figure(go.Pie(
                            labels=flows_df.index.astype(str),
                            values=cost_vals,
                            hole=0.62,
                            marker=dict(colors=PALETTE * 4, line=dict(color="#fff", width=2)),
                            textinfo="percent",
                            textfont=dict(size=11, color="#fff", family=FONT),
                            hovertemplate="Route %{label}<br>Cost: %{value:,.2f}<extra></extra>",
                        ))
                        fig_donut.update_layout(showlegend=False)
                        st.plotly_chart(
                            style_fig(fig_donut, height=300, title="Cost share by flow"),
                            width="stretch",
                        )
                    else:
                        st.plotly_chart(empty_fig("Cost column not present"), width="stretch")
                else:
                    st.plotly_chart(empty_fig("No flows returned"), width="stretch")

            st.markdown("#### Flow detail")
            st.dataframe(flows_df, width="stretch", hide_index=True)
            st.caption(
                "Trip cost is a fixed dispatch + distance charge. Low utilization is surfaced rather than hidden; "
                "unmet rows are not transportation with zero cost."
            )
        else:
            st.error(r.text)

    st.divider()
    section("Disruption scenario", "Stress-test the network against a single shock")
    scenario = st.selectbox(
        "Scenario",
        ["demand_surge", "capacity_shock", "fleet_shortage", "hub_outage", "road_disruption", "combined"],
        key="disruption_scenario",
    )
    if st.button("⚡  Run disruption", key="run_disruption"):
        r = post("/scenario", {"scenario": scenario})
        if r.ok:
            body = r.json()
            metrics = body.get("metrics", body)
            if isinstance(metrics, dict):
                rows = [
                    (k.replace("_", " ").title(), f"{v:,.2f}" if isinstance(v, (int, float)) else str(v))
                    for k, v in metrics.items()
                ]
                if rows:
                    kpi_row([(k, v, "") for k, v in rows[:4]])
                    if len(rows) > 4:
                        st.write("")
                        kpi_row([(k, v, "") for k, v in rows[4:8]])
            st.json(metrics)
        else:
            st.error(r.text)


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 3 — RESILIENCE
# ──────────────────────────────────────────────────────────────────────────────
with t3:
    section("Resilience analytics", "Risk exposure across hubs, lanes and disruption factors")
    if prod:
        r = get("/resilience")
        if r.ok:
            risk = pd.DataFrame(r.json()["risk_summary"])
            if not risk.empty:
                st.dataframe(risk, width="stretch", hide_index=True)

                num_cols = risk.select_dtypes(include="number").columns.tolist()
                label_col = next(
                    (c for c in ["hub_id", "lane", "factor", "risk_factor", "category"] if c in risk.columns),
                    risk.columns[0],
                )
                if num_cols:
                    val_col = num_cols[0]
                    top = risk.assign(_v=pd.to_numeric(risk[val_col], errors="coerce").fillna(0)) \
                              .sort_values("_v", ascending=False).head(15).sort_values("_v")
                    fig_risk = px.bar(
                        top, x="_v", y=label_col, orientation="h", text="_v",
                        color="_v",
                        color_continuous_scale=[[0, "#FFD1B0"], [0.5, FX_ORANGE], [1, "#B91C1C"]],
                    )
                    fig_risk.update_traces(
                        texttemplate="%{text:,.2f}", textposition="outside",
                        textfont=dict(size=11, color=INK, family=FONT),
                        cliponaxis=False, marker_line_width=0,
                    )
                    fig_risk.update_layout(coloraxis_showscale=False, bargap=0.35)
                    fig_risk.update_xaxes(title_text=val_col.replace("_", " ").title())
                    fig_risk.update_yaxes(title_text="")
                    st.plotly_chart(
                        style_fig(fig_risk, height=440, title=f"Top resilience risk by {val_col.replace('_',' ')}"),
                        width="stretch",
                    )
            else:
                st.info("Resilience table is empty for the current forecast window.")
        else:
            st.error(r.text)
    else:
        st.info("Resilience analytics appear after the production pipeline populates Supabase.")


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 4 — ROOT CAUSE
# ──────────────────────────────────────────────────────────────────────────────
with t4:
    section("Root cause analysis", "Factor attribution behind service-level gaps")
    if prod:
        r = get("/root-cause")
        if r.ok:
            rc = pd.DataFrame(r.json()["rows"])
            if not rc.empty:
                st.dataframe(rc, width="stretch", hide_index=True)

                if "analysis_type" in rc.columns:
                    grouped = rc[rc["analysis_type"] == "grouped_factor"].copy()
                    if not grouped.empty and {"factor", "contribution_score"}.issubset(grouped.columns):
                        grouped["contribution_score"] = pd.to_numeric(
                            grouped["contribution_score"], errors="coerce"
                        ).fillna(0)
                        grouped = grouped.sort_values("contribution_score", ascending=True)
                        fig_rc = px.bar(
                            grouped, x="contribution_score", y="factor", orientation="h",
                            text="contribution_score",
                            color="contribution_score",
                            color_continuous_scale=[[0, "#C4B0E2"], [0.5, FX_PURPLE_2], [1, FX_ORANGE]],
                        )
                        fig_rc.update_traces(
                            texttemplate="%{text:.3f}", textposition="outside",
                            textfont=dict(size=11, color=INK, family=FONT),
                            cliponaxis=False, marker_line_width=0,
                        )
                        fig_rc.update_layout(coloraxis_showscale=False, bargap=0.4)
                        fig_rc.update_xaxes(title_text="Contribution score")
                        fig_rc.update_yaxes(title_text="")
                        st.plotly_chart(
                            style_fig(
                                fig_rc, height=max(380, 42 * len(grouped) + 140),
                                title="Service-level contribution by disruption factor",
                            ),
                            width="stretch",
                        )
                    else:
                        st.info("Grouped-factor analysis rows are not present in this run.")
            else:
                st.info("Root-cause table is empty for the current forecast window.")
        else:
            st.error(r.text)
    else:
        st.info("Root-cause analysis appears after the production pipeline runs Step 1.")


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 5 — INTERVENTIONS
# ──────────────────────────────────────────────────────────────────────────────
with t5:
    section("Intervention portfolio", "Cost vs reliability trade-offs across candidate bundles")
    if prod:
        r = get("/interventions")
        if r.ok:
            it = pd.DataFrame(r.json().get("rows", []))
            if not it.empty:
                st.dataframe(it, width="stretch", hide_index=True)

                required_chart_cols = {
                    "intervention_cost",
                    "probability_target_met",
                    "expected_unmet_demand",
                }
                if required_chart_cols.issubset(it.columns):
                    chart_df = it.copy()
                    for _col in required_chart_cols:
                        chart_df[_col] = pd.to_numeric(chart_df[_col], errors="coerce")
                    chart_df = chart_df.dropna(subset=list(required_chart_cols))

                    if not chart_df.empty:
                        hover_cols = ["bundle_id"] if "bundle_id" in chart_df.columns else None
                        fig_iv = px.scatter(
                            chart_df,
                            x="intervention_cost",
                            y="probability_target_met",
                            size="expected_unmet_demand",
                            color="probability_target_met",
                            color_continuous_scale=[[0, "#FCA5A5"], [0.5, FX_ORANGE], [1, "#0E9F6E"]],
                            hover_data=hover_cols,
                            size_max=42,
                        )
                        fig_iv.update_traces(
                            marker=dict(line=dict(width=1.4, color="#fff"), opacity=0.9),
                        )
                        fig_iv.update_layout(coloraxis_showscale=False)
                        fig_iv.update_xaxes(title_text="Intervention cost")
                        fig_iv.update_yaxes(title_text="Probability target met", tickformat=".0%")
                        st.plotly_chart(
                            style_fig(
                                fig_iv, height=460,
                                title="Intervention cost vs reliability (bubble = expected unmet demand)",
                            ),
                            width="stretch",
                        )

                        # Ranked bar for readability
                        top_bundles = chart_df.sort_values(
                            "probability_target_met", ascending=False
                        ).head(12).sort_values("probability_target_met")
                        if "bundle_id" in top_bundles.columns:
                            fig_rank = px.bar(
                                top_bundles,
                                x="probability_target_met",
                                y="bundle_id",
                                orientation="h",
                                text="probability_target_met",
                                color="probability_target_met",
                                color_continuous_scale=[[0, FX_ORANGE], [1, "#0E9F6E"]],
                            )
                            fig_rank.update_traces(
                                texttemplate="%{text:.1%}", textposition="outside",
                                textfont=dict(size=11, color=INK, family=FONT),
                                cliponaxis=False, marker_line_width=0,
                            )
                            fig_rank.update_layout(coloraxis_showscale=False, bargap=0.4)
                            fig_rank.update_xaxes(title_text="Probability target met", tickformat=".0%")
                            fig_rank.update_yaxes(title_text="")
                            st.plotly_chart(
                                style_fig(fig_rank, height=420, title="Reliability ranking of top bundles"),
                                width="stretch",
                            )
                    else:
                        st.info("Intervention chart fields contain no numeric rows in this run.")
                else:
                    st.info("Intervention results loaded, but the reliability chart fields are not available in this run.")

                if "feasible" in it.columns:
                    feasible = it[it["feasible"].astype(bool)]
                    st.info(f"Feasible bundles in latest evaluation: **{len(feasible)}** of {len(it)}")
            else:
                st.info("No intervention bundles returned for the current forecast window.")
        else:
            st.error(r.text)
    else:
        st.info("Intervention analytics appear after the production pipeline runs.")


# ──────────────────────────────────────────────────────────────────────────────
#  TAB 6 — ROUTING
# ──────────────────────────────────────────────────────────────────────────────
with t6:
    section(
        "Parcel consolidation + multi-stop routing",
        "OSRM road distance/time · fleet availability · parcel, weight & cube capacity · detour guardrails · round-trip economics",
    )

    fleet_df = pd.DataFrame(network.get("fleet", []))
    vehicle_options = ["any"]
    if not fleet_df.empty and "vehicle_type" in fleet_df.columns:
        vehicle_options += list(fleet_df["vehicle_type"].astype(str).drop_duplicates())

    vehicle_type = st.selectbox(
        "Vehicle type", vehicle_options,
        index=1 if len(vehicle_options) > 1 else 0,
        key="routing_vehicle_type",
    )
    selected = (
        fleet_df[fleet_df["vehicle_type"].astype(str).eq(vehicle_type)].head(1)
        if vehicle_type != "any" else pd.DataFrame()
    )

    default_capacity = int(selected.iloc[0]["parcel_capacity"]) if not selected.empty else 40
    default_hours = (
        float(selected.iloc[0]["max_trip_hours"])
        if not selected.empty and "max_trip_hours" in selected.columns else 16.0
    )
    default_fixed = float(selected.iloc[0]["fixed_trip_cost"]) if not selected.empty else 45.0
    default_km = float(selected.iloc[0]["cost_per_km"]) if not selected.empty else 0.075

    st.markdown(
        f'<div class="fx-note">Fleet defaults: <b>{default_capacity}</b> parcels · '
        f'<b>{default_hours:.1f} h</b> max trip · <b>{default_fixed:.2f}</b> fixed trip cost · '
        f'<b>{default_km:.3f}/km</b> variable cost.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    with st.expander("⚙  Capacity & time constraints", expanded=True):
        c1, c2, c3, c4 = st.columns(4, gap="large")
        parcel_capacity = c1.number_input("Parcel capacity", 1, 500, default_capacity, 1, key="routing_parcel_capacity")
        max_route_hours = c2.number_input("Max route hours", 1.0, 72.0, default_hours, 1.0, key="routing_max_route_hours")
        max_stops = c3.number_input("Max stops", 1, 15, 5, 1, key="routing_max_stops")
        demand_multiplier = c4.slider("Demand multiplier", 0.5, 2.0, 1.0, 0.05, key="routing_demand_multiplier")

        c1, c2, c3, c4 = st.columns(4, gap="large")
        max_weight_kg = c1.number_input("Max weight (kg)", 100.0, value=12000.0, step=250.0, key="routing_max_weight")
        max_volume_m3 = c2.number_input("Max volume (m³)", 1.0, value=65.0, step=1.0, key="routing_max_volume")
        service_time = c3.number_input("Service min / stop", 0.0, 180.0, 15.0, 5.0, key="routing_service_time")
        min_util = c4.slider("Minimum load factor", 0.0, 1.0, 0.60, 0.05, key="routing_min_utilization")

    with st.expander("🕓 Driver & handling rules", expanded=False):
        c1, c2, c3, c4 = st.columns(4, gap="large")
        return_to_origin = c1.checkbox("Return to origin", value=False, key="routing_return_to_origin")
        driver_break = c2.number_input("Driver break (h)", 0.0, 4.0, 0.5, 0.25, key="routing_driver_break")
        loading_minutes = c3.number_input("Loading (min)", 0.0, 240.0, 30.0, 5.0, key="routing_loading")
        unloading_minutes = c4.number_input("Unload min / parcel", 0.0, 10.0, 0.5, 0.1, key="routing_unloading")

    with st.expander("🎯 Route scoring & detour guardrails", expanded=False):
        c1, c2, c3, c4 = st.columns(4, gap="large")
        max_detour = c1.slider("Max distance detour %", 0.0, 100.0, 25.0, 5.0, key="routing_max_distance_detour")
        max_time_detour = c2.slider("Max time detour %", 0.0, 100.0, 25.0, 5.0, key="routing_max_time_detour")
        distance_weight = c3.slider("Distance weight", 0.0, 1.0, 0.4, 0.05, key="routing_distance_weight")
        time_weight = c4.slider("Time weight", 0.0, 1.0, 0.4, 0.05, key="routing_time_weight")

    with st.expander("💰 Advanced economics", expanded=False):
        c1, c2, c3 = st.columns(3, gap="large")
        fixed_trip_cost = c1.number_input("Fixed trip cost", 0.0, value=default_fixed, step=1.0, key="routing_fixed_trip_cost")
        cost_per_km = c2.number_input("Cost / km", 0.0, value=default_km, step=0.005, format="%.3f", key="routing_cost_per_km")
        economic_weight = c3.slider("Economic weight", 0.0, 1.0, 0.2, 0.05, key="routing_economic_weight")
        empty_return_factor = st.slider("Empty return cost factor", 0.0, 1.0, 0.35, 0.05, key="routing_empty_return_factor")

    if distance_weight + time_weight + economic_weight <= 0:
        st.error("At least one route-scoring weight must be positive.")

    st.write("")
    if st.button("🚚  Build consolidated routes", type="primary", key="build_consolidated_routes"):
        payload = {
            "vehicle_type": vehicle_type,
            "parcel_capacity": int(parcel_capacity),
            "max_route_hours": float(max_route_hours),
            "max_stops": int(max_stops),
            "demand_multiplier": float(demand_multiplier),
            "fixed_trip_cost": float(fixed_trip_cost),
            "cost_per_km": float(cost_per_km),
            "distance_weight": float(distance_weight),
            "time_weight": float(time_weight),
            "economic_weight": float(economic_weight),
            "max_weight_kg": float(max_weight_kg),
            "max_volume_m3": float(max_volume_m3),
            "service_time_minutes_per_stop": float(service_time),
            "loading_minutes": float(loading_minutes),
            "unloading_minutes_per_parcel": float(unloading_minutes),
            "driver_break_hours": float(driver_break),
            "return_to_origin": bool(return_to_origin),
            "empty_return_factor": float(empty_return_factor),
            "max_detour_pct": float(max_detour),
            "max_time_detour_pct": float(max_time_detour),
            "min_capacity_utilization": float(min_util),
        }
        r = post("/routing", payload, timeout=120)

        if r.ok:
            body = r.json()
            metrics = body["metrics"]
            routes = pd.DataFrame(body["routes"])

            # ── Headline KPIs ─────────────────────────────────────────────
            kpi_row([
                ("Routes", f"{int(metrics['consolidated_routes'])}", "consolidated"),
                ("Avg stops", f"{metrics['average_stops']:.1f}", "per route"),
                ("Avg parcel fill", f"{metrics['average_capacity_utilization']:.1%}", "capacity utilisation"),
                ("Modeled savings", f"{metrics['estimated_cost_savings_pct']:.1f}%", "vs direct dispatch"),
            ])
            st.write("")
            kpi_row([
                ("Service level", f"{metrics['service_level']:.1%}", "demand served"),
                ("Weight fill", f"{metrics.get('average_weight_utilization', 0):.1%}", "of max weight"),
                ("Cube fill", f"{metrics.get('average_volume_utilization', 0):.1%}", "of max volume"),
                ("Unmet parcels", f"{metrics.get('unmet_parcels', 0):.0f}", "not routed"),
            ])

            if metrics.get("unmet_reasons"):
                st.caption(
                    "Unmet reasons: "
                    + ", ".join(f"{k} = {v:.0f}" for k, v in metrics["unmet_reasons"].items())
                )

            st.write("")

            # ── Interactive route analytics ───────────────────────────────
            if not routes.empty:
                r1, r2 = st.columns(2, gap="large")

                with r1:
                    if {"route_id", "capacity_utilization"}.issubset(routes.columns):
                        rr = routes.copy()
                        rr["capacity_utilization"] = pd.to_numeric(rr["capacity_utilization"], errors="coerce").fillna(0)
                        rr["_label"] = "R" + rr["route_id"].astype(str)
                        fig_util = px.bar(
                            rr, x="_label", y="capacity_utilization", text="capacity_utilization",
                            color="capacity_utilization",
                            color_continuous_scale=[[0, "#FCA5A5"], [0.6, FX_ORANGE], [1, "#0E9F6E"]],
                        )
                        fig_util.update_traces(
                            texttemplate="%{text:.0%}", textposition="outside",
                            textfont=dict(size=11, color=INK, family=FONT),
                            cliponaxis=False, marker_line_width=0,
                        )
                        fig_util.update_layout(coloraxis_showscale=False, bargap=0.4)
                        fig_util.update_xaxes(title_text="Route")
                        fig_util.update_yaxes(title_text="Parcel fill", tickformat=".0%")
                        st.plotly_chart(
                            style_fig(fig_util, height=360, title="Parcel fill by route"),
                            width="stretch",
                        )
                    else:
                        st.plotly_chart(empty_fig("Route utilisation fields unavailable"), width="stretch")

                with r2:
                    if {"route_id", "transport_cost"}.issubset(routes.columns):
                        rc = routes.copy()
                        rc["transport_cost"] = pd.to_numeric(rc["transport_cost"], errors="coerce").fillna(0)
                        rc["_label"] = "R" + rc["route_id"].astype(str)
                        fig_cost = px.bar(
                            rc, x="_label", y="transport_cost", text="transport_cost",
                            color="transport_cost",
                            color_continuous_scale=[[0, "#C4B0E2"], [1, FX_PURPLE]],
                        )
                        fig_cost.update_traces(
                            texttemplate="%{text:,.0f}", textposition="outside",
                            textfont=dict(size=11, color=INK, family=FONT),
                            cliponaxis=False, marker_line_width=0,
                        )
                        fig_cost.update_layout(coloraxis_showscale=False, bargap=0.4)
                        fig_cost.update_xaxes(title_text="Route")
                        fig_cost.update_yaxes(title_text="Modeled cost")
                        st.plotly_chart(
                            style_fig(fig_cost, height=360, title="Modeled transport cost by route"),
                            width="stretch",
                        )
                    else:
                        st.plotly_chart(empty_fig("Route cost fields unavailable"), width="stretch")

                # ── Map ───────────────────────────────────────────────────
                st.markdown("#### 🗺  Operational route map")
                coord = {
                    str(row.hub_id): (float(row.lat), float(row.lon))
                    for row in hubs.itertuples()
                    if pd.notna(row.lat) and pd.notna(row.lon)
                }

                if coord:
                    fmap = folium.Map(
                        location=[
                            sum(v[0] for v in coord.values()) / len(coord),
                            sum(v[1] for v in coord.values()) / len(coord),
                        ],
                        zoom_start=5,
                        control_scale=True,
                        tiles="CartoDB positron",
                    )
                    folium.TileLayer("OpenStreetMap", name="Road map", control=True, show=False).add_to(fmap)

                    # Hub layer — always drawn
                    hub_layer = folium.FeatureGroup(name="Hubs", show=True)
                    for hub_id, (lat, lon) in coord.items():
                        hub_row = hubs[hubs["hub_id"].eq(hub_id)].iloc[0]
                        folium.CircleMarker(
                            location=[lat, lon],
                            radius=9, fill=True, fill_opacity=.95,
                            color=FX_PURPLE, fill_color=FX_PURPLE,
                            tooltip=f"Hub {hub_id} · {hub_row.get('city','')}",
                            popup=folium.Popup(
                                f"<div style='font-family:{FONT};font-size:13px;color:{INK};'>"
                                f"<b>{hub_id} · {hub_row.get('city','')}</b><br>"
                                f"Capacity: {float(hub_row.get('capacity_parcels',0)):,.0f} parcels<br>"
                                f"Handling: {float(hub_row.get('handling_capacity',0)):,.0f}"
                                f"</div>",
                                max_width=280,
                            ),
                        ).add_to(hub_layer)
                    hub_layer.add_to(fmap)

                    # Route geometries
                    for idx, row in routes.iterrows():
                        sequence = [str(row["origin_hub"])] + [str(x) for x in row["destination_hubs"]]
                        route_points = []
                        for a, b in zip(sequence[:-1], sequence[1:]):
                            if a not in coord or b not in coord:
                                continue
                            geometry = None
                            try:
                                lonlat = f"{coord[a][1]},{coord[a][0]};{coord[b][1]},{coord[b][0]}"
                                rr = requests.get(
                                    "https://router.project-osrm.org/route/v1/driving/" + lonlat,
                                    params={"overview": "full", "geometries": "geojson", "steps": "false"},
                                    timeout=12,
                                )
                                if rr.ok:
                                    geometry = rr.json().get("routes", [{}])[0].get("geometry", {}).get("coordinates")
                            except Exception:
                                geometry = None

                            if geometry:
                                route_points.extend([(float(la), float(lo)) for lo, la in geometry])
                            else:
                                route_points.extend([coord[a], coord[b]])

                        color = PALETTE[idx % len(PALETTE)]
                        folium.PolyLine(
                            route_points,
                            color=color, weight=6, opacity=.9,
                            tooltip=f"R{int(row['route_id'])} · {int(row['parcels'])} parcels · {int(row['stops'])} stops",
                            popup=folium.Popup(
                                f"<div style='font-family:{FONT};font-size:12.5px;color:{INK};line-height:1.6;'>"
                                f"<b style='color:{FX_PURPLE};'>Route {int(row['route_id'])}</b><br>"
                                f"Vehicle: {row.get('vehicle_type','n/a')}<br>"
                                f"Stops: {int(row['stops'])}<br>"
                                f"Parcels: {row['parcels']:.1f}<br>"
                                f"Weight: {row.get('weight_kg',0):.1f} kg ({row.get('weight_utilization',0):.1%})<br>"
                                f"Cube: {row.get('volume_m3',0):.2f} m³ ({row.get('volume_utilization',0):.1%})<br>"
                                f"Distance: {row['distance_km']:.1f} km<br>"
                                f"Drive time: {row['travel_time_hours']:.1f} h<br>"
                                f"Operational time: {row.get('route_operational_hours', row['travel_time_hours']):.1f} h<br>"
                                f"Detour: {row.get('distance_detour_pct',0):.1f}% distance / "
                                f"{row.get('time_detour_pct',0):.1f}% time<br>"
                                f"Modeled cost: {row['transport_cost']:.2f}<br>"
                                f"Savings vs direct: {row.get('estimated_savings',0):.2f}"
                                f"</div>",
                                max_width=340,
                            ),
                        ).add_to(fmap)

                        for stop_no, hub_id in enumerate(sequence, 1):
                            if hub_id in coord:
                                folium.Marker(
                                    coord[hub_id],
                                    tooltip=f"R{int(row['route_id'])} · stop {stop_no} · hub {hub_id}",
                                    icon=folium.DivIcon(
                                        html=(
                                            f'<div style="font-family:{FONT};font-size:11px;font-weight:800;'
                                            f'color:{FX_PURPLE};background:#fff;border:2px solid {FX_ORANGE};'
                                            f'border-radius:11px;padding:2px 7px;box-shadow:0 2px 6px rgba(0,0,0,.18);'
                                            f'white-space:nowrap;">{stop_no}</div>'
                                        )
                                    ),
                                ).add_to(fmap)

                    folium.LayerControl(collapsed=False).add_to(fmap)
                    components.html(fmap.get_root().render(), height=780, scrolling=False)
                else:
                    st.warning("Hub coordinates are unavailable, so the operational map cannot be rendered.")

                # ── Route table ───────────────────────────────────────────
                st.markdown("#### Route manifest")
                display = routes.copy()
                if "destination_hubs" in display.columns:
                    display["destination_hubs"] = display["destination_hubs"].map(
                        lambda xs: " → ".join(map(str, xs)) if isinstance(xs, (list, tuple)) else str(xs)
                    )
                if "stop_parcels" in display.columns:
                    display["stop_parcels"] = display["stop_parcels"].astype(str)
                keep = [
                    "route_id", "origin_hub", "destination_hubs", "vehicle_type", "parcels", "stops",
                    "capacity_utilization", "weight_kg", "weight_utilization", "volume_m3", "volume_utilization",
                    "distance_km", "travel_time_hours", "distance_detour_pct", "time_detour_pct",
                    "transport_cost", "estimated_savings", "status",
                ]
                keep = [col for col in keep if col in display.columns]
                st.dataframe(display[keep], width="stretch", hide_index=True)

            else:
                st.markdown("### Network map")
                st.caption(
                    "No feasible consolidated routes were returned. The live hub network remains visible "
                    "so you can inspect the network before relaxing constraints."
                )
                coord = {
                    str(row.hub_id): (float(row.lat), float(row.lon))
                    for row in hubs.itertuples()
                    if pd.notna(row.lat) and pd.notna(row.lon)
                }
                if coord:
                    fmap = folium.Map(
                        location=[
                            sum(v[0] for v in coord.values()) / len(coord),
                            sum(v[1] for v in coord.values()) / len(coord),
                        ],
                        zoom_start=5, control_scale=True, tiles="CartoDB positron",
                    )
                    folium.TileLayer("OpenStreetMap", name="Road map", control=True).add_to(fmap)
                    for hub_id, (lat, lon) in coord.items():
                        hub_row = hubs[hubs["hub_id"].eq(hub_id)].iloc[0]
                        folium.CircleMarker(
                            location=[lat, lon], radius=10,
                            color=FX_PURPLE, fill=True, fill_color=FX_PURPLE, fill_opacity=.95,
                            tooltip=f"Hub {hub_id} · {hub_row.get('city','')}",
                            popup=folium.Popup(
                                f"<div style='font-family:{FONT};font-size:13px;color:{INK};'>"
                                f"<b>{hub_id} · {hub_row.get('city','')}</b><br>"
                                f"Capacity: {float(hub_row.get('capacity_parcels',0)):,.0f} parcels"
                                f"</div>",
                                max_width=280,
                            ),
                        ).add_to(fmap)
                    folium.LayerControl(collapsed=False).add_to(fmap)
                    components.html(fmap.get_root().render(), height=780, scrolling=False)
                else:
                    st.warning("Hub coordinates are unavailable, so the operational map cannot be rendered.")
        else:
            st.error(r.text)


# ──────────────────────────────────────────────────────────────────────────────
#  FOOTER
# ──────────────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Model: {summary.get('model_version')} · Optimizer: {summary.get('optimizer_version')} · "
    "Synthetic costs/disruption distributions are stress-test assumptions."
)

