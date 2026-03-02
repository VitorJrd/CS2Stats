# CS2 Analyst

A CS2 demo analysis dashboard built with Streamlit. Upload a `.dem` file and get instant access to deep match statistics — from HLTV-style scorecards and economy tracking to clutch detection, opening duel analysis, and position heatmaps.

---

## Features

### Overview
- Full scoreboard with K/D/A, ADR, HS%, KAST% and HLTV Rating 2.0
- Player rating bar chart and ADR vs KAST bubble scatter
- Per-player performance radar vs match average
- Multi-kill round tracking (3K / 4K / ACE) per player
- Weapon breakdown — kills and headshots per gun, per player

### Rounds
- Kill heatmap across all rounds, sorted by fragger
- Opening duel stats — who gets first blood, and how often their team wins afterwards
- Clutch situation detector — 1vX scenarios, win/loss per player, scenario breakdown
- Per-round breakdown with kill feed, player performance, and first blood highlight

### Utility
- Total grenade counts (flash, HE, smoke, molotov)
- Per-player grenade usage table
- Grenade usage per round heatmap
- HE damage per grenade and flash assist rate efficiency charts

### Economy
- Team equipment value per round (T vs CT)
- Win rate by buy type (Full / Half / Force / Eco)
- Buy timeline — visual per round showing buy type and outcome
- Per-player economy: total spent, average per round, average equipment value

### Positions
- Position heatmaps rendered on map radar images
- Modes: deaths, kills, or general positions
- Filter by player or view all players at once
- Floor filter for multi-level maps (e.g. Nuke)

---

## Installation

**Requirements:** Python 3.10+

```bash
git clone https://github.com/yourusername/cs2analyst.git
cd cs2analyst
pip install -r requirements.txt
streamlit run app.py
```

### requirements.txt
```
streamlit
pandas
plotly
demoparser2
requests
Pillow
polars
```

---

## Project Structure

```
cs2analyst/
├── app.py              # Main Streamlit dashboard
├── combat.py           # Clutch, opening duel, multi-kill, weapon analysis
├── kast.py             # KAST% computation
├── rating.py           # HLTV Rating 2.0 approximation
├── round_timeline.py   # Round-by-round kill feed and player matrix
├── utility.py          # Grenade and utility stats
├── economy.py          # Buy type classification and economy tracking
├── heatmap.py          # Position heatmap rendering on map radar
└── assets/
    └── favicon.ico     # App icon
```

---

## Usage

1. Launch the app with `streamlit run app.py`
2. Drop a `.dem` file into the upload area in the top navigation bar
3. The demo is parsed once and cached in session — switching tabs does not re-parse
4. Use the player selectors and sliders within each tab to drill into specific rounds or players

---

## How It Works

Demos are parsed using [`demoparser2`](https://github.com/LaihoE/demoparser), a fast Rust-based CS2 demo parser with a Python API. Raw event data (kills, damage, spawns, grenades, economy ticks) is processed into pandas DataFrames, which are then used to compute all derived statistics and rendered into Plotly charts.

---

## Future Improvements

### Analysis
- [ ] **Ask your demo** — chat interface where you can ask questions like "who performed best under pressure?" and get answers from the data
- [ ] **Side-split performance** — separate T-side and CT-side stats for each player
- [ ] **Smoke / molotov territory control** — detect which areas of the map are being smoked or burned off each round
- [ ] **Flash effectiveness** — track how many enemies were flashed per throw, and for how long

### Visuals
- [ ] **Player movement trails** — draw per-round movement paths on the map radar
- [ ] **Crosshair placement heatmap** — angle pre-aim analysis by position
- [ ] **Side-by-side player comparison** — pick two players and compare all stats in a split view

### Multi-demo / Tournament Support
- [ ] **Multi-demo upload** — analyze a series of matches and view trends over time
- [ ] **Player tracking across demos** — identify players by Steam ID instead of display name to handle name changes
- [ ] **Team aggregated stats** — combine multiple demos to build a full team profile
- [ ] **Map pool breakdown** — performance breakdown by map across multiple matches

### Quality of Life
- [ ] **Export to PDF** — generate a printable post-match report
- [ ] **Shareable match links** — encode match data into a URL for easy sharing
- [ ] **Dark/light theme toggle**
- [ ] **Demo metadata display** — server, matchmaking rank, date and duration

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## License

MIT
