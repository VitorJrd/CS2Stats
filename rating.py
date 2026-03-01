import pandas as pd

def compute_impact(kills_df, round_df):
    rounds = round_df[round_df["round"] > 0].copy()
    total_rounds = len(rounds)

    end_ticks = rounds.sort_values("round")["tick"].values
    round_numbers = rounds.sort_values("round")["round"].values

    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    def assign_round(tick):
        import numpy as np
        idx = int(pd.Series(end_ticks).searchsorted(tick, side="left"))
        return round_numbers[idx] if idx < len(round_numbers) else None

    kills_clean["round"] = kills_clean["tick"].apply(assign_round)
    kills_clean = kills_clean.dropna(subset=["round"])

    kills_per_round = kills_clean.groupby(["attacker_name", "round"]).size().reset_index(name="kill_count")

    impact = {}
    for player in kills_clean["attacker_name"].unique():
        player_rounds = kills_per_round[kills_per_round["attacker_name"] == player]
        rounds_with_1k  = len(player_rounds[player_rounds["kill_count"] == 1])
        rounds_with_2k_plus = len(player_rounds[player_rounds["kill_count"] >= 2])
        impact[player] = (
            2.13 * (rounds_with_2k_plus / total_rounds)
            + 0.42 * (rounds_with_1k / total_rounds)
            - 0.41
        )

    return impact


def compute_rating(stats: pd.DataFrame, kills_df, round_df) -> pd.Series:
    total_rounds = round_df[round_df["round"] > 0].shape[0]

    impact = compute_impact(kills_df, round_df)

    ratings = {}
    for player, row in stats.iterrows():
        kast  = row["KAST%"] / 100
        k_r   = row["kills"] / total_rounds
        d_r   = row["deaths"] / total_rounds
        adr   = row["ADR"]
        imp   = impact.get(player, -0.41)

        rating = (
            0.0073 * (kast * 100)
            + 0.3591 * k_r
            - 0.5329 * d_r
            + 0.2372 * imp
            + 0.0032 * adr
            + 0.1587
        )
        ratings[player] = round(rating, 3)

    return pd.Series(ratings, name="Rating")
