"""
combat.py — Advanced combat analytics
Provides:
  - compute_multikills()   : 3k / 4k / ace counts per player per round
  - compute_opening_duels(): first kill per round and impact on round outcome
  - compute_clutches()     : 1vX situations, who was in them, win/loss
  - compute_weapon_stats() : kills / hs / headshot% per weapon per player
"""

import pandas as pd


# ── Multi-kills ───────────────────────────────────────────────────────────────
def compute_multikills(kills_df: pd.DataFrame, round_df: pd.DataFrame) -> dict:
    """
    Returns:
        summary   : DataFrame(player × {3k,4k,ace}) — total counts
        by_round  : DataFrame with columns [round, player, kills, label]
    """
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    # Count kills per player per round
    grouped = (
        kills_clean
        .groupby(["round", "attacker_name"])
        .size()
        .reset_index(name="kills")
    )

    # Only keep rounds where someone got 3+
    multi = grouped[grouped["kills"] >= 3].copy()

    def label(k):
        if k >= 5: return "ACE"
        if k == 4: return "4K"
        return "3K"

    multi["label"] = multi["kills"].apply(label)

    # Summary pivot per player
    summary = (
        multi
        .groupby(["attacker_name", "label"])
        .size()
        .unstack(fill_value=0)
        .rename_axis("Player")
    )
    for col in ["3K", "4K", "ACE"]:
        if col not in summary.columns:
            summary[col] = 0
    summary = summary[["3K", "4K", "ACE"]]
    summary["Total"] = summary.sum(axis=1)
    summary = summary.sort_values("Total", ascending=False)

    return {"summary": summary, "by_round": multi.rename(columns={"attacker_name": "player"})}


# ── Opening duels ─────────────────────────────────────────────────────────────
def compute_opening_duels(kills_df: pd.DataFrame, round_df: pd.DataFrame) -> dict:
    """
    Returns:
        per_round : DataFrame [round, opener, victim, opener_team, round_winner, opener_won_round]
        summary   : DataFrame per player [opens, open_wins, open_losses, win_rate, impact_rate]
                    impact_rate = % of opening kills whose team won the round
    """
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    if "round" not in kills_clean.columns:
        return {"per_round": pd.DataFrame(), "summary": pd.DataFrame()}

    # First kill per round = lowest tick
    first_kills = (
        kills_clean
        .sort_values("tick")
        .groupby("round")
        .first()
        .reset_index()[["round", "attacker_name", "user_name", "attacker_team_name", "tick"]]
    )
    first_kills.columns = ["round", "opener", "victim", "opener_team", "tick"]

    # Map round winner
    round_winners = round_df[round_df["round"] > 0].set_index("round")["winner"].to_dict()
    first_kills["round_winner"] = first_kills["round"].map(round_winners)
    first_kills["opener_won_round"] = first_kills["opener_team"] == first_kills["round_winner"]

    # Per-player summary — opening kills
    open_kills = first_kills.groupby("opener").agg(
        opens=("round", "count"),
        open_round_wins=("opener_won_round", "sum"),
    ).rename_axis("Player")
    open_kills["open_win_rate"] = (open_kills["open_round_wins"] / open_kills["opens"] * 100).round(1)

    # Per-player summary — opening deaths
    open_deaths = first_kills.groupby("victim").agg(
        open_deaths=("round", "count"),
    ).rename_axis("Player")

    summary = open_kills.join(open_deaths, how="outer").fillna(0)
    summary["opens"]          = summary["opens"].astype(int)
    summary["open_deaths"]    = summary["open_deaths"].astype(int)
    summary["open_round_wins"]= summary["open_round_wins"].astype(int)
    summary["open_win_rate"]  = summary["open_win_rate"].fillna(0)
    summary["rating"]         = (summary["opens"] - summary["open_deaths"])
    summary = summary.sort_values("opens", ascending=False)

    return {"per_round": first_kills, "summary": summary}


