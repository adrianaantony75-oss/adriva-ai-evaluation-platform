"""Export the authoritative typed registry contract; no model calls."""

import json
from pathlib import Path

from adriva.domain.contracts import BenchmarkImport

target = Path(__file__).resolve().parents[1] / "benchmarks/schemas/benchmark-import-v1.schema.json"
target.parent.mkdir(parents=True, exist_ok=True)
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **BenchmarkImport.model_json_schema(),
}
target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(target.name)
