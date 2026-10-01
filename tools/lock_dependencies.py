"""Record exact installed dependency versions for the focused backend environment."""

from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement

queue = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pydantic-settings",
    "psycopg",
    "pytest",
    "httpx",
    "ruff",
]
versions: dict[str, str] = {}
while queue:
    name = queue.pop()
    normalized = name.lower().replace("_", "-")
    if normalized in versions:
        continue
    package = distribution(name)
    versions[normalized] = package.version
    for raw in package.requires or []:
        requirement = Requirement(raw)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            queue.append(requirement.name)
target = Path(__file__).resolve().parents[1] / "backend/requirements.lock.txt"
target.write_text(
    "# Exact versions used for verification; includes test tools.\n"
    + "\n".join(f"{name}=={version}" for name, version in sorted(versions.items()))
    + "\n",
    encoding="utf-8",
)
print(f"Locked {len(versions)} distributions.")
