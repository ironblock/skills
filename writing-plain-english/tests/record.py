#!/usr/bin/env python3
"""Write a RED or GREEN record of this working tree's test suite.

Usage (from the repository root):
  python3 tests/record.py red PARENT [NAME] > RED<n>.txt
  python3 tests/record.py green PARENT [NAME] > GREEN<n>.txt

red runs this working tree's tests against PARENT's ste_lint.py, exported
with `git archive PARENT` into a temporary directory. green runs them against
./ste_lint.py. NAME heads the record (default RED or GREEN).

A new test is a test id in this tree's tests/ that PARENT's tests/ does not
have. An existing test changed when its function's syntax tree differs from
PARENT's. Every new and changed test also runs alone, and its verdict is
that run's exit status, never the runner's text. The record replaces the
repository path with "." and the export path with "<PARENT export>".

Standard library and git only. Exit status: the full runner's exit status,
or 2 for a bad invocation.
"""
import ast
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TESTS = REPO / "tests"
RUNNER = ["-m", "unittest", "discover", "-s", "tests", "-v"]


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def test_functions(tests_dir):
    """{test id: (FunctionDef dump, first docstring line)} for tests_dir/test_*.py."""
    out = {}
    for path in sorted(Path(tests_dir).glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            for fn in cls.body:
                if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test"):
                    doc = (ast.get_docstring(fn) or "").strip().splitlines()
                    out[f"{path.stem}.{cls.name}.{fn.name}"] = (ast.dump(fn), doc[0] if doc else "")
    return out


def fixtures(tests_dir):
    d = Path(tests_dir) / "fixtures"
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())} if d.is_dir() else {}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv):
    if len(argv) not in (2, 3) or argv[0] not in ("red", "green"):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    mode, parent = argv[0], argv[1]
    name = argv[2] if len(argv) == 3 else mode.upper()
    try:
        sha = git("rev-parse", "--verify", "--quiet", f"{parent}^{{commit}}")
    except subprocess.CalledProcessError:
        print(f"record.py: {parent} is not a commit", file=sys.stderr)
        return 2
    short = sha[:8]
    with tempfile.TemporaryDirectory() as tmp:
        export = Path(tmp) / short
        export.mkdir()
        archive = subprocess.run(["git", "-C", str(REPO), "archive", sha],
                                 check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(export)], input=archive, check=True)
        return record(mode, name, short, export)


def record(mode, name, short, export):
    label = f"<{short} export>"

    def shorten(s):
        s = s.replace(str(export), label).replace(str(REPO), ".")
        home = os.path.expanduser("~")
        return s.replace(home, "~") if home not in ("", "/") else s

    env = {k: v for k, v in os.environ.items() if k != "LINT"}
    env["PYTHON_COLORS"] = "0"
    if mode == "red":
        lint = export / "ste_lint.py"
        env["LINT"] = str(lint)
        command = f"LINT={label}/ste_lint.py PYTHON_COLORS=0 python3 {' '.join(RUNNER)}"
    else:
        lint = REPO / "ste_lint.py"
        command = f"PYTHON_COLORS=0 python3 {' '.join(RUNNER)}"

    full = subprocess.run([sys.executable, *RUNNER], cwd=REPO, env=env,
                          capture_output=True, text=True)
    now, then = test_functions(TESTS), test_functions(export / "tests")
    new = sorted(set(now) - set(then))
    changed = sorted(t for t in set(now) & set(then) if now[t][0] != then[t][0])
    removed = sorted(set(then) - set(now))

    def alone(test_id):
        return subprocess.run([sys.executable, "-m", "unittest", test_id], cwd=TESTS, env=env,
                              capture_output=True, text=True).returncode

    status = {t: alone(t) for t in new + changed}
    fx_now, fx_then = fixtures(TESTS), fixtures(export / "tests")

    out = []
    w = out.append
    if mode == "red":
        w(f"{name}: this working tree's test suite run against the parent commit, {short}.")
        w("")
        w(f"The parent's tree was exported with `git archive {short}` into a temporary")
        w(f"directory outside this repository (\"{label}\" below). The tests and")
        w("fixtures come from this repository's working tree.")
        w("")
        w("A new test that fails here states its reason in its docstring's first line")
        w(f"(\"RED on {short}: ...\"). A new test that passes here is a guard (\"Guard,")
        w(f"passes on {short}: ...\"), not a test of a fix.")
    else:
        w(f"{name}: this working tree's test suite run against the lint in this repository.")
        w("")
        w(f"New and changed tests are counted against the parent commit, {short}.")
    w("")
    w(f"Written by: python3 tests/record.py {mode} {short}{' ' + name if name != mode.upper() else ''}")
    w(f"Implementation: {shorten(str(lint))} (sha256 {sha256(lint)})")
    w(f"Command: {command}")
    w(f"Runner exit status: {full.returncode}")
    w(f"Tests in the suite: {len(now)}; new in this round: {len(new)}; "
      f"existing tests changed: {len(changed)}; removed: {len(removed)}")
    w("")
    w("Each new and changed test was also run alone (python3 -m unittest <id>, from")
    w("tests/); the lists below come from those runs' exit statuses, not from the")
    w("runner's text. The path of this repository is shortened to \".\".")
    w("")
    def section(title, entries):
        """entries: one list of lines per test or fixture."""
        w(f"{title} ({len(entries)}):")
        if entries:
            w("")
            for lines in entries:
                out.extend(lines)
        w("")

    def listed(tests, exit_status):
        return [[f"  {t}  [exit {status[t]}]" if exit_status else f"  {t}", f"      {now[t][1]}"]
                for t in tests]

    section("New tests that failed (exit status non-zero)", listed([t for t in new if status[t]], True))
    section("New tests that passed (exit status 0)", listed([t for t in new if not status[t]], False))
    section("Existing tests whose body changed in this round", listed(changed, True))
    section("Tests removed in this round", [[f"  {t}"] for t in removed])
    for title, names in (("added", sorted(set(fx_now) - set(fx_then))),
                         ("changed", sorted(f for f in set(fx_now) & set(fx_then) if fx_now[f] != fx_then[f])),
                         ("removed", sorted(set(fx_then) - set(fx_now)))):
        section(f"Fixtures {title} in this round", [[f"  {n}"] for n in names])
    w("--- runner output ---")
    w(shorten(full.stderr + full.stdout).rstrip("\n"))
    print("\n".join(out))
    return full.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
