"""Regression gates and overlapping failure-label prevalence use the same pairing kernel."""

from dataclasses import replace

from adriva.evaluation.statistics import AnalysisPlan, Comparison, Pair, compare


def release_decision(results: dict[str, Comparison], *, required_gates: set[str]) -> str:
    if set(results) != required_gates or not results:
        return "HOLD"
    if any(r.status == "HOLD" for r in results.values()):
        return "HOLD"
    if any(r.decision == "REGRESSED" for r in results.values()):
        return "REGRESSION_DETECTED"
    if all(r.noninferior is True for r in results.values()):
        return "PASSES_PREDECLARED_NONINFERIORITY_GATES"
    return "INCONCLUSIVE"


def failure_distribution(
    observations: dict[str, list[Pair]],
    plan: AnalysisPlan,
    *,
    candidate_fingerprints: tuple[str, str, str],
) -> dict[str, Comparison]:
    """Each label has one binary incidence per planned response, including explicit zeros.

    Inputs must contain confirmed labels or a single clearly disclosed judge label source;
    absence of annotation must be None, never silently coded as absence of failure.
    """
    if not observations or len(observations) > plan.primary_gates:
        raise ValueError("Declare failure-label comparison family before inspecting outcomes")
    for rows in observations.values():
        if any(
            v is not None and v not in (0.0, 1.0) for r in rows for v in (r.baseline, r.candidate)
        ):
            raise ValueError("Failure incidence must be binary")
    return {
        label: compare(
            rows,
            replace(plan, higher_is_better=False),
            candidate_fingerprints=candidate_fingerprints,
        )
        for label, rows in observations.items()
    }


def case_transitions(
    pairs: list[Pair], *, pass_threshold: float
) -> dict[str, list[tuple[str, int]]]:
    if not 0 <= pass_threshold <= 1:
        raise ValueError("Freeze a threshold in [0,1]")
    result: dict[str, list[tuple[str, int]]] = {
        "regressed": [],
        "improved": [],
        "stable_pass": [],
        "stable_fail": [],
        "missing": [],
    }
    seen = set()
    for p in pairs:
        key = (p.case, p.repetition)
        if key in seen:
            raise ValueError("Duplicate paired case")
        seen.add(key)
        if p.baseline is None or p.candidate is None:
            result["missing"].append(key)
            continue
        if not 0 <= p.baseline <= 1 or not 0 <= p.candidate <= 1:
            raise ValueError("Finite [0,1] scores required")
        before, after = p.baseline >= pass_threshold, p.candidate >= pass_threshold
        label = (
            "stable_pass"
            if before and after
            else "regressed"
            if before
            else "improved"
            if after
            else "stable_fail"
        )
        result[label].append(key)
    return result
