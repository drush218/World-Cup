from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import requests as req_lib
import json
import os
import time
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "wc2026-leaderboard-secret-key")

API_KEY        = os.environ.get("FOOTBALL_API_KEY", "")
AWARDS_FILE    = os.path.join(os.path.dirname(__file__), "awards.json")
FIXTURES_FILE  = os.path.join(os.path.dirname(__file__), "fixtures.json")
CACHE_TTL      = 300  # seconds
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

PLAYERS = [
    {"name": "Paul Armstrong",     "picks": ["Portugal", "Germany", "Switzerland", "Sweden", "Scotland", "Bosnia"],            "ts": "Harry Kane",    "gg": "Emi Martinez",    "pott": "Kylian Mbappe"},
    {"name": "Luke Sullivan",      "picks": ["France", "Belgium", "Japan", "Canada", "Scotland", "Saudi Arabia"],              "ts": "Harry Kane",    "gg": "Jordan Pickford", "pott": "Lamine Yamal"},
    {"name": "William Lyons",      "picks": ["Spain", "Belgium", "Switzerland", "Sweden", "Scotland", "Bosnia"],               "ts": "Harry Kane",    "gg": "Emi Martinez",    "pott": "Lamine Yamal"},
    {"name": "Patrick Maguire",    "picks": ["Spain", "Germany", "Ecuador", "Norway", "Czech Republic", "Bosnia"],             "ts": "Kylian Mbappe", "gg": "Emi Martinez",    "pott": "Lamine Yamal"},
    {"name": "Dariush Abelehkoob", "picks": ["England", "Germany", "Switzerland", "Egypt", "Czech Republic", "Saudi Arabia"],  "ts": "Harry Kane",    "gg": "Mike Maignan",    "pott": "Jude Bellingham"},
    {"name": "Rory Fennell",       "picks": ["France", "Germany", "Ecuador", "Canada", "Scotland", "Ghana"],                  "ts": "Kylian Mbappe", "gg": "Jordan Pickford", "pott": "Lamine Yamal"},
    {"name": "Conor Mathews",      "picks": ["France", "Mexico", "Ecuador", "Algeria", "Scotland", "Bosnia"],                 "ts": "Kylian Mbappe", "gg": "Emi Martinez",    "pott": "Lamine Yamal"},
    {"name": "Ben Rainey",         "picks": ["England", "Germany", "Japan", "Algeria", "Saudi Arabia", "Bosnia"],             "ts": "Kylian Mbappe", "gg": "Unai Simon",      "pott": "Bruno Fernandes"},
    {"name": "Conor Devlin",       "picks": ["Spain", "Belgium", "Turkey", "Norway", "Scotland", "Bosnia"],                   "ts": "Harry Kane",    "gg": "Emi Martinez",    "pott": "Lamine Yamal"},
]

TEAM_GROUP = {
    # Group 1 — favourites tier
    "France": 1, "Spain": 1, "Brazil": 1, "England": 1,
    "Portugal": 1, "Netherlands": 1, "Argentina": 1, "Morocco": 1,
    # Group 2 — favourites tier
    "Uruguay": 2, "Belgium": 2, "Senegal": 2, "Croatia": 2,
    "Germany": 2, "Colombia": 2, "Mexico": 2, "USA": 2,
    # Group 3 — mid tier
    "Switzerland": 3, "Turkey": 3, "Iran": 3, "Japan": 3,
    "South Korea": 3, "Ecuador": 3, "Austria": 3, "Australia": 3,
    # Group 4 — mid tier
    "Algeria": 4, "Sweden": 4, "Panama": 4, "Egypt": 4,
    "Canada": 4, "Ivory Coast": 4, "Paraguay": 4, "Norway": 4,
    # Group 5 — underdog tier
    "Czech Republic": 5, "Uzbekistan": 5, "Qatar": 5, "Iraq": 5,
    "Congo DR": 5, "Scotland": 5, "South Africa": 5, "Tunisia": 5,
    # Group 6 — underdog tier
    "New Zealand": 6, "Haiti": 6, "Saudi Arabia": 6, "Bosnia": 6,
    "Jordan": 6, "Cape Verde": 6, "Curacao": 6, "Ghana": 6,
}

