# World Cup 2026 Predictor Leaderboard

## Setup

```bash
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000

## Routes

| Route | Description |
|---|---|
| `/` | Leaderboard — click any row to expand per-team breakdown |
| `/admin` | Set Golden Boot / Golden Glove / POTT / WC Winner; refresh cache |
| `/api/scores` | Full JSON scores for all players |

## Scoring

| Rule | Points |
|---|---|
| Tier 1–3 team wins a match | +3 |
| Tier 1–3 team loses a match | −6 |
| Tier 4–6 team wins a match | +6 |
| Tier 4–6 team loses a match | −3 |
| Any team loses by 3+ goals | −5 additional |
| Team qualifies from group stage | +5 |
| Each knockout round played | +5 |
| Team wins the World Cup | +8 |
| Correct Golden Boot pick | +5 |
| Correct Golden Glove pick | +5 |
| Correct Player of Tournament pick | +5 |

Knockout rounds are counted automatically: every game a team plays beyond their first 3 counts as one knockout round.

## Plugging in a different API

The `fetch_results()` function in `app.py` is the only place that talks to the API.
It currently calls `https://api.football-data.org/v4/competitions/WC/matches` with
an `X-Auth-Token` header. To swap in a different data source, replace the `try` block
inside that function. The function must return a `dict[team_name, stats_dict]` —
see the docstring for the expected shape.

If a team name from the API doesn't match the internal name used in `PLAYERS`, add
a mapping to `TEAM_NAME_MAP` near the top of `app.py`.

## API key

The key is currently hardcoded in `app.py`. To use an environment variable instead:

```bash
set FOOTBALL_API_KEY=your_key_here   # Windows
python app.py
```
