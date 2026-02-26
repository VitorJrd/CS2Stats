import os
os.environ["POLARS_SKIP_CPU_CHECK"] = "1"

from demoparser2 import DemoParser
import pandas as pd
from rich.console import Console
from rich.table import Table
from kast import compute_kast
from rating import compute_rating

console = Console()

def parse_demo(path: str):
    parser = DemoParser(path)
    _, kills_df  = parser.parse_events(["player_death"])[0]
    _, damage_df = parser.parse_events(["player_hurt"])[0]
    _, round_df  = parser.parse_events(["round_end"])[0]
    _, spawn_df  = parser.parse_events(["player_spawn"])[0]
    return kills_df, damage_df, round_df, spawn_df


def compute_stats(kills_df, damage_df, round_df, spawn_df):
    total_rounds = round_df[round_df["round"] > 0].shape[0]

    kills_clean = kills_df[
        kills_df["attacker_name"].notna() &
        (kills_df["attacker_name"] != kills_df["user_name"])
    ].copy()

    kills_per_player  = kills_clean.groupby("attacker_name").size().rename("kills")
    deaths_per_player = kills_clean.groupby("user_name").size().rename("deaths")
    hs_per_player     = kills_clean[kills_clean["headshot"] == True].groupby("attacker_name").size().rename("headshots")
    assists_per_player = (
        kills_df[kills_df["assister_name"].notna()]
        .groupby("assister_name").size().rename("assists")
    )

    damage_clean = damage_df[
        damage_df["attacker_name"].notna() &
        (damage_df["attacker_name"] != damage_df["user_name"])
    ].copy()
    damage_per_player = damage_clean.groupby("attacker_name")["dmg_health"].sum().rename("total_damage")

    all_players = set(kills_per_player.index) | set(deaths_per_player.index)
    stats = pd.DataFrame(index=sorted(all_players))
    stats = (
        stats
        .join(kills_per_player)
        .join(deaths_per_player)
        .join(hs_per_player)
        .join(assists_per_player)
        .join(damage_per_player)
    )
    stats = stats.fillna(0).astype(int)

    stats["K/D"] = (stats["kills"] / stats["deaths"].replace(0, 1)).round(2)
    stats["HS%"] = ((stats["headshots"] / stats["kills"].replace(0, 1)) * 100).round(1)
    stats["ADR"] = (stats["total_damage"] / total_rounds).round(1)

    # Add KAST
    kast_pct, _ = compute_kast(kills_df, round_df, spawn_df)
    stats["KAST%"] = stats.index.map(lambda p: kast_pct.get(p, 0.0))

    # Add Rating
    stats["Rating"] = compute_rating(stats, kills_df, round_df)

    return stats, total_rounds


def display_stats(stats: pd.DataFrame, total_rounds: int):
    console.print(f"\n[bold cyan]Total Rounds Played:[/bold cyan] {total_rounds}\n")

    table = Table(title="CS2 Match Stats", show_lines=True)
    table.add_column("Player", style="bold white", no_wrap=True)
    table.add_column("K",      style="green",  justify="right")
    table.add_column("D",      style="red",    justify="right")
    table.add_column("A",      style="yellow", justify="right")
    table.add_column("K/D",                    justify="right")
    table.add_column("HS%",                    justify="right")
    table.add_column("ADR",    style="cyan",   justify="right")
    table.add_column("KAST%",  style="magenta",justify="right")
    table.add_column("Rating", style="bold yellow", justify="right")

    for player, row in stats.sort_values("kills", ascending=False).iterrows():
        table.add_row(
            str(player),
            str(row["kills"]),
            str(row["deaths"]),
            str(row["assists"]),
            str(row["K/D"]),
            f"{row['HS%']}%",
            str(row["ADR"]),
            f"{row['KAST%']}%",
            f"{row['Rating']:.3f}",
        )

    console.print(table)


if __name__ == "__main__":
    kills_df, damage_df, round_df, spawn_df = parse_demo("test.dem")
    stats, total_rounds = compute_stats(kills_df, damage_df, round_df, spawn_df)
    display_stats(stats, total_rounds)
