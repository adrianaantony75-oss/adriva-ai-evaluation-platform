"""Narrow preservation checks; free-text mention is never relation preservation."""

import unicodedata
from decimal import Decimal, InvalidOperation

from adriva.evaluation.deterministic import Metric, normalize


def _word_character(char: str) -> bool:
    return unicodedata.category(char)[0] in {"L", "M", "N"} or char == "_"


def entity_mentions(text: str, aliases: dict[str, list[str]]) -> Metric:
    if not aliases or any(
        not names or any(not n.strip() for n in names) for names in aliases.values()
    ):
        raise ValueError("Nonempty reviewed alias sets required")
    normalized = normalize(text).casefold()

    def present(alias: str) -> bool:
        needle = normalize(alias).casefold()
        start = 0
        while (index := normalized.find(needle, start)) >= 0:
            end = index + len(needle)
            if (index == 0 or not _word_character(normalized[index - 1])) and (
                end == len(normalized) or not _word_character(normalized[end])
            ):
                return True
            start = index + 1
        return False

    found = {entity: any(present(a) for a in names) for entity, names in aliases.items()}
    return Metric(
        "entity_alias_mention_recall",
        "VALUE",
        sum(found.values()) / len(found),
        {
            "found": found,
            "scope": "diagnostic; absence may be inflection or unlisted transliteration; presence does not prove binding",
        },
    )


def bound_entities(actual: dict[str, str], expected: dict[str, list[str]]) -> Metric:
    """Only use directly requested, typed extraction fields, never guessed free-text parses."""
    if not expected or any(
        not aliases or any(not x.strip() for x in aliases) for aliases in expected.values()
    ):
        raise ValueError("Expected field bindings and approved aliases required")
    passed = {
        role: role in actual
        and normalize(actual[role]).casefold() in {normalize(a).casefold() for a in aliases}
        for role, aliases in expected.items()
    }
    return Metric(
        "bound_entity_accuracy",
        "VALUE",
        sum(passed.values()) / len(passed),
        {"fields": passed, "scope": "declared extraction roles only"},
    )


UNITS: dict[str, tuple[str, Decimal]] = {
    "INR": ("currency:INR", Decimal(1)),
    "paise": ("currency:INR", Decimal("0.01")),
    "kg": ("mass", Decimal(1000)),
    "g": ("mass", Decimal(1)),
    "hour": ("duration", Decimal(60)),
    "minute": ("duration", Decimal(1)),
    "count": ("count", Decimal(1)),
    "percent": ("percentage_points", Decimal(1)),
}


def _decimal(value: str) -> Decimal:
    if not isinstance(value, str) or not value or any(c in value for c in (",", "_", " ")):
        raise ValueError("Use explicit ungrouped decimal strings")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric representation") from exc
    if not number.is_finite():
        raise ValueError("Finite quantities required")
    return number


def quantity_equal(
    actual_value: str,
    actual_unit: str,
    expected_value: str,
    expected_unit: str,
    *,
    absolute_tolerance: str = "0",
) -> bool:
    """Tolerance is in the expected unit, frozen before model output is observed."""
    if actual_unit not in UNITS or expected_unit not in UNITS:
        raise ValueError("Unknown unit: needs reviewed conversion policy")
    actual, expected, tolerance = map(_decimal, (actual_value, expected_value, absolute_tolerance))
    if tolerance < 0:
        raise ValueError("Negative tolerance")
    adim, afactor = UNITS[actual_unit]
    edim, efactor = UNITS[expected_unit]
    return adim == edim and abs(actual * afactor - expected * efactor) <= tolerance * efactor


def bound_quantities(
    actual: dict[str, tuple[str, str]], expected: dict[str, tuple[str, str]]
) -> Metric:
    if not expected:
        raise ValueError("Quantity roles required")
    # Missing and invalid representations are different: unsupported parses raise, not silently fail.
    passed = {
        role: role in actual and quantity_equal(*actual[role], *quantity)
        for role, quantity in expected.items()
    }
    return Metric(
        "bound_quantity_accuracy",
        "VALUE",
        sum(passed.values()) / len(passed),
        {"fields": passed, "scope": "direct structured fields; no number-bag equivalence"},
    )
