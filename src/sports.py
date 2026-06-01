"""Sports module — fetches football/soccer data from football-data.org API."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

BASE_URL = "https://api.football-data.org/v4"

COMPETITIONS = {
    "WC": "FIFA World Cup",
    "CL": "Champions League",
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "MLS": "MLS",
}

EASTERN = ZoneInfo("US/Eastern")


def _headers() -> dict:
    token = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    return {"X-Auth-Token": token}


def _get(endpoint: str, params: dict = None) -> dict | None:
    try:
        resp = httpx.get(
            f"{BASE_URL}{endpoint}",
            headers=_headers(),
            params=params or {},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"  [WARN] football-data.org {endpoint} returned {resp.status_code}")
        return None
    except Exception as e:
        print(f"  [WARN] football-data.org request failed: {e}")
        return None


def fetchMatches(dateFrom: str = None, dateTo: str = None, competitionCodes: list[str] = None) -> list[dict]:
    """Fetch matches across tracked competitions for a date range.

    Args:
        dateFrom: YYYY-MM-DD (defaults to today)
        dateTo: YYYY-MM-DD (defaults to tomorrow)
        competitionCodes: list of competition codes to include (defaults to all tracked)

    Returns list of match dicts with normalized fields.
    """
    now = datetime.now(EASTERN)
    if not dateFrom:
        dateFrom = now.strftime("%Y-%m-%d")
    if not dateTo:
        dateTo = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    codes = competitionCodes or list(COMPETITIONS.keys())
    allMatches = []

    for code in codes:
        data = _get(f"/competitions/{code}/matches", {
            "dateFrom": dateFrom,
            "dateTo": dateTo,
        })
        if not data or "matches" not in data:
            print(f"  Skipping {code} — no data or not available on current plan")
            continue

        compName = COMPETITIONS.get(code, code)
        for m in data["matches"]:
            allMatches.append(_normalizeMatch(m, compName, code))

    allMatches.sort(key=lambda m: m["utcDate"])
    return allMatches


def fetchStandings(competitionCode: str) -> list[dict] | None:
    """Fetch current standings/table for a competition."""
    data = _get(f"/competitions/{competitionCode}/standings")
    if not data or "standings" not in data:
        return None

    standings = []
    for table in data["standings"]:
        if table.get("type") != "TOTAL":
            continue
        group = table.get("group", "")
        for row in table.get("table", []):
            standings.append({
                "position": row["position"],
                "team": row["team"]["name"],
                "teamShort": row["team"].get("tla", ""),
                "played": row["playedGames"],
                "won": row["won"],
                "draw": row["draw"],
                "lost": row["lost"],
                "gf": row["goalsFor"],
                "ga": row["goalsAgainst"],
                "gd": row["goalDifference"],
                "points": row["points"],
                "group": group,
            })
    return standings


def fetchTeamMatches(teamName: str, competitionCode: str = None, limit: int = 5) -> list[dict]:
    """Fetch recent/upcoming matches for a specific team by searching for it."""
    params = {"limit": limit}
    if competitionCode:
        params["competitions"] = competitionCode

    data = _get("/teams", {"name": teamName})
    if not data or not data.get("teams"):
        return []

    teamId = data["teams"][0]["id"]
    matchData = _get(f"/teams/{teamId}/matches", {
        "limit": limit,
        "status": "SCHEDULED,LIVE,IN_PLAY,PAUSED,FINISHED",
    })
    if not matchData or "matches" not in matchData:
        return []

    compName = COMPETITIONS.get(competitionCode, "") if competitionCode else ""
    return [_normalizeMatch(m, compName or m.get("competition", {}).get("name", ""), "") for m in matchData["matches"]]


def _normalizeMatch(m: dict, compName: str, compCode: str) -> dict:
    """Normalize a match object from the API."""
    homeTeam = m.get("homeTeam", {})
    awayTeam = m.get("awayTeam", {})
    score = m.get("score", {})
    fullTime = score.get("fullTime", {})
    halfTime = score.get("halfTime", {})

    utcDate = m.get("utcDate", "")
    localTime = ""
    if utcDate:
        try:
            dt = datetime.fromisoformat(utcDate.replace("Z", "+00:00"))
            localTime = dt.astimezone(EASTERN).strftime("%b %d, %I:%M %p ET")
        except (ValueError, TypeError):
            localTime = utcDate

    return {
        "competition": compName,
        "competitionCode": compCode,
        "matchday": m.get("matchday"),
        "stage": m.get("stage", ""),
        "group": m.get("group", ""),
        "status": m.get("status", ""),
        "utcDate": utcDate,
        "localTime": localTime,
        "homeTeam": homeTeam.get("name", "Unknown"),
        "homeShort": homeTeam.get("tla", ""),
        "awayTeam": awayTeam.get("name", "Unknown"),
        "awayShort": awayTeam.get("tla", ""),
        "homeScore": fullTime.get("home"),
        "awayScore": fullTime.get("away"),
        "halfTimeHome": halfTime.get("home"),
        "halfTimeAway": halfTime.get("away"),
        "winner": score.get("winner", ""),
    }


def buildSportsBriefText(matches: list[dict], standings: list[dict] = None) -> str:
    """Build a plain-text sports brief for AI summarization or direct delivery."""
    if not matches and not standings:
        return "No upcoming matches or results found for tracked competitions."

    sections = []

    if matches:
        byComp = {}
        for m in matches:
            comp = m["competition"] or "Other"
            byComp.setdefault(comp, []).append(m)

        for comp, compMatches in byComp.items():
            lines = [f"\n## {comp}"]
            for m in compMatches:
                status = m["status"]
                if status == "FINISHED":
                    result = f"{m['homeTeam']} {m['homeScore']} - {m['awayScore']} {m['awayTeam']}"
                    ht = ""
                    if m["halfTimeHome"] is not None:
                        ht = f" (HT: {m['halfTimeHome']}-{m['halfTimeAway']})"
                    lines.append(f"  RESULT: {result}{ht}")
                elif status in ("LIVE", "IN_PLAY", "PAUSED"):
                    lines.append(f"  LIVE: {m['homeTeam']} {m['homeScore']} - {m['awayScore']} {m['awayTeam']}")
                elif status in ("TIMED", "SCHEDULED"):
                    lines.append(f"  UPCOMING: {m['homeTeam']} vs {m['awayTeam']} — {m['localTime']}")
                else:
                    lines.append(f"  {status}: {m['homeTeam']} vs {m['awayTeam']} — {m['localTime']}")

                if m.get("stage") and m["stage"] not in ("REGULAR_SEASON", "LEAGUE_STAGE"):
                    lines.append(f"    Stage: {m['stage'].replace('_', ' ').title()}")
                if m.get("group"):
                    lines.append(f"    {m['group'].replace('_', ' ').title()}")

            sections.append("\n".join(lines))

    if standings:
        lines = ["\n## Standings"]
        currentGroup = ""
        for row in standings[:20]:
            if row["group"] and row["group"] != currentGroup:
                currentGroup = row["group"]
                lines.append(f"\n  {currentGroup.replace('_', ' ').title()}")
            lines.append(
                f"  {row['position']}. {row['team']} — "
                f"{row['points']}pts (W{row['won']} D{row['draw']} L{row['lost']}, "
                f"GD {row['gd']:+d})"
            )
        sections.append("\n".join(lines))

    return "\n".join(sections)
