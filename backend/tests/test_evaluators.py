import pytest
from adriva.domain.contracts import ExpectedContract
from adriva.evaluation.deterministic import evaluate, normalize, strict_json


def test_unicode_reference_and_negation() -> None:
    expected = ExpectedContract(accepted_answers=["café"])
    assert evaluate(" cafe\u0301 ", expected)[0].value == 1
    assert evaluate("not café", expected)[0].value == 0
    assert normalize("ൻ") == "ൻ"


@pytest.mark.parametrize(
    "text", ['{"n":true}', '{"n":"250"}', '{"n":251}', '{"n":250,"n":250}', '{"n":NaN}', "{}"]
)
def test_extraction_number_type_and_format(text: str) -> None:
    expected = ExpectedContract(
        json_schema={
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
            "additionalProperties": False,
        },
        expected_fields={"n": 250},
    )
    metrics = {m.dimension: m for m in evaluate(text, expected)}
    assert metrics["field_accuracy"].value == 0


def test_good_extraction_and_unknown_semantics() -> None:
    expected = ExpectedContract(
        json_schema={"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]},
        expected_fields={"n": 250},
    )
    assert all(m.value == 1 for m in evaluate('{"n":250}', expected))
    assert (
        evaluate("A fluent translation", ExpectedContract(semantic_units=["meaning"]))[0].status
        == "NOT_APPLICABLE"
    )


def test_empty_answer_does_not_pass_qa() -> None:
    assert evaluate("", ExpectedContract(accepted_answers=["250"]))[0].value == 0


def test_abstention_is_distinct() -> None:
    expected = ExpectedContract(answerable=False, abstention_answers=["unknown"])
    assert evaluate("unknown", expected)[0].value == 1
    assert evaluate("250", expected)[0].value == 0


def test_duplicate_and_nonfinite_json() -> None:
    with pytest.raises(ValueError):
        strict_json('{"a":1,"a":2}')
    with pytest.raises(ValueError):
        strict_json('{"a":Infinity}')
    with pytest.raises(ValueError):
        strict_json('{"a":1e10000}')
