import pandas as pd
import numpy as np

def classify_buy(equip_value: int, team: str) -> str:
    """
    Classify buy type based on equipment value at round start.
    Thresholds differ slightly between T and CT side.
    """
    if team == "CT":
        if equip_value < 1000:
            return "Eco"
        elif equip_value < 2000:
            return "Force"
        elif equip_value < 4000:
            return "Half Buy"
        else:
            return "Full Buy"
    else:  # TERRORIST
        if equip_value < 1000:
            return "Eco"
        elif equip_value < 2000:
            return "Force"
        elif equip_value < 4000:
            return "Half Buy"
        else:
            return "Full Buy"


def classify_team_buy(player_buys: pd.DataFrame) -> str:
    """
    Given a group of players on the same team in a round,
    classify the overall team buy type by average equip value.
    """
    avg = player_buys["current_equip_value"].mean()
    if avg < 1000:
        return "Eco"
    elif avg < 2000:
        return "Force"
    elif avg < 4000:
        return "Half Buy"
    else:
        return "Full Buy"


def compute_economy(tick_df: pd.DataFrame, round_df: pd.DataFrame) -> dict:
    """
    tick_df: parsed at freeze_end ticks, contains per-player economy snapshot
    round_df: round results with winner column
    """
    rounds = round_df[round_df["round"] > 0].copy()
    freeze_ticks = sorted(tick_df["tick"].unique())

    # Map freeze tick -> round number (freeze tick N belongs to round N)
    # freeze_ticks[0] = round 1, freeze_ticks[1] = round 2, etc.
    tick_to_round = {tick: i + 1 for i, tick in enumerate(freeze_ticks)}
    tick_df = tick_df.copy()
    tick_df["round"] = tick_df["tick"].map(tick_to_round)
    tick_df = tick_df.dropna(subset=["round"])
    tick_df["round"] = tick_df["round"].astype(int)

    # Merge with round results
    round_results = rounds[["round", "winner"]].set_index("round")
    tick_df = tick_df.join(round_results, on="round")

    # ── Per-player buy classification ──────────────────────────────────────
    tick_df["buy_type"] = tick_df.apply(
        lambda r: classify_buy(r["current_equip_value"], r["team_name"]), axis=1
    )

    # ── Per-player economy stats ───────────────────────────────────────────
    player_eco = tick_df.groupby("name").agg(
        total_spent   = ("cash_spent_this_round", "sum"),
        avg_spent     = ("cash_spent_this_round", "mean"),
        avg_equip     = ("current_equip_value", "mean"),
        rounds_played = ("round", "count"),
    ).round(0)

    # Buy type distribution per player
    buy_dist = (
        tick_df.groupby(["name", "buy_type"])
        .size()
        .unstack(fill_value=0)
    )
    for col in ["Eco", "Force", "Half Buy", "Full Buy"]:
        if col not in buy_dist.columns:
            buy_dist[col] = 0
    buy_dist = buy_dist[["Full Buy", "Half Buy", "Force", "Eco"]]
    player_eco = player_eco.join(buy_dist)

    # ── Team buy type per round ────────────────────────────────────────────
    team_round_buys = []
    for (round_num, team), group in tick_df.groupby(["round", "team_name"]):
        winner = group["winner"].iloc[0] if "winner" in group.columns else None
        team_side = "T" if team == "TERRORIST" else "CT"
        buy_type = classify_team_buy(group)
        won = (winner == team_side)
        total_equip = group["current_equip_value"].sum()
        total_spent = group["cash_spent_this_round"].sum()
        team_round_buys.append({
            "round":       round_num,
            "team":        team_side,
            "buy_type":    buy_type,
            "won":         won,
            "total_equip": total_equip,
            "total_spent": total_spent,
        })
    team_buys_df = pd.DataFrame(team_round_buys)

    # ── Win rates by buy type ──────────────────────────────────────────────
    win_rates = (
        team_buys_df.groupby(["team", "buy_type"])
        .agg(
            rounds  = ("won", "count"),
            wins    = ("won", "sum"),
        )
    )
    win_rates["win_rate"] = (win_rates["wins"] / win_rates["rounds"] * 100).round(1)

    # ── Economy per round (for timeline chart) ────────────────────────────
    round_economy = team_buys_df.pivot_table(
        index="round", columns="team",
        values="total_equip", aggfunc="first"
    ).fillna(0)

    # ── Eco kills: kills made AGAINST eco buyers ───────────────────────────
    # (useful context — counts rounds where a full-buy team beat an eco)
    eco_rounds = team_buys_df[team_buys_df["buy_type"] == "Eco"]
    eco_wins   = eco_rounds[eco_rounds["won"] == True]
    eco_losses = eco_rounds[eco_rounds["won"] == False]

    return {
        "player_eco":    player_eco,
        "team_buys_df":  team_buys_df,
        "win_rates":     win_rates,
        "round_economy": round_economy,
        "tick_df":       tick_df,
        "eco_wins":      len(eco_wins),
        "eco_losses":    len(eco_losses),
    }
