"""All numeric observations below are synthetic mathematical TEST FIXTURES."""

from dataclasses import replace

import pytest
from adriva.evaluation.agreement import evaluator_comparison, krippendorff_alpha
from adriva.evaluation.evidence import EvidenceJudgment, Span, aggregate_evidence
from adriva.evaluation.human import BlindPair, blind_assignments, canonical_choice
from adriva.evaluation.judge import JudgeObservation, audit_judge
from adriva.evaluation.preservation import (
    bound_entities,
    bound_quantities,
    entity_mentions,
    quantity_equal,
)
from adriva.evaluation.regression import case_transitions, release_decision
from adriva.evaluation.robustness import RobustnessPair, robustness_report
from adriva.evaluation.statistics import AnalysisPlan, Pair, adjust_pvalues, compare, exact_mcnemar


def plan_for(pairs, **kwargs):
    return AnalysisPlan(
        "bench",
        "scorer",
        "generation",
        frozenset((p.case, p.repetition) for p in pairs),
        0.05,
        0.3,
        **kwargs,
    )


def test_pairing_guards_and_missing_data():
    pairs = [Pair("a", 0, "f", "cluster", 0.3, 0.7)]
    plan = plan_for(pairs)
    with pytest.raises(ValueError, match="Unfair"):
        compare(pairs, plan, candidate_fingerprints=("other", "scorer", "generation"))
    with pytest.raises(ValueError, match="Duplicate"):
        compare(pairs * 2, plan, candidate_fingerprints=("bench", "scorer", "generation"))
    result = compare([], plan, candidate_fingerprints=("bench", "scorer", "generation"))
    assert result.decision == "HOLD" and result.observed_pairs == 0
    assert "INCOMPLETE_PLANNED_PAIRS" in result.reasons


def test_cluster_weighting_and_reproducible_bootstrap():
    # 100 correlated variants do not outweigh one independent cluster.
    pairs = [Pair(str(i), 0, "family-a", "source-a", 0, 1) for i in range(100)]
    pairs += [Pair("b", 0, "family-b", "source-b", 1, 0)]
    plan = plan_for(pairs)
    result = compare(pairs, plan, candidate_fingerprints=("bench", "scorer", "generation"))
    assert result.effect == 0 and result.clusters == 2 and result.status == "HOLD"
    assert result == compare(pairs, plan, candidate_fingerprints=("bench", "scorer", "generation"))


def test_decision_rules_and_degenerate_intervals():
    pairs = [Pair(str(i), 0, str(i), str(i), 0.1, 0.6 + (i % 2) * 0.1) for i in range(40)]
    plan = plan_for(pairs, evidence="REVIEWED_EVALUATION")
    result = compare(pairs, plan, candidate_fingerprints=("bench", "scorer", "generation"))
    assert result.decision == "IMPROVED"
    assert (
        release_decision({"primary": result}, required_gates={"primary"})
        == "PASSES_PREDECLARED_NONINFERIORITY_GATES"
    )
    reverse = [replace(p, baseline=p.candidate, candidate=p.baseline) for p in pairs]
    assert (
        compare(reverse, plan, candidate_fingerprints=("bench", "scorer", "generation")).decision
        == "REGRESSED"
    )
    equal = [replace(p, baseline=0.5, candidate=0.5) for p in pairs]
    degenerate = compare(equal, plan, candidate_fingerprints=("bench", "scorer", "generation"))
    assert degenerate.interval is None and degenerate.decision == "HOLD"
    assert case_transitions([Pair("x", 0, "f", "s", 1, 0)], pass_threshold=1)["regressed"] == [
        ("x", 0)
    ]


def test_multiplicity_and_exact_discordance():
    assert adjust_pvalues([0.01, 0.04, 0.03], "holm") == pytest.approx([0.03, 0.06, 0.06])
    assert adjust_pvalues([0.01, 0.04, 0.03], "by") == pytest.approx(
        [0.055, 0.073333333, 0.073333333]
    )
    assert exact_mcnemar(0, 5, independent_units=True) == pytest.approx(0.0625)
    assert exact_mcnemar(0, 0, independent_units=True) == 1
    with pytest.raises(ValueError):
        exact_mcnemar(2, 3, independent_units=False)