TEAM_CODE = {
    "France": "FRA", "Spain": "ESP", "Brazil": "BRA", "England": "ENG",
    "Portugal": "POR", "Netherlands": "NED", "Argentina": "ARG", "Morocco": "MAR",
    "Uruguay": "URU", "Belgium": "BEL", "Senegal": "SEN", "Croatia": "CRO",
    "Germany": "GER", "Colombia": "COL", "Mexico": "MEX", "USA": "USA",
    "Switzerland": "SUI", "Turkey": "TUR", "Iran": "IRN", "Japan": "JPN",
    "South Korea": "KOR", "Ecuador": "ECU", "Austria": "AUT", "Australia": "AUS",
    "Algeria": "ALG", "Sweden": "SWE", "Panama": "PAN", "Egypt": "EGY",
    "Canada": "CAN", "Ivory Coast": "CIV", "Paraguay": "PAR", "Norway": "NOR",
    "Czech Republic": "CZE", "Uzbekistan": "UZB", "Qatar": "QAT", "Iraq": "IRQ",
    "Congo DR": "COD", "Scotland": "SCO", "South Africa": "RSA", "Tunisia": "TUN",
    "New Zealand": "NZL", "Haiti": "HAI", "Saudi Arabia": "KSA", "Bosnia": "BIH",
    "Jordan": "JOR", "Cape Verde": "CPV", "Curacao": "CUR", "Ghana": "GHA",
}

TEAM_NAME_MAP = {
    "Bosnia and Herzegovina": "Bosnia",
    "Bosnia-Herzegovina": "Bosnia",
    "Czechia": "Czech Republic",
    "Korea Republic": "South Korea",
    "Republic of Korea": "South Korea",
    "DR Congo": "Congo DR",
    "Democratic Republic of Congo": "Congo DR",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "United States": "USA",
    "Cabo Verde": "Cape Verde",
    "Iran (Islamic Republic of)": "Iran",
}

KNOCKOUT_QUALIFIED = {
    "Germany", "Paraguay", "France", "Sweden", "South Africa", "Canada",
    "Netherlands", "Morocco", "Portugal", "Croatia", "Spain", "Austria",
    "USA", "Bosnia", "Belgium", "Senegal", "Brazil", "Japan", "Ivory Coast",
    "Ecuador", "England", "Congo DR", "Argentina", "Cape Verde", "Australia",
    "Egypt", "Switzerland", "Algeria", "Colombia", "Ghana",
}

GROUP_STAGE_DONE = True  # all groups have finished

