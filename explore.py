import os
os.environ["POLARS_SKIP_CPU_CHECK"] = "1"

from demoparser2 import DemoParser
parser = DemoParser("test.dem")

kills_name, kills_df = parser.parse_events(["player_death"])[0]
damage_name, damage_df = parser.parse_events(["player_hurt"])[0]
round_name, round_df = parser.parse_events(["round_end"])[0]

print("=== player_death columns ===")
print(kills_df.columns.tolist())
print(kills_df.head(2).to_string())

print("\n=== player_hurt columns ===")
print(damage_df.columns.tolist())
print(damage_df.head(2).to_string())

print("\n=== round_end columns ===")
print(round_df.columns.tolist())
print(round_df.head(2).to_string())

_, spawn_df = parser.parse_events(["player_spawn"])[0]
print("=== player_spawn columns ===")
print(spawn_df.columns.tolist())
print(spawn_df.head(3).to_string())

_, round_end_df = parser.parse_events(["round_end"])[0]
_, round_freeze_df = parser.parse_events(["round_freeze_end"])[0]

print("=== round_end columns ===")
print(round_end_df.columns.tolist())
print(round_end_df.to_string())

print("\n=== round_freeze_end columns ===")
print(round_freeze_df.columns.tolist())
print(round_freeze_df.head(3).to_string())
