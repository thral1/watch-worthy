"""Reusable excitement scoring utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass
class ExcitementAnalysis:
    score: float
    verdict: str
    lead_changes: int
    avg_swing: float
    max_swing: float
    close_ratio: float


def load_home_win_probabilities(source: Sequence[dict]) -> List[float]:
    """Extract and validate home win probability values."""
    probabilities: List[float] = []
    for index, play in enumerate(source):
        if "homeWinPercentage" not in play:
            raise KeyError(f"winprobability[{index}] missing 'homeWinPercentage'")
        value = float(play["homeWinPercentage"])
        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"winprobability[{index}].homeWinPercentage must be between 0 and 1"
            )
        probabilities.append(value)
    if not probabilities:
        raise ValueError("No win probability data available")
    return probabilities


def calculate_excitement(probabilities: Sequence[float]) -> ExcitementAnalysis:
    """Create an excitement score using win probability swings and lead changes."""
    if len(probabilities) < 2:
        raise ValueError("Need at least two win probability points to analyze the game")

    swings = [
        abs(curr - prev) for prev, curr in zip(probabilities, probabilities[1:])
    ]
    total_swing = sum(swings)
    avg_swing = total_swing / len(swings)
    max_swing = max(swings)
    lead_changes = sum(
        1
        for prev, curr in zip(probabilities, probabilities[1:])
        if (prev >= 0.5) != (curr >= 0.5)
    )
    close_ratio = sum(1 for p in probabilities if 0.45 <= p <= 0.55) / len(
        probabilities
    )

    score = (
        min(avg_swing / 0.04, 1.0) * 2.5
        + min(max_swing / 0.18, 1.0) * 2.5
        + min(lead_changes / 3, 1.0) * 3.0
        + min(close_ratio / 0.45, 1.0) * 2.0
    )
    score = min(score, 10.0)

    if score >= 6.5:
        verdict = "Exciting"
    elif score >= 4.0:
        verdict = "Worth a look"
    else:
        verdict = "Skip it"

    return ExcitementAnalysis(
        score=score,
        verdict=verdict,
        lead_changes=lead_changes,
        avg_swing=avg_swing,
        max_swing=max_swing,
        close_ratio=close_ratio,
    )

