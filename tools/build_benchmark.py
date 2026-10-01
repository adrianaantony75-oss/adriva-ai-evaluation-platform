"""Reproducible authored seed pack. Never substitutes for native-speaker review."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = [
    (
        "price",
        "GROUNDED_QA",
        "The fictional shop lists the notebook at 250 rupees.",
        [
            "Return only the notebook price as digits.",
            "നോട്ട്ബുക്കിന്റെ വില അക്കങ്ങളിൽ മാത്രം നൽകുക.",
            "Notebookinte vila akkangalil mathram tharuka.",
            "നോട്ട്ബുക്കിന്റെ price digits ആയി മാത്രം നൽകുക.",
        ],
        {"accepted_answers": ["250"]},
    ),
    (
        "order",
        "EXTRACTION",
        "Fictional order: item=pen; quantity=3.",
        [
            "Extract item and quantity as a JSON object, with no extra keys.",
            "സാധനവും എണ്ണവും item, quantity എന്നീ കീകളുള്ള JSON ആയി നൽകുക. മറ്റ് കീകൾ വേണ്ട.",
            "Itemum quantityum JSON aayi tharuka. Vere keys venda.",
            "item, quantity മാത്രം ഉള്ള JSON നൽകുക.",
        ],
        {
            "json_schema": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "quantity": {"type": "integer"},
                },
                "required": ["item", "quantity"],
                "additionalProperties": False,
            },
            "expected_fields": {"item": "pen", "quantity": 3},
        },
    ),
    (
        "translation",
        "TRANSLATION",
        "",
        [
            'Translate "Good morning" into Malayalam.',
            '"Good morning" മലയാളത്തിലേക്ക് വിവർത്തനം ചെയ്യുക.',
            '"Good morning" Malayalathilekku translate cheyyuka.',
            '"Good morning" മലയാളത്തിലേക്ക് translate ചെയ്യുക.',
        ],
        {
            "accepted_answers": ["സുപ്രഭാതം", "സുപ്രഭാതം."],
            "semantic_units": ["A morning greeting"],
        },
    ),
    (
        "notice",
        "SUMMARIZATION",
        "A fictional library closes on Monday for repairs and reopens on Tuesday.",
        [
            "Summarize in English in at most 100 characters. Retain Monday and Tuesday.",
            "Monday, Tuesday എന്നീ വാക്കുകൾ ഉൾപ്പെടുത്തി ഇംഗ്ലീഷിൽ 100 അക്ഷരങ്ങളിൽ കവിയാതെ സംഗ്രഹിക്കുക.",
            "Englishil 100 charactersil kaviyathe churukki ezhuthuka. Mondayum Tuesdayum venam.",
            "English summary 100 charactersൽ കവിയരുത്. Monday, Tuesday ഉൾപ്പെടുത്തുക.",
        ],
        {
            "max_characters": 100,
            "required_literals": ["Monday", "Tuesday"],
            "semantic_units": [
                "Library closed Monday for repairs",
                "Library reopens Tuesday",
            ],
        },
    ),
    (
        "format",
        "INSTRUCTION",
        "",
        [
            "Reply with exactly READY in uppercase and nothing else.",
            "READY എന്ന് വലിയ ഇംഗ്ലീഷ് അക്ഷരങ്ങളിൽ മാത്രം മറുപടി നൽകുക.",
            "READY ennu capital lettersil mathram marupadi tharuka.",
            "READY മാത്രം reply ചെയ്യുക; uppercase വേണം.",
        ],
        {"accepted_answers": ["READY"], "max_characters": 5},
    ),
    (
        "addition",
        "REASONING",
        "",
        [
            "There are 7 red balls and 5 blue balls. How many balls total? Return digits only.",
            "7 ചുവന്ന പന്തുകളും 5 നീല പന്തുകളും ഉണ്ട്. ആകെ എത്ര പന്തുകൾ? അക്കങ്ങളിൽ മാത്രം മറുപടി നൽകുക.",
            "7 chuvanna panthukalum 5 neela panthukalum undu. Aake ethra? Akkangal mathram tharuka.",
            "7 red പന്തുകളും 5 blue പന്തുകളും ഉണ്ട്. Total എത്ര? Digits മാത്രം നൽകുക.",
        ],
        {"accepted_answers": ["12"]},
    ),
]


def build():
    profiles = [
        {"languages": ["en"], "script": "Latin"},
        {"languages": ["ml"], "script": "Malayalam"},
        {"languages": ["ml"], "script": "Latin", "romanization": "informal-Manglish"},
        {"languages": ["ml", "en"], "script": "mixed", "mixing": "within_sentence"},
    ]
    cases = []
    for family, task, context, prompts, expected in PROMPTS:
        for index, (mode, profile, prompt) in enumerate(
            zip(("en", "ml", "manglish", "mixed"), profiles, prompts, strict=True)
        ):
            case = dict(
                key=f"{family}-{mode}",
                cluster_key=family,
                family_key=family,
                task=task,
                prompt=prompt,
                context=context,
                input_profile=profile,
                output_profile={
                    "languages": ["ml" if task == "TRANSLATION" else "en"],
                    "script": "Malayalam" if task == "TRANSLATION" else "Latin",
                },
                expected=expected,
                usage="PILOT",
                origin="SYNTHETIC",
                source_uri=f"adriva://authored-seed/0.1.0/{family}",
                license="Project-authored synthetic examples; no external dataset content",
                creator_ref="AI-assisted authoring; no human certification",
                generator_metadata={
                    "generator": "ChatGPT Codex session",
                    "version": "2026-10-01; exact model build unavailable",
                    "prompt_digest": hashlib.sha256(prompt.encode()).hexdigest(),
                },
                split="development",
            )
            if index:
                case["derivation"] = {
                    "parent_key": f"{family}-en",
                    "operator_version": f"authored-{mode}-0.1",
                    "relation": "INVARIANT",
                    "invariant": "Same intended task and constraints; human verification pending",
                }
            cases.append(case)
    target = ROOT / "benchmarks" / "pilot"
    target.mkdir(exist_ok=True)
    (target / "adriva-bench-0.1.0.json").write_text(
        json.dumps(
            {"name": "ADRIVA-BENCH", "version": "0.1.0", "cases": cases},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    for case in cases:
        case["usage"] = "FIXTURE"
        case["source_uri"] = case["source_uri"].replace("adriva://", "fixture://")
    (ROOT / "benchmarks/fixtures/product-0.1.0.json").write_text(
        json.dumps(
            {"name": "ADRIVA-ENGINEERING", "version": "0.1.0", "cases": cases},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
