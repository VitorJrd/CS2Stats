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

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CS2 Stats Analyzer",
    page_icon="🎯",
    layout="wide"
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: #1e2530;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .metric-label { color: #8b9cbe; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #e0e6f0; font-size: 28px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# -- Fetching images 
@st.cache_data
def fetch_map_image(map_name: str):
    """Fetch map radar image with Streamlit's network access."""
    urls = [
        f"https://radar-overviews.cs2.app/{map_name}.png",
        f"https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/{map_name}.png",
        f"https://cdn.rawgit.com/zifnab87/cs-go-map-images/master/{map_name}.png",
    ]
    for url in urls:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            continue
    return None


# ── Parsing & Stats ───────────────────────────────────────────────────────────
@st.cache_data
def parse_and_compute(dem_bytes: bytes):
    # Write to temp file (demoparser2 needs a file path)
    with tempfile.NamedTemporaryFile(suffix=".dem", delete=False) as f:
        f.write(dem_bytes)
        tmp_path = f.name

    try:
        parser = DemoParser(tmp_path)
        _, kills_df  = parser.parse_events(["player_death"])[0]
        _, damage_df = parser.parse_events(["player_hurt"])[0]
        _, round_df  = parser.parse_events(["round_end"])[0]
        _, spawn_df  = parser.parse_events(["player_spawn"])[0]
        _, flash_df   = parser.parse_events(["flashbang_detonate"])[0]
        _, he_df      = parser.parse_events(["hegrenade_detonate"])[0]
        _, smoke_df   = parser.parse_events(["smokegrenade_detonate"])[0]
        _, molotov_df = parser.parse_events(["inferno_startburn"])[0]
        _, freeze_df = parser.parse_events(["round_freeze_end"])[0]
        freeze_ticks = sorted(freeze_df["tick"].tolist())
        tick_df = parser.parse_ticks(
            ["current_equip_value", "cash_spent_this_round", "total_cash_spent", "cash", "team_name"],
            ticks=freeze_ticks
        )
        all_ticks = list(range(0, 200000, 640))  # every ~10s
        pos_df = parser.parse_ticks(
            ["X", "Y", "Z", "team_name", "is_alive"],
            ticks=all_ticks
        )
        header = parser.parse_header()
        map_name = header.get("map_name", "de_nuke")

    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass  # If deletion fails on Windows, just leave it — temp files are cleaned on reboot

    total_rounds = round_df[round_df["round"] > 0].shape[0]

    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_per_player   = kills_clean.groupby("attacker_name").size().rename("kills")
    deaths_per_player  = kills_clean.groupby("user_name").size().rename("deaths")
    hs_per_player      = kills_clean[kills_clean["headshot"] == True].groupby("attacker_name").size().rename("headshots")
    assists_per_player = (
        kills_df[kills_df["assister_name"].notna()]
        .groupby("assister_name").size().rename("assists")
    )
    damage_clean = damage_df[
        damage_df["attacker_name"].notna() &
        (damage_df["attacker_name"] != damage_df["user_name"])
    ].copy()
    damage_per_player = damage_clean.groupby("attacker_name")["dmg_health"].sum().rename("total_damage")

    all_players = set(kills_per_player.index) | set(deaths_per_player.index)
    stats = pd.DataFrame(index=sorted(all_players))
    stats = stats.join(kills_per_player).join(deaths_per_player).join(hs_per_player).join(assists_per_player).join(damage_per_player)
    stats = stats.fillna(0).astype(int)

    stats["K/D"]    = (stats["kills"] / stats["deaths"].replace(0, 1)).round(2)
    stats["HS%"]    = ((stats["headshots"] / stats["kills"].replace(0, 1)) * 100).round(1)
    stats["ADR"]    = (stats["total_damage"] / total_rounds).round(1)

    kast_pct, _ = compute_kast(kills_df, round_df, spawn_df)
    stats["KAST%"]  = stats.index.map(lambda p: kast_pct.get(p, 0.0))
    stats["Rating"] = compute_rating(stats, kills_df, round_df)

    return stats, total_rounds, kills_df, damage_df, round_df, spawn_df, flash_df, he_df, smoke_df, molotov_df, tick_df, pos_df, map_name


