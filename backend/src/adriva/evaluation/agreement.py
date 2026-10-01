"""Agreement on independent, original ratings; missingness is not disagreement."""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Agreement:
    alpha: float | None
    raw_agreement: float | None
    pairable_units: int
    excluded_units: int
    pairable_ratings: int
    reason: str | None


def krippendorff_alpha(
    units: dict[str, dict[str, str | None]],
    *,
    level: Literal["nominal", "ordinal"],
    categories: tuple[str, ...],
) -> Agreement:
    if (
        level not in {"nominal", "ordinal"}
        or len(categories) < 2
        or len(set(categories)) != len(categories)
    ):
        raise ValueError("Distinct, ordered category domain and valid level required")
    counts: list[Counter[str]] = []
    for ratings in units.values():
        observed = [v for v in ratings.values() if v is not None]
        if not set(observed).issubset(categories):
            raise ValueError("Undeclared rating category")
        if len(observed) >= 2:
            counts.append(Counter(observed))
    margins: Counter[str] = Counter()
    coincidences: Counter[tuple[str, str]] = Counter()
    pair_matches = pair_total = 0
    for counter in counts:
        size = sum(counter.values())
        margins.update(counter)
        pair_total += size * (size - 1)
        pair_matches += sum(n * (n - 1) for n in counter.values())
        for a, na in counter.items():
            for b, nb in counter.items():
                coincidences[a, b] += na * (nb - (a == b)) / (size - 1)
    n = sum(margins.values())
    raw = pair_matches / pair_total if pair_total else None
    if not n:
        return Agreement(None, raw, 0, len(units), 0, "NO_PAIRABLE_RATINGS")

    def distance(a: str, b: str) -> float:
        if a == b:
            return 0.0
        if level == "nominal":
            return 1.0
        left, right = sorted((categories.index(a), categories.index(b)))
        return (
            sum(margins[c] for c in categories[left : right + 1]) - (margins[a] + margins[b]) / 2
        ) ** 2

    observed_disagreement = (
        sum(value * distance(a, b) for (a, b), value in coincidences.items()) / n
    )
    expected_disagreement = sum(
        na * nb * distance(a, b) for a, na in margins.items() for b, nb in margins.items()
    ) / (n * (n - 1))
    alpha = 1 - observed_disagreement / expected_disagreement if expected_disagreement else None
    return Agreement(
        alpha,
        raw,
        len(counts),
        len(units) - len(counts),
        n,
        None if expected_disagreement else "NO_CATEGORY_VARIATION",
    )


def evaluator_comparison(
    pairs: list[tuple[str | None, str | None]],
    *,
    categories: tuple[str, ...],
    positive: str | None = None,
) -> dict:
    """(human reference, automatic) pairs; reference must be independently obtained."""
    if (
        len(categories) < 2
        or len(set(categories)) != len(categories)
        or (positive is not None and positive not in categories)
    ):
        raise ValueError("Invalid comparison domain")
    if any(v is not None and v not in categories for pair in pairs for v in pair):
        raise ValueError("Unknown evaluator label")
    paired = [(h, a) for h, a in pairs if h is not None and a is not None]
    matrix = {h: {a: 0 for a in categories} for h in categories}
    for human, automatic in paired:
        matrix[human][automatic] += 1
    agreement = sum(h == a for h, a in paired) / len(paired) if paired else None
    precision = recall = None
    if positive is not None:
        tp = matrix[positive][positive]
        predicted = sum(matrix[h][positive] for h in categories)
        actual = sum(matrix[positive].values())
        precision = tp / predicted if predicted else None
        recall = tp / actual if actual else None
    return {
        "n_planned": len(pairs),
        "n_paired": len(paired),
        "coverage": len(paired) / len(pairs) if pairs else None,
        "confusion": matrix,
        "agreement": agreement,
        "precision": precision,
        "recall": recall,
        "scope": "descriptive; independent held-out human reference required; no causal or validity claim",
    }


def ordinal_error(pairs: list[tuple[int, int]]) -> float | None:
    """Secondary distance diagnostic, not interval-scale quality or IAA."""
    if any(type(v) is not int or not 1 <= v <= 5 for p in pairs for v in p):
        raise ValueError("Expected rubric levels 1..5")
    result = sum(abs(a - b) for a, b in pairs) / len(pairs) if pairs else None
    assert result is None or math.isfinite(result)
    return result
