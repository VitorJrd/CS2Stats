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
from combat import compute_multikills, compute_opening_duels, compute_clutches, compute_weapon_stats
import requests
from PIL import Image

st.set_page_config(
    page_title="CS2 ANALYST",
    page_icon="assets/favicon.ico" if os.path.exists("assets/favicon.ico") else None,
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=IBM+Plex+Mono:wght@300;400;500&family=Saira+Condensed:wght@300;400;600;700;800;900&display=swap');

:root {
    --bg:#050709; --bg1:#090c10; --bg2:#0d1117;
    --border:#1c2730; --border2:#243040;
    --text:#dce8f0; --muted:#3d5060; --muted2:#527080;
    --accent:#e8ff00; --t:#ff3d3d; --ct:#00c2ff;
    --green:#00e676; --red:#ff1744; --yellow:#ffd600;
}
*, *::before, *::after { box-sizing:border-box; }
html, body { background:var(--bg) !important; color:var(--text) !important; font-family:'Rajdhani',sans-serif !important; }

[data-testid="stAppViewContainer"]::before {
    content:""; position:fixed; top:0; left:0; right:0; bottom:0; pointer-events:none; z-index:9999;
    background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.025) 2px,rgba(0,0,0,0.025) 4px);
}
[data-testid="stAppViewContainer"] {
    background:radial-gradient(circle at 15% 15%,rgba(232,255,0,0.025) 0%,transparent 45%),
               radial-gradient(circle at 85% 85%,rgba(0,194,255,0.025) 0%,transparent 45%),
               var(--bg) !important;
}
#MainMenu,footer,header,[data-testid="stToolbar"],[data-testid="stSidebarCollapsedControl"],.stDeployButton{display:none!important;}
[data-testid="stMainBlockContainer"]{padding:0 2.5rem !important;max-width:100% !important;}

.cs2-wordmark{font-family:'Saira Condensed',sans-serif!important;font-weight:900;font-size:21px;letter-spacing:0.25em;text-transform:uppercase;color:#fff;}
.cs2-wordmark .acc{color:var(--accent);}
.cs2-wordmark .pre{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--accent);margin-right:8px;opacity:0.5;}

[data-testid="stTabs"]{gap:0!important;}
[data-testid="stTabsTabList"]{background:transparent!important;border-bottom:1px solid var(--border)!important;gap:0!important;padding:0!important;}
button[data-testid="stTab"]{font-family:'Saira Condensed',sans-serif!important;font-size:13px!important;font-weight:700!important;letter-spacing:0.2em!important;text-transform:uppercase!important;color:var(--muted)!important;background:transparent!important;border:none!important;border-bottom:2px solid transparent!important;padding:14px 24px!important;border-radius:0!important;transition:all 0.2s!important;}
button[data-testid="stTab"]:hover{color:var(--text)!important;background:rgba(232,255,0,0.03)!important;}
button[data-testid="stTab"][aria-selected="true"]{color:var(--accent)!important;border-bottom:2px solid var(--accent)!important;text-shadow:0 0 20px rgba(232,255,0,0.35);}
[data-testid="stTabsContent"]{padding-top:28px!important;background:transparent!important;}

.sh-wrap{display:flex;align-items:center;gap:12px;margin:32px 0 16px;}
.sh-bracket{font-family:'IBM Plex Mono',monospace;font-size:12px;color:var(--accent);opacity:0.5;font-weight:300;}
.sh-title{font-family:'Saira Condensed',sans-serif;font-size:11px;font-weight:700;letter-spacing:0.3em;text-transform:uppercase;color:var(--muted2);white-space:nowrap;}
.sh-line{flex:1;height:1px;background:linear-gradient(90deg,var(--border2) 0%,transparent 100%);}
.sh-num{font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--border2);}