def rating_color(val):
    if val >= 1.3:   return "#00ff88"
    elif val >= 1.1: return "#7fff7f"
    elif val >= 0.9: return "#ffd700"
    elif val >= 0.7: return "#ff9933"
    else:            return "#ff4444"


def build_stats_table(stats):
    fig = go.Figure(data=[go.Table(
        columnwidth=[140, 60, 60, 60, 70, 70, 70, 70, 80],
        header=dict(
            values=["<b>Player</b>","<b>K</b>","<b>D</b>","<b>A</b>",
                    "<b>K/D</b>","<b>HS%</b>","<b>ADR</b>","<b>KAST%</b>","<b>Rating</b>"],
            fill_color="#1a2332",
            font=dict(color="#a0b4cc", size=13),
            align="center",
            height=36,
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
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                ["#141920"] * len(stats),
                [rating_color(v) for v in stats["Rating"]],
            ],
            font=dict(color="#dce6f0", size=13),
            align="center",
            height=32,
        )
    )])
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#0e1117",
        height=36 + 32 * len(stats) + 20,
    )
    return fig


def build_rating_bar(stats):
    sorted_stats = stats.sort_values("Rating")
    colors = [rating_color(v) for v in sorted_stats["Rating"]]
    fig = go.Figure(go.Bar(
        x=sorted_stats["Rating"],
        y=sorted_stats.index,
        orientation="h",
        marker_color=colors,
        text=[f"{v:.3f}" for v in sorted_stats["Rating"]],
        textposition="outside",
    ))
    fig.add_vline(x=1.0, line_dash="dash", line_color="#666", annotation_text="Avg (1.0)")
    fig.update_layout(
        title="Player Ratings",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(gridcolor="#2a3444", range=[0, max(stats["Rating"]) + 0.2]),
        yaxis=dict(gridcolor="#2a3444"),
        margin=dict(l=10, r=60, t=40, b=10),
        height=350,
    )
    return fig


def build_radar(stats, player):
    row = stats.loc[player]
    avg = stats.mean()

    # Normalize each stat 0-1 relative to match max
    def norm(col): return row[col] / stats[col].max() if stats[col].max() > 0 else 0

    categories = ["Kills", "ADR", "KAST%", "HS%", "K/D", "Rating"]
    values_player = [norm("kills"), norm("ADR"), norm("KAST%"), norm("HS%"), norm("K/D"), norm("Rating")]
    values_avg    = [
        avg["kills"] / stats["kills"].max(),
        avg["ADR"]   / stats["ADR"].max(),
        avg["KAST%"] / stats["KAST%"].max(),
        avg["HS%"]   / stats["HS%"].max(),
        avg["K/D"]   / stats["K/D"].max(),
        avg["Rating"]/ stats["Rating"].max(),
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=values_avg + [values_avg[0]], theta=categories + [categories[0]],
        fill="toself", name="Match Avg", line_color="#4a6fa5", fillcolor="rgba(74,111,165,0.2)"))
    fig.add_trace(go.Scatterpolar(r=values_player + [values_player[0]], theta=categories + [categories[0]],
        fill="toself", name=player, line_color="#00ff88", fillcolor="rgba(0,255,136,0.15)"))
    fig.update_layout(
        polar=dict(
            bgcolor="#141920",
            radialaxis=dict(visible=True, range=[0, 1], gridcolor="#2a3444", tickfont=dict(color="#666")),
            angularaxis=dict(gridcolor="#2a3444", tickfont=dict(color="#dce6f0")),
        ),
        paper_bgcolor="#0e1117",
        font_color="#dce6f0",
        legend=dict(bgcolor="#1a2332"),
        margin=dict(l=40, r=40, t=40, b=40),
        height=360,
    )
    return fig


