import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
from PIL import Image
import io
import base64

# ── de_nuke map calibration ───────────────────────────────────────────────────
# These values come from Valve's radar .txt files
MAP_DATA = {
    "de_nuke": {
        "pos_x": -3453,   # top-left X in game units
        "pos_y": 2887,    # top-left Y in game units
        "scale": 7.0,     # game units per pixel
        # Nuke has two levels — upper (Z > -100) and lower (Z <= -100)
        "upper_z": -100,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_nuke.png",
    },
    # Add more maps here as needed
    "de_mirage": {
        "pos_x": -3230, "pos_y": 1713, "scale": 5.0,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_mirage.png",
    },
    "de_inferno": {
        "pos_x": -2087, "pos_y": 3870, "scale": 4.9,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_inferno.png",
    },
    "de_dust2": {
        "pos_x": -2476, "pos_y": 3239, "scale": 4.4,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_dust2.png",
    },
    "de_ancient": {
        "pos_x": -2953, "pos_y": 2164, "scale": 5.0,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_ancient.png",
    },
    "de_anubis": {
        "pos_x": -2796, "pos_y": 3328, "scale": 5.22,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_anubis.png",
    },
    "de_vertigo": {
        "pos_x": -3168, "pos_y": 1762, "scale": 4.0,
        "radar_url": "https://raw.githubusercontent.com/zifnab87/cs-go-map-images/master/de_vertigo.png",
    },
}


def game_to_pixel(x, y, map_name):
    """Convert CS2 game coordinates to pixel coordinates on radar image."""
    m = MAP_DATA.get(map_name, MAP_DATA["de_nuke"])
    px = (x - m["pos_x"]) / m["scale"]
    py = (m["pos_y"] - y) / m["scale"]
    return px, py


def get_map_image(map_name: str) -> str:
    """Fetch radar image and return as base64 string for Plotly."""
    # Try to use local fallback first
    m = MAP_DATA.get(map_name)
    if not m:
        return None
    try:
        resp = requests.get(m["radar_url"], timeout=10)
        img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
        # Darken slightly for better contrast with overlays
        darkened = Image.blend(
            Image.new("RGBA", img.size, (0, 0, 0, 255)),
            img, alpha=0.75
        )
        buf = io.BytesIO()
        darkened.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}", img.size
    except Exception:
        return None, (1024, 1024)


def build_kill_heatmap(kills_df, map_name: str, player_filter=None):
    """
    Plot kill and death positions on the map radar.
    kills_df must have: attacker_name, user_name, x, y, z, headshot
    (x/y/z come from the grenade events — for kills we use player_death directly)
    """
    m = MAP_DATA.get(map_name, MAP_DATA["de_nuke"])
    img_b64, img_size = get_map_image(map_name)
    W, H = img_size

    df = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    if player_filter:
        df = df[
            (df["attacker_name"] == player_filter) |
            (df["user_name"] == player_filter)
        ]

    # We don't have X/Y in player_death — we'll use the tick positions
    # For now build density heatmap from what we have
    # This function expects pre-joined position data
    return df, W, H, img_b64