def test_alpha_reference_examples_missingness_and_negative():
    units = {
        "1": {"a": "x", "b": "x"},
        "2": {"a": "x", "b": "y"},
        "3": {"a": "y", "b": "y"},
        "4": {"a": "x", "b": None},
    }
    result = krippendorff_alpha(units, level="nominal", categories=("x", "y"))
    # Six pairable values: Do=1/3, De=3/5, alpha=4/9.
    assert result.alpha == pytest.approx(4 / 9) and result.excluded_units == 1
    assert result.raw_agreement == pytest.approx(2 / 3)
    constant = krippendorff_alpha(
        {"1": {"a": "x", "b": "x"}}, level="nominal", categories=("x", "y")
    )
    assert constant.alpha is None and constant.raw_agreement == 1
    disagree = krippendorff_alpha(
        {"1": {"a": "x", "b": "y"}, "2": {"a": "x", "b": "y"}},
        level="ordinal",
        categories=("x", "y"),
    )
    assert disagree.alpha == pytest.approx(-0.5)


def test_preservation_role_binding_and_unicode():
    assert entity_mentions("Anna met Ravi", {"Ann": ["Ann"], "ravi": ["Ravi"]}).value == 0.5
    assert (
        bound_entities(
            {"sender": "B", "recipient": "A"}, {"sender": ["A"], "recipient": ["B"]}
        ).value
        == 0
    )
    assert quantity_equal("1000", "g", "1", "kg")
    assert quantity_equal("൨൫൦", "INR", "250", "INR")
    assert not quantity_equal("10", "percent", "10", "count")
    assert (
        bound_quantities(
            {"price": ("5", "INR"), "count": ("250", "count")},
            {"price": ("250", "INR"), "count": ("5", "count")},
        ).value
        == 0
    )
    with pytest.raises(ValueError):
        quantity_equal("NaN", "kg", "1", "kg")


def test_evidence_never_infers_semantics_or_fabricates_humans():
    assert (
        aggregate_evidence(
            [], expected_unit_ids={"u"}, source="", response="fluent", inventory_complete=True
        )[0].value
        is None
    )
    judgment = EvidenceJudgment(
        unit_id="u",
        kind="SEMANTIC_UNIT",
        verdict="PRESERVED",
        origin="FIXTURE",
        assessor_ref="test-only",
        rubric_digest="fixture",
        rationale="Mathematical test",
        response_spans=[Span(start=0, end=3, quote="yes")],
    )
    metric = aggregate_evidence(
        [judgment], expected_unit_ids={"u"}, source="", response="yes", inventory_complete=True
    )[0]
    assert metric.value == 1 and metric.evidence["origin"] == "FIXTURE"
    with pytest.raises(ValueError, match="span"):
        aggregate_evidence(
            [judgment], expected_unit_ids={"u"}, source="", response="no", inventory_complete=True
        )


def test_blinding_and_judge_order_bias():
    pairs = [
        BlindPair(
            str(i), "ml", "prompt", "source", f"baseline-{i}", "text a", f"candidate-{i}", "text b"
        )
        for i in range(10)
    ]
    public, private = blind_assignments(pairs, seed=7)
    assert sum(m["baseline_slot"] == "A" for m in private.values()) == 5
    assert all(set(p) == {"assignment_id", "prompt", "context", "A", "B"} for p in public)
    assert canonical_choice("A", "B") == "CANDIDATE"
    observations = [
        JudgeObservation("pair", slot, repeat, "A", "fixture")
        for slot in ("A", "B")
        for repeat in range(2)
    ]
    audit = audit_judge(observations)
    assert audit["canonical_swap_agreement"] == 0 and audit["repeat_agreement"] == 1
    assert audit["first_position_choice_rate"] == 1


def test_robustness_and_evaluator_coverage():
    result = robustness_report(
        [
            RobustnessPair("f", "v1", "noise", True, False, True),
            RobustnessPair("f", "v2", "translation", True, True, False),
        ]
    )
    assert result["pass_to_fail"] == 1 and result["excluded_unverified_or_missing"] == 1
    comparison = evaluator_comparison(
        [("FAIL", "FAIL"), ("PASS", "FAIL"), ("PASS", None)],
        categories=("PASS", "FAIL"),
        positive="FAIL",
    )
    assert (
        comparison["precision"] == 0.5
        and comparison["recall"] == 1
        and comparison["coverage"] == pytest.approx(2 / 3)
    )
