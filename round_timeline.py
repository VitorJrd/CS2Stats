import pandas as pd
import numpy as np

def assign_rounds_to_df(df, round_df, tick_col="tick"):
    """Assign a round number to every row based on its tick."""
    rounds = round_df[round_df["round"] > 0].sort_values("round")
    end_ticks = rounds["tick"].values
    round_numbers = rounds["round"].values

    def get_round(tick):
        idx = np.searchsorted(end_ticks, tick, side="left")
        return int(round_numbers[idx]) if idx < len(round_numbers) else None

    df = df.copy()
    df["round"] = df[tick_col].apply(get_round)
    return df.dropna(subset=["round"])


def build_round_timeline(kills_df, damage_df, round_df):
    rounds = round_df[round_df["round"] > 0].copy()

    # Assign rounds to kills and damage
    kills = assign_rounds_to_df(kills_df, round_df)
    damage = assign_rounds_to_df(damage_df, round_df)

    # Clean kills (no suicides, no world kills)
    kills_clean = kills[
        kills["attacker_name"].notna() &
        (kills["attacker_name"] != kills["user_name"])
    ].copy()

    # Per round damage per player
    damage_clean = damage[
        damage["attacker_name"].notna() &
        (damage["attacker_name"] != damage["user_name"])
    ].copy()

    timeline = []

    for _, round_row in rounds.iterrows():
        r = int(round_row["round"])
        winner = round_row["winner"]
        reason = round_row["reason"]

        round_kills = kills_clean[kills_clean["round"] == r].sort_values("tick")
        round_damage = damage_clean[damage_clean["round"] == r]

        # Kill feed for this round
        kill_feed = []
        for _, k in round_kills.iterrows():
            kill_feed.append({
                "killer":   k["attacker_name"],
                "victim":   k["user_name"],
                "weapon":   k["weapon"],
                "headshot": bool(k["headshot"]),
                "tick":     int(k["tick"]),
            })

        # Per player stats this round
        player_kills = round_kills.groupby("attacker_name").size().to_dict()
        player_hs    = round_kills[round_kills["headshot"] == True].groupby("attacker_name").size().to_dict()
        player_dmg   = round_damage.groupby("attacker_name")["dmg_health"].sum().to_dict()
        player_died  = set(kills[kills["round"] == r]["user_name"].dropna())

        # Determine if it was a clutch (last player alive won the round)
        # Simple version: if only 1 kill left on one side and they survived
        t_alive_end  = None
        ct_alive_end = None

        timeline.append({
            "round":        r,
            "winner":       winner,
            "reason":       reason,
            "kill_feed":    kill_feed,
            "player_kills": player_kills,
            "player_hs":    player_hs,
            "player_dmg":   player_dmg,
            "player_died":  list(player_died),
            "total_kills":  len(round_kills),
        })

    return timeline


def build_player_round_matrix(kills_df, damage_df, round_df, spawn_df):
    """
    Returns a DataFrame: rows = players, cols = rounds
    Value = kills that round (for heatmap)
    Also returns damage matrix.
    """
    rounds = round_df[round_df["round"] > 0].copy()
    total_rounds = len(rounds)
    round_nums = sorted(rounds["round"].unique())

    kills = assign_rounds_to_df(kills_df, round_df)
    kills_clean = kills[
        kills["attacker_name"].notna() &
        (kills["attacker_name"] != kills["user_name"])
    ].copy()

    damage = assign_rounds_to_df(damage_df, round_df)
    damage_clean = damage[
        damage["attacker_name"].notna() &
        (damage["attacker_name"] != damage["user_name"])
    ].copy()

    all_players = sorted(
        set(kills_clean["attacker_name"]) | set(kills_clean["user_name"])
    )

    # Kills matrix
    kills_matrix = pd.DataFrame(0, index=all_players, columns=round_nums)
    for (player, r), count in kills_clean.groupby(["attacker_name", "round"]).size().items():
        if player in kills_matrix.index and r in kills_matrix.columns:
            kills_matrix.loc[player, r] = count

    # Damage matrix
    dmg_matrix = pd.DataFrame(0.0, index=all_players, columns=round_nums)
    for (player, r), val in damage_clean.groupby(["attacker_name", "round"])["dmg_health"].sum().items():
        if player in dmg_matrix.index and r in dmg_matrix.columns:
            dmg_matrix.loc[player, r] = round(val, 1)

    # Deaths matrix (1 = died that round)
    deaths = assign_rounds_to_df(kills_df, round_df)
    deaths_matrix = pd.DataFrame(0, index=all_players, columns=round_nums)
    for (player, r), count in deaths.groupby(["user_name", "round"]).size().items():
        if player in deaths_matrix.index and r in deaths_matrix.columns:
            deaths_matrix.loc[player, r] = 1

    return kills_matrix, dmg_matrix, deaths_matrix, all_players
