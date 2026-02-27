import os
os.environ["POLARS_SKIP_CPU_CHECK"] = "1"

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import tempfile

from demoparser2 import DemoParser
from kast import compute_kast
from rating import compute_rating
from round_timeline import build_round_timeline, build_player_round_matrix
from utility import compute_utility_stats
from economy import compute_economy
from heatmap import build_position_heatmap
import requests
from PIL import Image

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CS2 ANALYST",
    page_icon="assets/favicon.ico" if os.path.exists("assets/favicon.ico") else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Design System ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700;800&family=Barlow:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [data-testid="stAppViewContainer"] {
    background: #080b0f !important;
    color: #c8d0dc !important;
    font-family: 'Barlow', sans-serif !important;
    font-weight: 400;
}

/* Hide ALL Streamlit chrome including header/sidebar toggle */
#MainMenu, footer, header { visibility: hidden !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
.stDeployButton { display: none !important; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #0c1018 !important;
    border-right: 1px solid #1a2030 !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* ── Main content area ── */
[data-testid="stMainBlockContainer"] {
    padding: 0 2rem !important;
    max-width: 100% !important;
}

/* ── Top nav bar ── */
.topnav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 0 18px 0;
    border-bottom: 1px solid #1a2030;
    margin-bottom: 28px;
}
.cs2-wordmark {
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800;
    font-size: 22px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #ffffff;
}
.cs2-wordmark span { color: #f0b429; }

/* ── Sidebar content styles (still used for match info) ── */
.sidebar-divider { height: 1px; background: #1a2030; margin: 16px 20px; }
.sidebar-section-label {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 10px; font-weight: 600; letter-spacing: 0.2em;
    text-transform: uppercase; color: #3a4558;
    padding: 0 20px; margin-bottom: 8px; display: block;
}
.match-info-block { padding: 0 20px; margin-bottom: 6px; }
.match-info-label {
    font-size: 10px; font-weight: 600; letter-spacing: 0.15em;
    text-transform: uppercase; color: #3a4558; margin-bottom: 2px;
}
.match-info-value {
    font-family: 'Barlow Condensed', sans-serif;
    font-size: 16px; font-weight: 700; color: #e8ecf2; letter-spacing: 0.02em;
}
.score-block {
    padding: 16px 20px; background: #0f1520;
    margin: 0 12px 16px 12px; border-radius: 4px;
    border: 1px solid #1a2030; text-align: center;
}
.score-teams { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.score-team {
    font-family: 'Barlow Condensed', sans-serif; font-size: 11px; font-weight: 700;
    letter-spacing: 0.15em; text-transform: uppercase; color: #5a6a82;
}
.score-num {
    font-family: 'Barlow Condensed', sans-serif; font-size: 36px; font-weight: 800;
    letter-spacing: -0.02em; color: #ffffff; line-height: 1;
}
.score-vs {
    font-family: 'Barlow Condensed', sans-serif; font-size: 11px; font-weight: 600;
    color: #2a3448; letter-spacing: 0.1em;
}

/* ── Section headers ── */
.section-header { display: flex; align-items: center; gap: 10px; margin: 28px 0 14px 0; }
.section-header-line { flex: 1; height: 1px; background: #1a2030; }
.section-title {
    font-family: 'Barlow Condensed', sans-serif; font-size: 11px; font-weight: 700;
    letter-spacing: 0.22em; text-transform: uppercase; color: #3a4a62; white-space: nowrap;
}

/* ── Tabs ── */
[data-testid="stTabs"] { gap: 0 !important; }
[data-testid="stTabsTabList"] {
    background: transparent !important; border-bottom: 1px solid #1a2030 !important;
    gap: 0 !important; padding: 0 !important;
}
button[data-testid="stTab"] {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 12px !important;
    font-weight: 700 !important; letter-spacing: 0.18em !important;
    text-transform: uppercase !important; color: #3a4a62 !important;
    background: transparent !important; border: none !important;
    border-bottom: 2px solid transparent !important; padding: 12px 20px !important;
    border-radius: 0 !important; transition: color 0.15s !important;
}
button[data-testid="stTab"]:hover { color: #8a9ab8 !important; background: transparent !important; }
button[data-testid="stTab"][aria-selected="true"] {
    color: #f0b429 !important; border-bottom: 2px solid #f0b429 !important;
    background: transparent !important;
}
[data-testid="stTabsContent"] { padding-top: 24px !important; background: transparent !important; }

/* ── Dataframes ── */
[data-testid="stDataFrame"] { border: 1px solid #1a2030 !important; border-radius: 3px !important; }
[data-testid="stDataFrame"] th {
    background: #0c1018 !important; font-family: 'Barlow Condensed', sans-serif !important;
    font-size: 11px !important; font-weight: 700 !important; letter-spacing: 0.15em !important;
    text-transform: uppercase !important; color: #3a4a62 !important;
}
[data-testid="stDataFrame"] td {
    font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important;
    color: #c8d0dc !important; background: #080b0f !important;
}

/* ── Metrics ── */
[data-testid="metric-container"] {
    background: #0c1018 !important; border: 1px solid #1a2030 !important;
    border-radius: 3px !important; padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 10px !important;
    font-weight: 700 !important; letter-spacing: 0.18em !important;
    text-transform: uppercase !important; color: #3a4a62 !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 24px !important;
    font-weight: 800 !important; color: #ffffff !important;
}

/* ── Select boxes & sliders ── */
[data-testid="stSelectbox"] label, [data-testid="stSlider"] label {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 11px !important;
    font-weight: 700 !important; letter-spacing: 0.15em !important;
    text-transform: uppercase !important; color: #3a4a62 !important;
}
[data-testid="stSelectbox"] > div > div {
    background: #0c1018 !important; border: 1px solid #1a2030 !important;
    border-radius: 3px !important; color: #c8d0dc !important;
    font-family: 'Barlow', sans-serif !important; font-size: 13px !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    border: 1px dashed #1a2030 !important; border-radius: 4px !important;
    background: #0c1018 !important; padding: 8px !important;
}
[data-testid="stFileUploader"] label {
    font-family: 'Barlow Condensed', sans-serif !important; font-size: 11px !important;
    letter-spacing: 0.1em !important; text-transform: uppercase !important; color: #5a6a82 !important;
}

/* compact uploader in nav */
.nav-uploader [data-testid="stFileUploader"] {
    border: 1px solid #1a2030 !important; border-radius: 3px !important;
    background: #0c1018 !important; padding: 4px 8px !important;
    min-height: 0 !important;
}

/* ── Spinner ── */
[data-testid="stSpinner"] { color: #f0b429 !important; }

/* ── Plotly ── */
.js-plotly-plot, .plotly { border-radius: 3px; }

/* ── Kill feed ── */
.killfeed-entry {
    display: flex; align-items: center; gap: 8px;
    padding: 7px 12px; border-bottom: 1px solid #0f1520;
    font-size: 13px; font-family: 'Barlow', sans-serif;
}
.killfeed-entry:hover { background: #0c1018; }
.killfeed-killer { color: #4a9eff; font-weight: 600; }
.killfeed-victim { color: #ff5555; font-weight: 600; }
.killfeed-weapon { color: #3a4a62; font-size: 11px; font-family: 'JetBrains Mono', monospace; }
.killfeed-hs { color: #f0b429; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; }

/* ── Round result ── */
.round-result { padding: 12px 16px; border-radius: 3px; border-left: 3px solid; margin-bottom: 16px; }
.round-result.t-win  { background: rgba(255,107,53,0.08); border-color: #ff6b35; }
.round-result.ct-win { background: rgba(74,158,255,0.08);  border-color: #4a9eff; }
.round-result-label  { font-size: 10px; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: #3a4a62; margin-bottom: 4px; }
.round-result-winner { font-family: 'Barlow Condensed', sans-serif; font-size: 22px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
.round-result-reason { font-size: 11px; color: #3a4a62; margin-top: 2px; font-family: 'JetBrains Mono', monospace; }

/* ── Upload hero ── */
.upload-hero { text-align: center; padding: 60px 40px 40px 40px; }
.upload-hero-title {
    font-family: 'Barlow Condensed', sans-serif; font-size: 52px; font-weight: 800;
    letter-spacing: 0.08em; text-transform: uppercase; color: #ffffff; line-height: 1; margin-bottom: 8px;
}
.upload-hero-title span { color: #f0b429; }
.upload-hero-sub { font-size: 14px; color: #3a4a62; margin-bottom: 32px; letter-spacing: 0.05em; }
.upload-feature-grid {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
    max-width: 640px; margin: 0 auto; text-align: left;
}
.upload-feature {
    background: #0c1018; border: 1px solid #1a2030; border-radius: 3px; padding: 14px 16px;
}
.upload-feature-title {
    font-family: 'Barlow Condensed', sans-serif; font-size: 13px; font-weight: 700;
    letter-spacing: 0.1em; text-transform: uppercase; color: #8a9ab8; margin-bottom: 4px;
}
.upload-feature-desc { font-size: 11px; color: #3a4a62; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)

# ── Chart theme ───────────────────────────────────────────────────────────────
CHART_DEFAULTS = dict(
    paper_bgcolor="#080b0f",
    plot_bgcolor="#0c1018",
    font=dict(family="Barlow, sans-serif", color="#5a6a82", size=11),
    margin=dict(l=12, r=12, t=32, b=12),
    xaxis=dict(gridcolor="#0f1520", linecolor="#1a2030", tickcolor="#1a2030", zerolinecolor="#1a2030"),
    yaxis=dict(gridcolor="#0f1520", linecolor="#1a2030", tickcolor="#1a2030", zerolinecolor="#1a2030"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1a2030", font=dict(size=11, color="#5a6a82")),
)

ACCENT       = "#f0b429"
COLOR_T      = "#ff6b35"
COLOR_CT     = "#4a9eff"
COLOR_GREEN  = "#22c55e"
COLOR_RED    = "#ef4444"
COLOR_YELLOW = "#eab308"


def rating_color(val):
    if val >= 1.3:   return COLOR_GREEN
    elif val >= 1.1: return "#86efac"
    elif val >= 0.9: return COLOR_YELLOW
    elif val >= 0.7: return "#f97316"
    else:            return COLOR_RED


def section_header(title):
    st.markdown(f"""
    <div class="section-header">
        <span class="section-title">{title}</span>
        <div class="section-header-line"></div>
    </div>""", unsafe_allow_html=True)


# ── Image fetch ───────────────────────────────────────────────────────────────
@st.cache_data
def fetch_map_image(map_name: str):
    urls = [
        f"https://radar-overviews.cs2.app/{map_name}.png",
        f"https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/{map_name}.png",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            continue
    return None


# ── Parse & compute ───────────────────────────────────────────────────────────
def parse_and_compute(dem_bytes: bytes):
    with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as f:
        f.write(dem_bytes)
        tmp_path = f.name

    try:
        parser = DemoParser(tmp_path)
        _, kills_df   = parser.parse_events(["player_death"])[0]
        _, damage_df  = parser.parse_events(["player_hurt"])[0]
        _, round_df   = parser.parse_events(["round_end"])[0]
        _, spawn_df   = parser.parse_events(["player_spawn"])[0]
        _, flash_df   = parser.parse_events(["flashbang_detonate"])[0]
        _, he_df      = parser.parse_events(["hegrenade_detonate"])[0]
        _, smoke_df   = parser.parse_events(["smokegrenade_detonate"])[0]
        _, molotov_df = parser.parse_events(["inferno_startburn"])[0]
        _, freeze_df  = parser.parse_events(["round_freeze_end"])[0]

        freeze_ticks = sorted(freeze_df["tick"].tolist())
        tick_df = parser.parse_ticks(
            ["current_equip_value", "cash_spent_this_round", "total_cash_spent", "cash", "team_name"],
            ticks=freeze_ticks
        )
        pos_df = parser.parse_ticks(
            ["X", "Y", "Z", "team_name", "is_alive"],
            ticks=list(range(0, 200000, 640))
        )
        header   = parser.parse_header()
        map_name = header.get("map_name", "de_unknown")
        server   = header.get("server_name", "")

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    total_rounds = round_df[round_df["round"] > 0].shape[0]
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_per_player   = kills_clean.groupby("attacker_name").size().rename("kills")
    deaths_per_player  = kills_clean.groupby("user_name").size().rename("deaths")
    hs_per_player      = kills_clean[kills_clean["headshot"] == True].groupby("attacker_name").size().rename("headshots")
    assists_per_player = kills_df[kills_df["assister_name"].notna()].groupby("assister_name").size().rename("assists")
    damage_clean       = damage_df[damage_df["attacker_name"].notna() & (damage_df["attacker_name"] != damage_df["user_name"])].copy()
    damage_per_player  = damage_clean.groupby("attacker_name")["dmg_health"].sum().rename("total_damage")

    all_players = set(kills_per_player.index) | set(deaths_per_player.index)
    stats = pd.DataFrame(index=sorted(all_players))
    stats = stats.join(kills_per_player).join(deaths_per_player).join(hs_per_player).join(assists_per_player).join(damage_per_player)
    stats = stats.fillna(0).astype(int)

    stats["K/D"]   = (stats["kills"] / stats["deaths"].replace(0, 1)).round(2)
    stats["HS%"]   = ((stats["headshots"] / stats["kills"].replace(0, 1)) * 100).round(1)
    stats["ADR"]   = (stats["total_damage"] / total_rounds).round(1)

    kast_pct, _ = compute_kast(kills_df, round_df, spawn_df)
    stats["KAST%"]  = stats.index.map(lambda p: kast_pct.get(p, 0.0))
    stats["Rating"] = compute_rating(stats, kills_df, round_df)

    t_wins  = round_df[round_df["winner"] == "T"].shape[0]
    ct_wins = round_df[round_df["winner"] == "CT"].shape[0]

    return (stats, total_rounds, kills_df, damage_df, round_df, spawn_df,
            flash_df, he_df, smoke_df, molotov_df, tick_df, pos_df,
            map_name, server, t_wins, ct_wins)

def hex_to_rgba(hex_color, alpha=0.13):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# ── Chart builders ────────────────────────────────────────────────────────────
def build_stats_table(stats):
    fig = go.Figure(data=[go.Table(
        columnwidth=[160, 55, 55, 55, 65, 65, 70, 70, 80],
        header=dict(
            values=["PLAYER", "K", "D", "A", "K/D", "HS%", "ADR", "KAST%", "RATING"],
            fill_color="#0c1018",
            font=dict(family="Barlow Condensed, sans-serif", color="#3a4a62", size=11),
            align=["left"] + ["center"] * 8, height=32,
            line=dict(color="#1a2030", width=1),
        ),
        cells=dict(
            values=[
                stats.index.tolist(),
                stats["kills"].astype(int).tolist(),
                stats["deaths"].astype(int).tolist(),
                stats["assists"].astype(int).tolist(),
                stats["K/D"].tolist(),
                [f"{v}%" for v in stats["HS%"]],
                stats["ADR"].tolist(),
                [f"{v}%" for v in stats["KAST%"]],
                [f"{v:.3f}" for v in stats["Rating"]],
            ],
            fill_color=[
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                ["#080b0f"] * len(stats),
                [hex_to_rgba(rating_color(v)) for v in stats["Rating"]],
            ],
            font=dict(
                family=["Barlow, sans-serif"] * 1 + ["JetBrains Mono, monospace"] * 8,
                color=["#c8d0dc"] * 1 + ["#8a9ab8"] * 7 + [[rating_color(v) for v in stats["Rating"]]],
                size=12,
            ),
            align=["left"] + ["center"] * 8, height=30,
            line=dict(color="#0f1520", width=1),
        )
    )])
    fig.update_layout(
        **{k: v for k, v in CHART_DEFAULTS.items() if k in ["paper_bgcolor", "font"]},
        margin=dict(l=0, r=0, t=0, b=0),
        height=34 + 30 * len(stats),
    )
    return fig


def build_rating_bar(stats):
    s = stats.sort_values("Rating")
    fig = go.Figure(go.Bar(
        x=s["Rating"], y=s.index, orientation="h",
        marker=dict(color=[rating_color(v) for v in s["Rating"]], opacity=0.85),
        text=[f"{v:.3f}" for v in s["Rating"]], textposition="outside",
        textfont=dict(family="JetBrains Mono", size=11, color="#5a6a82"),
    ))
    fig.add_vline(x=1.0, line_dash="dot", line_color="#1a2030", line_width=1,
                  annotation_text="1.000", annotation_font=dict(color="#2a3448", size=10))
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="PLAYER RATING", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
        xaxis=dict(**CHART_DEFAULTS["xaxis"], range=[0, max(stats["Rating"]) + 0.25]),
        height=320,
    )
    return fig


def build_adr_scatter(stats):
    df = stats.reset_index()
    df.columns = ["Player"] + list(df.columns[1:])
    fig = px.scatter(
        df, x="ADR", y="KAST%", text="Player", size="kills",
        color="Rating",
        color_continuous_scale=[[0, COLOR_RED], [0.45, COLOR_YELLOW], [1, COLOR_GREEN]],
        range_color=[0.3, 1.5], size_max=28,
    )
    fig.update_traces(
        textposition="top center",
        textfont=dict(family="Barlow Condensed", size=12, color="#8a9ab8"),
        marker=dict(line=dict(width=1, color="#0c1018")),
    )
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="ADR vs KAST  —  bubble = kills", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
        coloraxis_colorbar=dict(
            title=dict(text="RTG", font=dict(size=10, color="#3a4a62")),
            tickfont=dict(size=9, color="#3a4a62", family="JetBrains Mono"),
            bgcolor="#0c1018", bordercolor="#1a2030", thickness=10,
        ),
        height=360,
    )
    return fig


def build_radar(stats, player):
    num_stats = stats.select_dtypes(include="number")
    avg  = num_stats.mean()
    cats = ["Kills", "ADR", "KAST%", "HS%", "K/D", "Rating"]
    cols = ["kills", "ADR", "KAST%", "HS%", "K/D", "Rating"]

    def norm(col):
        mx = num_stats[col].max()
        return float(num_stats.loc[player, col]) / mx if mx > 0 else 0

    vp = [norm(c) for c in cols]
    va = [float(avg[c]) / float(num_stats[c].max()) if num_stats[c].max() > 0 else 0 for c in cols]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=va + [va[0]], theta=cats + [cats[0]], fill="toself", name="Match avg",
        line=dict(color="#1a2030", width=1), fillcolor="rgba(26,32,48,0.4)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=vp + [vp[0]], theta=cats + [cats[0]], fill="toself", name=player,
        line=dict(color=ACCENT, width=2), fillcolor="rgba(240,180,41,0.12)",
    ))
    fig.update_layout(
        **{k: v for k, v in CHART_DEFAULTS.items() if k in ["paper_bgcolor", "font", "legend"]},
        polar=dict(
            bgcolor="#0c1018",
            radialaxis=dict(visible=True, range=[0, 1], gridcolor="#0f1520",
                           tickfont=dict(size=9, color="#2a3448"), showticklabels=False),
            angularaxis=dict(gridcolor="#1a2030", tickfont=dict(family="Barlow Condensed", size=12, color="#5a6a82")),
        ),
        margin=dict(l=40, r=40, t=40, b=40), height=340,
    )
    return fig


# ══════════════════════════════════════════════════════════════════════════════
# TOP NAV  — always visible, contains wordmark + file uploader
# ══════════════════════════════════════════════════════════════════════════════
nav_left, nav_right = st.columns([3, 2])

with nav_left:
    st.markdown('<div style="padding-top:14px"><span class="cs2-wordmark">CS2<span>ANALYST</span></span></div>',
                unsafe_allow_html=True)

with nav_right:
    uploaded = st.file_uploader(
        "Upload .dem", type=["dem"],
        label_visibility="collapsed",
        key="demo_upload",
    )

st.markdown('<div style="height:1px;background:#1a2030;margin-bottom:28px"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
if uploaded is None:
    st.markdown("""
    <div class="upload-hero">
        <div class="upload-hero-title">CS2<span>ANALYST</span></div>
        <div class="upload-hero-sub">Professional demo analysis. Drop a .dem file above to begin.</div>
    </div>
    """, unsafe_allow_html=True)

    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown("""
        <div class="upload-feature-grid">
            <div class="upload-feature">
                <div class="upload-feature-title">Performance</div>
                <div class="upload-feature-desc">K/D/A, ADR, KAST%, HLTV Rating 2.0</div>
            </div>
            <div class="upload-feature">
                <div class="upload-feature-title">Round Data</div>
                <div class="upload-feature-desc">Kill heatmap, round timeline, kill feed</div>
            </div>
            <div class="upload-feature">
                <div class="upload-feature-title">Utility</div>
                <div class="upload-feature-desc">Flash, HE, smoke and molotov efficiency</div>
            </div>
            <div class="upload-feature">
                <div class="upload-feature-title">Economy</div>
                <div class="upload-feature-desc">Buy types, win rates, team equity</div>
            </div>
            <div class="upload-feature">
                <div class="upload-feature-title">Positions</div>
                <div class="upload-feature-desc">Kill and death heatmaps on map radar</div>
            </div>
            <div class="upload-feature">
                <div class="upload-feature-title">Player Dive</div>
                <div class="upload-feature-desc">Per-player radar vs. match average</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

else:
    # ── Parse ──────────────────────────────────────────────────────────────
    if "parsed" not in st.session_state or st.session_state.get("last_file") != uploaded.name:
        with st.spinner("Parsing demo..."):
            result = parse_and_compute(uploaded.read())
            (stats, total_rounds, kills_df, damage_df, round_df, spawn_df,
             flash_df, he_df, smoke_df, molotov_df, tick_df, pos_df,
             map_name, server, t_wins, ct_wins) = result

            st.session_state.parsed = dict(
                stats=stats, total_rounds=total_rounds, kills_df=kills_df,
                damage_df=damage_df, round_df=round_df, spawn_df=spawn_df,
                flash_df=flash_df, he_df=he_df, smoke_df=smoke_df,
                molotov_df=molotov_df, tick_df=tick_df, pos_df=pos_df,
                map_name=map_name, server=server, t_wins=t_wins, ct_wins=ct_wins,
            )
            st.session_state.last_file = uploaded.name
        st.rerun()

    d            = st.session_state.parsed
    stats        = d["stats"]
    total_rounds = d["total_rounds"]
    kills_df     = d["kills_df"]
    damage_df    = d["damage_df"]
    round_df     = d["round_df"]
    spawn_df     = d["spawn_df"]
    flash_df     = d["flash_df"]
    he_df        = d["he_df"]
    smoke_df     = d["smoke_df"]
    molotov_df   = d["molotov_df"]
    tick_df      = d["tick_df"]
    pos_df       = d["pos_df"]
    map_name     = d["map_name"]
    map_display  = d["map_name"].replace("de_", "").upper()

    stats_sorted = stats.sort_values("Rating", ascending=False)

    # ── Match summary bar ─────────────────────────────────────────────────
    mc1, mc2, mc3, mc4, mc5 = st.columns([1, 1, 1, 1, 1])
    with mc1:
        st.metric("Map", map_display)
    with mc2:
        st.metric("Rounds", d["total_rounds"])
    with mc3:
        st.metric("T Wins", d["t_wins"])
    with mc4:
        st.metric("CT Wins", d["ct_wins"])
    with mc5:
        top_player = stats["Rating"].idxmax()
        st.metric("Rating MVP", f"{top_player}  {stats.loc[top_player,'Rating']:.3f}")

    # ── Tabs ───────────────────────────────────────────────────────────────
    tab_overview, tab_rounds, tab_utility, tab_economy, tab_heatmap = st.tabs([
        "OVERVIEW", "ROUNDS", "UTILITY", "ECONOMY", "POSITIONS",
    ])

    # ══════════════════════════════════════════════════════════════════════
    # TAB 1 — OVERVIEW
    # ══════════════════════════════════════════════════════════════════════
    with tab_overview:
        section_header("SCOREBOARD")
        st.plotly_chart(build_stats_table(stats_sorted), use_container_width=True)

        section_header("PERFORMANCE")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(build_rating_bar(stats), use_container_width=True)
        with c2:
            st.plotly_chart(build_adr_scatter(stats), use_container_width=True)

        section_header("PLAYER PROFILE")
        selected = st.selectbox("Player", options=stats_sorted.index.tolist(), label_visibility="collapsed")
        if selected:
            r = stats.loc[selected]
            pcols = st.columns(6)
            for col, (label, val) in zip(pcols, [
                ("Kills",   int(r["kills"])),
                ("Deaths",  int(r["deaths"])),
                ("Assists", int(r["assists"])),
                ("ADR",     r["ADR"]),
                ("KAST",    f"{r['KAST%']}%"),
                ("Rating",  f"{r['Rating']:.3f}"),
            ]):
                with col:
                    st.metric(label, val)
            st.plotly_chart(build_radar(stats, selected), use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 2 — ROUNDS
    # ══════════════════════════════════════════════════════════════════════
    with tab_rounds:
        kills_matrix, dmg_matrix, deaths_matrix, all_players = build_player_round_matrix(
            kills_df, damage_df, round_df, spawn_df
        )
        timeline     = build_round_timeline(kills_df, damage_df, round_df)
        player_order = stats.sort_values("kills", ascending=False).index.tolist()
        kills_matrix = kills_matrix.reindex(player_order)

        round_cols = kills_matrix.columns.tolist()
        winners    = {r["round"]: r["winner"] for r in timeline}
        col_labels = [f"R{r}  {'T' if winners.get(r) == 'T' else 'CT'}" for r in round_cols]

        section_header("KILL HEATMAP")
        fig_heatmap = go.Figure(go.Heatmap(
            z=kills_matrix.values, x=col_labels, y=kills_matrix.index.tolist(),
            colorscale=[[0, "#080b0f"], [0.01, "#0c2a18"], [0.4, "#166534"], [1.0, COLOR_GREEN]],
            showscale=False, text=kills_matrix.values, texttemplate="%{text}",
            textfont=dict(family="JetBrains Mono", size=11),
            hovertemplate="<b>%{y}</b>  Round %{x}  Kills: %{z}<extra></extra>",
            zmin=0, zmax=4,
        ))
        fig_heatmap.update_layout(
            **{k: v for k, v in CHART_DEFAULTS.items() if k in ["paper_bgcolor", "plot_bgcolor", "font", "margin"]},
            xaxis=dict(side="top", tickfont=dict(size=9, family="JetBrains Mono", color="#3a4a62"),
                       tickcolor="#1a2030", linecolor="#1a2030", gridcolor="#0f1520"),
            yaxis=dict(tickfont=dict(size=12, family="Barlow Condensed", color="#8a9ab8"),
                       tickcolor="#1a2030", linecolor="#1a2030", gridcolor="#0f1520"),
            margin=dict(l=0, r=0, t=48, b=0),
            height=38 * len(player_order) + 60,
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

        section_header("ROUND BREAKDOWN")
        round_nums     = [r["round"] for r in timeline]
        selected_round = st.select_slider("Round", options=round_nums, label_visibility="collapsed")
        round_data     = next(r for r in timeline if r["round"] == selected_round)

        winner    = round_data["winner"] or "?"
        reason    = (round_data["reason"] or "unknown").replace("_", " ").upper()
        win_class = "t-win" if winner == "T" else "ct-win"
        win_color = COLOR_T if winner == "T" else COLOR_CT
        win_label = "TERRORIST WIN" if winner == "T" else "CT WIN"

        rcols = st.columns([1, 1, 1])
        with rcols[0]:
            st.markdown(f"""
            <div class="round-result {win_class}">
                <div class="round-result-label">Round {selected_round}</div>
                <div class="round-result-winner" style="color:{win_color}">{win_label}</div>
                <div class="round-result-reason">{reason}</div>
            </div>""", unsafe_allow_html=True)

            perf_rows = []
            for p in player_order:
                k    = round_data["player_kills"].get(p, 0)
                dmg  = round_data["player_dmg"].get(p, 0)
                died = "dead" if p in round_data["player_died"] else "alive"
                perf_rows.append({"Player": p, "K": k, "DMG": int(dmg), "Status": died})
            st.dataframe(pd.DataFrame(perf_rows).set_index("Player"), use_container_width=True, height=300)

        with rcols[1]:
            st.markdown(
                '<div style="font-family:\'Barlow Condensed\';font-size:11px;font-weight:700;'
                'letter-spacing:0.2em;text-transform:uppercase;color:#3a4a62;margin-bottom:12px">'
                'KILL FEED</div>', unsafe_allow_html=True
            )
            if round_data["kill_feed"]:
                feed_html = '<div style="background:#0c1018;border:1px solid #1a2030;border-radius:3px">'
                for kf in round_data["kill_feed"]:
                    hs = '<span class="killfeed-hs">HS</span>' if kf["headshot"] else ""
                    feed_html += f"""
                    <div class="killfeed-entry">
                        <span class="killfeed-killer">{kf['killer']}</span>
                        <span style="color:#1a2030">›</span>
                        <span class="killfeed-victim">{kf['victim']}</span>
                        <span class="killfeed-weapon">{kf['weapon']}</span>
                        {hs}
                    </div>"""
                feed_html += "</div>"
                st.markdown(feed_html, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#2a3448;font-size:12px">No kills this round</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 3 — UTILITY
    # ══════════════════════════════════════════════════════════════════════
    with tab_utility:
        util, round_util, avg_smokes = compute_utility_stats(
            flash_df, he_df, smoke_df, molotov_df, damage_df, kills_df, round_df
        )

        section_header("SUMMARY")
        ucols = st.columns(4)
        for col, (label, val) in zip(ucols, [
            ("Flashbangs", flash_df.shape[0]), ("HE Grenades", he_df.shape[0]),
            ("Smokes", smoke_df.shape[0]),     ("Molotovs", molotov_df.shape[0]),
        ]):
            with col: st.metric(label, val)

        section_header("PER-PLAYER BREAKDOWN")
        util_display = util.copy().rename(columns={
            "flashes_thrown": "Flashes", "flash_assists": "Flash Assists",
            "flash_assist_rate": "Assist/Flash", "he_thrown": "HEs",
            "he_damage": "HE DMG", "he_dmg_per_nade": "DMG/HE",
            "smokes_thrown": "Smokes", "molotovs_thrown": "Molotovs",
            "molotov_damage": "Molotov DMG",
        })
        util_display["Total"] = util_display["Flashes"] + util_display["HEs"] + util_display["Smokes"] + util_display["Molotovs"]
        util_display = util_display.sort_values("Total", ascending=False).drop(columns="Total")
        util_display.index.name = "Player"
        st.dataframe(util_display, use_container_width=True)

        section_header("GRENADE USAGE")
        c1, c2 = st.columns(2)
        with c1:
            nade_fig = go.Figure()
            for col_name, color, label in [
                ("Flashes", COLOR_CT, "Flash"), ("HEs", COLOR_T, "HE"),
                ("Smokes", "#5a6a82", "Smoke"), ("Molotovs", COLOR_RED, "Molotov"),
            ]:
                nade_fig.add_trace(go.Bar(
                    name=label, x=util_display.index.tolist(),
                    y=util_display[col_name].tolist(), marker_color=color,
                ))
            nade_fig.update_layout(**CHART_DEFAULTS, barmode="stack",
                title=dict(text="GRENADES BY PLAYER", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
                height=300)
            st.plotly_chart(nade_fig, use_container_width=True)

        with c2:
            rutil_fig = go.Figure(go.Heatmap(
                z=round_util.T.values, x=[f"R{r}" for r in round_util.index],
                y=["Flash", "HE", "Smoke", "Molotov"],
                colorscale=[[0, "#080b0f"], [0.2, "#0c2a18"], [0.6, "#166534"], [1.0, COLOR_GREEN]],
                text=round_util.T.values, texttemplate="%{text}",
                textfont=dict(family="JetBrains Mono", size=10), showscale=False,
                hovertemplate="Round %{x}  %{y}: %{z}<extra></extra>",
            ))
            rutil_fig.update_layout(**CHART_DEFAULTS,
                title=dict(text="GRENADES PER ROUND", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
                xaxis=dict(**CHART_DEFAULTS["xaxis"], side="top", tickfont=dict(size=9, family="JetBrains Mono", color="#3a4a62")),
                height=300, margin=dict(l=12, r=12, t=48, b=12))
            st.plotly_chart(rutil_fig, use_container_width=True)

        section_header("EFFICIENCY")
        c1, c2 = st.columns(2)
        with c1:
            s = util_display.sort_values("DMG/HE", ascending=True)
            he_fig = go.Figure(go.Bar(
                x=s.index.tolist(), y=s["DMG/HE"].tolist(), marker_color=COLOR_T, opacity=0.8,
                text=s["DMG/HE"].tolist(), textposition="outside",
                textfont=dict(family="JetBrains Mono", size=10, color="#5a6a82"),
            ))
            he_fig.update_layout(**CHART_DEFAULTS,
                title=dict(text="HE DAMAGE PER GRENADE", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
                height=280)
            st.plotly_chart(he_fig, use_container_width=True)

        with c2:
            s = util_display.sort_values("Assist/Flash", ascending=True)
            fl_fig = go.Figure(go.Bar(
                x=s.index.tolist(), y=s["Assist/Flash"].tolist(), marker_color=COLOR_CT, opacity=0.8,
                text=s["Assist/Flash"].tolist(), textposition="outside",
                textfont=dict(family="JetBrains Mono", size=10, color="#5a6a82"),
            ))
            fl_fig.update_layout(**CHART_DEFAULTS,
                title=dict(text="FLASH ASSIST RATE", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
                height=280)
            st.plotly_chart(fl_fig, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 4 — ECONOMY
    # ══════════════════════════════════════════════════════════════════════
    with tab_economy:
        eco_data   = compute_economy(tick_df, round_df)
        team_buys  = eco_data["team_buys_df"]
        win_rates  = eco_data["win_rates"]
        round_econ = eco_data["round_economy"]
        player_eco = eco_data["player_eco"]

        section_header("SUMMARY")
        ecols = st.columns(4)
        for col, (label, val) in zip(ecols, [
            ("Total Spent",      f"${int(player_eco['total_spent'].sum()):,}"),
            ("Avg / Round",      f"${int(player_eco['avg_spent'].mean()):,}"),
            ("Eco Round Wins",   eco_data["eco_wins"]),
            ("Eco Round Losses", eco_data["eco_losses"]),
        ]):
            with col: st.metric(label, val)

        section_header("TEAM EQUIPMENT VALUE")
        eq_fig = go.Figure()
        for team_side, color, label in [("T", COLOR_T, "Terrorist"), ("CT", COLOR_CT, "Counter-Terrorist")]:
            if team_side in round_econ.columns:
                eq_fig.add_trace(go.Scatter(
                    x=round_econ.index.tolist(), y=round_econ[team_side].tolist(),
                    name=label, line=dict(color=color, width=2),
                    mode="lines+markers", marker=dict(size=5, color=color),
                ))
        eq_fig.update_layout(**CHART_DEFAULTS,
            title=dict(text="EQUIPMENT VALUE PER ROUND", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
            xaxis=dict(**CHART_DEFAULTS["xaxis"], title="Round", dtick=1, tickfont=dict(family="JetBrains Mono", size=10)),
            yaxis=dict(**CHART_DEFAULTS["yaxis"], title="$ Value"), height=300)
        st.plotly_chart(eq_fig, use_container_width=True)

        section_header("WIN RATE BY BUY TYPE")
        buy_colors_map = {"Full Buy": COLOR_GREEN, "Half Buy": COLOR_YELLOW, "Force": "#f97316", "Eco": COLOR_RED}
        wr_cols = st.columns(2)
        for i, (team_side, label) in enumerate([("T", "TERRORIST"), ("CT", "COUNTER-TERRORIST")]):
            with wr_cols[i]:
                st.markdown(f'<div style="font-family:\'Barlow Condensed\';font-size:11px;font-weight:700;letter-spacing:0.2em;color:#3a4a62;margin-bottom:8px">{label}</div>', unsafe_allow_html=True)
                try:
                    team_wr = win_rates.loc[team_side].reset_index()
                    team_wr.columns = ["Buy Type", "Rounds", "Wins", "Win Rate"]
                    buy_order = ["Full Buy", "Half Buy", "Force", "Eco"]
                    team_wr["Buy Type"] = pd.Categorical(team_wr["Buy Type"], categories=buy_order, ordered=True)
                    team_wr = team_wr.sort_values("Buy Type")
                    wr_fig = go.Figure(go.Bar(
                        x=team_wr["Buy Type"].tolist(), y=team_wr["Win Rate"].tolist(),
                        marker_color=[buy_colors_map.get(b, "#5a6a82") for b in team_wr["Buy Type"]],
                        opacity=0.8,
                        text=[f"{v}%" for v in team_wr["Win Rate"]], textposition="outside",
                        textfont=dict(family="JetBrains Mono", size=10, color="#5a6a82"),
                    ))
                    wr_fig.update_layout(**CHART_DEFAULTS,
                        yaxis=dict(**CHART_DEFAULTS["yaxis"], range=[0, 115]), height=260)
                    st.plotly_chart(wr_fig, use_container_width=True)
                except KeyError:
                    st.markdown('<div style="color:#2a3448;font-size:12px">No data</div>', unsafe_allow_html=True)

        section_header("BUY TIMELINE")
        bt_fig = go.Figure()
        for team_side, marker_symbol in [("T", "circle"), ("CT", "square")]:
            team_data = team_buys[team_buys["team"] == team_side]
            for buy_type, color in buy_colors_map.items():
                subset = team_data[team_data["buy_type"] == buy_type]
                if not subset.empty:
                    bt_fig.add_trace(go.Scatter(
                        x=subset["round"].tolist(), y=[team_side] * len(subset), mode="markers",
                        marker=dict(symbol=marker_symbol, size=14,
                                   color=[color if w else "#0c1018" for w in subset["won"]],
                                   line=dict(width=2, color=color)),
                        text=[f"R{r}  {bt}  {'WIN' if w else 'LOSS'}" for r, bt, w in
                              zip(subset["round"], subset["buy_type"], subset["won"])],
                        hoverinfo="text", showlegend=False,
                    ))
        for buy_type, color in buy_colors_map.items():
            bt_fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                marker=dict(size=9, color=color), name=buy_type, showlegend=True))
        bt_fig.update_layout(**CHART_DEFAULTS,
            title=dict(text="BUY TYPE PER ROUND  —  filled = win", font=dict(family="Barlow Condensed", size=11, color="#3a4a62"), x=0),
            xaxis=dict(**CHART_DEFAULTS["xaxis"], title="Round", dtick=1, tickfont=dict(family="JetBrains Mono", size=10)),
            height=220)
        st.plotly_chart(bt_fig, use_container_width=True)

        section_header("PER-PLAYER ECONOMY")
        eco_display = player_eco.copy()
        eco_display["total_spent"] = eco_display["total_spent"].apply(lambda x: f"${int(x):,}")
        eco_display["avg_spent"]   = eco_display["avg_spent"].apply(lambda x: f"${int(x):,}")
        eco_display["avg_equip"]   = eco_display["avg_equip"].apply(lambda x: f"${int(x):,}")
        eco_display = eco_display.rename(columns={
            "total_spent": "Total Spent", "avg_spent": "Avg/Round",
            "avg_equip": "Avg Equip", "rounds_played": "Rounds",
            "Full Buy": "Full", "Half Buy": "Half", "Force": "Force", "Eco": "Eco",
        })
        eco_display.index.name = "Player"
        st.dataframe(eco_display, use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════
    # TAB 5 — POSITIONS
    # ══════════════════════════════════════════════════════════════════════
    with tab_heatmap:
        section_header("POSITION HEATMAP")

        hm_cols = st.columns(3)
        with hm_cols[0]:
            hm_mode = st.selectbox("Mode", ["deaths", "kills", "positions"],
                format_func=lambda x: {"deaths": "Deaths", "kills": "Kills", "positions": "Positions"}[x])
        with hm_cols[1]:
            hm_player = st.selectbox("Player", ["All Players"] + stats_sorted.index.tolist())
            player_filter = None if hm_player == "All Players" else hm_player
        with hm_cols[2]:
            floor = st.selectbox("Floor", ["both", "upper", "lower"],
                help="Upper/lower applies to Nuke only")

        with st.spinner("Building heatmap..."):
            map_img_bytes = fetch_map_image(map_name)
            fig_hm = build_position_heatmap(
                pos_df, kills_df, map_name,
                mode=hm_mode, player_filter=player_filter,
                floor_filter=floor, map_img_bytes=map_img_bytes,
            )

        if fig_hm:
            _, hm_center, _ = st.columns([0.2, 3, 0.2])
            with hm_center:
                st.plotly_chart(fig_hm, use_container_width=True)
        else:
            st.markdown('<div style="color:#2a3448;font-size:13px;padding:24px 0">No data for this selection.</div>', unsafe_allow_html=True)
