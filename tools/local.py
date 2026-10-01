"""Local-only process launcher. Own database cluster; never uses another project database."""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import psycopg
from adriva.config import Settings
from adriva.db.connection import connect

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"


def spawn(args, name):
    with (LOCAL / f"{name}.log").open("ab") as log:
        child = subprocess.Popen(
            args,
            cwd=ROOT,
            env=os.environ.copy(),
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    return child.pid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start"])
    parser.add_argument("--port", type=int, default=8019)
    args = parser.parse_args()
    LOCAL.mkdir(exist_ok=True)
    settings = Settings()
    if settings.database_url.get_secret_value() != "postgresql://adriva@127.0.0.1:55439/adriva":
        parser.error("Local launcher requires its dedicated loopback database on port 55439")
    pg = Path(os.environ["ADRIVA_LIBPQ_DIR"])
    data = LOCAL / "pgdata"
    if not (data / "PG_VERSION").exists():
        subprocess.run(
            [
                str(pg / "initdb.exe"),
                "-D",
                str(data),
                "-U",
                "adriva",
                "--auth=trust",
                "--encoding=UTF8",
                "--locale=C",
            ],
            check=True,
        )
    try:
        with connect(settings) as db:
            actual = db.execute("SHOW data_directory").fetchone()["data_directory"]
            if Path(actual).resolve() != data.resolve():
                parser.error("Port 55439 is occupied by a different database cluster")
    except SystemExit:
        raise
    except psycopg.OperationalError:
        spawn(
            [
                str(pg / "postgres.exe"),
                "-D",
                str(data),
                "-h",
                "127.0.0.1",
                "-p",
                "55439",
            ],
            "database",
        )
        for _ in range(40):
            result = subprocess.run(
                [str(pg / "pg_isready.exe"), "-h", "127.0.0.1", "-p", "55439"],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                break
            time.sleep(0.25)
        result = subprocess.run(
            [
                str(pg / "createdb.exe"),
                "-h",
                "127.0.0.1",
                "-p",
                "55439",
                "-U",
                "adriva",
                "adriva",
            ],
            capture_output=True,
            check=False,
        )
        with connect(settings) as db:
            actual = db.execute("SHOW data_directory").fetchone()["data_directory"]
            if Path(actual).resolve() != data.resolve():
                parser.error("Unexpected PostgreSQL data directory")
    from tools.bootstrap import main as bootstrap

    bootstrap()
    url = f"http://127.0.0.1:{args.port}"
    try:
        urllib.request.urlopen(url + "/api/v1/health/ready", timeout=1)
        print(f"ADRIVA is already responding at {url}")
        return
    except OSError:
        pass
    runner = str(ROOT / "tools/run_local.py")
    api = spawn(
        [
            sys.executable,
            runner,
            "uvicorn",
            "adriva.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        "api",
    )
    worker = spawn([sys.executable, runner, "adriva.workers.runner", "--watch"], "worker")
    (LOCAL / "processes.json").write_text(
        json.dumps({"api_pid": api, "worker_pid": worker, "url": url})
    )
    for _ in range(40):
        try:
            with urllib.request.urlopen(url + "/api/v1/health/ready", timeout=1) as response:
                if response.status == 200:
                    print(f"ADRIVA ready: {url}")
                    return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("API did not become ready; inspect .local/api.log")


if __name__ == "__main__":
    main()