_cache: dict = {"stats": None, "fixtures": None, "matchday": None, "ts": 0.0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_team(name: str) -> str:
    return TEAM_NAME_MAP.get(name, name)


def _empty_raw() -> dict:
    return {"wins": 0, "losses": 0, "draws": 0, "heavy_losses": 0, "games_played": 0, "ko_eliminated": False}


def _finalize(raw: dict, team: str = "") -> dict:
    ko = max(0, raw["games_played"] - 3)
    out = ko > 0 or team in KNOCKOUT_QUALIFIED
    return {**raw, "ko_rounds": ko, "out_of_group": out, "ko_eliminated": raw.get("ko_eliminated", False), "won_wc": False}


def _pickers_for(team: str) -> list[str]:
    result = []
    for p in PLAYERS:
        if team in p["picks"]:
            parts = p["name"].split()
            result.append(f"{parts[0]} {parts[1][0]}" if len(parts) > 1 else parts[0])
    return result


# ---------------------------------------------------------------------------
# Admin auth
# ---------------------------------------------------------------------------

def is_admin_authed() -> bool:
    return session.get("admin_authed") is True


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------

def fetch_raw_from_api() -> tuple[dict, dict, dict]:
    """Returns (raw_stats, team_matches, matchday_info)."""
    try:
        url = "https://api.football-data.org/v4/competitions/WC/matches"
        r = req_lib.get(url, headers={"X-Auth-Token": API_KEY}, timeout=10)
        r.raise_for_status()
        matches = r.json().get("matches", [])
    except Exception:
        return {}, {}, {}

    all_teams = set(TEAM_GROUP.keys())
    raw: dict[str, dict]  = {t: _empty_raw() for t in all_teams}
    team_matches: dict[str, list] = {t: [] for t in all_teams}

    finished_by_date: dict[str, list] = {}  # "YYYY-MM-DD" -> matches

    for match in matches:
        if match.get("status") != "FINISHED":
            continue
        home = normalize_team(match.get("homeTeam", {}).get("name", ""))
        away = normalize_team(match.get("awayTeam", {}).get("name", ""))
        hs   = match["score"]["fullTime"].get("home") or 0
        as_  = match["score"]["fullTime"].get("away") or 0
        winner = match["score"].get("winner")
        utc_str = match.get("utcDate") or ""
        if utc_str:
            utc_dt = datetime.strptime(utc_str[:19], "%Y-%m-%dT%H:%M:%S")
            date = (utc_dt - timedelta(hours=12)).strftime("%Y-%m-%d")
        else:
            date = ""

        finished_by_date.setdefault(date, []).append({
            "home": home, "away": away,
            "home_score": int(hs), "away_score": int(as_),
        })

        stage = match.get("stage", "")
        is_ko_match = bool(stage) and stage != "GROUP_STAGE"

        for team, is_home in [(home, True), (away, False)]:
            if team not in raw:
                continue
            opponent   = away if is_home else home
            team_score = hs   if is_home else as_
            opp_score  = as_  if is_home else hs

            raw[team]["games_played"] += 1
            if winner == "DRAW":
                raw[team]["draws"] += 1
                result = "D"
            elif (winner == "HOME_TEAM") == is_home:
                raw[team]["wins"] += 1
                result = "W"
            else:
                raw[team]["losses"] += 1
                if abs(hs - as_) >= 3:
                    raw[team]["heavy_losses"] += 1
                result = "L"
                if is_ko_match:
                    raw[team]["ko_eliminated"] = True

            team_matches[team].append({
                "opponent": opponent,
                "team_score": int(team_score),
                "opp_score":  int(opp_score),
                "result": result,
                "source": "api",
            })

    # Number match days chronologically; use noon-UTC boundary so late Americas
    # kickoffs (00:xx UTC next day) stay on the same match day as earlier games.
    all_dates = sorted(d for d in finished_by_date if d)
    date_to_number = {d: i + 1 for i, d in enumerate(all_dates)}

    last_date = all_dates[-1] if all_dates else ""
    last_md_number = date_to_number.get(last_date, 0)

    last_md_matches = []
    for m in finished_by_date.get(last_date, []):
        hs, as_ = m["home_score"], m["away_score"]
        result = "H" if hs > as_ else ("A" if as_ > hs else "D")
        last_md_matches.append({
            **m,
            "result": result,
            "home_pickers": _pickers_for(m["home"]),
            "away_pickers": _pickers_for(m["away"]),
        })

    matchday_info = {"number": last_md_number, "matches": last_md_matches}
    return raw, team_matches, matchday_info


# ---------------------------------------------------------------------------
# Manual fixtures
# ---------------------------------------------------------------------------

def load_fixtures() -> list[dict]:
    if os.path.exists(FIXTURES_FILE):
        with open(FIXTURES_FILE) as f:
            return json.load(f)
    return []


def save_fixtures(fixtures: list[dict]) -> None:
    with open(FIXTURES_FILE, "w") as f:
        json.dump(fixtures, f, indent=2)


def compute_raw_from_fixtures(fixtures: list[dict]) -> tuple[dict, dict]:
    all_teams = set(TEAM_GROUP.keys())
    raw: dict[str, dict]  = {t: _empty_raw() for t in all_teams}
    team_matches: dict[str, list] = {t: [] for t in all_teams}

    for fix in fixtures:
        home, away = fix["home"], fix["away"]
        hs,   as_  = fix["home_score"], fix["away_score"]

        if hs > as_:
            winner = "HOME_TEAM"
        elif as_ > hs:
            winner = "AWAY_TEAM"
        else:
            winner = "DRAW"

        for team, is_home in [(home, True), (away, False)]:
            if team not in raw:
                continue
            opponent   = away if is_home else home
            team_score = hs   if is_home else as_
            opp_score  = as_  if is_home else hs

            raw[team]["games_played"] += 1
            if winner == "DRAW":
                raw[team]["draws"] += 1
                result = "D"
            elif (winner == "HOME_TEAM") == is_home:
                raw[team]["wins"] += 1
                result = "W"
            else:
                raw[team]["losses"] += 1
                if abs(hs - as_) >= 3:
                    raw[team]["heavy_losses"] += 1
                result = "L"

            team_matches[team].append({
                "opponent": opponent,
                "team_score": int(team_score),
                "opp_score":  int(opp_score),
                "result": result,
                "source": "manual",
            })

    return raw, team_matches


# ---------------------------------------------------------------------------
# Build & cache results
# ---------------------------------------------------------------------------

def _build_results() -> tuple[dict, dict, dict]:
    api_raw, api_matches, matchday_info = fetch_raw_from_api()
    fix_raw, fix_matches = compute_raw_from_fixtures(load_fixtures())

    all_teams = set(api_raw) | set(fix_raw)
    stats: dict[str, dict] = {}
    for team in all_teams:
        a = api_raw.get(team, _empty_raw())
        f = fix_raw.get(team, _empty_raw())
        numeric_keys = [k for k in _empty_raw() if k != "ko_eliminated"]
        combined = {k: a[k] + f[k] for k in numeric_keys}
        combined["ko_eliminated"] = a.get("ko_eliminated", False) or f.get("ko_eliminated", False)
        stats[team] = _finalize(combined, team)

    team_fixtures: dict[str, list] = {}
    for team in set(api_matches) | set(fix_matches):
        team_fixtures[team] = api_matches.get(team, []) + fix_matches.get(team, [])

    return stats, team_fixtures, matchday_info


def get_cached() -> tuple[dict, dict, dict]:
    now = time.time()
    if _cache["stats"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["stats"], _cache["fixtures"], _cache["matchday"]
    stats, fixtures, matchday = _build_results()
    _cache["stats"]    = stats
    _cache["fixtures"] = fixtures
    _cache["matchday"] = matchday
    _cache["ts"]       = now
    return stats, fixtures, matchday


def _invalidate_cache() -> None:
    _cache["stats"] = _cache["fixtures"] = _cache["matchday"] = None
    _cache["ts"] = 0.0


# ---------------------------------------------------------------------------
# Awards
# ---------------------------------------------------------------------------

def load_awards() -> dict:
    if os.path.exists(AWARDS_FILE):
        with open(AWARDS_FILE) as f:
            return json.load(f)
    return {"golden_boot": "", "golden_glove": "", "pott": "", "wc_winner": ""}


def save_awards(awards: dict) -> None:
    with open(AWARDS_FILE, "w") as f:
        json.dump(awards, f, indent=2)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _empty_team_stats() -> dict:
    return {
        "wins": 0, "losses": 0, "draws": 0, "heavy_losses": 0,
        "games_played": 0, "ko_rounds": 0, "out_of_group": False, "ko_eliminated": False, "won_wc": False,
    }


def _team_pts(group: int, s: dict) -> int:
    pts = 0
    if group <= 3:
        pts += s["wins"] * 3 + s["losses"] * -6
    else:
        pts += s["wins"] * 6 + s["losses"] * -3
    pts += s["heavy_losses"] * -5
    if s["out_of_group"]:
        pts += 5
    pts += s["ko_rounds"] * 5
    if s["won_wc"]:
        pts += 8
    return pts


def score_player(player: dict, results: dict, awards: dict) -> dict:
    total = 0
    breakdown = []

    for pick in player["picks"]:
        group = TEAM_GROUP.get(pick, 0)
        s = results.get(pick, _empty_team_stats())
        pts = _team_pts(group, s)
        total += pts
        breakdown.append({**s, "team": pick, "group": group, "points": pts})

    award_pts = 0
    if awards.get("golden_boot")  == player["ts"]:  award_pts += 5
    if awards.get("golden_glove") == player["gg"]:   award_pts += 5
    if awards.get("pott")         == player["pott"]: award_pts += 5
    total += award_pts

    return {
        "name": player["name"],
        "ts": player["ts"], "gg": player["gg"], "pott": player["pott"],
        "breakdown": breakdown,
        "award_pts": award_pts,
        "total": total,
        "games_played": sum(b["games_played"] for b in breakdown),
        "is_goat": False,
    }


def score_goat(stats: dict) -> dict:
    """Retroactively picks the highest-scoring team from each group."""
    group_teams: dict[int, list[str]] = {}
    for team, group in TEAM_GROUP.items():
        group_teams.setdefault(group, []).append(team)

    breakdown = []
    total = 0

    for group in sorted(group_teams):
        best_team, best_pts = None, None
        for team in group_teams[group]:
            s = stats.get(team, _empty_team_stats())
            pts = _team_pts(group, s)
            if best_pts is None or pts > best_pts:
                best_pts, best_team = pts, team

        s = stats.get(best_team, _empty_team_stats())
        breakdown.append({**s, "team": best_team, "group": group, "points": best_pts})
        total += best_pts

    return {
        "name": "The GOAT",
        "ts": "", "gg": "", "pott": "",
        "breakdown": breakdown,
        "award_pts": 0,
        "total": total,
        "games_played": sum(b["games_played"] for b in breakdown),
        "is_goat": True,
    }


def compute_scores() -> tuple[list, dict, dict]:
    stats, team_fixtures, matchday_info = get_cached()
    awards = load_awards()

    wc_winner = awards.get("wc_winner", "")
    if wc_winner and wc_winner in stats:
        stats = {**stats, wc_winner: {**stats[wc_winner], "won_wc": True}}

    scores = [score_player(p, stats, awards) for p in PLAYERS]
    goat = score_goat(stats)
    scores.sort(key=lambda x: x["total"], reverse=True)
    for i, s in enumerate(scores):
        s["rank"] = i + 1
        s["is_last"] = False
    scores[-1]["is_last"] = True
    scores.append(goat)

    return scores, team_fixtures, matchday_info


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    scores, team_fixtures, matchday_info = compute_scores()
    last_updated = (
        datetime.fromtimestamp(_cache["ts"]).strftime("%d %b %Y, %H:%M")
        if _cache["ts"] else "—"
    )
    return render_template("index.html",
        scores=scores,
        team_fixtures=team_fixtures,
        matchday_info=matchday_info,
        awards=load_awards(),
        last_updated=last_updated,
        num_players=len(PLAYERS),
        team_code=TEAM_CODE,
        group_stage_done=GROUP_STAGE_DONE,
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_authed"] = True
            return redirect(url_for("admin"))
        error = "Incorrect password."
    return render_template("login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_authed", None)
    return redirect(url_for("index"))


@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not is_admin_authed():
        return redirect(url_for("admin_login"))

    awards   = load_awards()
    fixtures = load_fixtures()
    all_ts    = sorted({p["ts"]   for p in PLAYERS})
    all_gg    = sorted({p["gg"]   for p in PLAYERS})
    all_pott  = sorted({p["pott"] for p in PLAYERS})
    all_teams = sorted({pick for p in PLAYERS for pick in p["picks"]})

    if request.method == "POST":
        if "refresh" in request.form:
            _invalidate_cache()
        else:
            awards = {
                "golden_boot":  request.form.get("golden_boot", ""),
                "golden_glove": request.form.get("golden_glove", ""),
                "pott":         request.form.get("pott", ""),
                "wc_winner":    request.form.get("wc_winner", ""),
            }
            save_awards(awards)
            _invalidate_cache()
        return redirect(url_for("admin"))

    return render_template("admin.html", awards=awards, fixtures=fixtures,
                           all_ts=all_ts, all_gg=all_gg,
                           all_pott=all_pott, all_teams=all_teams)


@app.route("/admin/fixture/add", methods=["POST"])
def fixture_add():
    if not is_admin_authed():
        return redirect(url_for("admin_login"))

    home = request.form.get("home", "").strip()
    away = request.form.get("away", "").strip()
    try:
        home_score = int(request.form.get("home_score", 0))
        away_score = int(request.form.get("away_score", 0))
    except ValueError:
        return redirect(url_for("admin"))

    if not home or not away or home == away:
        return redirect(url_for("admin"))

    fixtures = load_fixtures()
    next_id  = max((f.get("id", 0) for f in fixtures), default=0) + 1
    fixtures.append({"id": next_id, "home": home, "away": away,
                     "home_score": home_score, "away_score": away_score})
    save_fixtures(fixtures)
    _invalidate_cache()
    return redirect(url_for("admin"))


@app.route("/admin/fixture/delete", methods=["POST"])
def fixture_delete():
    if not is_admin_authed():
        return redirect(url_for("admin_login"))

    fix_id = request.form.get("fixture_id", type=int)
    if fix_id is not None:
        fixtures = [f for f in load_fixtures() if f.get("id") != fix_id]
        save_fixtures(fixtures)
        _invalidate_cache()
    return redirect(url_for("admin"))


@app.route("/api/scores")
def api_scores():
    scores, _, _ = compute_scores()
    return jsonify(scores)


if __name__ == "__main__":
    app.run(debug=True)
