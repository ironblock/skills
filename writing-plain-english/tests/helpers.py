"""Shared helpers: run the lint under test as a command, on fixture files.

The implementation under test is the file named by the LINT environment
variable, or ../ste_lint.py when LINT is unset. Every run uses the fixtures
directory as its working directory and passes bare fixture names, so the
lint's output names no machine path.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
LINT = Path(os.environ.get("LINT") or HERE.parent / "ste_lint.py").resolve()


def run(*args):
    """(exit status, stdout, stderr) of one lint run."""
    p = subprocess.run([sys.executable, "-I", str(LINT), *args], cwd=FIXTURES,
                       capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def run_json(*args):
    """(exit status, parsed stdout) of one lint run with --json."""
    code, out, _ = run("--json", *args)
    return code, json.loads(out)


def lint_report(name, *flags):
    """(exit status, the report for one file) in lint mode."""
    code, data = run_json(*flags, name)
    return code, data[name]


def kinds(report):
    return [f["kind"] for f in report["findings"]]


def findings_of(report, kind):
    return [(f["kind"], f["line"]) for f in report["findings"] if f["kind"] == kind]


def load_module():
    spec = importlib.util.spec_from_file_location("lint_under_test", LINT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def source():
    return LINT.read_text(encoding="utf-8")
