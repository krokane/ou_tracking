"""
Fetches current MLB standings from the MLB Stats API and writes them to data/standings.json.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STANDINGS_PATH = DATA_DIR / "standings.json"

MLB_STANDINGS_URL = (
    "https://statsapi.mlb.com/api/v1/standings"
    "?leagueId=103,104"
    "&season={year}"
    "&standingsTypes=regularSeason"
    "&hydrate=team"
)

DIVISION_NAMES = {
    200: "American League West",
    201: "American League East",
    202: "American League Central",
    203: "National League West",
    204: "National League East",
    205: "National League Central",
}

DIVISION_ORDER = {
    "American League East":    0,
    "American League Central": 1,
    "American League West":    2,
    "National League East":    3,
    "National League Central": 4,
    "National League West":    5,
}

AL_DIVISIONS = {"American League East", "American League Central", "American League West"}
NL_DIVISIONS = {"National League East", "National League Central", "National League West"}


def compute_playoff_badges(standings: list) -> dict:
    """
    Returns a dict of team_id -> badge string.
    Badge values: 'DIV', 'WC1', 'WC2', 'WC3', or None (not in playoffs).
    """
    badges = {}
    for league_divs in [AL_DIVISIONS, NL_DIVISIONS]:
        by_div = {}
        for t in standings:
            if t["division"] in league_divs:
                by_div.setdefault(t["division"], []).append(t)

        other_teams = []
        for div_teams in by_div.values():
            if div_teams:
                # div_teams already sorted wins desc; first is division leader
                badges[div_teams[0]["team_id"]] = "DIV"
                other_teams.extend(div_teams[1:])

        # Sort non-division-winners by win pct for wild card race
        other_teams.sort(
            key=lambda t: t["wins"] / max(t["wins"] + t["losses"], 1),
            reverse=True,
        )
        for i, t in enumerate(other_teams[:3]):
            badges[t["team_id"]] = f"WC{i + 1}"

    return badges


def fetch_standings() -> Optional[dict]:
    DATA_DIR.mkdir(exist_ok=True)
    year = datetime.now().year
    url = MLB_STANDINGS_URL.format(year=year)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        raw = resp.json()
    except Exception as exc:
        print(f"[refresh] ERROR fetching standings: {exc}", file=sys.stderr)
        return None

    standings = []
    for record in raw.get("records", []):
        div_id = record["division"]["id"]
        division_name = DIVISION_NAMES.get(div_id, f"Division {div_id}")

        for tr in record["teamRecords"]:
            team = tr["team"]

            last10 = home_rec = away_rec = ""
            for split in tr.get("records", {}).get("splitRecords", []):
                t = split.get("type")
                if t == "lastTen":
                    last10 = f"{split['wins']}-{split['losses']}"
                elif t == "home":
                    home_rec = f"{split['wins']}-{split['losses']}"
                elif t == "away":
                    away_rec = f"{split['wins']}-{split['losses']}"

            standings.append(
                {
                    "team_id":      team["id"],
                    "team":         team["name"],
                    "abbreviation": team.get("abbreviation", ""),
                    "wins":         tr["wins"],
                    "losses":       tr["losses"],
                    "pct":          tr["winningPercentage"],
                    "gb":           tr.get("gamesBack", "-"),
                    "division":     division_name,
                    "streak":       tr.get("streak", {}).get("streakCode", ""),
                    "last10":       last10,
                    "home":         home_rec,
                    "away":         away_rec,
                    "games_played": tr.get("gamesPlayed", 0),
                }
            )

    standings.sort(
        key=lambda x: (DIVISION_ORDER.get(x["division"], 99), -x["wins"], x["losses"])
    )

    # Annotate each team with its playoff position badge
    badges = compute_playoff_badges(standings)
    for t in standings:
        t["playoff_badge"] = badges.get(t["team_id"])

    result = {
        "last_updated": datetime.now().isoformat(),
        "season":       year,
        "standings":    standings,
    }

    with open(STANDINGS_PATH, "w") as f:
        json.dump(result, f, indent=2)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Standings updated — {len(standings)} teams, season {year}")
    return result


if __name__ == "__main__":
    result = fetch_standings()
    if result is None:
        sys.exit(1)
