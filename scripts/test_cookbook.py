#!/usr/bin/env python3
"""Run every recipe in the cookbook against dummy_data/ and report pass/fail.

Each recipe runs in a throwaway directory with dummy_data/ symlinked in, so
commands are exactly what a user would type from the repository root and any
output files they create are discarded afterwards.

    python3 scripts/test_cookbook.py            # run everything
    python3 scripts/test_cookbook.py B04 V01    # run named recipes
    python3 scripts/test_cookbook.py -v         # show output of each command

Exit status is non-zero if any recipe fails, which is what CI checks.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from recipes import RECIPES, by_category   # noqa: E402

GREEN, RED, YELLOW, DIM, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m")
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    GREEN = RED = YELLOW = DIM = BOLD = RESET = ""

TIMEOUT = 60


def have(tool):
    return shutil.which(tool) is not None


def check(recipe, stdout, code):
    """Return None if the recipe passed, else a failure reason."""
    expect = recipe.get("expect")
    out = stdout.strip()

    if code != 0:
        return "exit status %d" % code
    if expect == "ok":
        return None
    if expect is None:
        return None if out else "no output"
    if expect.startswith("="):
        want = expect[1:]
        return None if out == want else "expected %r, got %r" % (want, out[:60])
    if expect.startswith("~"):
        pattern = expect[1:]
        if re.search(pattern, out, re.MULTILINE):
            return None
        return "output did not match /%s/: %r" % (pattern, out[:60])
    return "unknown expect syntax %r" % expect


def run(recipe, verbose=False):
    missing = [t for t in recipe.get("tools", []) if not have(t)]
    if missing:
        return "skip", "missing: " + ", ".join(missing), ""

    workdir = tempfile.mkdtemp(prefix="cookbook-")
    try:
        os.symlink(os.path.join(ROOT, "dummy_data"),
                   os.path.join(workdir, "dummy_data"))
        proc = subprocess.run(
            ["bash", "-c", recipe["cmd"]],
            cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT)
        reason = check(recipe, proc.stdout, proc.returncode)
        detail = proc.stdout if verbose else ""
        if reason:
            err = proc.stderr.strip().splitlines()
            if err:
                reason += " | stderr: " + err[-1][:80]
            return "fail", reason, detail
        return "pass", "", detail
    except subprocess.TimeoutExpired:
        return "fail", "timed out after %ds" % TIMEOUT, ""
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    wanted = set(a.upper() for a in args)

    if not os.path.isdir(os.path.join(ROOT, "dummy_data")):
        sys.exit("dummy_data/ not found - run scripts/build_dummy_data.sh")

    counts = {"pass": 0, "fail": 0, "skip": 0}
    failures = []

    for key, title, items in by_category():
        items = [r for r in items if not wanted or r["id"] in wanted]
        if not items:
            continue
        print("\n%s%s%s" % (BOLD, title, RESET))
        for recipe in items:
            status, reason, detail = run(recipe, verbose)
            counts[status] += 1
            mark = {"pass": GREEN + "PASS" + RESET,
                    "fail": RED + "FAIL" + RESET,
                    "skip": YELLOW + "SKIP" + RESET}[status]
            trap = DIM + "  [trap]" + RESET if recipe.get("trap") else ""
            print("  %s  %-4s %s%s" % (mark, recipe["id"], recipe["task"], trap))
            if reason:
                print("        %s%s%s" % (DIM, reason, RESET))
            if detail:
                for line in detail.strip().splitlines()[:6]:
                    print("        %s| %s%s" % (DIM, line[:100], RESET))
            if status == "fail":
                failures.append((recipe["id"], reason))

    total = sum(counts.values())
    print("\n%s%d recipes: %d passed, %d failed, %d skipped%s"
          % (BOLD, total, counts["pass"], counts["fail"], counts["skip"], RESET))

    if failures:
        print("\n%sFailures:%s" % (RED, RESET))
        for rid, reason in failures:
            print("  %s  %s" % (rid, reason))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
