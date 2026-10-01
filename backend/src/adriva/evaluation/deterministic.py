import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from adriva.domain.contracts import ExpectedContract
from adriva.evaluation.schema import conforms


@dataclass(frozen=True)
class Metric:
    dimension: str
    status: Literal["VALUE", "NOT_APPLICABLE", "INSUFFICIENT_EVIDENCE", "SCORER_ERROR"]
    value: float | None
    evidence: dict[str, Any]


def normalize(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def strict_json(text: str) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(value: str) -> None:
        raise ValueError("Nonfinite JSON number")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError("Nonfinite JSON number")
        return parsed

    return json.loads(
        text,
        object_pairs_hook=no_duplicates,
        parse_constant=reject_constant,
        parse_float=finite_float,
    )


def typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(
            typed_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def evaluate(text: str, expected: ExpectedContract) -> list[Metric]:
    results: list[Metric] = []
    answers = expected.accepted_answers if expected.answerable else expected.abstention_answers
    if answers:
        match = normalize(text) in {normalize(a) for a in answers}
        results.append(
            Metric(
                "reference_exact_match",
                "VALUE",
                float(match),
                {
                    "normalizer": "NFC-strip-v1",
                    "scope": "reference overlap, not semantic correctness",
                },
            )
        )
    if expected.json_schema:
        try:
            parsed = strict_json(text)
            valid = conforms(parsed, expected.json_schema)
        except (ValueError, TypeError, RecursionError):
            parsed, valid = None, False
        results.append(
            Metric("schema_valid", "VALUE", float(valid), {"schema_subset": "adriva-json-v1"})
        )
        if expected.expected_fields is not None:
            values = {
                k: isinstance(parsed, dict) and k in parsed and typed_equal(parsed[k], v)
                for k, v in expected.expected_fields.items()
            }
            if values:
                results.append(
                    Metric(
                        "field_accuracy",
                        "VALUE",
                        sum(values.values()) / len(values),
                        {"field_pass": values, "n_fields": len(values)},
                    )
                )
            else:
                results.append(
                    Metric(
                        "field_accuracy", "NOT_APPLICABLE", None, {"reason": "No expected fields"}
                    )
                )
    if expected.required_literals:
        present = {s: s in text for s in expected.required_literals}
        results.append(
            Metric(
                "required_literals",
                "VALUE",
                float(all(present.values())),
                {"present": present, "scope": "literal presence only"},
            )
        )
    if expected.max_characters is not None:
        results.append(
            Metric(
                "character_limit",
                "VALUE",
                float(len(text) <= expected.max_characters),
                {"count": len(text), "unit": "Unicode code points"},
            )
        )
    if not results:
        results.append(
            Metric(
                "deterministic_coverage",
                "NOT_APPLICABLE",
                None,
                {"reason": "No deterministic constraint"},
            )
        )
    return results