def build_adr_kast_scatter(stats):
    fig = px.scatter(
        stats.reset_index(),
        x="ADR", y="KAST%",
        text="index",
        size="kills",
        color="Rating",
        color_continuous_scale=["#ff4444", "#ffd700", "#00ff88"],
        range_color=[0.3, 1.5],
    )
    fig.update_traces(textposition="top center", marker=dict(line=dict(width=1, color="#333")))
    fig.update_layout(
        title="ADR vs KAST% (bubble size = kills)",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(gridcolor="#2a3444"),
        yaxis=dict(gridcolor="#2a3444"),
        coloraxis_colorbar=dict(title="Rating"),
        height=380,
    )
    return fig


# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🎯 CS2 Stats Analyzer")

uploaded = st.file_uploader("Upload a CS2 demo file (.dem)", type=["dem"])

if uploaded:
    with st.spinner("Parsing demo..."):
        stats, total_rounds, kills_df, damage_df, round_df, spawn_df, flash_df, he_df, smoke_df, molotov_df, tick_df, pos_df, map_name = parse_and_compute(uploaded.read())

    stats_sorted = stats.sort_values("Rating", ascending=False)

    # ── Top metrics ──
    st.markdown("---")
    cols = st.columns(5)
    top = stats_sorted.iloc[0]
    metrics = [
        ("Total Rounds", str(total_rounds), ""),
        ("MVP (Rating)", stats_sorted.index[0], f"{top['Rating']:.3f}"),
        ("Top Fragger", stats_sorted.sort_values('kills', ascending=False).index[0],
         f"{int(stats_sorted.sort_values('kills', ascending=False).iloc[0]['kills'])} kills"),
        ("Highest ADR",  stats_sorted.sort_values('ADR', ascending=False).index[0],
         f"{stats_sorted.sort_values('ADR', ascending=False).iloc[0]['ADR']}"),
        ("Best KAST%",   stats_sorted.sort_values('KAST%', ascending=False).index[0],
         f"{stats_sorted.sort_values('KAST%', ascending=False).iloc[0]['KAST%']}%"),
    ]
    for col, (label, value, sub) in zip(cols, metrics):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-label">{sub}</div>
            </div>""", unsafe_allow_html=True)

    # ── Stats table ──
    st.markdown("### 📊 Full Match Stats")
    st.plotly_chart(build_stats_table(stats_sorted), use_container_width=True)

    # ── Charts row 1 ──
    st.markdown("### 📈 Performance Overview")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(build_rating_bar(stats), use_container_width=True)
    with c2:
        st.plotly_chart(build_adr_kast_scatter(stats), use_container_width=True)

    # ── Player deep dive ──
    st.markdown("### 🔍 Player Deep Dive")
    selected = st.selectbox("Select a player", options=stats_sorted.index.tolist())
    if selected:
        r = stats.loc[selected]
        dcols = st.columns(6)
        for col, (label, val) in zip(dcols, [
            ("Kills", int(r["kills"])), ("Deaths", int(r["deaths"])),
            ("Assists", int(r["assists"])), ("ADR", r["ADR"]),
            ("KAST%", f"{r['KAST%']}%"), ("Rating", f"{r['Rating']:.3f}")
        ]):
            col.metric(label, val)

        st.plotly_chart(build_radar(stats, selected), use_container_width=True)
    
    # ── Round Timeline ──
    st.markdown("---")
    st.markdown("### 🕐 Round Timeline")

    kills_matrix, dmg_matrix, deaths_matrix, all_players = build_player_round_matrix(
        kills_df, damage_df, round_df, spawn_df
    )
    timeline = build_round_timeline(kills_df, damage_df, round_df)

    # ── Kills heatmap ──
    st.markdown("#### Kill Heatmap (per round)")

    # Sort players by total kills descending
    player_order = stats.sort_values("kills", ascending=False).index.tolist()
    kills_matrix = kills_matrix.reindex(player_order)

    round_cols = kills_matrix.columns.tolist()
    winners = {r["round"]: r["winner"] for r in timeline}
    col_labels = [f"R{r}<br>{'🟠T' if winners.get(r)=='T' else '🔵CT'}" for r in round_cols]

    fig_heatmap = go.Figure(go.Heatmap(
        z=kills_matrix.values,
        x=col_labels,
        y=kills_matrix.index.tolist(),
        colorscale=[[0, "#141920"], [0.01, "#1a3a2a"], [0.4, "#00aa55"], [1.0, "#00ff88"]],
        showscale=True,
        text=kills_matrix.values,
        texttemplate="%{text}",
        hovertemplate="<b>%{y}</b><br>Round %{x}<br>Kills: %{z}<extra></extra>",
        zmin=0, zmax=4,
    ))
    fig_heatmap.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(side="top", tickfont=dict(size=10)),
        yaxis=dict(tickfont=dict(size=12)),
        margin=dict(l=10, r=10, t=60, b=10),
        height=40 * len(player_order) + 80,
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

    # ── Round selector ──
    st.markdown("#### Round Breakdown")
    round_nums = [r["round"] for r in timeline]
    selected_round = st.select_slider("Select Round", options=round_nums)

    round_data = next(r for r in timeline if r["round"] == selected_round)

    rcols = st.columns([1, 2])

    with rcols[0]:
        winner = round_data["winner"] or "?"
        reason = (round_data["reason"] or "unknown").replace("_", " ")
        winner_color = "#ff6b35" if winner == "T" else "#4a90d9"
        st.markdown(f"""
        <div style="background:#1e2530;border-radius:10px;padding:16px;margin-bottom:12px">
            <div style="color:#8b9cbe;font-size:12px">ROUND {selected_round} RESULT</div>
            <div style="color:{winner_color};font-size:24px;font-weight:700">{winner} WIN</div>
            <div style="color:#8b9cbe;font-size:13px">{reason}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Player performance this round:**")
        perf_rows = []
        for p in player_order:
            k = round_data["player_kills"].get(p, 0)
            d = round_data["player_dmg"].get(p, 0)
            died = "💀" if p in round_data["player_died"] else "✅"
            perf_rows.append({"Player": p, "K": k, "DMG": int(d), "": died})
        perf_df = pd.DataFrame(perf_rows).set_index("Player")
        st.dataframe(perf_df, use_container_width=True)

    with rcols[1]:
        st.markdown("**Kill feed:**")
        if round_data["kill_feed"]:
            for kf in round_data["kill_feed"]:
                hs_tag = " 🎯" if kf["headshot"] else ""
                st.markdown(
                    f"<div style='background:#1a2332;border-radius:6px;padding:8px 12px;"
                    f"margin-bottom:6px;font-size:14px'>"
                    f"<span style='color:#00ff88'>{kf['killer']}</span>"
                    f" <span style='color:#666'>killed</span> "
                    f"<span style='color:#ff4444'>{kf['victim']}</span>"
                    f" <span style='color:#8b9cbe'>with {kf['weapon']}</span>{hs_tag}"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            st.info("No kills this round")
    
    # ── Utility Stats ──
    st.markdown("---")
    st.markdown("### 💣 Utility Stats")

    util, round_util, avg_smokes = compute_utility_stats(
        flash_df, he_df, smoke_df, molotov_df, damage_df, kills_df, round_df
    )

    # ── Summary metrics ──
    ucols = st.columns(4)
    total_flashes  = int(flash_df.shape[0])
    total_he       = int(he_df.shape[0])
    total_smokes   = int(smoke_df.shape[0])
    total_molotovs = int(molotov_df.shape[0])
    for col, (label, val) in zip(ucols, [
        ("Flashbangs Thrown", total_flashes),
        ("HE Grenades Thrown", total_he),
        ("Smokes Thrown", total_smokes),
        ("Molotovs Thrown", total_molotovs),
    ]):
        col.metric(label, val)

    # ── Per-player utility table ──
    st.markdown("#### Per-Player Utility Breakdown")

    util_display = util.copy()
    util_display.index.name = "Player"
    util_display = util_display.rename(columns={
        "flashes_thrown":    "Flashes",
        "flash_assists":     "Flash Assists",
        "flash_assist_rate": "Assist/Flash",
        "he_thrown":         "HEs",
        "he_damage":         "HE DMG",
        "he_dmg_per_nade":   "HE DMG/Nade",
        "smokes_thrown":     "Smokes",
        "molotovs_thrown":   "Molotovs",
        "molotov_damage":    "Molotov DMG",
    })

    # Sort by total utility thrown
    util_display["Total Thrown"] = (
        util_display["Flashes"] + util_display["HEs"] +
        util_display["Smokes"] + util_display["Molotovs"]
    )
    util_display = util_display.sort_values("Total Thrown", ascending=False).drop(columns="Total Thrown")
    st.dataframe(util_display, use_container_width=True)

    # ── Grenade usage bar chart ──
    st.markdown("#### Grenade Usage by Player")
    nade_fig = go.Figure()
    for col, color, label in [
        ("Flashes",  "#4a90d9", "Flashbangs"),
        ("HEs",      "#ff6b35", "HE Grenades"),
        ("Smokes",   "#8b9cbe", "Smokes"),
        ("Molotovs", "#ff4444", "Molotovs"),
    ]:
        nade_fig.add_trace(go.Bar(
            name=label,
            x=util_display.index.tolist(),
            y=util_display[col].tolist(),
            marker_color=color,
        ))
    nade_fig.update_layout(
        barmode="stack",
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(gridcolor="#2a3444"),
        yaxis=dict(gridcolor="#2a3444", title="Grenades Thrown"),
        legend=dict(bgcolor="#1a2332"),
        height=350,
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(nade_fig, use_container_width=True)

    # ── HE damage vs flash assists scatter ──
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### HE Damage per Grenade")
        he_fig = go.Figure(go.Bar(
            x=util_display.sort_values("HE DMG/Nade", ascending=True).index.tolist(),
            y=util_display.sort_values("HE DMG/Nade", ascending=True)["HE DMG/Nade"].tolist(),
            marker_color="#ff6b35",
            text=util_display.sort_values("HE DMG/Nade", ascending=True)["HE DMG/Nade"].tolist(),
            textposition="outside",
        ))
        he_fig.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#141920",
            font_color="#dce6f0",
            xaxis=dict(gridcolor="#2a3444"),
            yaxis=dict(gridcolor="#2a3444", title="Avg DMG per HE"),
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(he_fig, use_container_width=True)

    with c2:
        st.markdown("#### Flash Assists per Flash Thrown")
        flash_fig = go.Figure(go.Bar(
            x=util_display.sort_values("Assist/Flash", ascending=True).index.tolist(),
            y=util_display.sort_values("Assist/Flash", ascending=True)["Assist/Flash"].tolist(),
            marker_color="#4a90d9",
            text=util_display.sort_values("Assist/Flash", ascending=True)["Assist/Flash"].tolist(),
            textposition="outside",
        ))
        flash_fig.update_layout(
            paper_bgcolor="#0e1117",
            plot_bgcolor="#141920",
            font_color="#dce6f0",
            xaxis=dict(gridcolor="#2a3444"),
            yaxis=dict(gridcolor="#2a3444", title="Assists per Flash"),
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(flash_fig, use_container_width=True)

    # ── Grenades per round heatmap ──
    st.markdown("#### Grenade Usage per Round")
    rutil_fig = go.Figure(go.Heatmap(
        z=round_util.T.values,
        x=[f"R{r}" for r in round_util.index],
        y=["Flashes", "HEs", "Smokes", "Molotovs"],
        colorscale=[[0, "#141920"], [0.2, "#1a3a2a"], [0.6, "#00aa55"], [1.0, "#00ff88"]],
        text=round_util.T.values,
        texttemplate="%{text}",
        showscale=True,
        hovertemplate="Round %{x}<br>%{y}: %{z}<extra></extra>",
    ))
    rutil_fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(side="top", tickfont=dict(size=10)),
        height=220,
        margin=dict(l=10, r=10, t=60, b=10),
    )
    st.plotly_chart(rutil_fig, use_container_width=True)

    # ── Economy Tracker ──
    st.markdown("---")
    st.markdown("### 💰 Economy Tracker")

    eco_data = compute_economy(tick_df, round_df)
    team_buys   = eco_data["team_buys_df"]
    win_rates   = eco_data["win_rates"]
    round_econ  = eco_data["round_economy"]
    player_eco  = eco_data["player_eco"]

    # ── Summary metrics ──
    ecols = st.columns(4)
    total_spent_all = int(player_eco["total_spent"].sum())
    avg_spent_round = round(player_eco["avg_spent"].mean(), 0)
    eco_wins   = eco_data["eco_wins"]
    eco_losses = eco_data["eco_losses"]
    for col, (label, val) in zip(ecols, [
        ("Total Money Spent", f"${total_spent_all:,}"),
        ("Avg Spent per Round", f"${int(avg_spent_round):,}"),
        ("Eco Round Wins", eco_wins),
        ("Eco Round Losses", eco_losses),
    ]):
        col.metric(label, val)

    # ── Win rates by buy type ──
    st.markdown("#### Win Rate by Buy Type")
    wr_cols = st.columns(2)

    for i, team_side in enumerate(["T", "CT"]):
        with wr_cols[i]:
            st.markdown(f"**{'Terrorist' if team_side == 'T' else 'Counter-Terrorist'} Side**")
            try:
                team_wr = win_rates.loc[team_side].reset_index()
                team_wr.columns = ["Buy Type", "Rounds", "Wins", "Win Rate %"]
                buy_order = ["Full Buy", "Half Buy", "Force", "Eco"]
                team_wr["Buy Type"] = pd.Categorical(team_wr["Buy Type"], categories=buy_order, ordered=True)
                team_wr = team_wr.sort_values("Buy Type")

                wr_fig = go.Figure(go.Bar(
                    x=team_wr["Buy Type"].tolist(),
                    y=team_wr["Win Rate %"].tolist(),
                    text=[f"{v}%" for v in team_wr["Win Rate %"]],
                    textposition="outside",
                    marker_color=["#00ff88", "#ffd700", "#ff9933", "#ff4444"],
                ))
                wr_fig.update_layout(
                    paper_bgcolor="#0e1117",
                    plot_bgcolor="#141920",
                    font_color="#dce6f0",
                    xaxis=dict(gridcolor="#2a3444"),
                    yaxis=dict(gridcolor="#2a3444", range=[0, 110], title="Win Rate %"),
                    height=280,
                    margin=dict(l=10, r=10, t=10, b=10),
                )
                st.plotly_chart(wr_fig, use_container_width=True)
            except KeyError:
                st.info(f"No data for {team_side} side")

    # ── Team equipment value per round ──
    st.markdown("#### Team Equipment Value per Round")
    eq_fig = go.Figure()
    colors = {"T": "#ff6b35", "CT": "#4a90d9"}
    for team_side in ["T", "CT"]:
        if team_side in round_econ.columns:
            eq_fig.add_trace(go.Scatter(
                x=round_econ.index.tolist(),
                y=round_econ[team_side].tolist(),
                name=f"{'Terrorist' if team_side == 'T' else 'CT'} Side",
                line=dict(color=colors[team_side], width=2),
                mode="lines+markers",
            ))
    eq_fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(gridcolor="#2a3444", title="Round", dtick=1),
        yaxis=dict(gridcolor="#2a3444", title="Total Equipment Value ($)"),
        legend=dict(bgcolor="#1a2332"),
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
    )
    st.plotly_chart(eq_fig, use_container_width=True)

    # ── Buy type per round timeline ──
    st.markdown("#### Buy Type Timeline")
    buy_colors = {"Full Buy": "#00ff88", "Half Buy": "#ffd700", "Force": "#ff9933", "Eco": "#ff4444"}

    bt_fig = go.Figure()
    for team_side, marker_symbol in [("T", "circle"), ("CT", "square")]:
        team_data = team_buys[team_buys["team"] == team_side]
        for buy_type, color in buy_colors.items():
            subset = team_data[team_data["buy_type"] == buy_type]
            if not subset.empty:
                bt_fig.add_trace(go.Scatter(
                    x=subset["round"].tolist(),
                    y=[team_side] * len(subset),
                    mode="markers",
                    marker=dict(
                        symbol=marker_symbol,
                        size=16,
                        color=[color if w else "#333" for w in subset["won"]],
                        line=dict(width=2, color=color),
                    ),
                    name=f"{team_side} {buy_type}",
                    text=[f"R{r} {bt} {'✓' if w else '✗'}" for r, bt, w in
                          zip(subset["round"], subset["buy_type"], subset["won"])],
                    hoverinfo="text",
                    showlegend=False,
                ))

    # Add legend manually
    for buy_type, color in buy_colors.items():
        bt_fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=10, color=color),
            name=buy_type, showlegend=True,
        ))

    bt_fig.update_layout(
        paper_bgcolor="#0e1117",
        plot_bgcolor="#141920",
        font_color="#dce6f0",
        xaxis=dict(gridcolor="#2a3444", title="Round", dtick=1),
        yaxis=dict(gridcolor="#2a3444"),
        legend=dict(bgcolor="#1a2332"),
        height=250,
        margin=dict(l=10, r=10, t=10, b=40),
    )
    st.plotly_chart(bt_fig, use_container_width=True)
    st.caption("Filled = won, hollow = lost")

    # ── Per-player economy table ──
    st.markdown("#### Per-Player Economy")
    eco_display = player_eco.copy()
    eco_display["total_spent"] = eco_display["total_spent"].apply(lambda x: f"${int(x):,}")
    eco_display["avg_spent"]   = eco_display["avg_spent"].apply(lambda x: f"${int(x):,}")
    eco_display["avg_equip"]   = eco_display["avg_equip"].apply(lambda x: f"${int(x):,}")
    eco_display = eco_display.rename(columns={
        "total_spent":   "Total Spent",
        "avg_spent":     "Avg/Round",
        "avg_equip":     "Avg Equip",
        "rounds_played": "Rounds",
        "Full Buy":      "Full Buys",
        "Half Buy":      "Half Buys",
        "Force":         "Forces",
        "Eco":           "Ecos",
    })
    eco_display.index.name = "Player"
    st.dataframe(eco_display, use_container_width=True)

    # ── Position Heatmaps ──
    st.markdown("---")
    st.markdown("### 🗺️ Position Heatmaps")

    # Controls
    hm_cols = st.columns(3)
    with hm_cols[0]:
        hm_mode = st.selectbox("Mode", ["deaths", "kills", "positions"], 
                                format_func=lambda x: {"deaths": "💀 Deaths", 
                                                        "kills": "🔫 Kills",
                                                        "positions": "📍 Positions"}[x])
    with hm_cols[1]:
        hm_player = st.selectbox("Player", ["All Players"] + stats_sorted.index.tolist())
        player_filter = None if hm_player == "All Players" else hm_player
    with hm_cols[2]:
        floor = st.selectbox("Floor", ["upper", "lower", "both"], 
                     help="Nuke only — upper/lower refer to Z level. Use 'both' for other maps.")

    with st.spinner("Building heatmap..."):
        map_img_bytes = fetch_map_image(map_name)
        fig_hm = build_position_heatmap(
            pos_df, kills_df, map_name,
            mode=hm_mode,
            player_filter=player_filter,
            floor_filter=floor,
            map_img_bytes=map_img_bytes,
        )

    if fig_hm:
        st.plotly_chart(fig_hm, use_container_width=False)
    else:
        st.warning("No data for this selection.")
    
    

else:
    st.info("👆 Upload a .dem file to get started")
    st.markdown("""
    **What this tool shows you:**
    - K / D / A, HS%, ADR for every player
    - KAST% (Kill / Assist / Survive / Trade)
    - HLTV-style Rating per player
    - ADR vs KAST scatter plot
    - Per-player radar chart vs match average

    **Where to find your demos:**
```
    C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\replays\\
```
    """)
