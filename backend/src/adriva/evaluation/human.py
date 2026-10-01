"""Blind task construction and validated human submissions. No synthesized ratings."""

import random
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from adriva.domain.contracts import StrictModel

DIMENSIONS = (
    "MEANING",
    "NATURALNESS",
    "GRAMMAR",
    "FACTUALITY",
    "INSTRUCTION",
    "CULTURAL_FIT",
    "COMPLETENESS",
    "GROUNDEDNESS",
)
Choice = Literal["A", "B", "TIE", "CANNOT_JUDGE"]


class Rating(StrictModel):
    slot: Literal["A", "B"]
    dimension: Literal[
        "MEANING",
        "NATURALNESS",
        "GRAMMAR",
        "FACTUALITY",
        "INSTRUCTION",
        "CULTURAL_FIT",
        "COMPLETENESS",
        "GROUNDEDNESS",
    ]
    status: Literal["RATED", "NOT_APPLICABLE", "CANNOT_JUDGE"]
    value: int | None = Field(default=None, strict=True, ge=1, le=5)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def correct_status(self) -> "Rating":
        if (self.status == "RATED") != (self.value is not None):
            raise ValueError("Only RATED entries have ordinal values")
        return self


class HumanSubmission(StrictModel):
    assignment_id: str = Field(min_length=1)
    reviewer_ref: str = Field(min_length=1)
    rubric_digest: str = Field(min_length=1)
    preference: Choice
    rationale: str = Field(min_length=1)
    ratings: list[Rating]
    data_origin: Literal["ACTUAL_HUMAN", "TEST_FIXTURE"]

    @model_validator(mode="after")
    def complete_dimensions(self) -> "HumanSubmission":
        keys = [(r.slot, r.dimension) for r in self.ratings]
        expected = {(s, d) for s in ("A", "B") for d in DIMENSIONS}
        if len(keys) != len(set(keys)) or set(keys) != expected:
            raise ValueError("Explicit rating/NA/cannot-judge for each slot and dimension required")
        return self


@dataclass(frozen=True)
class BlindPair:
    pair_id: str
    stratum: str
    prompt: str
    context: str
    baseline_id: str
    baseline_text: str
    candidate_id: str
    candidate_text: str


def blind_assignments(
    pairs: list[BlindPair], *, seed: int
) -> tuple[list[dict], dict[str, dict[str, str]]]:
    """Call separately per reviewer; seed and returned mappings are server/auditor-only."""
    if len({p.pair_id for p in pairs}) != len(pairs) or any(
        p.baseline_id == p.candidate_id for p in pairs
    ):
        raise ValueError("Unique pairs with distinct response IDs required")
    grouped: dict[str, list[BlindPair]] = {}
    for pair in pairs:
        grouped.setdefault(pair.stratum, []).append(pair)
    rng = random.Random(seed)
    public, private = [], {}
    for stratum in sorted(grouped):
        group = sorted(grouped[stratum], key=lambda p: p.pair_id)
        rng.shuffle(group)
        offset = rng.randrange(2)
        for index, pair in enumerate(group):
            baseline_first = (index + offset) % 2 == 0
            assignment_id = str(uuid4())
            public.append(
                {
                    "assignment_id": assignment_id,
                    "prompt": pair.prompt,
                    "context": pair.context,
                    "A": pair.baseline_text if baseline_first else pair.candidate_text,
                    "B": pair.candidate_text if baseline_first else pair.baseline_text,
                }
            )
            private[assignment_id] = {
                "pair_id": pair.pair_id,
                "A": pair.baseline_id if baseline_first else pair.candidate_id,
                "B": pair.candidate_id if baseline_first else pair.baseline_id,
                "baseline_slot": "A" if baseline_first else "B",
            }
    rng.shuffle(public)
    return public, private


def canonical_choice(choice: Choice, baseline_slot: str) -> str:
    if choice not in {"A", "B", "TIE", "CANNOT_JUDGE"} or baseline_slot not in {"A", "B"}:
        raise ValueError("Invalid displayed preference or mapping")
    if choice in {"TIE", "CANNOT_JUDGE"}:
        return choice
    return "BASELINE" if choice == baseline_slot else "CANDIDATE"
