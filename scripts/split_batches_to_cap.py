#!/usr/bin/env python3
"""
Generate batch_definitions.txt with every batch ≤ max_tests (default 200).
Reads current batches from run_phase_12a_batched.sh --list-batches, gets count per batch
via pytest --collect-only in api-service-test; splits any batch over the cap by path or by file.
Output: scripts/batch_definitions.txt (one line per batch: Name|path1|path2|...).

Usage:
  From repo root, with test stack up (api-service-test running):
  python3 scripts/split_batches_to_cap.py [--max 200] [--output scripts/batch_definitions.txt]

Requires: docker compose -f docker-compose.test.yml, api-service-test running.
"""

from __future__ import annotations

import argparse
import glob
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = "docker-compose.test.yml"
API_SVC = "api-service-test"


def run_pytest_collect(paths: list[str], repo_root: Path, compose_cmd: list[str]) -> int:
    """Run pytest --collect-only -q for paths in container; return test count."""
    # Quote each path for safe shell passing (spaces/special chars)
    path_args = " ".join(shlex.quote(p) for p in paths)
    cmd = compose_cmd + [
        "exec",
        "-T",
        API_SVC,
        "bash",
        "-c",
        "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings "
        f"python -m pytest {path_args} --collect-only -q 2>&1",
    ]
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        return 0
    m = re.search(r"(\d+)\s+(?:tests?|items)\s+collected", out)
    return int(m.group(1)) if m else 0


def _split_path_by_file(
    single_path: str,
    name: str,
    label: str,
    max_tests: int,
    repo_root: Path,
    compose_cmd: list[str],
) -> list[str]:
    """Split a single path into batches of files each ≤ max_tests. Returns list of 'Name|path1|path2|...'."""
    files = list_test_files(single_path, repo_root)
    if not files:
        return [f"{name} - {label}|{single_path}"]
    file_counts: list[tuple[str, int]] = []
    for f in files:
        c = run_pytest_collect([f], repo_root, compose_cmd)
        file_counts.append((f, c))
    batches: list[str] = []
    current: list[str] = []
    current_sum = 0
    batch_idx = 0
    for f, c in file_counts:
        if current_sum + c > max_tests and current:
            batch_idx += 1
            batches.append(f"{name} - {label} {batch_idx}|{'|'.join(current)}")
            current = []
            current_sum = 0
        current.append(f)
        current_sum += c
    if current:
        batch_idx += 1
        batches.append(f"{name} - {label} {batch_idx}|{'|'.join(current)}")
    return batches


def list_test_files(path: str, repo_root: Path) -> list[str]:
    """Expand path to list of test .py files (glob or directory)."""
    # Glob pattern (e.g. test_odps_*.py)
    if "*" in path or "?" in path:
        files = sorted(glob.glob(str(repo_root / path)))
        return [str(Path(f).relative_to(repo_root)).replace("\\", "/") for f in files]
    path_obj = repo_root / path.rstrip("/")
    if not path_obj.exists():
        return []
    if path_obj.is_file():
        return [path] if path.endswith(".py") else []
    # Directory: all .py under it
    out = []
    for f in path_obj.rglob("*.py"):
        if f.name.startswith("__"):
            continue
        out.append(str(f.relative_to(repo_root)).replace("\\", "/"))
    return sorted(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate batch_definitions.txt with batches ≤ max tests."
    )
    parser.add_argument("--max", type=int, default=200, help="Max tests per batch (default 200).")
    parser.add_argument(
        "--output", type=str, default="scripts/batch_definitions.txt", help="Output file path."
    )
    parser.add_argument(
        "--compose-file", type=str, default=COMPOSE_FILE, help="Docker Compose file."
    )
    args = parser.parse_args()
    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    compose_cmd = ["docker", "compose", "-f", args.compose_file]

    # Get current batch list from shell script
    result = subprocess.run(
        [str(REPO_ROOT / "scripts" / "run_phase_12a_batched.sh"), "--list-batches"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    lines = [
        l.strip()
        for l in (result.stdout or "").strip().splitlines()
        if l.strip() and l.strip()[0].isdigit()
    ]
    if not lines:
        print(
            "Error: No batch lines from run_phase_12a_batched.sh --list-batches.", file=sys.stderr
        )
        return 1

    new_batches: list[str] = []
    max_tests = args.max

    for line in lines:
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        name = parts[1]
        paths = [p.strip() for p in parts[2:] if p.strip()]
        if not paths:
            continue
        count = run_pytest_collect(paths, REPO_ROOT, compose_cmd)
        if count <= max_tests:
            new_batches.append(f"{name}|{'|'.join(paths)}")
            continue
        # Split
        if len(paths) > 1:
            # Multi-path: one batch per path (or split by file if path still > max_tests)
            for p in paths:
                c = run_pytest_collect([p], REPO_ROOT, compose_cmd)
                label = Path(p.rstrip("/")).parent.name or Path(p).stem
                if c <= max_tests:
                    new_batches.append(f"{name} - {label}|{p}")
                else:
                    # Path still too large; split by file
                    new_batches.extend(
                        _split_path_by_file(p, name, label, max_tests, REPO_ROOT, compose_cmd)
                    )
            continue
        # Single path: split by file
        single_path = paths[0]
        label = Path(single_path.rstrip("/")).parent.name or Path(single_path).stem
        new_batches.extend(
            _split_path_by_file(single_path, name, label, max_tests, REPO_ROOT, compose_cmd)
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(new_batches) + "\n", encoding="utf-8")
    print(f"Wrote {len(new_batches)} batches to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
