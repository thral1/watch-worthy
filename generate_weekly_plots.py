#!/usr/bin/env python3
"""
Fetch the last 7 days of NBA games, score excitement, and build a spoiler-safe dashboard.

By default we only render an excitement meter, keeping win probability charts hidden so that
final outcomes are not revealed. Pass --charts if you still want PNG charts saved alongside.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from excitement import ExcitementAnalysis, calculate_excitement, load_home_win_probabilities

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"


def fetch_json(url: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def extract_game_cards(scoreboard: Dict[str, Any]) -> List[Dict[str, Any]]:
    games: List[Dict[str, Any]] = []
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
    home_name = away_name = "Unknown"
    for comp in competitors:
        team = comp.get("team", {})
        display_name = team.get("displayName") or team.get("name") or "Unknown"
        if comp.get("homeAway") == "home":
            home_name = display_name
        elif comp.get("homeAway") == "away":
            away_name = display_name
    return f"{away_name} at {home_name}"


def slugify(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "game"


def plot_win_probability(
    probabilities: List[float],
    play_ids: List[str],
    matchup: str,
    date_label: str,
    excitement: ExcitementAnalysis,
    output_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    percent_values = [p * 100 for p in probabilities]
    indices = list(range(len(percent_values)))
    labels = [pid[-3:] if len(pid) > 3 else pid for pid in play_ids]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(indices, percent_values, color="#1f77b4", linewidth=2, label="Home win %")
    ax.fill_between(
        indices,
        percent_values,
        50,
        where=[value >= 50 for value in percent_values],
        color="#1f77b4",
        alpha=0.15,
    )
    ax.fill_between(
        indices,
        percent_values,
        50,
        where=[value < 50 for value in percent_values],
        color="#d62728",
        alpha=0.15,
    )
    ax.axhline(50, color="#666666", linestyle="--", linewidth=1, label="Even odds")

    ax.set_ylabel("Home win probability (%)")
    ax.set_xlabel("Play sequence")
    ax.set_ylim(0, 100)
    ax.set_xlim(0, len(indices) - 1)
    ax.set_title(
        f"{matchup} — {date_label}\nExcitement: {excitement.score:.2f}/10 ({excitement.verdict})"
    )

    tick_count = min(10, len(labels))
    if tick_count > 1:
        step = max(1, len(labels) // tick_count)
        positions = indices[::step]
        tick_labels = labels[::step]
        if len(positions) > tick_count:
            positions = positions[:tick_count]
            tick_labels = tick_labels[:tick_count]
        ax.set_xticks(positions)
        ax.set_xticklabels(tick_labels, rotation=45, fontsize=8)
    else:
        ax.set_xticks(indices)
        ax.set_xticklabels(labels)

    ax.legend(loc="lower center", ncol=3, frameon=False)
    ax.grid(axis="y", linestyle=":", linewidth=0.5, alpha=0.5)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def build_dashboard(
    results_by_date: Dict[str, List[Dict[str, Any]]],
    *,
    dashboard_path: Path,
    include_charts: bool,
) -> None:
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='utf-8' />",
        "  <meta name='viewport' content='width=device-width, initial-scale=1' />",
        "  <title>Weekly NBA Excitement Dashboard</title>",
        "  <style>",
        "    :root { color-scheme: dark; }",
        "    body { font-family: 'Inter', 'Segoe UI', Arial, sans-serif; background:#0c1116; color:#e3f2fd; margin:0; padding:0; }",
        "    header { padding: 28px 34px 22px; background: linear-gradient(135deg,#1a237e,#0d47a1 40%,#26a69a); box-shadow:0 12px 32px rgba(13,71,161,0.35); }",
        "    header h1 { margin:0; font-size: 30px; font-weight:700; color:#fff; letter-spacing:0.4px; }",
        "    header p { margin:10px 0 0; color:#bbdefb; max-width:720px; line-height:1.45; }",
        "    main { padding: 28px 34px 56px; }",
        "    section { margin-bottom: 52px; }",
        "    section h2 { font-size:24px; margin:0 0 18px; color:#80deea; letter-spacing:0.3px; }",
        "    .grid { display:grid; gap:26px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }",
        "    .card { background:#121a21; border-radius:16px; border:1px solid rgba(128,222,234,0.18); overflow:hidden; box-shadow:0 12px 32px rgba(0,0,0,0.45); display:flex; flex-direction:column; }",
        "    .card header { padding:20px 22px 18px; border-bottom:1px solid rgba(128,222,234,0.12); background:linear-gradient(135deg,rgba(38,166,154,0.18),rgba(13,71,161,0.18)); }",
        "    .card header h3 { margin:0; font-size:19px; color:#fff; letter-spacing:0.2px; }",
        "    .card header p { margin:6px 0 0; color:#b0bec5; font-size:14px; letter-spacing:0.4px; text-transform:uppercase; }",
        "    .meter { margin:22px 22px 0; height:18px; background:#0f1419; border-radius:999px; position:relative; overflow:hidden; border:1px solid rgba(128,222,234,0.35); box-shadow: inset 0 0 12px rgba(0,0,0,0.45); }",
        "    .meter .fill { display:block; height:100%; border-radius:999px; background:linear-gradient(90deg,#ef5350,#ffa726,#ffee58,#66bb6a,#26a69a); box-shadow:0 0 20px rgba(102,187,106,0.45); transition:width 0.6s ease; }",
        "    .meter-label { margin:12px 22px 0; font-size:13px; letter-spacing:0.6px; color:#e0f2f1; text-transform:uppercase; }",
        "    .card footer { padding:14px 22px 20px; color:#cfd8dc; font-size:13px; background:#10161c; border-top:1px solid rgba(128,222,234,0.12); }",
        "    .metrics { margin:10px 0 0; display:flex; flex-wrap:wrap; gap:12px; font-size:12px; letter-spacing:0.8px; text-transform:uppercase; }",
        "    .chip { background:rgba(12,97,109,0.45); padding:7px 12px; border-radius:999px; border:1px solid rgba(128,222,234,0.28); color:#80deea; }",
        "    .chip strong { color:#e1f5fe; margin-left:4px; font-size:12px; }",
        "    .note { margin-top: 10px; font-size:12px; color:#90a4ae; letter-spacing:0.3px; }",
        "    @media (max-width: 720px) { main { padding: 20px 18px 48px; } header { padding: 24px 18px 20px; } }",
        "  </style>",
        "</head>",
        "<body>",
        "  <header>",
        "    <h1>Weekly NBA Excitement Dashboard</h1>",
        "    <p>Each card shows how wild the win-probability swings were without revealing final scores. The excitement bar is scaled 0–10, with colors shifting from calm (left) to chaos (right).</p>",
        "  </header>",
        "  <main>",
    ]

    for date in sorted(results_by_date.keys(), reverse=True):
        entries = results_by_date[date]
        html_parts.append("    <section>")
        html_parts.append(f"      <h2>{date}</h2>")
        html_parts.append("      <div class='grid'>")
        for rank, item in enumerate(entries, start=1):
            score_pct = f"{item['score_percent'] * 100:.1f}%"
            html_parts.append("        <article class='card'>")
            html_parts.append("          <header>")
            html_parts.append(f"            <h3>{rank}. {item['matchup']}</h3>")
            html_parts.append(
                f"            <p>{item['verdict']} &nbsp;&bull;&nbsp; {item['score']:.2f}/10 excitement</p>"
            )
            html_parts.append("          </header>")
            html_parts.append(
                f"          <div class='meter' role='img' aria-label='Excitement {item['score']:.2f} out of 10'>"
            )
            html_parts.append(f"            <span class='fill' style='width:{score_pct};'></span>")
            html_parts.append("          </div>")
            html_parts.append(
                f"          <p class='meter-label'>Intensity meter: {item['score']:.2f}/10</p>"
            )
            html_parts.append("          <footer>")
            html_parts.append("            <div class='metrics'>")
            html_parts.append(
                f"              <span class='chip'>Lead changes<strong>{item['lead_changes']}</strong></span>"
            )
            html_parts.append(
                f"              <span class='chip'>Biggest swing<strong>{item['max_swing']:.3f}</strong></span>"
            )
            if include_charts and item.get("image"):
                html_parts.append(
                    f"              <span class='chip'>Chart saved<strong>{item['image']}</strong></span>"
                )
            html_parts.append("            </div>")
            html_parts.append("            <p class='note'>Higher bars mean more volatile finish-time drama.</p>")
            html_parts.append("          </footer>")
            html_parts.append("        </article>")
        html_parts.append("      </div>")
        html_parts.append("    </section>")

    html_parts.extend(
        [
            "  </main>",
            "</body>",
            "</html>",
        ]
    )

    dashboard_path.write_text("\n".join(html_parts), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank NBA games by excitement and build a spoiler-friendly dashboard."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of past days to include (default: 7).",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Also render PNG win probability charts (may reveal spoilers).",
    )
    args = parser.parse_args()

    day_count = max(1, args.days)
    include_charts = bool(args.charts)

    today = dt.date.today()
    dates = [(today - dt.timedelta(days=offset)) for offset in range(1, day_count + 1)]
    output_dir = Path("plots")
    summary_path = output_dir / "weekly_summary.json"
    dashboard_path = output_dir / "index.html"
    summary_lines: List[str] = []
    results_by_date: Dict[str, List[Dict[str, Any]]] = {}

    for target_date in dates:
        yyyymmdd = target_date.strftime("%Y%m%d")
        try:
            scoreboard = fetch_json(SCOREBOARD_URL, params={"dates": yyyymmdd})
        except requests.HTTPError as exc:
            summary_lines.append(f"{target_date}: failed to fetch scoreboard ({exc})")
            continue

        games = extract_game_cards(scoreboard)
        if not games:
            summary_lines.append(f"{target_date}: no games.")
            continue

        for game in games:
            event_id = game["event_id"]
            matchup = describe_matchup(game["competitors"])
            try:
                summary = fetch_json(SUMMARY_URL, params={"event": event_id})
            except requests.HTTPError as exc:
                summary_lines.append(f"{target_date} {matchup}: summary fetch failed ({exc})")
                continue

            winprob = summary.get("winprobability")
            if not isinstance(winprob, list) or not winprob:
                summary_lines.append(f"{target_date} {matchup}: no win probability data.")
                continue

            try:
                probabilities = load_home_win_probabilities(winprob)
            except (KeyError, ValueError) as exc:
                summary_lines.append(f"{target_date} {matchup}: invalid data ({exc})")
                continue

            play_ids = [entry.get("playId", str(idx)) for idx, entry in enumerate(winprob)]
            excitement = calculate_excitement(probabilities)

            image_name: Optional[str] = None
            if include_charts:
                filename = f"{target_date.isoformat()}_{slugify(matchup)}.png"
                output_path = output_dir / filename
                plot_win_probability(
                    probabilities,
                    play_ids,
                    matchup,
                    target_date.isoformat(),
                    excitement,
                    output_path,
                )
                image_name = output_path.name
                summary_lines.append(
                    f"{target_date} {matchup}: saved {output_path.name} (score {excitement.score:.2f})"
                )
            else:
                summary_lines.append(
                    f"{target_date} {matchup}: excitement {excitement.score:.2f} (charts disabled)"
                )

            results_by_date.setdefault(target_date.isoformat(), []).append(
                {
                    "date": target_date.isoformat(),
                    "matchup": matchup,
                    "score": excitement.score,
                    "score_percent": max(0.0, min(1.0, excitement.score / 10.0)),
                    "verdict": excitement.verdict,
                    "lead_changes": excitement.lead_changes,
                    "max_swing": excitement.max_swing,
                    "image": image_name,
                }
            )

    print("Excitement summaries:")
    for line in summary_lines:
        print(" -", line)

    if not results_by_date:
        print("No results to summarize.")
        return

    for entries in results_by_date.values():
        entries.sort(key=lambda item: item["score"], reverse=True)

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results_by_date, indent=2), encoding="utf-8")

    build_dashboard(results_by_date, dashboard_path=dashboard_path, include_charts=include_charts)
    print(f"\nSaved summary JSON to {summary_path}")
    print(f"Saved dashboard to {dashboard_path}")
    if include_charts:
        print("PNG charts saved next to the dashboard; open them manually if you want spoilers.")


if __name__ == "__main__":
    main()

