#!/usr/bin/env python3
"""
Analyze win probability data to decide if a game was exciting.

Usage:
    python exciting_game.py box.json
"""

from __future__ import annotations

import argparse
import json

from excitement import (
    ExcitementAnalysis,
    calculate_excitement,
    load_home_win_probabilities,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rate how exciting a game was using win probability data."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="box.json",
        help="Path to JSON file with a top-level 'winprobability' list (default: box.json)",
    )
    args = parser.parse_args()

    with open(args.input_file, encoding="utf-8") as fp:
        payload = json.load(fp)

    if "winprobability" not in payload:
        raise KeyError("JSON is missing the top-level 'winprobability' field")

    probabilities = load_home_win_probabilities(payload["winprobability"])
    analysis = calculate_excitement(probabilities)

    print(f"Verdict: {analysis.verdict} ({analysis.score:.2f}/10)")
    print(f"Lead changes: {analysis.lead_changes}")
    print(f"Average swing: {analysis.avg_swing:.3f}")
    print(f"Largest swing: {analysis.max_swing:.3f}")
    print(f"Time in toss-up range (45%%-55%%): {analysis.close_ratio:.2%}")


if __name__ == "__main__":
    main()
