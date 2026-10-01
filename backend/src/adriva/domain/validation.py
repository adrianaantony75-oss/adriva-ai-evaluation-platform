from dataclasses import dataclass

from adriva.domain.contracts import BenchmarkImport
from adriva.domain.hashing import digest


@dataclass(frozen=True)
class QualityFinding:
    rule: str
    case_key: str
    severity: str


def validate_import(batch: BenchmarkImport) -> list[QualityFinding]:
    findings: list[QualityFinding] = []
    keys: dict[str, object] = {}
    splits: dict[str, str] = {}
    families: dict[str, tuple[str, str]] = {}
    prompts: dict[str, str] = {}
    for case in batch.cases:
        if case.key in keys:
            findings.append(QualityFinding("DUPLICATE_KEY", case.key, "CRITICAL"))
        keys[case.key] = case
        if splits.setdefault(case.cluster_key, case.split) != case.split:
            findings.append(QualityFinding("CLUSTER_SPLIT_LEAKAGE", case.key, "CRITICAL"))
        if families.setdefault(case.family_key, (case.cluster_key, case.task)) != (
            case.cluster_key,
            case.task,
        ):
            findings.append(QualityFinding("FAMILY_CONTRACT_MISMATCH", case.key, "CRITICAL"))
        fingerprint = digest({"prompt": case.prompt, "context": case.context, "task": case.task})
        if fingerprint in prompts:
            findings.append(QualityFinding("EXACT_DUPLICATE", case.key, "CRITICAL"))
        prompts[fingerprint] = case.key
    for case in batch.cases:
        if case.derivation:
            parent = next((p for p in batch.cases if p.key == case.derivation.parent_key), None)
            if parent is None or parent.family_key != case.family_key or parent.key == case.key:
                findings.append(QualityFinding("INVALID_PARENT", case.key, "CRITICAL"))
            visited = {case.key}
            while parent and parent.derivation:
                if parent.key in visited:
                    findings.append(QualityFinding("LINEAGE_CYCLE", case.key, "CRITICAL"))
                    break
                visited.add(parent.key)
                parent = next(
                    (p for p in batch.cases if p.key == parent.derivation.parent_key), None
                )
    return findings
