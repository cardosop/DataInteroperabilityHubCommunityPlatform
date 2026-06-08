#!/usr/bin/env python3
"""
TR.Q.3 — CI lint: prevent future markdown report accumulation in test directories.

Scans ``tests/`` for ``.md`` files (excluding ``README.md``) and flags them.
Test directories should only contain test code, not audit/report documents.

Usage:
    python scripts/lint_test_dir_markdown.py
    python scripts/lint_test_dir_markdown.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TEST_DIRS = ["tests/integration", "tests/e2e"]


def run_lint(repo_root: Path, json_output: bool = False) -> int:
    violations = []
    for test_dir in TEST_DIRS:
        dir_path = repo_root / test_dir
        if not dir_path.is_dir():
            continue
        for md_file in dir_path.rglob("*.md"):
            if md_file.name == "README.md":
                continue
            violations.append(str(md_file.relative_to(repo_root)))

    if json_output:
        print(json.dumps({
            "status": "fail" if violations else "ok",
            "violations": violations,
        }, indent=2))
    else:
        if violations:
            print(f"Markdown files in test directories: {len(violations)}")
            for v in violations:
                print(f"  - {v}")
            print("\nMove report files to docs/audits/test-reports/ instead.")
        else:
            print("OK: No markdown report files in test directories.")

    return 1 if violations else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.Q.3 — Test dir markdown lint")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return run_lint(args.repo_root, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
