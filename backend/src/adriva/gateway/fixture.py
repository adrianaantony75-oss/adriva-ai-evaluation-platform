from adriva.gateway.contracts import AdapterError, GenerationRequest, GenerationResult, ModelConfig


class FixtureAdapter:
    """Explicit injected engineering response; never computes a fake model quality score."""

    def validate(self, config: ModelConfig) -> None:
        if config.provider != "fixture" or config.usage_class != "FIXTURE":
            raise AdapterError("INVALID_REQUEST")
        if set(config.parameters) - {"fixture_text"} or not isinstance(
            config.parameters.get("fixture_text"), str
        ):
            raise AdapterError("INVALID_REQUEST")

    def generate(self, request: GenerationRequest) -> GenerationResult:
        text = request.parameters["fixture_text"]
        return GenerationResult(
            text=text,
            finish_reason="FIXTURE",
            returned_model="fixture-engineering-only",
            raw={"usage_class": "FIXTURE", "text": text},
        )
