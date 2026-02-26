import pandas as pd

# ~5 seconds at 64 tick = 320 ticks, at 128 tick = 640 ticks
TRADE_WINDOW_TICKS = 320

def compute_kast(kills_df, round_df, spawn_df):
    rounds = round_df[round_df["round"] > 0].copy()
    total_rounds = len(rounds)

    # Map each tick to a round number
    # Each round ends at round_df tick — so a kill belongs to a round
    # if its tick is <= that round's end tick and > previous round's end tick
    round_ticks = rounds[["round", "tick"]].sort_values("round").reset_index(drop=True)

    def get_round_for_tick(tick):
        for _, row in round_ticks.iterrows():
            if tick <= row["tick"]:
                return row["round"]
        return None

    # Vectorized round assignment using searchsorted
    end_ticks = round_ticks["tick"].values
    round_numbers = round_ticks["round"].values

    def assign_rounds(ticks):
        idxs = pd.Series(ticks).apply(lambda t: int(pd.Series(end_ticks).searchsorted(t, side="left")))
        return idxs.apply(lambda i: round_numbers[i] if i < len(round_numbers) else None)

    # --- Clean kills ---
    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()
    kills_clean["round"] = assign_rounds(kills_clean["tick"].values)

    # --- All players ---
    all_players = set(kills_clean["attacker_name"]) | set(kills_clean["user_name"])
    spawned = set(spawn_df["user_name"].dropna())
    all_players = all_players | spawned

    # --- Per round: who got a kill ---
    killers_per_round = kills_clean.groupby("round")["attacker_name"].apply(set).to_dict()

    # --- Per round: who got an assist ---
    assists_df = kills_df[kills_df["assister_name"].notna()].copy()
    assists_df["round"] = assign_rounds(assists_df["tick"].values)
    assisters_per_round = assists_df.groupby("round")["assister_name"].apply(set).to_dict()

    # --- Per round: who died ---
    kills_clean2 = kills_df[kills_df["user_name"].notna()].copy()
    kills_clean2["round"] = assign_rounds(kills_clean2["tick"].values)
    deaths_per_round = kills_clean2.groupby("round")[["user_name", "tick"]].apply(
        lambda x: dict(zip(x["user_name"], x["tick"]))
    ).to_dict()

    # --- Trades: player is traded if killed within TRADE_WINDOW_TICKS of a teammate death ---
    # We need team info — derive from kills: attacker killed user, so they're on opposite teams
    # Build a steamid->team map using kills (attacker and victim are always enemies)
    # Instead, use spawn_df player list and kills to detect trades by timing only
    # A player is traded if someone on their team kills their killer within the window

    # Build kills with round for trade detection
    kills_for_trade = kills_clean.copy()

    def get_traded_players(round_num):
        """Returns set of players who were traded in this round."""
        round_kills = kills_for_trade[kills_for_trade["round"] == round_num].sort_values("tick")
        traded = set()
        for i, death in round_kills.iterrows():
            victim = death["user_name"]
            victim_tick = death["tick"]
            killer = death["attacker_name"]
            # Check if the killer died shortly after (within trade window)
            killer_death = round_kills[
                (round_kills["user_name"] == killer) &
                (round_kills["tick"] > victim_tick) &
                (round_kills["tick"] <= victim_tick + TRADE_WINDOW_TICKS)
            ]
            if not killer_death.empty:
                traded.add(victim)
        return traded

    # --- Per round: who survived ---
    # A player survived if they spawned that round and didn't die
    spawn_df2 = spawn_df.copy()
    spawn_df2["round"] = assign_rounds(spawn_df2["tick"].values)

    def get_survivors(round_num):
        spawned_this_round = set(spawn_df2[spawn_df2["round"] == round_num]["user_name"])
        died_this_round = set(deaths_per_round.get(round_num, {}).keys())
        return spawned_this_round - died_this_round

    # --- Build KAST matrix ---
    kast_data = {player: 0 for player in all_players}

    for _, round_row in rounds.iterrows():
        r = round_row["round"]
        killers   = killers_per_round.get(r, set())
        assisters = assisters_per_round.get(r, set())
        survivors = get_survivors(r)
        traded    = get_traded_players(r)

        for player in all_players:
            if player in killers or player in assisters or player in survivors or player in traded:
                kast_data[player] += 1

    # --- Compute KAST% ---
    kast_pct = {
        player: round((count / total_rounds) * 100, 1)
        for player, count in kast_data.items()
    }

    return kast_pct, total_rounds
