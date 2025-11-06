#!/usr/bin/env python3
"""
Rank the previous day's NBA games by excitement using ESPN win probability data.

Examples:
    python daily_exciting_games.py             # analyzes last night's games (Eastern Time)
    python daily_exciting_games.py --date 2025-11-01  # analyze a specific date
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from typing import Any, Dict, List, Optional

import requests
from excitement import ExcitementAnalysis, calculate_excitement, load_home_win_probabilities

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None  # type: ignore

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"


def determine_target_date(raw: Optional[str]) -> dt.date:
    """Use supplied ISO date or fall back to 'yesterday' in Eastern Time."""
    if raw:
        return dt.date.fromisoformat(raw)

    if ZoneInfo is None:
        eastern_now = dt.datetime.utcnow()
    else:
        eastern_now = dt.datetime.now(tz=ZoneInfo("America/New_York"))
    return (eastern_now - dt.timedelta(days=1)).date()


def fetch_json(url: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fetch a JSON payload, raising an informative error on failure."""
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def extract_game_cards(scoreboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return competitions with event metadata."""
    games = []
    for event in scoreboard.get("events", []):
        event_id = event.get("id")
        competitions = event.get("competitions", [])
        if not event_id or not competitions:
            continue
        competition = competitions[0]
        competitors = competition.get("competitors", [])
        if len(competitors) < 2:
            continue
        games.append({"event_id": event_id, "competitors": competitors})
    return games


def describe_matchup(competitors: List[Dict[str, Any]]) -> str:
    """Produce a matchup description without final scores."""
    home_name = away_name = "Unknown"
    for comp in competitors:
        team = comp.get("team", {})
        display_name = team.get("displayName") or team.get("name") or "Unknown"
        if comp.get("homeAway") == "home":
            home_name = display_name
        elif comp.get("homeAway") == "away":
            away_name = display_name
    return f"{away_name} at {home_name}"


def analyze_game(event_id: str, competitors: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Fetch summary data for a game and return excitement analysis if available."""
    summary = fetch_json(SUMMARY_URL, params={"event": event_id})
    winprob = summary.get("winprobability")
    if not isinstance(winprob, list) or not winprob:
        return None

    probabilities = load_home_win_probabilities(winprob)
    analysis: ExcitementAnalysis = calculate_excitement(probabilities)

    return {
        "event_id": event_id,
        "matchup": describe_matchup(competitors),
        "analysis": analysis,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rank NBA games by excitement using ESPN win probability data."
    )
    parser.add_argument(
        "--date",
        help="ISO date (YYYY-MM-DD) to analyze. Defaults to yesterday in Eastern Time.",
    )
    args = parser.parse_args()

    target_date = determine_target_date(args.date)
    yyyymmdd = target_date.strftime("%Y%m%d")

    try:
        scoreboard = fetch_json(SCOREBOARD_URL, params={"dates": yyyymmdd})
    except requests.HTTPError as exc:
        print(f"Failed to fetch scoreboard for {target_date}: {exc}", file=sys.stderr)
        return 1

    games = extract_game_cards(scoreboard)
    if not games:
        print(f"No games found for {target_date}.")
        return 0

    results = []
    for game in games:
        try:
            outcome = analyze_game(game["event_id"], game["competitors"])
        except requests.HTTPError as exc:
            print(f"Failed to fetch summary for event {game['event_id']}: {exc}", file=sys.stderr)
            continue
        except (KeyError, ValueError) as exc:
            print(f"Skipping event {game['event_id']}: {exc}", file=sys.stderr)
            continue

        if outcome:
            results.append(outcome)

    if not results:
        print(f"No excitement data available for {target_date}.")
        return 0

    results.sort(key=lambda item: item["analysis"].score, reverse=True)

    print(f"Excitement rankings for {target_date.isoformat()}:")
    for idx, result in enumerate(results, start=1):
        analysis: ExcitementAnalysis = result["analysis"]
        print(
            f"{idx}. {result['matchup']}: "
            f"{analysis.verdict} — excitement {analysis.score:.2f}/10 "
            f"(lead changes {analysis.lead_changes}, biggest swing {analysis.max_swing:.3f})"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