[data-testid="metric-container"]{background:var(--bg1)!important;border:1px solid var(--border)!important;border-radius:0!important;padding:14px 18px!important;position:relative;overflow:hidden;}
[data-testid="metric-container"]::before{content:"";position:absolute;top:0;left:0;width:2px;height:100%;background:var(--accent);opacity:0.4;}
[data-testid="metric-container"]::after{content:"";position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,var(--accent) 0%,transparent 60%);opacity:0.25;}
[data-testid="stMetricLabel"]{font-family:'IBM Plex Mono',monospace!important;font-size:9px!important;font-weight:400!important;letter-spacing:0.2em!important;text-transform:uppercase!important;color:var(--muted)!important;}
[data-testid="stMetricValue"]{font-family:'Saira Condensed',sans-serif!important;font-size:28px!important;font-weight:800!important;color:#fff!important;}

[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:0!important;}
[data-testid="stDataFrame"] th{background:var(--bg1)!important;font-family:'IBM Plex Mono',monospace!important;font-size:9px!important;font-weight:500!important;letter-spacing:0.18em!important;text-transform:uppercase!important;color:var(--muted)!important;}
[data-testid="stDataFrame"] td{font-family:'IBM Plex Mono',monospace!important;font-size:11px!important;color:var(--text)!important;background:var(--bg)!important;}

[data-testid="stSelectbox"] label,[data-testid="stSlider"] label{font-family:'IBM Plex Mono',monospace!important;font-size:9px!important;font-weight:500!important;letter-spacing:0.2em!important;text-transform:uppercase!important;color:var(--muted)!important;}
[data-testid="stSelectbox"] > div > div{background:var(--bg1)!important;border:1px solid var(--border)!important;border-radius:0!important;color:var(--text)!important;font-family:'Rajdhani',sans-serif!important;font-size:14px!important;}
[data-testid="stFileUploader"]{border:1px solid var(--border)!important;border-radius:0!important;background:var(--bg1)!important;padding:6px 12px!important;}
[data-testid="stFileUploader"]:hover{border-color:var(--accent)!important;}
[data-testid="stFileUploader"] label{font-family:'IBM Plex Mono',monospace!important;font-size:9px!important;letter-spacing:0.15em!important;text-transform:uppercase!important;color:var(--muted)!important;}

.js-plotly-plot,.plotly{border-radius:0!important;}
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border2);}

.rr{padding:14px 18px;border-left:2px solid;margin-bottom:16px;background:var(--bg1);}
.rr.t-win{border-color:var(--t);background:rgba(255,61,61,0.06);}
.rr.ct-win{border-color:var(--ct);background:rgba(0,194,255,0.06);}
.rr-label{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:0.2em;text-transform:uppercase;color:var(--muted);margin-bottom:6px;}
.rr-winner{font-family:'Saira Condensed',sans-serif;font-size:22px;font-weight:800;letter-spacing:0.05em;text-transform:uppercase;}
.rr-reason{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted);margin-top:4px;}

