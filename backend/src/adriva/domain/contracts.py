from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Task = Literal[
    "GROUNDED_QA", "EXTRACTION", "TRANSLATION", "SUMMARIZATION", "INSTRUCTION", "REASONING"
]
Usage = Literal["FIXTURE", "PILOT", "EVALUATION"]
Origin = Literal["HUMAN_CREATED", "SYNTHETIC", "PUBLIC_DATASET"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", serialize_by_alias=True, validate_by_name=True)


class LanguageProfile(StrictModel):
    languages: list[Literal["en", "ml"]] = Field(min_length=1, max_length=2)
    script: Literal["Latin", "Malayalam", "mixed"]
    register_style: Literal["formal", "conversational", "colloquial", "unspecified"] = Field(
        default="unspecified", alias="register"
    )
    mixing: Literal["none", "lexical", "within_sentence", "between_sentence", "ambiguous"] = "none"
    romanization: str | None = None

    @model_validator(mode="after")
    def valid_combination(self) -> "LanguageProfile":
        if len(set(self.languages)) != len(self.languages):
            raise ValueError("duplicate language labels")
        if self.romanization and "ml" not in self.languages:
            raise ValueError("Romanization requires Malayalam")
        return self


class ExpectedContract(StrictModel):
    accepted_answers: list[str] = Field(default_factory=list)
    json_schema: dict[str, Any] | None = None
    expected_fields: dict[str, Any] | None = None
    required_literals: list[str] = Field(default_factory=list)
    max_characters: int | None = Field(default=None, ge=1)
    answerable: bool = True
    abstention_answers: list[str] = Field(default_factory=list)
    semantic_units: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_schema(self) -> "ExpectedContract":
        if self.expected_fields is not None and self.json_schema is None:
            raise ValueError("expected_fields requires a json_schema")
        if self.json_schema is not None:
            from adriva.evaluation.schema import conforms, validate_schema

            validate_schema(self.json_schema)
            if self.expected_fields is not None:
                props = self.json_schema.get("properties", {})
                if self.json_schema["type"] != "object" or any(
                    k not in props or not conforms(v, props[k])
                    for k, v in self.expected_fields.items()
                ):
                    raise ValueError("Expected fields must match declared property schemas")
        return self


class DerivationInput(StrictModel):
    parent_key: str
    operator_version: str
    relation: Literal["INVARIANT", "DIRECTIONAL"]
    invariant: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class CaseInput(StrictModel):
    key: str = Field(min_length=1, max_length=128)
    cluster_key: str = Field(min_length=1, max_length=128)
    family_key: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1)
    task: Task
    prompt: str = Field(min_length=1, max_length=20000)
    context: str = Field(default="", max_length=100000)
    input_profile: LanguageProfile
    output_profile: LanguageProfile
    expected: ExpectedContract
    usage: Usage
    origin: Origin
    source_uri: str = Field(min_length=1, max_length=2000)
    license: str = Field(min_length=1, max_length=200)
    source_revision: str | None = None
    source_item_key: str | None = None
    permission_note: str | None = None
    sensitivity: Literal["PUBLIC", "INTERNAL", "SENSITIVE"] = "PUBLIC"
    creator_ref: str | None = None
    generator_metadata: dict[str, str] | None = None
    derivation: DerivationInput | None = None
    split: Literal["development", "calibration", "evaluation"]

    @model_validator(mode="after")
    def evidence_contract(self) -> "CaseInput":
        if not self.license.strip() or not self.source_uri.strip():
            raise ValueError("Source and license cannot be blank")
        if self.origin == "PUBLIC_DATASET" and (
            not self.source_revision or not self.source_item_key
        ):
            raise ValueError("Public datasets require source revision and item key")
        if self.usage != "FIXTURE":
            if not self.creator_ref:
                raise ValueError("Scientific cases require creator reference")
            if self.origin == "SYNTHETIC" and (
                not self.generator_metadata
                or not {"generator", "version", "prompt_digest"}.issubset(self.generator_metadata)
            ):
                raise ValueError("Synthetic scientific cases require generator lineage")
        if self.task in {"GROUNDED_QA", "SUMMARIZATION"} and not self.context:
            raise ValueError("grounded tasks require context")
        if self.task == "GROUNDED_QA":
            answers = (
                self.expected.accepted_answers
                if self.expected.answerable
                else self.expected.abstention_answers
            )
            if not answers:
                raise ValueError("QA requires answer or abstention references")
        if self.task == "EXTRACTION" and self.expected.expected_fields is None:
            raise ValueError("extraction requires typed expected fields")
        return self


class BenchmarkImport(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    cases: list[CaseInput] = Field(min_length=1, max_length=1000)
