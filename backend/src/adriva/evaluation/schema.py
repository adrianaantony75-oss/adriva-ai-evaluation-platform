from typing import Any

ALLOWED = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "enum",
    "minimum",
    "maximum",
}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def validate_schema(schema: dict[str, Any], depth: int = 0) -> None:
    """Deliberately bounded JSON Schema subset; unsupported keywords fail closed."""
    if depth > 8 or set(schema) - ALLOWED or schema.get("type") not in TYPES:
        raise ValueError("Unsupported or excessively nested schema")
    if schema["type"] == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if (
            not isinstance(properties, dict)
            or not isinstance(required, list)
            or any(not isinstance(v, str) for v in required)
        ):
            raise ValueError("Invalid properties/required")
        if set(required) - properties.keys() or not isinstance(
            schema.get("additionalProperties", True), bool
        ):
            raise ValueError("Unsupported object schema")
        for child in properties.values():
            validate_schema(child, depth + 1)
    if schema["type"] == "array":
        if not isinstance(schema.get("items"), dict):
            raise ValueError("Array items schema required")
        validate_schema(schema["items"], depth + 1)
    for bound in ("minimum", "maximum"):
        if bound in schema and (
            type(schema[bound]) not in (int, float) or schema["type"] not in {"number", "integer"}
        ):
            raise ValueError("Numeric bounds require numeric schemas")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError("Nonempty enum required")


def conforms(value: Any, schema: dict[str, Any]) -> bool:
    kind = schema["type"]
    matches = {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "integer": type(value) is int,
        "number": type(value) in (int, float),
        "boolean": type(value) is bool,
        "null": value is None,
    }
    if not matches[kind]:
        return False
    if "enum" in schema and not any(type(value) is type(v) and value == v for v in schema["enum"]):
        return False
    if kind == "object":
        props = schema.get("properties", {})
        if not set(schema.get("required", [])).issubset(value):
            return False
        if not schema.get("additionalProperties", True) and set(value) - props.keys():
            return False
        return all(conforms(v, props[k]) for k, v in value.items() if k in props)
    if kind == "array":
        return all(conforms(v, schema["items"]) for v in value)
    if kind in {"number", "integer"}:
        return value >= schema.get("minimum", float("-inf")) and value <= schema.get(
            "maximum", float("inf")
        )
    return True
