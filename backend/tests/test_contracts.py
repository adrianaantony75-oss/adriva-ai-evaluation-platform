import pytest
from adriva.domain.contracts import BenchmarkImport, ExpectedContract, LanguageProfile
from adriva.domain.hashing import digest
from adriva.domain.validation import validate_import
from pydantic import ValidationError


def test_fixture_profiles_and_origin(batch: BenchmarkImport) -> None:
    assert validate_import(batch) == []
    assert all(c.usage == "FIXTURE" and c.origin == "SYNTHETIC" for c in batch.cases)
    assert batch.cases[2].input_profile.languages == ["ml"]
    assert batch.cases[3].input_profile.languages == ["ml", "en"]
    assert "register" in batch.cases[0].input_profile.model_dump()


def test_split_leakage(batch: BenchmarkImport) -> None:
    modified = batch.model_copy(deep=True)
    modified.cases[1].split = "evaluation"
    assert "CLUSTER_SPLIT_LEAKAGE" in {i.rule for i in validate_import(modified)}


def test_cycle(batch: BenchmarkImport) -> None:
    modified = batch.model_copy(deep=True)
    modified.cases[1].derivation.parent_key = "qa-manglish"
    assert "LINEAGE_CYCLE" in {i.rule for i in validate_import(modified)}


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "object", "$ref": "http://example.org"},
        {"type": "array"},
        {"type": "object", "required": ["missing"]},
    ],
)
def test_unsupported_schema_is_rejected(schema: dict) -> None:
    with pytest.raises(ValidationError):
        ExpectedContract(json_schema=schema)


def test_profiles_reject_false_romanization() -> None:
    with pytest.raises(ValidationError):
        LanguageProfile(languages=["en"], script="Latin", romanization="Manglish")


def test_canonical_hash() -> None:
    assert digest({"b": "മ", "a": 1}) == digest({"a": 1, "b": "മ"})
    with pytest.raises(ValueError):
        digest(float("nan"))


def test_gold_fields_must_conform() -> None:
    with pytest.raises(ValidationError):
        ExpectedContract(
            json_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            expected_fields={"n": True},
        )
