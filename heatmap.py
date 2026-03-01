import pandas as pd
import numpy as np
import plotly.graph_objects as go
from PIL import Image
import io
import base64

MAP_DATA = {
    "de_nuke":     {"pos_x": -3453, "pos_y": 2887,  "scale": 7.0,  "upper_z": -100},
    "de_mirage":   {"pos_x": -3230, "pos_y": 1713,  "scale": 5.0,  "upper_z": None},
    "de_inferno":  {"pos_x": -2087, "pos_y": 3870,  "scale": 4.9,  "upper_z": None},
    "de_dust2":    {"pos_x": -2476, "pos_y": 3239,  "scale": 4.4,  "upper_z": None},
    "de_ancient":  {"pos_x": -2953, "pos_y": 2164,  "scale": 5.0,  "upper_z": None},
    "de_anubis":   {"pos_x": -2796, "pos_y": 3328,  "scale": 5.22, "upper_z": None},
    "de_vertigo":  {"pos_x": -3168, "pos_y": 1762,  "scale": 4.0,  "upper_z": None},
    "de_overpass": {"pos_x": -4831, "pos_y": 1781,  "scale": 5.2,  "upper_z": None},
    "de_train":    {"pos_x": -2477, "pos_y": 2392,  "scale": 4.7,  "upper_z": None},
}


def game_to_pixel(x, y, map_name):
    m = MAP_DATA.get(map_name, MAP_DATA["de_nuke"])
    px = (x - m["pos_x"]) / m["scale"]
    py = (m["pos_y"] - y) / m["scale"]
    return px, py


def process_map_image(img_bytes):
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        dark = Image.new("RGBA", img.size, (0, 0, 0, 255))
        blended = Image.blend(dark, img, alpha=0.75)
        buf = io.BytesIO()
        blended.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}", img.size
    except Exception:
        return None, (1024, 1024)


def get_event_positions(kills_df, pos_df, mode, player_filter=None):
    if mode == "deaths":
        events = kills_df[kills_df["user_name"].notna()][["user_name", "tick"]].copy()
        events = events.rename(columns={"user_name": "player"})
    else:  #kills
        events = kills_df[
            kills_df["attacker_name"].notna() &
            (kills_df["attacker_name"] != kills_df["user_name"])
        ][["attacker_name", "tick"]].copy()
        events = events.rename(columns={"attacker_name": "player"})

    if player_filter:
        events = events[events["player"] == player_filter]

    if events.empty:
        return pd.DataFrame()

    positions = []
    player_pos_map = {
        name: grp.reset_index(drop=True)
        for name, grp in pos_df.groupby("name")
    }

    for _, row in events.iterrows():
        player = row["player"]
        tick   = row["tick"]
        player_pos = player_pos_map.get(player)
        if player_pos is None or player_pos.empty:
            continue
        nearest_idx = (player_pos["tick"] - tick).abs().idxmin()
        nearest = player_pos.loc[nearest_idx]
        positions.append({
            "name": player,
            "X": float(nearest["X"]),
            "Y": float(nearest["Y"]),
            "Z": float(nearest["Z"]),
        })

    return pd.DataFrame(positions)


def build_position_heatmap(pos_df, kills_df, map_name: str,
                            mode="deaths", player_filter=None,
                            floor_filter="both", map_img_bytes=None):

    m = MAP_DATA.get(map_name, MAP_DATA["de_nuke"])

    if map_img_bytes:
        img_b64, (W, H) = process_map_image(map_img_bytes)
    else:
        img_b64, (W, H) = None, (1024, 1024)

    if mode == "positions":
        df = pos_df.copy()
        if player_filter:
            df = df[df["name"] == player_filter]
        df = df[df["is_alive"].astype(bool) == True]
        point_color = "rgba(0, 200, 255, 0.5)"
        title = f"Position Heatmap — {'All Players' if not player_filter else player_filter}"

    elif mode in ("deaths", "kills"):
        df = get_event_positions(kills_df, pos_df, mode, player_filter)
        if df.empty:
            return None
        point_color = "rgba(255, 80, 80, 0.8)" if mode == "deaths" else "rgba(0, 255, 136, 0.8)"
        label = "Death" if mode == "deaths" else "Kill"
        title = f"{label} Positions — {'All Players' if not player_filter else player_filter}"
    else:
        return None

    if df.empty:
        return None

    upper_z = m.get("upper_z")
    if upper_z is not None and floor_filter != "both":
        if floor_filter == "upper":
            df = df[df["Z"] > upper_z]
            title += " (Upper)"
        elif floor_filter == "lower":
            df = df[df["Z"] <= upper_z]
            title += " (Lower)"
    
    if df.empty:
        return None

    coords  = [game_to_pixel(x, y, map_name) for x, y in zip(df["X"], df["Y"])]
    px_list = [c[0] for c in coords]
    py_list = [c[1] for c in coords]
    names   = df["name"].tolist() if "name" in df.columns else [""] * len(px_list)

    fig = go.Figure()

    if img_b64:
        fig.add_layout_image(
            source=img_b64,
            xref="x", yref="y",
            x=0, y=0,
            sizex=W, sizey=H,
            sizing="stretch",
            opacity=1.0,
            layer="below",
        )

    if len(px_list) >= 3:
        fig.add_trace(go.Histogram2dContour(
            x=px_list,
            y=py_list,
            colorscale=[
                [0.00, "rgba(0,0,0,0)"],
                [0.15, "rgba(0,0,180,0.25)"],
                [0.40, "rgba(0,180,255,0.4)"],
                [0.65, "rgba(255,200,0,0.55)"],
                [0.85, "rgba(255,80,0,0.7)"],
                [1.00, "rgba(255,0,0,0.85)"],
            ],
            reversescale=False,
            showscale=True,
            colorbar=dict(
                title=dict(text="Density", font=dict(color="#dce6f0")),
                tickfont=dict(color="#dce6f0"),
                bgcolor="#1a2332",
                bordercolor="#2a3444",
            ),
            ncontours=25,
            contours=dict(coloring="fill"),
            line=dict(width=0),
            hoverinfo="skip",
        ))

    fig.add_trace(go.Scatter(
        x=px_list,
        y=py_list,
        mode="markers",
        marker=dict(
            size=8,
            color=point_color,
            line=dict(width=1, color="rgba(255,255,255,0.5)"),
        ),
        text=names,
        hovertemplate="<b>%{text}</b><extra></extra>",
        showlegend=False,
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(color="#dce6f0", size=16)),
        xaxis=dict(
            range=[0, W],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="y",
        ),
        yaxis=dict(
            range=[H, 0],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
        ),
        paper_bgcolor="#0e1117",
        plot_bgcolor="#0e1117",
        font_color="#dce6f0",
        margin=dict(l=0, r=0, t=44, b=0),
        height=620,
    )

    return fig
