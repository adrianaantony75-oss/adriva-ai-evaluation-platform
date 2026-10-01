"""Aggregate attributed judgments; do not manufacture semantic truth from surface text."""

from typing import Literal

from pydantic import Field, model_validator

from adriva.domain.contracts import StrictModel
from adriva.evaluation.deterministic import Metric


class Span(StrictModel):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    def validate_against(self, text: str) -> None:
        if (
            self.end <= self.start
            or text[self.start : self.end] != self.quote
            or self.end > len(text)
        ):
            raise ValueError("Evidence span does not match its immutable text")


class EvidenceJudgment(StrictModel):
    unit_id: str = Field(min_length=1)
    kind: Literal["SEMANTIC_UNIT", "CLAIM"]
    verdict: Literal[
        "PRESERVED",
        "OMITTED",
        "ALTERED",
        "SUPPORTED",
        "CONTRADICTED",
        "UNSUPPORTED",
        "UNVERIFIABLE",
        "CANNOT_JUDGE",
    ]
    origin: Literal["HUMAN", "JUDGE", "FIXTURE"]
    assessor_ref: str = Field(min_length=1)
    rubric_digest: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    response_spans: list[Span] = Field(default_factory=list)
    source_spans: list[Span] = Field(default_factory=list)

    @model_validator(mode="after")
    def appropriate_verdict(self) -> "EvidenceJudgment":
        valid = (
            {"PRESERVED", "OMITTED", "ALTERED", "CANNOT_JUDGE"}
            if self.kind == "SEMANTIC_UNIT"
            else {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "UNVERIFIABLE", "CANNOT_JUDGE"}
        )
        if self.verdict not in valid:
            raise ValueError("Verdict is incompatible with evidence kind")
        if self.verdict not in {"OMITTED", "CANNOT_JUDGE"} and not self.response_spans:
            raise ValueError("Response evidence required")
        if self.verdict in {"SUPPORTED", "CONTRADICTED"} and not self.source_spans:
            raise ValueError("Source evidence required")
        return self


def aggregate_evidence(
    judgments: list[EvidenceJudgment],
    *,
    expected_unit_ids: set[str],
    source: str,
    response: str,
    inventory_complete: bool,
) -> list[Metric]:
    ids = [j.unit_id for j in judgments]
    if len(ids) != len(set(ids)) or not set(ids).issubset(expected_unit_ids):
        raise ValueError("Duplicate or unregistered evidence units")
    if len({(j.kind, j.origin, j.assessor_ref, j.rubric_digest) for j in judgments}) > 1:
        raise ValueError("Aggregate one assessor, origin, rubric and kind at a time")
    for j in judgments:
        for span in j.response_spans:
            span.validate_against(response)
        for span in j.source_spans:
            span.validate_against(source)
    metadata = {
        "origin": judgments[0].origin if judgments else None,
        "assessor": judgments[0].assessor_ref if judgments else None,
        "observed": len(ids),
        "expected": len(expected_unit_ids),
        "inventory_complete": inventory_complete,
        "scope": "attributed judgments, not automatic ground truth",
    }
    if (
        not judgments
        or not inventory_complete
        or set(ids) != expected_unit_ids
        or any(j.verdict == "CANNOT_JUDGE" for j in judgments)
    ):
        return [Metric("semantic_evidence", "INSUFFICIENT_EVIDENCE", None, metadata)]
    n = len(judgments)
    if judgments[0].kind == "SEMANTIC_UNIT":
        return [
            Metric(
                "semantic_unit_preservation",
                "VALUE",
                sum(j.verdict == "PRESERVED" for j in judgments) / n,
                metadata,
            )
        ]
    # UNVERIFIABLE remains in denominator; it is not unsupported and not a true claim.
    return [
        Metric(name, "VALUE", sum(j.verdict == verdict for j in judgments) / n, metadata)
        for name, verdict in [
            ("supported_claim_fraction", "SUPPORTED"),
            ("contradicted_claim_fraction", "CONTRADICTED"),
            ("unsupported_claim_fraction", "UNSUPPORTED"),
            ("unverifiable_claim_fraction", "UNVERIFIABLE"),
        ]
    ]


def proposed_failures(judgment: EvidenceJudgment) -> tuple[str, ...]:
    """Taxonomy proposals; never promote a judge verdict to human confirmation."""
    return {
        "OMITTED": ("OMISSION",),
        "ALTERED": ("MEANING_DRIFT",),
        "CONTRADICTED": ("CONTRADICTION",),
        "UNSUPPORTED": ("UNSUPPORTED_ADDITION",),
    }.get(judgment.verdict, ())
