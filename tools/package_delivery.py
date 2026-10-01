"""Create a source-only review package, excluding runtime data and local secrets."""

import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "outputs"
EXCLUDED = {
    ".venv",
    ".local",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
}


def source_files():
    for p in sorted(ROOT.rglob("*")):
        relative = p.relative_to(ROOT)
        if not p.is_file() or any(
            part in EXCLUDED or part.endswith(".egg-info") for part in relative.parts
        ):
            continue
        if p.name.startswith(".env") and p.name != ".env.example":
            continue
        if p.suffix in {".pyc", ".log", ".whl"}:
            continue
        yield p, relative


def main():
    OUTPUT.mkdir(exist_ok=True)
    evidence = ROOT / "docs/evidence"
    evidence.mkdir(exist_ok=True)
    for name in ("test-results.xml", "browser-results.json"):
        shutil.copyfile(ROOT / ".local" / name, evidence / name)
    screenshots = ROOT / "docs/screenshots"
    screenshots.mkdir(exist_ok=True)
    for name in ("overview", "comparison", "case", "mobile", "languages", "models", "health"):
        shutil.copyfile(ROOT / f".local/screenshots/{name}.png", screenshots / f"{name}.png")
    (ROOT / "docs/PROGRESS.md").write_text(
        "# Current status\n\nSee FINAL-DELIVERY.md, VERIFICATION.md and AUDIT.md for authoritative scope.\n\nLocal application: implemented and verified. 63 automated tests passed. Ten browser modules checked. ADRIVA-BENCH 0.1.0 remains a 24-case synthetic draft. Genuine model/human studies and production deployment are not complete.\n",
        encoding="utf-8",
    )
    protocol = ROOT / "docs/science/01-protocol.md"
    text = protocol.read_text(encoding="utf-8")
    if not text.startswith("> Current implementation"):
        text = (
            "> Current implementation note (2026-10-01): ADRIVA-BENCH 0.1.0 is a 24-case synthetic draft spanning all six tasks. Deterministic checks do not validate free-text semantics. The SQL release gate now requires two distinct reviewer records; qualifications remain self-attested locally. See BENCHMARK-CARD.md and FINAL-DELIVERY.md. The v1 title below describes the inherited protocol, not a released benchmark.\n\n"
            + text
        )
        protocol.write_text(text, encoding="utf-8")
    files = list(source_files())
    suspicious = []
    patterns = [
        r"sk-[A-Za-z0-9_-]{24,}",
        r"ghp_[A-Za-z0-9]{30,}",
        r"AKIA[0-9A-Z]{16}",
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    ]
    for p, rel in files:
        if p.suffix in {".py", ".md", ".json", ".yaml", ".yml", ".ps1", ".js", ".html", ".txt"}:
            content = p.read_text(encoding="utf-8")
            if any(re.search(pattern, content) for pattern in patterns):
                suspicious.append(str(rel))
    if suspicious:
        raise RuntimeError("Potential secrets need inspection in: " + ", ".join(suspicious))
    manifest = {
        str(rel).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
        for p, rel in files
        if rel != Path("docs/evidence/source-manifest.json")
    }
    (evidence / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    archive = OUTPUT / "ADRIVA-Local-Edition.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p, rel in source_files():
            z.write(p, Path("ADRIVA") / rel)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert "ADRIVA/backend/src/adriva/web/index.html" in z.namelist()
        assert "ADRIVA/backend/src/adriva/db/migrations/009_review_quorum.sql" in z.namelist()
        assert not any(
            "/.local/" in n or "/.venv/" in n or n.endswith("/.env") for n in z.namelist()
        )
    shutil.copyfile(ROOT / "docs/FINAL-DELIVERY.md", OUTPUT / "ADRIVA-Final-Delivery.md")
    print(
        json.dumps(
            {
                "archive": str(archive),
                "bytes": archive.stat().st_size,
                "source_files": len(files),
                "secret_pattern_findings": len(suspicious),
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
