"""Paired, cluster-level inference. No model calls or inferred human labels."""

import math
import random
from collections import defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Literal


@dataclass(frozen=True)
class Pair:
    case: str
    repetition: int
    family: str
    cluster: str
    baseline: float | None
    candidate: float | None


@dataclass(frozen=True)
class AnalysisPlan:
    benchmark_digest: str
    scorer_digest: str
    generation_protocol_digest: str
    expected_keys: frozenset[tuple[str, int]]
    margin: float
    max_interval_width: float
    primary_gates: int = 1
    alpha: float = 0.05
    draws: int = 5000
    seed: int = 1729
    min_clusters: int = 30
    higher_is_better: bool = True
    evidence: Literal["REVIEWED_EVALUATION", "PILOT", "FIXTURE"] = "PILOT"

    def __post_init__(self) -> None:
        if not all((self.benchmark_digest, self.scorer_digest, self.generation_protocol_digest)):
            raise ValueError("Frozen comparison fingerprints are required")
        if not self.expected_keys or any(
            not k or type(r) is not int or r < 0 for k, r in self.expected_keys
        ):
            raise ValueError("Nonempty planned case/repetition grid required")
        if not 0 <= self.margin < 1 or not 0 < self.max_interval_width <= 2:
            raise ValueError("Invalid practical margin or precision target")
        if not 0 < self.alpha < 1 or self.primary_gates < 1 or self.min_clusters < 2:
            raise ValueError("Invalid inference settings")
        if self.draws * self.alpha / (2 * self.primary_gates) < 20:
            raise ValueError("Too few bootstrap tail draws for planned multiplicity")
        if self.evidence not in {"REVIEWED_EVALUATION", "PILOT", "FIXTURE"}:
            raise ValueError("Invalid evidence class")


@dataclass(frozen=True)
class Comparison:
    status: str
    effect: float | None
    interval: tuple[float, float] | None
    decision: str
    noninferior: bool | None
    planned_pairs: int
    observed_pairs: int
    clusters: int
    reasons: tuple[str, ...]
    evidence: str


def quantile(ordered: list[float], probability: float) -> float:
    if not ordered or not 0 <= probability <= 1:
        raise ValueError("Invalid quantile")
    index = (len(ordered) - 1) * probability
    lower = int(index)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (
        index - lower
    )


def compare(
    pairs: list[Pair], plan: AnalysisPlan, *, candidate_fingerprints: tuple[str, str, str]
) -> Comparison:
    if candidate_fingerprints != (
        plan.benchmark_digest,
        plan.scorer_digest,
        plan.generation_protocol_digest,
    ):
        raise ValueError("Unfair comparison: benchmark/scorer/generation protocol differs")
    seen: set[tuple[str, int]] = set()
    case_identity: dict[str, tuple[str, str]] = {}
    family_cluster: dict[str, str] = {}
    values: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for p in pairs:
        key = (p.case, p.repetition)
        if key in seen or key not in plan.expected_keys or not p.family or not p.cluster:
            raise ValueError("Duplicate, unplanned or unidentified observation")
        seen.add(key)
        if case_identity.setdefault(p.case, (p.family, p.cluster)) != (p.family, p.cluster):
            raise ValueError("Case changes family/cluster")
        if family_cluster.setdefault(p.family, p.cluster) != p.cluster:
            raise ValueError("Family crosses dependency clusters")
        for value in (p.baseline, p.candidate):
            if value is not None and (
                isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1
            ):
                raise ValueError("Scores must be finite [0,1] values or missing")
        if p.baseline is not None and p.candidate is not None:
            effect = (p.candidate - p.baseline) * (1 if plan.higher_is_better else -1)
            values[p.cluster][p.family][p.case].append(effect)
    observed = sum(
        len(reps)
        for families in values.values()
        for cases in families.values()
        for reps in cases.values()
    )
    clusters = [
        mean(mean(mean(reps) for reps in cases.values()) for cases in families.values())
        for families in values.values()
    ]
    reasons: list[str] = []
    if observed != len(plan.expected_keys):
        reasons.append("INCOMPLETE_PLANNED_PAIRS")
    if plan.evidence != "REVIEWED_EVALUATION":
        reasons.append("NOT_REVIEWED_EVALUATION")
    if len(clusters) < plan.min_clusters:
        reasons.append("INSUFFICIENT_INDEPENDENT_CLUSTERS")
    interval = None
    if len(clusters) >= 2 and max(clusters) != min(clusters):
        rng = random.Random(plan.seed)
        draws = sorted(mean(rng.choices(clusters, k=len(clusters))) for _ in range(plan.draws))
        tail = plan.alpha / (2 * plan.primary_gates)
        interval = (quantile(draws, tail), quantile(draws, 1 - tail))
        if interval[1] - interval[0] > plan.max_interval_width:
            reasons.append("INSUFFICIENT_PRECISION")
    elif clusters:
        reasons.append("DEGENERATE_BOOTSTRAP")
    effect = mean(clusters) if clusters else None
    decision, noninferior = "HOLD", None
    if not reasons and interval:
        low, high = interval
        noninferior = low > -plan.margin
        decision = (
            "IMPROVED"
            if low > plan.margin
            else "REGRESSED"
            if high < -plan.margin
            else "PRACTICALLY_EQUIVALENT"
            if low > -plan.margin and high < plan.margin
            else "INCONCLUSIVE"
        )
    return Comparison(
        "HOLD" if reasons else "ESTIMATED",
        effect,
        interval,
        decision,
        noninferior,
        len(plan.expected_keys),
        observed,
        len(clusters),
        tuple(reasons),
        plan.evidence,
    )


def adjust_pvalues(values: list[float], method: Literal["holm", "by"] = "holm") -> list[float]:
    if method not in {"holm", "by"} or any(not math.isfinite(p) or not 0 <= p <= 1 for p in values):
        raise ValueError("Valid p-values and Holm/BY method required")
    n = len(values)
    order = sorted(range(n), key=values.__getitem__)
    result = [0.0] * n
    if method == "holm":
        running = 0.0
        for rank, index in enumerate(order):
            running = max(running, (n - rank) * values[index])
            result[index] = min(1.0, running)
    else:
        harmonic = sum(1 / k for k in range(1, n + 1))
        running = 1.0
        for rank in range(n - 1, -1, -1):
            index = order[rank]
            running = min(running, values[index] * n * harmonic / (rank + 1))
            result[index] = min(1.0, running)
    return result


def exact_mcnemar(baseline_only: int, candidate_only: int, *, independent_units: bool) -> float:
    """Two-sided exact binomial conditional on discordance, independent binary pairs only."""
    if not independent_units or any(
        type(x) is not int or x < 0 for x in (baseline_only, candidate_only)
    ):
        raise ValueError("Nonnegative discordance counts and independent units required")
    n = baseline_only + candidate_only
    if not n:
        return 1.0
    # Log probabilities avoid converting enormous binomial coefficients to floats.
    k = min(baseline_only, candidate_only)
    tail = sum(
        math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) - n * math.log(2))
        for i in range(k + 1)
    )
    return min(1.0, 2 * tail)
