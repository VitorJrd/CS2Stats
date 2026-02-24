from demoparser2 import DemoParser
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()

def parse_demo(path: str):
    parser = DemoParser(path)

    #Pull raw events
    kills_df = parser.parse_events("player_death", player_props=[
        "team_name", "total_rounds_played"
    ])

    damage_df = parser.parse_events("player_hurt", player_props=[
        "team_name"
    ])

    round_end_df = parser.parse_events("round_end")

    return parser, kills_df, damage_df, round_end_df


def compute_stats(kills_df, damage_df, round_end_df):
    #Total rounds played
    total_rounds = round_end_df.shape[0]

    #Kills table cleanup
    # demoparser2 prefixes attacker/victim columns
    kills_df = kills_df.rename(columns={
        "attacker_name": "killer",
        "user_name": "victim",
        "attacker_team_name": "killer_team",
        "user_team_name": "victim_team",
        "headshot": "headshot",
    })

    #Remove team kills and suicide
    kills_clean = kills_df[
        kills_df["killer_team"] != kills_df["victim_team"]
    ].copy()
    kills_clean = kills_clean[kills_clean["killer"] != kills_clean["victim"]]

    #Per-player kill/death/assist stats
    kills_per_player = kills_clean.groupby("killer").size().rename("kills")
    deaths_per_player = kills_clean.groupby("victim").size().rename("deaths")
    hs_per_player = kills_clean[kills_clean["headshot"] == True].groupby("killer").size().rename("headshots")
    assists = kills_df[kills_df["assister_name"].notna()]
    assists_per_player = assists.groupby("assister_name").size().rename("assists")

    #Damage per player
    damage_df = damage_df.rename(columns={
        "attacker_name": "attacker",
        "attacker_team_name": "attacker_team",
        "user_team_name": "victim_team",
    })
    damage_clean = damage_df[
        damage_df["attacker_team"] != damage_df["victim_team"]
    ]
    damage_per_player = damage_clean.groupby("attacker")["dmg_health"].sum().rename("total_damage")

    #Combine into one dataframe
    all_players = set(kills_per_player.index) | set(deaths_per_player.index)
    stats = pd.DataFrame(index=sorted(all_players))

    stats = stats.join(kills_per_player).join(deaths_per_player).join(hs_per_player).join(assists_per_player).join(damage_per_player)
    stats = stats.fillna(0).astype(int)

    #Derived stats
    stats["K/D"] = (stats["kills"] / stats["deaths"].replace(0, 1)).round(2)
    stats["HS%"] = ((stats["headshots"] / stats["kills"].replace(0, 1)) * 100).round(1)
    stats["ADR"] = (stats["total_damage"] / total_rounds).round(1)

    return stats, total_rounds


def display_stats(stats: pd.DataFrame, total_rounds: int):
    console.print(f"\n[bold cyan]Total Rounds:[/bold cyan] {total_rounds}\n")

    table = Table(title="Player Stats", show_lines=True)

    table.add_column("Player", style="bold white", no_wrap=True)
    table.add_column("K", style="green", justify="right")
    table.add_column("D", style="red", justify="right")
    table.add_column("A", style="yellow", justify="right")
    table.add_column("K/D", justify="right")
    table.add_column("HS%", justify="right")
    table.add_column("ADR", style="cyan", justify="right")

    #Sort by kills descending
    stats_sorted = stats.sort_values("kills", ascending=False)

    for player, row in stats_sorted.iterrows():
        table.add_row(
            str(player),
            str(row["kills"]),
            str(row["deaths"]),
            str(row["assists"]),
            str(row["K/D"]),
            f"{row['HS%']}%",
            str(row["ADR"]),
        )

    console.print(table)


if __name__ == "__main__":
    parser, kills_df, damage_df, round_end_df = parse_demo("test.dem")
    stats, total_rounds = compute_stats(kills_df, damage_df, round_end_df)
    display_stats(stats, total_rounds)
