"""Run every test file in its own pytest process.

The suite normally runs as one pytest session, so a test file that depends on
another file having already imported something can pass by accident. CI runs
``pytest -n auto --dist=worksteal``, which repartitions tests across workers
nondeterministically, so that kind of accident shows up as an intermittent
failure that does not reproduce on rerun. Running each file alone makes it
deterministic.

Used by both ``make test-isolated`` and ``.\\dev-commands.ps1 dev-test-isolated``
so the two stay in sync.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

DEFAULT_MARKER = "not solidworks_only and not smoke"

# pytest exits 5 when it collected nothing. Several files legitimately collect
# nothing under the marker filter: the all-``solidworks_only`` integration
# modules, the ones that ``importorskip`` a missing optional dependency at
# module level, and the all-``smoke`` module. Those are not isolation failures.
OK_EXIT_CODES = frozenset({0, 5})


def repo_root() -> Path:
    """Return the repository root (this file lives in ``tests/scripts/``)."""
    return Path(__file__).resolve().parents[2]


def discover_test_files(root: Path, tests_dir: str) -> list[Path]:
    """Return every ``test_*.py`` under ``tests_dir``, in a stable order."""
    return sorted((root / tests_dir).rglob("test_*.py"))


def run_one(root: Path, test_file: Path, marker: str) -> int:
    """Run a single test file in its own pytest process and return its exit code."""
    rel = test_file.relative_to(root).as_posix()
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            rel,
            "-m",
            marker,
            "--no-cov",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=root,
        check=False,
    )
    return completed.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--marker",
        default=DEFAULT_MARKER,
        help=f"pytest -m expression (default: {DEFAULT_MARKER!r})",
    )
    parser.add_argument(
        "--tests-dir",
        default="tests",
        help="Directory to search for test files (default: tests)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run each test file in isolation; return 1 if any of them failed."""
    args = parse_args(argv)
    root = repo_root()
    test_files = discover_test_files(root, args.tests_dir)

    if not test_files:
        print(f"No test files found under {args.tests_dir!r}.")
        return 1

    print(f"Running {len(test_files)} test files in isolation...")
    failed: list[str] = []

    for test_file in test_files:
        rel = test_file.relative_to(root).as_posix()
        print(f"==> {rel}", flush=True)
        code = run_one(root, test_file, args.marker)
        if code not in OK_EXIT_CODES:
            failed.append(f"{rel} (exit {code})")

    if failed:
        print(f"\nIsolated test failures ({len(failed)}):")
        for entry in failed:
            print(f"  {entry}")
        return 1

    print(f"\nAll {len(test_files)} test files passed in isolation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
