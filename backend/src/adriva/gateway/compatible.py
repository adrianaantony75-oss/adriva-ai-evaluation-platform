"""Opt-in OpenAI-compatible HTTP gateway; endpoint and secrets remain in environment."""

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from adriva.gateway.contracts import AdapterError, GenerationRequest, GenerationResult, ModelConfig


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AdapterError("PROVIDER_REDIRECT_REJECTED")


class CompatibleAdapter:
    def __init__(self) -> None:
        self.config: ModelConfig | None = None

    def validate(self, config: ModelConfig) -> None:
        if config.provider != "openai_compatible" or config.usage_class != "REAL":
            raise AdapterError("INVALID_PROVIDER")
        for ref, prefix in (
            (config.endpoint_ref, "ADRIVA_ENDPOINT_"),
            (config.credential_ref, "ADRIVA_PROVIDER_KEY_"),
        ):
            if ref is not None and not re.fullmatch(prefix + r"[A-Z0-9_]+", ref):
                raise AdapterError("INVALID_ENVIRONMENT_REFERENCE")
        if not config.endpoint_ref:
            raise AdapterError("ENDPOINT_REQUIRED")
        if set(config.parameters) - {"temperature", "max_tokens", "top_p", "seed"}:
            raise AdapterError("UNSUPPORTED_GENERATION_PARAMETER")
        for name, value in config.parameters.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise AdapterError("INVALID_GENERATION_PARAMETER")
            if name == "max_tokens" and (type(value) is not int or not 1 <= value <= 32768):
                raise AdapterError("INVALID_TOKEN_LIMIT")
            if name == "temperature" and not 0 <= value <= 2:
                raise AdapterError("INVALID_TEMPERATURE")
            if name == "top_p" and not 0 < value <= 1:
                raise AdapterError("INVALID_TOP_P")
            if name == "seed" and type(value) is not int:
                raise AdapterError("INVALID_SEED")
        self.config = config

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if self.config is None:
            raise AdapterError("ADAPTER_NOT_CONFIGURED")
        endpoint = os.environ.get(self.config.endpoint_ref or "", "")
        parsed = urlparse(endpoint)
        if (
            parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.hostname
            or (
                parsed.scheme != "https"
                and not (
                    parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                )
            )
        ):
            raise AdapterError("INVALID_CONFIGURED_ENDPOINT")
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": str(request.logical_request_id),
        }
        if self.config.credential_ref:
            token = os.environ.get(self.config.credential_ref)
            if not token:
                raise AdapterError("CREDENTIAL_UNAVAILABLE")
            headers["Authorization"] = "Bearer " + token
        body = {
            "model": self.config.requested_model,
            "messages": [
                {
                    "role": "user",
                    "content": ("Context:\n" + request.context + "\n\n" if request.context else "")
                    + request.prompt,
                }
            ],
            **self.config.parameters,
        }
        try:
            with build_opener(NoRedirect()).open(
                Request(endpoint, data=json.dumps(body).encode(), headers=headers, method="POST"),
                timeout=30,
            ) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise AdapterError("PROVIDER_RESPONSE_TOO_LARGE")
            payload = json.loads(raw)
            choice = payload["choices"][0]
            text = choice["message"]["content"]
            if not isinstance(text, str) or not isinstance(payload.get("model"), str):
                raise ValueError("Malformed provider response")
            return GenerationResult(
                text=text,
                finish_reason=choice.get("finish_reason") or "unknown",
                returned_model=payload["model"],
                provider_request_id=payload.get("id"),
                usage={
                    "tokens_known": bool(payload.get("usage")),
                    "cost_known": False,
                    **payload.get("usage", {}),
                },
                raw=payload,
            )
        except HTTPError as exc:
            raise AdapterError(
                "PROVIDER_HTTP_" + str(exc.code), retryable=exc.code == 429 or exc.code >= 500
            ) from None
        except (URLError, TimeoutError, OSError):
            raise AdapterError("PROVIDER_TRANSPORT_ERROR", retryable=True) from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise AdapterError("PROVIDER_SCHEMA_ERROR") from None


def select_adapter(provider: str):
    if provider == "fixture":
        from adriva.gateway.fixture import FixtureAdapter

        return FixtureAdapter()
    if provider == "openai_compatible":
        return CompatibleAdapter()
    raise AdapterError("ADAPTER_UNAVAILABLE")
