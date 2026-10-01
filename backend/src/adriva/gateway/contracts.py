from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import Field

from adriva.domain.contracts import StrictModel


class ModelConfig(StrictModel):
    provider: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    endpoint_ref: str | None = None
    credential_ref: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Literal["SUPPORTED", "UNSUPPORTED", "UNKNOWN"]] = Field(
        default_factory=dict
    )
    usage_class: Literal["FIXTURE", "REAL"]


class GenerationRequest(StrictModel):
    logical_request_id: UUID
    prompt: str
    context: str
    parameters: dict[str, Any]


class GenerationResult(StrictModel):
    text: str
    finish_reason: str
    returned_model: str
    provider_request_id: str | None = None
    usage: dict[str, Any] = Field(
        default_factory=lambda: {"tokens_known": False, "cost_known": False}
    )
    raw: dict[str, Any] = Field(default_factory=dict)


class AdapterError(Exception):
    def __init__(self, code: str, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(code)


class ModelAdapter(Protocol):
    def validate(self, config: ModelConfig) -> None: ...
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
