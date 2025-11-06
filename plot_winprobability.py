#!/usr/bin/env python3
"""
Create a win probability chart for a completed game.

Example:
    python plot_winprobability.py box.json --output kings-bucks.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # ensure we can render without a display
import matplotlib.pyplot as plt

from excitement import calculate_excitement, load_home_win_probabilities


def derive_x_axis_labels(play_ids: Sequence[str]) -> list[str]:
    """Produce simplified labels for the x-axis based on play identifiers."""
    labels: list[str] = []
    for play_id in play_ids:
        labels.append(play_id[-3:] if len(play_id) > 3 else play_id)
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot win probability over the course of a game."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default="box.json",
        help="Path to JSON file with a top-level 'winprobability' list (default: box.json).",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="winprobability.png",
        help="Output image file (PNG, SVG, etc.). Default: winprobability.png",
    )
    args = parser.parse_args()

    payload = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    winprob_entries = payload.get("winprobability")
    if not isinstance(winprob_entries, list):
        raise KeyError("JSON is missing the top-level 'winprobability' list")

    probabilities = load_home_win_probabilities(winprob_entries)
    play_ids = [entry.get("playId", str(index)) for index, entry in enumerate(winprob_entries)]
    labels = derive_x_axis_labels(play_ids)

    excitement = calculate_excitement(probabilities)
    percent_values = [p * 100 for p in probabilities]
    indices = list(range(len(percent_values)))

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
        f"Win Probability Trend\nVerdict: {excitement.verdict} — {excitement.score:.2f}/10"
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
    output_path = Path(args.output)
    fig.savefig(output_path, dpi=150)
    print(f"Saved win probability chart to {output_path}")


if __name__ == "__main__":
    main()