@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}
.hero-wrap{text-align:center;padding:80px 40px 48px;animation:fadeUp 0.5s ease both;}
.hero-pre{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:0.4em;text-transform:uppercase;color:var(--accent);margin-bottom:16px;animation:blink 3s 1s infinite;}
.hero-title{font-family:'Saira Condensed',sans-serif;font-size:76px;font-weight:900;letter-spacing:0.1em;text-transform:uppercase;color:#fff;line-height:0.9;margin-bottom:4px;}
.hero-title .acc{color:var(--accent);text-shadow:0 0 40px rgba(232,255,0,0.25);}
.hero-sub{font-family:'IBM Plex Mono',monospace;font-size:10px;color:var(--muted2);margin-bottom:48px;letter-spacing:0.08em;}
.hero-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;max-width:700px;margin:0 auto;background:var(--border);border:1px solid var(--border);}
.hero-cell{background:var(--bg1);padding:20px 22px;text-align:left;transition:background 0.2s;}
.hero-cell:hover{background:var(--bg2);}
.hero-cell:hover .hcn{color:var(--accent);}
.hcn{font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--border2);letter-spacing:0.1em;margin-bottom:8px;transition:color 0.2s;}
.hct{font-family:'Saira Condensed',sans-serif;font-size:15px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:var(--text);margin-bottom:4px;}
.hcd{font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);line-height:1.6;}
</style>
""", unsafe_allow_html=True)

CHART_DEFAULTS = dict(
    paper_bgcolor="#050709",
    plot_bgcolor="#090c10",
    font=dict(family="IBM Plex Mono, monospace", color="#3d5060", size=10),
    margin=dict(l=12, r=12, t=36, b=12),
    xaxis=dict(gridcolor="#0d1520", linecolor="#1c2730", tickcolor="#1c2730", zerolinecolor="#1c2730"),
    yaxis=dict(gridcolor="#0d1520", linecolor="#1c2730", tickcolor="#1c2730", zerolinecolor="#1c2730"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1c2730", font=dict(size=10, color="#3d5060")),
)

ACCENT       = "#e8ff00"
COLOR_T      = "#ff3d3d"
COLOR_CT     = "#00c2ff"
COLOR_GREEN  = "#00e676"
COLOR_RED    = "#ff1744"
COLOR_YELLOW = "#ffd600"

def chart_layout(**overrides):
    """Merge CHART_DEFAULTS with overrides, safely handling xaxis/yaxis."""
    base = {k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")}
    result = {**base, **overrides}
    if "xaxis" not in result:
        result["xaxis"] = CHART_DEFAULTS["xaxis"]
    if "yaxis" not in result:
        result["yaxis"] = CHART_DEFAULTS["yaxis"]
    return result

def hex_to_rgba(hex_color, alpha=0.13):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def rating_color(val):
    if val >= 1.3:   return COLOR_GREEN
    elif val >= 1.1: return "#69f0ae"
    elif val >= 0.9: return COLOR_YELLOW
    elif val >= 0.7: return "#f97316"
    else:            return COLOR_RED

_sh_counter = [0]
def section_header(title):
    _sh_counter[0] += 1
    n = str(_sh_counter[0]).zfill(2)
    st.markdown(
        f'<div class="sh-wrap">' +
        '<span class="sh-bracket">[</span>' +
        f'<span class="sh-title">{title}</span>' +
        '<span class="sh-bracket">]</span>' +
        '<div class="sh-line"></div>' +
        f'<span class="sh-num">{n}</span>' +
        '</div>',
        unsafe_allow_html=True
    )

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

def build_stats_table(stats):
    fig = go.Figure(data=[go.Table(
        columnwidth=[160, 55, 55, 55, 65, 65, 70, 70, 80],
        header=dict(
            values=["PLAYER", "K", "D", "A", "K/D", "HS%", "ADR", "KAST%", "RATING"],
            fill_color="#090c10",
            font=dict(family="Saira Condensed, sans-serif", color="#3d5060", size=11),
            align=["left"] + ["center"] * 8, height=32,
            line=dict(color="#1c2730", width=1),
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
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                ["#050709"] * len(stats),
                [hex_to_rgba(rating_color(v)) for v in stats["Rating"]],
            ],
            font=dict(
                family=["Barlow, sans-serif"] + ["JetBrains Mono, monospace"] * 8,
                color=["#dce8f0"] + ["#7090a8"] * 7 + [[rating_color(v) for v in stats["Rating"]]],
                size=12,
            ),
            align=["left"] + ["center"] * 8, height=30,
            line=dict(color="#0d1520", width=1),
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
        textfont=dict(family="IBM Plex Mono", size=11, color="#527080"),
    ))
    fig.add_vline(x=1.0, line_dash="dot", line_color="#1c2730", line_width=1,
                  annotation_text="1.000", annotation_font=dict(color="#243040", size=10))
    base = {k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")}
    fig.update_layout(
        **base,
        xaxis=dict(**CHART_DEFAULTS["xaxis"], range=[0, max(stats["Rating"]) + 0.25]),
        yaxis=dict(**CHART_DEFAULTS["yaxis"]),
        title=dict(text="PLAYER RATING", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
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
        textfont=dict(family="Saira Condensed", size=12, color="#7090a8"),
        marker=dict(line=dict(width=1, color="#090c10")),
    )
    fig.update_layout(
        **CHART_DEFAULTS,
        title=dict(text="ADR vs KAST  —  bubble = kills", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
        coloraxis_colorbar=dict(
            title=dict(text="RTG", font=dict(size=10, color="#3d5060")),
            tickfont=dict(size=9, color="#3d5060", family="IBM Plex Mono"),
            bgcolor="#090c10", bordercolor="#1c2730", thickness=10,
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
        line=dict(color="#1c2730", width=1), fillcolor="rgba(13,17,23,0.5)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=vp + [vp[0]], theta=cats + [cats[0]], fill="toself", name=player,
        line=dict(color=ACCENT, width=2), fillcolor="rgba(232,255,0,0.08)",
    ))
    fig.update_layout(
        **{k: v for k, v in CHART_DEFAULTS.items() if k in ["paper_bgcolor", "font", "legend"]},
        polar=dict(
            bgcolor="#090c10",
            radialaxis=dict(visible=True, range=[0, 1], gridcolor="#0d1520",
                           tickfont=dict(size=9, color="#243040"), showticklabels=False),
            angularaxis=dict(gridcolor="#1c2730", tickfont=dict(family="Saira Condensed", size=12, color="#527080")),
        ),
        margin=dict(l=40, r=40, t=40, b=40), height=340,
    )
    return fig

nav_left, nav_right = st.columns([3, 2])
with nav_left:
    st.markdown(
        '<div style="padding-top:16px">'
        '<span class="cs2-wordmark"><span class="pre">//</span>CS2<span class="acc">ANALYST</span></span>'
        '<span style="font-family:IBM Plex Mono,monospace;font-size:9px;color:#1c2730;margin-left:20px;letter-spacing:0.2em">v2.0 // TACTICAL INTELLIGENCE PLATFORM</span>'
        '</div>',
        unsafe_allow_html=True
    )
with nav_right:
    uploaded = st.file_uploader("Upload .dem", type=["dem"], label_visibility="collapsed", key="demo_upload")

st.markdown(
    '<div style="height:1px;background:linear-gradient(90deg,#e8ff00 0%,#1c2730 35%,transparent 100%);'
    'margin-bottom:28px;box-shadow:0 0 10px rgba(232,255,0,0.15)"></div>',
    unsafe_allow_html=True
)

if uploaded is None:
    features = [
        ("01","Performance","K/D/A, ADR, KAST%, HLTV Rating 2.0"),
        ("02","Round Data","Kill heatmap, timeline, kill feed"),
        ("03","Utility","Flash, HE, smoke, molotov efficiency"),
        ("04","Economy","Buy types, win rates, team equity"),
        ("05","Positions","Kill and death heatmaps on radar"),
        ("06","Combat","Clutches, opening duels, multi-kills"),
    ]
    cells = "".join(
        f'<div class="hero-cell"><div class="hcn">{n}</div><div class="hct">{t}</div><div class="hcd">{d}</div></div>'
        for n, t, d in features
    )
    st.markdown(
        '<div class="hero-wrap">'
        '<div class="hero-pre">&#9632; &nbsp; tactical demo analysis platform &nbsp; &#9632;</div>'
        '<div class="hero-title">CS2<span class="acc">ANALYST</span></div>'
        '<div class="hero-sub">// drop a .dem file above to load match data</div>'
        f'<div class="hero-grid">{cells}</div>'
        '</div>',
        unsafe_allow_html=True
    )

else:
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

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1: st.metric("Map", map_display)
    with mc2: st.metric("Rounds", d["total_rounds"])
    with mc3: st.metric("T Wins", d["t_wins"])
    with mc4: st.metric("CT Wins", d["ct_wins"])
    with mc5:
        top_player = stats["Rating"].idxmax()
        st.metric("Rating MVP", f"{top_player}  {stats.loc[top_player,'Rating']:.3f}")

    tab_overview, tab_rounds, tab_utility, tab_economy, tab_heatmap = st.tabs([
        "OVERVIEW", "ROUNDS", "UTILITY", "ECONOMY", "POSITIONS",
    ])

    with tab_overview:
        section_header("SCOREBOARD")
        st.plotly_chart(build_stats_table(stats_sorted), use_container_width=True)

        section_header("PERFORMANCE")
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(build_rating_bar(stats), use_container_width=True)
        with c2: st.plotly_chart(build_adr_scatter(stats), use_container_width=True)

        section_header("MULTI-KILL ROUNDS")
        mk_data = compute_multikills(kills_df, round_df)
        mk_summary = mk_data["summary"]

        if not mk_summary.empty:
            mk_cols = st.columns([2, 3])
            with mk_cols[0]:
                mk_display = mk_summary.copy()
                mk_display.index.name = "Player"
                st.dataframe(mk_display, use_container_width=True)

            with mk_cols[1]:
                mk_fig = go.Figure()
                colors = {"3K": COLOR_YELLOW, "4K": "#f97316", "ACE": COLOR_RED}
                for label, color in colors.items():
                    if label in mk_summary.columns:
                        mk_fig.add_trace(go.Bar(
                            name=label,
                            x=mk_summary.index.tolist(),
                            y=mk_summary[label].tolist(),
                            marker_color=color, opacity=0.85,
                        ))
                mk_fig.update_layout(
                    **CHART_DEFAULTS, barmode="stack",
                    title=dict(text="MULTI-KILL ROUNDS BY PLAYER", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                    height=300,
                )
                st.plotly_chart(mk_fig, use_container_width=True)
        else:
            st.markdown('<div style="color:#2a3448;font-size:12px;padding:12px 0">No multi-kill rounds found.</div>', unsafe_allow_html=True)

        section_header("WEAPON BREAKDOWN")
        wpn_data   = compute_weapon_stats(kills_df)
        by_weapon  = wpn_data["by_weapon"]
        by_player  = wpn_data["by_player"]

        if not by_weapon.empty:
            wpn_cols = st.columns([1, 2])
            with wpn_cols[0]:
                top_wpn = by_weapon.head(12).copy()
                wpn_fig = go.Figure(go.Bar(
                    x=top_wpn["kills"], y=top_wpn["weapon"],
                    orientation="h",
                    marker=dict(color=COLOR_CT, opacity=0.8),
                    text=top_wpn["kills"], textposition="outside",
                    textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                    customdata=top_wpn["hs_pct"],
                    hovertemplate="<b>%{y}</b><br>Kills: %{x}<br>HS%: %{customdata}%<extra></extra>",
                ))
                wpn_fig.update_layout(
                    **{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")},
                    title=dict(text="TOP WEAPONS (TOTAL KILLS)", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                    yaxis=dict(**CHART_DEFAULTS["yaxis"], autorange="reversed"),
                    height=340,
                )
                st.plotly_chart(wpn_fig, use_container_width=True)

            with wpn_cols[1]:
                wpn_player = st.selectbox(
                    "Player weapon breakdown",
                    options=stats_sorted.index.tolist(),
                    label_visibility="collapsed",
                    key="wpn_player",
                )
                if wpn_player and wpn_player in by_player:
                    pw = by_player[wpn_player].head(10)
                    pw_fig = go.Figure()
                    pw_fig.add_trace(go.Bar(
                        name="Kills", x=pw["weapon"], y=pw["kills"],
                        marker_color=COLOR_CT, opacity=0.85,
                        text=pw["kills"], textposition="outside",
                        textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                    ))
                    pw_fig.add_trace(go.Bar(
                        name="HS", x=pw["weapon"], y=pw["hs"],
                        marker_color=ACCENT, opacity=0.7,
                        text=pw["hs"], textposition="outside",
                        textfont=dict(family="IBM Plex Mono", size=10, color=ACCENT),
                    ))
                    pw_fig.update_layout(
                        **CHART_DEFAULTS, barmode="overlay",
                        title=dict(text=f"{wpn_player.upper()}  —  KILLS & HEADSHOTS PER WEAPON",
                                   font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                        height=340,
                    )
                    st.plotly_chart(pw_fig, use_container_width=True)

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
                with col: st.metric(label, val)
            st.plotly_chart(build_radar(stats, selected), use_container_width=True)

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
            colorscale=[[0, "#050709"], [0.01, "#0c2a18"], [0.4, "#166534"], [1.0, COLOR_GREEN]],
            showscale=False, text=kills_matrix.values, texttemplate="%{text}",
            textfont=dict(family="IBM Plex Mono", size=11),
            hovertemplate="<b>%{y}</b>  Round %{x}  Kills: %{z}<extra></extra>",
            zmin=0, zmax=4,
        ))
        fig_heatmap.update_layout(
            **{k: v for k, v in CHART_DEFAULTS.items() if k in ["paper_bgcolor", "plot_bgcolor", "font"]},
            xaxis=dict(side="top", tickfont=dict(size=9, family="IBM Plex Mono", color="#3d5060"),
                       tickcolor="#1c2730", linecolor="#1c2730", gridcolor="#0d1520"),
            yaxis=dict(tickfont=dict(size=12, family="Saira Condensed", color="#7090a8"),
                       tickcolor="#1c2730", linecolor="#1c2730", gridcolor="#0d1520"),
            margin=dict(l=0, r=0, t=48, b=0),
            height=38 * len(player_order) + 60,
        )
        st.plotly_chart(fig_heatmap, use_container_width=True)

        section_header("OPENING DUELS")
        od_data   = compute_opening_duels(kills_df, round_df)
        od_summary = od_data["summary"]
        od_rounds  = od_data["per_round"]

        if not od_summary.empty:
            od_c1, od_c2 = st.columns(2)
            with od_c1:
                od_plot = od_summary.reset_index()
                od_fig = go.Figure()
                od_fig.add_trace(go.Bar(
                    name="Opening Kills", x=od_plot["Player"], y=od_plot["opens"],
                    marker_color=COLOR_GREEN, opacity=0.85,
                    text=od_plot["opens"], textposition="outside",
                    textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                ))
                od_fig.add_trace(go.Bar(
                    name="Opening Deaths", x=od_plot["Player"], y=od_plot["open_deaths"],
                    marker_color=COLOR_RED, opacity=0.75,
                    text=od_plot["open_deaths"], textposition="outside",
                    textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                ))
                od_fig.update_layout(
                    **CHART_DEFAULTS, barmode="group",
                    title=dict(text="OPENING KILLS vs OPENING DEATHS", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                    height=300,
                )
                st.plotly_chart(od_fig, use_container_width=True)

            with od_c2:
                od_wr = od_summary[od_summary["opens"] > 0].reset_index()
                wr_fig = go.Figure(go.Bar(
                    x=od_wr["Player"], y=od_wr["open_win_rate"],
                    marker_color=[COLOR_GREEN if v >= 50 else COLOR_RED for v in od_wr["open_win_rate"]],
                    opacity=0.85,
                    text=[f"{v}%" for v in od_wr["open_win_rate"]], textposition="outside",
                    textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                ))
                wr_fig.add_hline(y=50, line_dash="dot", line_color="#1c2730", line_width=1)
                wr_fig.update_layout(
                    **{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")},
                    title=dict(text="ROUND WIN RATE AFTER OPENING KILL", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                    yaxis=dict(**CHART_DEFAULTS["yaxis"], range=[0, 115]),
                    height=300,
                )
                st.plotly_chart(wr_fig, use_container_width=True)

            od_display = od_summary.copy().rename(columns={
                "opens": "Opening Kills", "open_deaths": "Opening Deaths",
                "open_round_wins": "Round Wins", "open_win_rate": "Win Rate %",
                "rating": "+/−",
            })
            od_display.index.name = "Player"
            st.dataframe(od_display[["Opening Kills", "Opening Deaths", "+/−", "Round Wins", "Win Rate %"]],
                         use_container_width=True)

        section_header("CLUTCH SITUATIONS")
        cl_data    = compute_clutches(kills_df, round_df, spawn_df)
        cl_summary = cl_data["summary"]
        cl_rounds  = cl_data["clutches"]

        if not cl_summary.empty:
            cl_c1, cl_c2 = st.columns(2)
            with cl_c1:
                cl_plot = cl_summary.reset_index()
                cl_fig = go.Figure()
                cl_fig.add_trace(go.Bar(
                    name="Won", x=cl_plot["Player"], y=cl_plot["won"],
                    marker_color=COLOR_GREEN, opacity=0.85,
                ))
                cl_fig.add_trace(go.Bar(
                    name="Lost", x=cl_plot["Player"], y=cl_plot["lost"],
                    marker_color=COLOR_RED, opacity=0.75,
                ))
                cl_fig.update_layout(
                    **CHART_DEFAULTS, barmode="stack",
                    title=dict(text="CLUTCH WINS vs LOSSES", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                    height=280,
                )
                st.plotly_chart(cl_fig, use_container_width=True)

            with cl_c2:
                vs_cols = [c for c in cl_summary.columns if c.startswith("1v")]
                if vs_cols:
                    scenario_totals = cl_summary[vs_cols].sum()
                    sc_fig = go.Figure(go.Bar(
                        x=scenario_totals.index.tolist(),
                        y=scenario_totals.values.tolist(),
                        marker_color=[COLOR_CT, COLOR_T, COLOR_RED][:len(vs_cols)],
                        opacity=0.85,
                        text=scenario_totals.values.tolist(), textposition="outside",
                        textfont=dict(family="IBM Plex Mono", size=11, color="#527080"),
                    ))
                    sc_fig.update_layout(
                        **CHART_DEFAULTS,
                        title=dict(text="CLUTCH SCENARIOS (ALL PLAYERS)", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                        height=280,
                    )
                    st.plotly_chart(sc_fig, use_container_width=True)

            cl_display = cl_summary.copy().rename(columns={"won": "Won", "lost": "Lost", "win_rate": "Win Rate %"})
            cl_display.index.name = "Player"
            st.dataframe(cl_display, use_container_width=True)

        else:
            st.markdown('<div style="color:#2a3448;font-size:12px;padding:12px 0">No clutch situations detected.</div>', unsafe_allow_html=True)

        section_header("ROUND BREAKDOWN")
        round_nums     = [r["round"] for r in timeline]
        selected_round = st.select_slider("Round", options=round_nums, label_visibility="collapsed")
        round_data     = next(r for r in timeline if r["round"] == selected_round)

        winner    = round_data["winner"] or "?"
        reason    = (round_data["reason"] or "unknown").replace("_", " ").upper()
        win_class = "rr t-win" if winner == "T" else "rr ct-win"
        win_color = COLOR_T if winner == "T" else COLOR_CT
        win_label = "TERRORIST WIN" if winner == "T" else "CT WIN"

        if not od_rounds.empty and selected_round in od_rounds["round"].values:
            opener_row = od_rounds[od_rounds["round"] == selected_round].iloc[0]
            impact_color = COLOR_GREEN if opener_row["opener_won_round"] else COLOR_RED
            impact_text  = "ROUND WIN" if opener_row["opener_won_round"] else "ROUND LOSS"
            st.markdown(f"""
            <div style="background:#0c1018;border:1px solid #1a2030;border-radius:3px;
                        padding:10px 14px;margin-bottom:14px;display:flex;gap:16px;align-items:center">
                <div style="font-size:10px;font-weight:700;letter-spacing:0.18em;
                            text-transform:uppercase;color:
                <div style="font-family:'Saira Condensed';font-size:15px;font-weight:700;color:#4a9eff">
                    {opener_row['opener']}</div>
                <div style="color:#1a2030">›</div>
                <div style="font-family:'Saira Condensed';font-size:15px;font-weight:700;color:#ff5555">
                    {opener_row['victim']}</div>
                <div style="margin-left:auto;font-family:'IBM Plex Mono';font-size:11px;
                            font-weight:700;color:{impact_color}">{impact_text}</div>
            </div>""", unsafe_allow_html=True)

        rcols = st.columns([1, 1, 1])
        with rcols[0]:
            st.markdown(f"""
            <div class="{win_class}">
                <div class="rr-label">Round {selected_round}</div>
                <div class="rr-winner" style="color:{win_color}">{win_label}</div>
                <div class="rr-reason">{reason}</div>
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
            WEAPON_NAMES = {
                "ak47": "AK-47", "m4a1": "M4A1-S", "m4a1_silencer": "M4A1-S",
                "m4a4": "M4A4", "awp": "AWP", "deagle": "Desert Eagle",
                "usp_silencer": "USP-S", "glock": "Glock-18", "p250": "P250",
                "tec9": "Tec-9", "fiveseven": "Five-SeveN", "cz75a": "CZ75-Auto",
                "p2000": "P2000", "revolver": "R8 Revolver", "hkp2000": "P2000",
                "mp9": "MP9", "mp7": "MP7", "mp5sd": "MP5-SD", "mac10": "MAC-10",
                "ump45": "UMP-45", "p90": "P90", "bizon": "PP-Bizon",
                "famas": "FAMAS", "galilar": "Galil AR", "sg556": "SG 553",
                "aug": "AUG", "ssg08": "SSG 08", "g3sg1": "G3SG1", "scar20": "SCAR-20",
                "xm1014": "XM1014", "mag7": "MAG-7", "nova": "Nova", "sawedoff": "Sawed-Off",
                "m249": "M249", "negev": "Negev",
                "knife": "Knife", "knife_t": "Knife", "bayonet": "Knife",
                "stiletto": "Knife", "talon": "Knife", "ursus": "Knife",
                "flashbang": "Flashbang", "hegrenade": "HE Grenade",
                "smokegrenade": "Smoke", "molotov": "Molotov", "incgrenade": "Incendiary",
            }
            S_ENTRY  = "display:flex;align-items:center;gap:8px;padding:7px 12px;border-bottom:1px solid #0f1520;font-size:13px;font-family:Barlow,sans-serif;"
            S_KILLER = "color:#4a9eff;font-weight:600;"
            S_VICTIM = "color:#ff5555;font-weight:600;"
            S_WEAPON = "color:#3a4a62;font-size:11px;font-family:IBM Plex Mono,monospace;"
            S_HS     = "color:#f0b429;font-size:10px;font-weight:700;letter-spacing:0.1em;margin-left:4px;"
            S_ARROW  = "color:#2a3448;"
            if round_data["kill_feed"]:
                feed_html = '<div style="background:#0c1018;border:1px solid #1a2030;border-radius:3px">'
                for kf in round_data["kill_feed"]:
                    wpn_raw  = (kf["weapon"] or "").lower()
                    wpn_disp = WEAPON_NAMES.get(wpn_raw, wpn_raw.replace("_", " ").title())
                    hs_html  = f'<span style="{S_HS}">HS</span>' if kf["headshot"] else ""
                    feed_html += (
                        f'<div style="{S_ENTRY}">'
                        f'<span style="{S_KILLER}">{kf["killer"]}</span>'
                        f'<span style="{S_ARROW}">&#8250;</span>'
                        f'<span style="{S_VICTIM}">{kf["victim"]}</span>'
                        f'<span style="{S_WEAPON}">{wpn_disp}</span>'
                        + hs_html + '</div>'
                    )
                feed_html += "</div>"
                st.markdown(feed_html, unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#2a3448;font-size:12px">No kills this round</div>', unsafe_allow_html=True)

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
                ("Smokes", "#527080", "Smoke"), ("Molotovs", COLOR_RED, "Molotov"),
            ]:
                nade_fig.add_trace(go.Bar(
                    name=label, x=util_display.index.tolist(),
                    y=util_display[col_name].tolist(), marker_color=color,
                ))
            nade_fig.update_layout(**CHART_DEFAULTS, barmode="stack",
                title=dict(text="GRENADES BY PLAYER", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                height=300)
            st.plotly_chart(nade_fig, use_container_width=True)

        with c2:
            rutil_fig = go.Figure(go.Heatmap(
                z=round_util.T.values, x=[f"R{r}" for r in round_util.index],
                y=["Flash", "HE", "Smoke", "Molotov"],
                colorscale=[[0, "#050709"], [0.2, "#051a09"], [0.6, "#0a3518"], [1.0, COLOR_GREEN]],
                text=round_util.T.values, texttemplate="%{text}",
                textfont=dict(family="IBM Plex Mono", size=10), showscale=False,
                hovertemplate="Round %{x}  %{y}: %{z}<extra></extra>",
            ))
            rutil_fig.update_layout(**{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis", "margin")},
                title=dict(text="GRENADES PER ROUND", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                xaxis=dict(**CHART_DEFAULTS["xaxis"], side="top", tickfont=dict(size=9, family="IBM Plex Mono", color="#3d5060")),
                height=300, margin=dict(l=12, r=12, t=48, b=12))
            st.plotly_chart(rutil_fig, use_container_width=True)

        section_header("EFFICIENCY")
        c1, c2 = st.columns(2)
        with c1:
            s = util_display.sort_values("DMG/HE", ascending=True)
            he_fig = go.Figure(go.Bar(
                x=s.index.tolist(), y=s["DMG/HE"].tolist(), marker_color=COLOR_T, opacity=0.8,
                text=s["DMG/HE"].tolist(), textposition="outside",
                textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
            ))
            he_fig.update_layout(**CHART_DEFAULTS,
                title=dict(text="HE DAMAGE PER GRENADE", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                height=280)
            st.plotly_chart(he_fig, use_container_width=True)

        with c2:
            s = util_display.sort_values("Assist/Flash", ascending=True)
            fl_fig = go.Figure(go.Bar(
                x=s.index.tolist(), y=s["Assist/Flash"].tolist(), marker_color=COLOR_CT, opacity=0.8,
                text=s["Assist/Flash"].tolist(), textposition="outside",
                textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
            ))
            fl_fig.update_layout(**CHART_DEFAULTS,
                title=dict(text="FLASH ASSIST RATE", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
                height=280)
            st.plotly_chart(fl_fig, use_container_width=True)

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
        eq_fig.update_layout(**{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")},
            title=dict(text="EQUIPMENT VALUE PER ROUND", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
            xaxis=dict(**CHART_DEFAULTS["xaxis"], title="Round", dtick=1, tickfont=dict(family="IBM Plex Mono", size=10)),
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
                        marker_color=[buy_colors_map.get(b, "#527080") for b in team_wr["Buy Type"]],
                        opacity=0.8,
                        text=[f"{v}%" for v in team_wr["Win Rate"]], textposition="outside",
                        textfont=dict(family="IBM Plex Mono", size=10, color="#527080"),
                    ))
                    wr_fig.update_layout(**{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")},
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
                                   color=[color if w else "#090c10" for w in subset["won"]],
                                   line=dict(width=2, color=color)),
                        text=[f"R{r}  {bt}  {'WIN' if w else 'LOSS'}" for r, bt, w in
                              zip(subset["round"], subset["buy_type"], subset["won"])],
                        hoverinfo="text", showlegend=False,
                    ))
        for buy_type, color in buy_colors_map.items():
            bt_fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                marker=dict(size=9, color=color), name=buy_type, showlegend=True))
        bt_fig.update_layout(**{k: v for k, v in CHART_DEFAULTS.items() if k not in ("xaxis", "yaxis")},
            title=dict(text="BUY TYPE PER ROUND  —  filled = win", font=dict(family="Saira Condensed", size=11, color="#3d5060"), x=0),
            xaxis=dict(**CHART_DEFAULTS["xaxis"], title="Round", dtick=1, tickfont=dict(family="IBM Plex Mono", size=10)),
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