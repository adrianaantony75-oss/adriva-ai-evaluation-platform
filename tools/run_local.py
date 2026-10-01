"""Run a Python module with optional native libpq location on constrained Windows hosts.

Usage: python tools/run_local.py pytest backend/tests -q
Set ADRIVA_LIBPQ_DIR only for a trusted local PostgreSQL installation.
"""

import os
import runpy
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "backend" / "src"))
if directory := os.environ.get("ADRIVA_LIBPQ_DIR"):
    os.environ["PATH"] = directory + os.pathsep + os.environ["PATH"]
    if sys.platform == "win32":
        dll_handle = os.add_dll_directory(directory)
module, *arguments = sys.argv[1:]
sys.argv = [module, *arguments]
runpy.run_module(module, run_name="__main__")
