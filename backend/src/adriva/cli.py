import argparse
import json
from pathlib import Path
from uuid import UUID

from adriva.config import Settings
from adriva.db.connection import connect
from adriva.db.migrate import migrate
from adriva.domain.benchmarks import create_project, import_benchmark, publish_release
from adriva.domain.contracts import BenchmarkImport


def main() -> None:
    parser = argparse.ArgumentParser(prog="adriva")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate")
    project = sub.add_parser("project")
    project.add_argument("name")
    project.add_argument("slug")
    registry = sub.add_parser("import")
    registry.add_argument("project_id", type=UUID)
    registry.add_argument("file", type=Path)
    publish = sub.add_parser("publish")
    publish.add_argument("project_id", type=UUID)
    publish.add_argument("release_id", type=UUID)
    args = parser.parse_args()
    settings = Settings()
    if args.command == "migrate":
        print(json.dumps({"applied": migrate(settings)}))
        return
    with connect(settings) as db:
        if args.command == "project":
            print(create_project(db, args.name, args.slug))
        elif args.command == "import":
            if args.file.stat().st_size > 5_000_000:
                parser.error("Import exceeds 5 MB limit")
            batch = BenchmarkImport.model_validate_json(args.file.read_text(encoding="utf-8"))
            print(import_benchmark(db, args.project_id, batch))
        elif args.command == "publish":
            print(publish_release(db, args.project_id, args.release_id))


if __name__ == "__main__":
    main()