# ── Clutch situations ─────────────────────────────────────────────────────────
def compute_clutches(kills_df: pd.DataFrame, round_df: pd.DataFrame,
                     spawn_df: pd.DataFrame) -> dict:
    """
    A clutch = a player is the last alive on their team facing 1 or more opponents.
    Returns:
        clutches : DataFrame [round, player, team, vs (int), won (bool)]
        summary  : DataFrame per player [clutches, won, lost, win_rate, by scenario]
    """
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    if "round" not in kills_clean.columns or spawn_df.empty:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    round_winners = round_df[round_df["round"] > 0].set_index("round")["winner"].to_dict()

    # Get players alive at round start per round
    # spawn_df has player_name and team_name per round
    spawn_col = "player_name" if "player_name" in spawn_df.columns else \
                "user_name"   if "user_name"   in spawn_df.columns else None

    if spawn_col is None:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    spawns = spawn_df[[spawn_col, "team_name", "round"]].dropna()
    spawns.columns = ["player", "team", "round"]

    clutch_records = []

    for rnd, rnd_kills in kills_clean.groupby("round"):
        winner = round_winners.get(rnd)
        if winner is None:
            continue

        rnd_spawns = spawns[spawns["round"] == rnd]
        if rnd_spawns.empty:
            continue

        # Build alive sets per team
        alive = {
            team: set(grp["player"])
            for team, grp in rnd_spawns.groupby("team")
        }

        # Walk kills in tick order
        for _, kill in rnd_kills.sort_values("tick").iterrows():
            attacker = kill["attacker_name"]
            victim   = kill["user_name"]

            # Remove victim from alive
            for team_set in alive.values():
                team_set.discard(victim)

            # Check if any team is down to 1 vs 2+
            teams = list(alive.keys())
            if len(teams) < 2:
                break

            for i, team_a in enumerate(teams):
                team_b = teams[1 - i]
                if len(alive[team_a]) == 1 and len(alive[team_b]) >= 2:
                    clutch_player = next(iter(alive[team_a]))
                    vs_count      = len(alive[team_b])
                    # Determine if clutch player's team won
                    player_team_name = rnd_spawns[rnd_spawns["player"] == clutch_player]["team"].values
                    if len(player_team_name) == 0:
                        break
                    won = (player_team_name[0] == winner)
                    clutch_records.append({
                        "round":  rnd,
                        "player": clutch_player,
                        "team":   player_team_name[0],
                        "vs":     vs_count,
                        "won":    won,
                    })
                    break  # one clutch per team per round

    if not clutch_records:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    clutches = pd.DataFrame(clutch_records).drop_duplicates(subset=["round", "player"])

    # Summary
    summary = clutches.groupby("player").agg(
        clutches=("round", "count"),
        won=("won", "sum"),
    ).rename_axis("Player")
    summary["lost"]     = summary["clutches"] - summary["won"]
    summary["win_rate"] = (summary["won"] / summary["clutches"] * 100).round(1)

    # Breakdown by vs count
    vs_pivot = (
        clutches.groupby(["player", "vs"])
        .size()
        .unstack(fill_value=0)
        .rename_axis("Player")
    )
    vs_pivot.columns = [f"1v{c}" for c in vs_pivot.columns]
    summary = summary.join(vs_pivot, how="left").fillna(0)
    summary = summary.sort_values("clutches", ascending=False)

    return {"clutches": clutches, "summary": summary}


# ── Weapon breakdown ──────────────────────────────────────────────────────────
def compute_weapon_stats(kills_df: pd.DataFrame) -> dict:
    """
    Returns:
        by_weapon  : DataFrame [weapon, kills, hs, hs_pct] — overall
        by_player  : dict {player: DataFrame [weapon, kills, hs, hs_pct]}
    """
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    weapon_col = "weapon" if "weapon" in kills_clean.columns else \
                 "weapon_name" if "weapon_name" in kills_clean.columns else None

    if weapon_col is None:
        return {"by_weapon": pd.DataFrame(), "by_player": {}}

    kills_clean = kills_clean.rename(columns={weapon_col: "weapon"})

    def agg_weapons(df):
        grp = df.groupby("weapon").agg(
            kills=("weapon", "count"),
            hs=("headshot", "sum"),
        ).reset_index()
        grp["hs_pct"] = (grp["hs"] / grp["kills"] * 100).round(1)
        return grp.sort_values("kills", ascending=False)

    by_weapon = agg_weapons(kills_clean)

    by_player = {}
    for player, grp in kills_clean.groupby("attacker_name"):
        by_player[player] = agg_weapons(grp)

    return {"by_weapon": by_weapon, "by_player": by_player}
