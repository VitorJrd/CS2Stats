import pandas as pd
import numpy as np

def assign_rounds_to_df(df, round_df, tick_col="tick"):
    rounds = round_df[round_df["round"] > 0].sort_values("round")
    end_ticks = rounds["tick"].values
    round_numbers = rounds["round"].values

    def get_round(tick):
        idx = np.searchsorted(end_ticks, tick, side="left")
        return int(round_numbers[idx]) if idx < len(round_numbers) else None

    df = df.copy()
    df["round"] = df[tick_col].apply(get_round)
    return df.dropna(subset=["round"])


def compute_utility_stats(flash_df, he_df, smoke_df, molotov_df,
                           damage_df, kills_df, round_df):
    total_rounds = round_df[round_df["round"] > 0].shape[0]

    flash_df   = assign_rounds_to_df(flash_df,   round_df)
    he_df      = assign_rounds_to_df(he_df,      round_df)
    smoke_df   = assign_rounds_to_df(smoke_df,   round_df)
    molotov_df = assign_rounds_to_df(molotov_df, round_df)
    damage_df  = assign_rounds_to_df(damage_df,  round_df)
    kills_df   = assign_rounds_to_df(kills_df,   round_df)

    all_players = sorted(
        set(flash_df["user_name"])   |
        set(he_df["user_name"])      |
        set(smoke_df["user_name"])   |
        set(molotov_df["user_name"])
    )


    flashes_thrown = flash_df.groupby("user_name").size().rename("flashes_thrown")

    flash_assist_kills = kills_df[kills_df["assistedflash"] == True]
    flash_assists = flash_assist_kills.groupby("assister_name").size().rename("flash_assists")


    effective_flashes = (
        flash_assist_kills[flash_assist_kills["assister_name"].notna()]
        .groupby(["assister_name", "round"])
        .size()
        .reset_index()
        .groupby("assister_name")
        .size()
        .rename("rounds_with_flash_assist")
    )

    flash_stats = pd.DataFrame(index=all_players)
    flash_stats = flash_stats.join(flashes_thrown).join(flash_assists).join(effective_flashes)
    flash_stats = flash_stats.fillna(0)
    flash_stats["flash_assist_rate"] = (
        flash_stats["flash_assists"] / flash_stats["flashes_thrown"].replace(0, 1)
    ).round(2)

    he_damage = damage_df[damage_df["weapon"] == "hegrenade"].copy()
    he_damage_clean = he_damage[
        he_damage["attacker_name"].notna() &
        (he_damage["attacker_name"] != he_damage["user_name"])
    ]
    he_dmg_per_player  = he_damage_clean.groupby("attacker_name")["dmg_health"].sum().rename("he_damage")
    he_thrown          = he_df.groupby("user_name").size().rename("he_thrown")
    he_dmg_per_grenade = (he_dmg_per_player / he_thrown.replace(0, 1)).round(1).rename("he_dmg_per_nade")


    smokes_thrown      = smoke_df.groupby("user_name").size().rename("smokes_thrown")
    smokes_per_round   = smoke_df.groupby("round").size()
    avg_smokes_per_round = round(smokes_per_round.mean(), 1)

    
    molotov_damage = damage_df[damage_df["weapon"].isin(["inferno", "molotov", "incgrenade"])].copy()
    molotov_damage_clean = molotov_damage[
        molotov_damage["attacker_name"].notna() &
        (molotov_damage["attacker_name"] != molotov_damage["user_name"])
    ]
    molotov_dmg_per_player = molotov_damage_clean.groupby("attacker_name")["dmg_health"].sum().rename("molotov_damage")
    molotovs_thrown        = molotov_df.groupby("user_name").size().rename("molotovs_thrown")

    
    util = pd.DataFrame(index=sorted(all_players))
    util = (
        util
        .join(flashes_thrown)
        .join(flash_assists)
        .join(flash_stats["flash_assist_rate"])
        .join(he_thrown)
        .join(he_dmg_per_player)
        .join(he_dmg_per_grenade)
        .join(smokes_thrown)
        .join(molotovs_thrown)
        .join(molotov_dmg_per_player)
    )
    util = util.fillna(0)
    util["he_damage"]       = util["he_damage"].astype(int)
    util["molotov_damage"]  = util["molotov_damage"].astype(int)
    util["flashes_thrown"]  = util["flashes_thrown"].astype(int)
    util["flash_assists"]   = util["flash_assists"].astype(int)
    util["he_thrown"]       = util["he_thrown"].astype(int)
    util["smokes_thrown"]   = util["smokes_thrown"].astype(int)
    util["molotovs_thrown"] = util["molotovs_thrown"].astype(int)

    round_util = pd.DataFrame({
        "flashes":  flash_df.groupby("round").size(),
        "he":       he_df.groupby("round").size(),
        "smokes":   smoke_df.groupby("round").size(),
        "molotovs": molotov_df.groupby("round").size(),
    }).fillna(0).astype(int)

    valid_rounds = round_df[round_df["round"] > 0]["round"].values
    round_util = round_util.reindex(valid_rounds, fill_value=0)

    return util, round_util, avg_smokes_per_round
