import pandas as pd


def _add_round_col(kills_df: pd.DataFrame, round_df: pd.DataFrame) -> pd.DataFrame:
    df = kills_df.copy()
    if "round" in df.columns:
        return df
    valid_rounds = round_df[round_df["round"] > 0].sort_values("tick")
    round_ticks = valid_rounds["tick"].tolist()
    round_nums  = valid_rounds["round"].tolist()
    def assign_round(tick):
        r = 0
        for i, rt in enumerate(round_ticks):
            if tick >= rt:
                r = round_nums[i]
            else:
                break
        return r
    df["round"] = df["tick"].apply(assign_round)
    df = df[df["round"] > 0]
    return df


def compute_multikills(kills_df: pd.DataFrame, round_df: pd.DataFrame) -> dict:
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_clean = _add_round_col(kills_clean, round_df)

    if kills_clean.empty or "round" not in kills_clean.columns:
        return {"summary": pd.DataFrame(), "by_round": pd.DataFrame()}

    grouped = (
        kills_clean
        .groupby(["round", "attacker_name"])
        .size()
        .reset_index(name="kills")
    )

    multi = grouped[grouped["kills"] >= 3].copy()

    if multi.empty:
        return {"summary": pd.DataFrame(), "by_round": pd.DataFrame()}

    def label(k):
        if k >= 5: return "ACE"
        if k == 4: return "4K"
        return "3K"

    multi["label"] = multi["kills"].apply(label)

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


def compute_opening_duels(kills_df: pd.DataFrame, round_df: pd.DataFrame) -> dict:
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_clean = _add_round_col(kills_clean, round_df)

    if kills_clean.empty or "round" not in kills_clean.columns:
        return {"per_round": pd.DataFrame(), "summary": pd.DataFrame()}

    team_col = None
    for candidate in ["attacker_team_name", "attacker_team", "team_name"]:
        if candidate in kills_clean.columns:
            team_col = candidate
            break

    select_cols = ["round", "attacker_name", "user_name", "tick"]
    if team_col:
        select_cols.append(team_col)

    first_kills = (
        kills_clean
        .sort_values("tick")
        .groupby("round")
        .first()
        .reset_index()[select_cols]
    )

    if team_col:
        first_kills = first_kills.rename(columns={
            "attacker_name": "opener", "user_name": "victim", team_col: "opener_team"
        })
    else:
        first_kills = first_kills.rename(columns={"attacker_name": "opener", "user_name": "victim"})
        first_kills["opener_team"] = None

    round_winners = round_df[round_df["round"] > 0].set_index("round")["winner"].to_dict()
    first_kills["round_winner"]    = first_kills["round"].map(round_winners)
    first_kills["opener_won_round"] = first_kills["opener_team"] == first_kills["round_winner"]

    open_kills = first_kills.groupby("opener").agg(
        opens=("round", "count"),
        open_round_wins=("opener_won_round", "sum"),
    ).rename_axis("Player")
    open_kills["open_win_rate"] = (open_kills["open_round_wins"] / open_kills["opens"] * 100).round(1)

    open_deaths = first_kills.groupby("victim").agg(
        open_deaths=("round", "count"),
    ).rename_axis("Player")

    summary = open_kills.join(open_deaths, how="outer").fillna(0)
    summary["opens"]           = summary["opens"].astype(int)
    summary["open_deaths"]     = summary["open_deaths"].astype(int)
    summary["open_round_wins"] = summary["open_round_wins"].astype(int)
    summary["open_win_rate"]   = summary["open_win_rate"].fillna(0)
    summary["rating"]          = summary["opens"] - summary["open_deaths"]
    summary = summary.sort_values("opens", ascending=False)

    return {"per_round": first_kills, "summary": summary}


def compute_clutches(kills_df: pd.DataFrame, round_df: pd.DataFrame,
                     spawn_df: pd.DataFrame) -> dict:
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_clean = _add_round_col(kills_clean, round_df)

    if kills_clean.empty or spawn_df.empty:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    spawn_col = None
    for candidate in ["player_name", "user_name", "name"]:
        if candidate in spawn_df.columns:
            spawn_col = candidate
            break

    team_col = None
    for candidate in ["team_name", "team"]:
        if candidate in spawn_df.columns:
            team_col = candidate
            break

    round_col_spawn = "round" if "round" in spawn_df.columns else None

    if spawn_col is None or team_col is None or round_col_spawn is None:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    spawns = spawn_df[[spawn_col, team_col, round_col_spawn]].dropna().copy()
    spawns.columns = ["player", "team", "round"]

    round_winners = round_df[round_df["round"] > 0].set_index("round")["winner"].to_dict()
    clutch_records = []

    for rnd, rnd_kills in kills_clean.groupby("round"):
        winner = round_winners.get(rnd)
        if winner is None:
            continue

        rnd_spawns = spawns[spawns["round"] == rnd]
        if rnd_spawns.empty:
            continue

        alive = {
            team: set(grp["player"])
            for team, grp in rnd_spawns.groupby("team")
        }

        for _, kill in rnd_kills.sort_values("tick").iterrows():
            victim = kill["user_name"]
            for team_set in alive.values():
                team_set.discard(victim)

            teams = [t for t, s in alive.items() if len(s) > 0]
            if len(teams) < 2:
                break

            for team_a in teams:
                others = [t for t in teams if t != team_a]
                other_count = sum(len(alive[t]) for t in others)
                if len(alive[team_a]) == 1 and other_count >= 2:
                    clutch_player    = next(iter(alive[team_a]))
                    player_team_rows = rnd_spawns[rnd_spawns["player"] == clutch_player]["team"].values
                    if len(player_team_rows) == 0:
                        break
                    won = (player_team_rows[0] == winner)
                    clutch_records.append({
                        "round":  rnd,
                        "player": clutch_player,
                        "team":   player_team_rows[0],
                        "vs":     other_count,
                        "won":    won,
                    })
                    break

    if not clutch_records:
        return {"clutches": pd.DataFrame(), "summary": pd.DataFrame()}

    clutches = pd.DataFrame(clutch_records).drop_duplicates(subset=["round", "player"])

    summary = clutches.groupby("player").agg(
        clutches=("round", "count"),
        won=("won", "sum"),
    ).rename_axis("Player")
    summary["lost"]     = summary["clutches"] - summary["won"]
    summary["win_rate"] = (summary["won"] / summary["clutches"] * 100).round(1)

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


def compute_weapon_stats(kills_df: pd.DataFrame) -> dict:
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        kills_df["user_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    weapon_col = None
    for candidate in ["weapon", "weapon_name"]:
        if candidate in kills_clean.columns:
            weapon_col = candidate
            break

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