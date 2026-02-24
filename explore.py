from demoparser2 import DemoParser

parser = DemoParser("test.dem")

# See all available event types in this demo
events = parser.list_game_events()
print(events)

props = parser.list_player_props()
print(props)
