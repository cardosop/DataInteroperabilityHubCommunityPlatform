#!/usr/bin/env python3
"""
Generate test batch files with ~100-200 tests per batch (count-based).

Use with docs/GAP_FIX_AND_FULL_TEST_EXECUTION_PLAN.md: collect all test node IDs,
split into chunks of --size, write batch files so a runner can invoke pytest
with the nodes in each file.

Usage:
  # From repo root, with venv active and DJANGO_SETTINGS_MODULE=hub.settings:
  python scripts/generate_test_batches_by_count.py [--size=150] [--output-dir=test_batches]

  # Then run a batch (example):
  pytest $(cat test_batches/batch_001.txt) -v --reuse-db --timeout=300 --tb=short

Requires: pytest, Django env (so collect-only can load hub).
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def collect_node_ids(repo_root: Path, paths: list[str], env: dict) -> list[str]:
    """Run pytest --collect-only and parse node ids from output."""
    node_ids = []
    # Pytest --collect-only prints a tree; node ids appear as "path/to/file.py::test_func" or "path::Class::method"
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *paths,
        "--collect-only",
        "--no-header",
        "-q",
    ]
    try:
        r = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=repo_root,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(
            "Error: pytest --collect-only timed out (300s). Narrow --paths or run in container.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Parse: lines containing "::" and test-like names (test_ or Test)
    for line in (r.stdout or "").splitlines() + (r.stderr or "").splitlines():
        s = line.strip()
        if "::" in s and re.search(r"(test_|Test)", s) and not s.startswith("<"):
            if ".py" in s and s not in node_ids:
                # Take first token if there's extra text (e.g. "path::test_foo PASSED")
                node_id = s.split()[0] if s.split() else s
                if node_id not in node_ids:
                    node_ids.append(node_id)

    # Fallback: collect per path to avoid huge single run
    if not node_ids:
        for p in paths:
            path_dir = repo_root / p.rstrip("/")
            if not path_dir.exists():
                continue
            try:
                r2 = subprocess.run(
                    [sys.executable, "-m", "pytest", p, "--collect-only", "-q", "--no-header"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    cwd=repo_root,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                continue
            for line in (r2.stdout or "").splitlines() + (r2.stderr or "").splitlines():
                s = line.strip()
                if "::" in s and re.search(r"(test_|Test)", s) and ".py" in s and s not in node_ids:
                    node_ids.append(s)

    return node_ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate test batches by test count (100-200 per batch)."
    )
    parser.add_argument(
        "--size", type=int, default=150, help="Target number of tests per batch (default 150)."
    )
    parser.add_argument(
        "--output-dir", type=str, default="test_batches", help="Output directory for batch files."
    )
    parser.add_argument(
        "--paths",
        type=str,
        nargs="*",
        default=["hub/apps/", "tests/unit/", "tests/integration/", "tests/e2e/"],
        help="Paths to collect tests from.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only print total and batch count.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    env["PYTHONPATH"] = str(repo_root)

    node_ids = collect_node_ids(repo_root, args.paths, env)
    if not node_ids:
        print(
            "Warning: No test node IDs collected. Check paths and DJANGO_SETTINGS_MODULE.",
            file=sys.stderr,
        )
        return 1

    total = len(node_ids)
    n_batches = (total + args.size - 1) // args.size
    print(f"Total tests collected: {total}")
    print(f"Batch size: {args.size}")
    print(f"Number of batches: {n_batches}")

    if args.dry_run:
        return 0

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in range(n_batches):
        start = i * args.size
        end = min(start + args.size, total)
        batch_nodes = node_ids[start:end]
        batch_file = out_dir / f"batch_{i + 1:03d}.txt"
        batch_file.write_text("\n".join(batch_nodes) + "\n")
        print(f"  Wrote {batch_file} ({len(batch_nodes)} tests)")

    (out_dir / "README.txt").write_text(
        f"Generated by scripts/generate_test_batches_by_count.py --size={args.size}\n"
        f"Total: {total} tests, {n_batches} batches.\n"
        f"Run a batch: pytest $(cat {args.output_dir}/batch_001.txt) -v --reuse-db --timeout=300 --tb=short\n"
    )
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
