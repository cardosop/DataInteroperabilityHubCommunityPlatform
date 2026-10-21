#!/usr/bin/env python3
"""
close-test-coverage-gaps 0.5 — local-run Redis plumbing gate.

Root cause: the contracts Redis-touching tests (ODPS rate limiting,
ref-resolver caching, cache invalidation tasks, concurrent-API) skip on
HOST-side runs because the recipes never set ``REDIS_CACHE_URL`` — the
settings default resolves to ``redis://localhost:6379/0`` (the dev-stack
cache, usually not the test one) and the pub/client code falls back
there, so the tests connection-refuse and skip. The canonical plumbing
is the test stack's cache Redis published on the host:
``REDIS_CACHE_URL=redis://localhost:6479/0`` (precedent
``test-batch-12-4``; host port docker-compose.test.yml). In-container
batch recipes already inherit the compose env — they need nothing.

This gate enforces the plumbing on the local-run surfaces:

1. The canonical host-side recipe docs (their bash env blocks) MUST set
   ``REDIS_CACHE_URL=redis://localhost:6479/0``.
2. Any Makefile recipe that lists a contracts Redis test file AND runs
   it locally (no ``docker`` in the recipe) MUST carry the same env var.

Exit 0 on clean, 1 with the offending file/recipe list.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
CONTRACTS_TESTS_DIR = REPO_ROOT / "hub" / "apps" / "contracts" / "tests"

PLUMBING = "REDIS_CACHE_URL=redis://localhost:6479/0"

# Canonical host-side run recipes — the docs whose bash env blocks are the
# local-run contract (HOST_SIDE_VERIFICATION.md is the authoritative one;
# host-env-matrix.md documents the same block; LOCAL_FULL_TEST_SWEEP.md
# carries the sweep variant).
RECIPE_DOCS: tuple[Path, ...] = (
    REPO_ROOT / "docs" / "runbooks" / "HOST_SIDE_VERIFICATION.md",
    REPO_ROOT / "docs" / "test-infrastructure" / "host-env-matrix.md",
    REPO_ROOT / "docs" / "runbooks" / "LOCAL_FULL_TEST_SWEEP.md",
)


def redis_touching_contracts_tests() -> set[str]:
    """Contract test files that reference redis (the skip-risk surface)."""
    hits: set[str] = set()
    for path in CONTRACTS_TESTS_DIR.glob("*.py"):
        try:
            text = path.read_text()
        except OSError:
            continue
        if "redis" in text.lower():
            hits.add(f"hub/apps/contracts/tests/{path.name}")
    return hits


def check_docs(docs: tuple[Path, ...] = RECIPE_DOCS) -> list[str]:
    """Return the recipe docs whose env blocks lack the plumbing line."""
    missing: list[str] = []
    for doc in docs:
        try:
            text = doc.read_text()
        except OSError:
            missing.append(f"{doc} — unreadable")
            continue
        if PLUMBING not in text:
            missing.append(str(doc))
    return missing


def check_makefile_local_recipes(makefile_text: str, redis_tests: set[str]) -> list[str]:
    """Return Makefile targets that run contracts Redis tests locally
    (no docker) without the plumbing env var."""
    offenders: list[str] = []
    # Split into target blocks: lines starting with a target name at
    # column 0 followed by ':'.
    current_target: str | None = None
    block: list[str] = []
    for raw_line in makefile_text.splitlines():
        m = re.match(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)\s*:(?!=)", raw_line)
        if m and not raw_line.startswith((".PHONY", "\t", " ")):
            if current_target is not None:
                _judge_block(current_target, block, redis_tests, offenders)
            current_target = m.group(1)
            block = [raw_line]
            continue
        if current_target is not None:
            block.append(raw_line)
    if current_target is not None:
        _judge_block(current_target, block, redis_tests, offenders)
    return offenders


def _judge_block(
    target: str, block: list[str], redis_tests: set[str], offenders: list[str]
) -> None:
    text = "\n".join(block)
    if not any(test_path in text for test_path in redis_tests):
        return  # doesn't touch contracts Redis tests
    if re.search(r"\bdocker\b", text):
        return  # in-container — compose env provides the plumbing
    if PLUMBING not in text:
        offenders.append(target)


def main() -> int:
    problems: list[str] = []
    problems.extend(check_docs())
    redis_tests = redis_touching_contracts_tests()
    problems.extend(check_makefile_local_recipes(MAKEFILE.read_text(), redis_tests))

    if problems:
        print(
            f"LOCAL-REDIS-PLUMBING gate: {len(problems)} local-run surface(s) missing {PLUMBING}:"
        )
        for problem in problems:
            print(f"  {problem}")
        print(f"  ({len(redis_tests)} contracts Redis-touching test file(s) scanned)")
        return 1

    print(
        f"LOCAL-REDIS-PLUMBING gate: PASSED — {len(redis_tests)} contracts "
        "Redis tests covered by local-run plumbing."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