def build_position_heatmap(pos_df, kills_df, map_name: str,
                            mode="deaths", player_filter=None,
                            floor_filter="upper"):
    """
    pos_df: tick-sampled positions with X, Y, Z, name, team_name, is_alive
    kills_df: player_death events with user_name, attacker_name
    mode: 'deaths', 'kills', 'positions'
    floor_filter: 'upper', 'lower', 'both' (nuke-specific)
    """
    m = MAP_DATA.get(map_name, MAP_DATA["de_nuke"])
    img_b64, img_size = get_map_image(map_name)
    W, H = img_size

    # ── Select data based on mode ──────────────────────────────────────────
    if mode == "positions":
        df = pos_df.copy()
        if player_filter:
            df = df[df["name"] == player_filter]
        x_col, y_col, z_col = "X", "Y", "Z"
        title = f"Position Heatmap{' — ' + player_filter if player_filter else ' — All Players'}"
        color = "rgba(0, 200, 255, 0.6)"

    elif mode == "deaths":
        # Join kill events (which have no X/Y) with position data at closest tick
        # Use the kills_df user_name + tick to find position
        death_ticks = kills_df[["user_name", "tick"]].dropna()
        # Find nearest position tick for each death
        pos_indexed = pos_df.set_index(["name", "tick"])
        positions = []
        for _, row in death_ticks.iterrows():
            player = row["user_name"]
            tick   = row["tick"]
            player_pos = pos_df[pos_df["name"] == player]
            if player_pos.empty:
                continue
            nearest_idx = (player_pos["tick"] - tick).abs().idxmin()
            nearest = player_pos.loc[nearest_idx]
            positions.append({"X": nearest["X"], "Y": nearest["Y"],
                               "Z": nearest["Z"], "name": player})
        df = pd.DataFrame(positions)
        if df.empty:
            return None
        if player_filter:
            df = df[df["name"] == player_filter]
        x_col, y_col, z_col = "X", "Y", "Z"
        title = f"Death Positions{' — ' + player_filter if player_filter else ' — All Players'}"
        color = "rgba(255, 80, 80, 0.7)"

    elif mode == "kills":
        kill_ticks = kills_df[["attacker_name", "tick"]].dropna()
        kill_ticks = kill_ticks[kill_ticks["attacker_name"] != kills_df.get("user_name", "")]
        positions = []
        for _, row in kill_ticks.iterrows():
            player = row["attacker_name"]
            tick   = row["tick"]
            player_pos = pos_df[pos_df["name"] == player]
            if player_pos.empty:
                continue
            nearest_idx = (player_pos["tick"] - tick).abs().idxmin()
            nearest = player_pos.loc[nearest_idx]
            positions.append({"X": nearest["X"], "Y": nearest["Y"],
                               "Z": nearest["Z"], "name": player})
        df = pd.DataFrame(positions)
        if df.empty:
            return None
        if player_filter:
            df = df[df["name"] == player_filter]
        x_col, y_col, z_col = "X", "Y", "Z"
        title = f"Kill Positions{' — ' + player_filter if player_filter else ' — All Players'}"
        color = "rgba(0, 255, 136, 0.7)"

    # ── Floor filter for Nuke ──────────────────────────────────────────────
    upper_z = m.get("upper_z", -100)
    if floor_filter == "upper":
        df = df[df[z_col] > upper_z]
        title += " (Upper)"
    elif floor_filter == "lower":
        df = df[df[z_col] <= upper_z]
        title += " (Lower)"

    if df.empty:
        return None

    # ── Convert to pixel coordinates ──────────────────────────────────────
    px_coords = [game_to_pixel(x, y, map_name) for x, y in zip(df[x_col], df[y_col])]
    px = [c[0] for c in px_coords]
    py = [c[1] for c in px_coords]

    # ── Build figure ──────────────────────────────────────────────────────
    fig = go.Figure()

    # Background map image
    if img_b64:
        fig.add_layout_image(
            source=img_b64,
            xref="x", yref="y",
            x=0, y=0,
            sizex=W, sizey=H,
            sizing="stretch",
            opacity=1.0,
            layer="below"
        )

    # Density heatmap overlay
    fig.add_trace(go.Histogram2dContour(
        x=px, y=py,
        colorscale=[
            [0.0,  "rgba(0,0,0,0)"],
            [0.2,  "rgba(0,80,255,0.3)"],
            [0.5,  "rgba(255,200,0,0.5)"],
            [0.8,  "rgba(255,80,0,0.65)"],
            [1.0,  "rgba(255,0,0,0.8)"],
        ],
        reversescale=False,
        showscale=False,
        ncontours=20,
        contours=dict(coloring="fill"),
        line=dict(width=0),
    ))

    # Individual scatter points
    hover_text = df["name"].tolist() if "name" in df.columns else [""] * len(px)
    fig.add_trace(go.Scatter(
        x=px, y=py,
        mode="markers",
        marker=dict(
            size=8,
            color=color,
            line=dict(width=1, color="white"),
        ),
        text=hover_text,
        hovertemplate="<b>%{text}</b><br>(%{x:.0f}, %{y:.0f})<extra></extra>",
        showlegend=False,
    ))

    fig.update_layout(
        title=title,
        xaxis=dict(range=[0, W], showgrid=False, zeroline=False,
                   showticklabels=False, scaleanchor="y"),
        yaxis=dict(range=[H, 0], showgrid=False, zeroline=False,
                   showticklabels=False),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font_color="#dce6f0",
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        width=600,
    )

    return fig
