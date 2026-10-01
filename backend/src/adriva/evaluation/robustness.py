"""Task-valid semantic behavior, not string equality, defines robustness."""

from collections import defaultdict
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class RobustnessPair:
    family: str
    variant_id: str
    operator: str
    baseline_pass: bool | None
    variant_pass: bool | None
    invariant_verified: bool


def robustness_report(pairs: list[RobustnessPair]) -> dict:
    seen = set()
    families: dict[str, list[float]] = defaultdict(list)
    losses = gains = stable_pass = stable_fail = excluded = 0
    for p in pairs:
        if p.variant_id in seen or not p.family or not p.operator:
            raise ValueError("Distinct variants, family and operator required")
        seen.add(p.variant_id)
        if any(v is not None and type(v) is not bool for v in (p.baseline_pass, p.variant_pass)):
            raise ValueError("Reviewed task-valid pass/fail or missing required")
        if not p.invariant_verified or p.baseline_pass is None or p.variant_pass is None:
            excluded += 1
            continue
        families[p.family].append(float(p.variant_pass) - float(p.baseline_pass))
        losses += p.baseline_pass and not p.variant_pass
        gains += not p.baseline_pass and p.variant_pass
        stable_pass += p.baseline_pass and p.variant_pass
        stable_fail += not p.baseline_pass and not p.variant_pass
    return {
        "planned_variants": len(pairs),
        "eligible_variants": len(pairs) - excluded,
        "excluded_unverified_or_missing": excluded,
        "families": len(families),
        "family_macro_change": mean(mean(v) for v in families.values()) if families else None,
        "pass_to_fail": losses,
        "fail_to_pass": gains,
        "stable_pass": stable_pass,
        "stable_fail": stable_fail,
        "conditional_pass_loss": losses / (losses + stable_pass) if losses + stable_pass else None,
        "scope": "descriptive; inspect by operator; shared baselines are dependent; use cluster inference for claims",
    }


def transform_prompt(prompt: str, operator: str) -> str:
    """Mechanical candidate transformations; even these require semantic review."""
    if not prompt.strip():
        raise ValueError("Empty prompt")
    if operator == "outer-whitespace-v1":
        return "  " + prompt + "\n"
    if operator == "terminal-punctuation-v1":
        if not prompt.endswith("?"):
            raise ValueError("Punctuation operator requires terminal question mark")
        return prompt[:-1] + "??"
    raise ValueError("Unreviewed transformation operator")
