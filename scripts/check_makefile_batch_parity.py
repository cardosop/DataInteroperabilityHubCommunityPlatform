#!/usr/bin/env python3
"""Makefile batch-coverage + CI-parity gate (GATE-43, close-test-coverage-gaps task 0.2).

Pins two contracts that previously drifted silently:

1. **Batch-coverage completeness** — every defined ``test-batch-*`` target
   must be reachable from ``test-batch-all`` through the ``$(MAKE)``
   invocation graph, unless it sits in ``EXCLUDED_FROM_BATCH_ALL`` with a
   reason. Reachability follows the graph transitively, so umbrella
   targets (``test-batch-1`` → ``1-1``…``1-9``) count. A pure fan-out
   umbrella (a target whose recipe holds ONLY ``$(MAKE)`` lines) is
   itself covered when every child it invokes is covered. The task-0.2
   incident class: ``6-7``…``6-21``, ``7-7``…``7-12`` and ``12-1``…``12-3``
   were defined as targets but never invoked by ``test-batch-all``, so
   ``make test-batch-all`` silently skipped roughly a third of the suite.

2. **CI-Makefile parity comment** — the "CI-Makefile parity note" block's
   numbers (CI jobs, reusable workflows, CI-parity targets, batch targets)
   are DERIVED from the tree, not recited:
   * CI jobs = jobs in ``ci.yml`` + ``e2e.yml`` + every workflow whose
     ``on`` map carries ``workflow_call`` (the reusable set);
   * CI-parity targets = ``test-ci`` umbrella + every ``test-ci-*``;
   * batch targets = every ``test-batch-*`` definition minus
     ``test-batch-all`` itself.

   The block must state them in the fixed format this checker parses.

Exit 0 clean, 1 violations.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = REPO_ROOT / "Makefile"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

BATCH_ALL = "test-batch-all"

# Batch targets intentionally OUT of test-batch-all. Every entry must
# carry a reason; a stale entry (target no longer defined) is a violation
# in the same way a missing coverage edge is.
EXCLUDED_FROM_BATCH_ALL: dict[str, str] = {
    # Alternate per-file splits of the CLI suite for iterate-and-fix
    # cycles. test-batch-9-3 (which test-batch-all DOES run) executes the
    # whole CLI suite — adding the splits would double-run the same files.
    "test-batch-9-3a": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    "test-batch-9-3b": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    "test-batch-9-3c": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    "test-batch-9-3d": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    "test-batch-9-3e": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    "test-batch-9-3f": "CLI per-file iteration split; test-batch-9-3 in test-batch-all already runs the CLI suite",
    # ClamAV-profile variant: starts the clamav-test docker profile and
    # live-scanner envs; standard virus-scan coverage runs via
    # test-batch-1-6 in test-batch-all.
    "test-batch-1-6-clamav": "ClamAV-profile variant (live scanner + clamav-test profile); test-batch-1-6 covers the standard virus-scan suite",
    # Explicit proof-of-concept target (tests/integration/test_kafka_rabbitmq_poc.py);
    # not part of the standard suite sequence.
    "test-batch-10-2f-poc": "explicit POC target, not part of the standard suite",
    # close-test-coverage-gaps task 0.4 — the DATABRICKS_E2E=1-gated live
    # sandbox E2E wrapper runs out-of-band (an operator arms the gate),
    # never as part of the every-push test-batch-all sequence.
    "test-batch-13-8": "DATABRICKS_E2E=1-gated live sandbox E2E; out of test-batch-all by design (task 0.4)",
}

TARGET_LINE_RE = re.compile(r"^([a-z0-9][a-z0-9_-]*):")
INVOKE_RE = re.compile(r"(?:\(MAKE\)|\{MAKE\})\s+([a-z0-9][a-z0-9_-]+)")
# NB: no word boundary after the group — ')' is a non-word char, so a
# '\b' there would never match the following space.
FANOUT_LINE_RE = re.compile(r"^[ \t]*[-@]*\$(?:\(MAKE\)|\{MAKE\})")


def parse_makefile(text: str) -> dict[str, list[str]]:
    """Parse Makefile text into {target: recipe lines}.

    A target line is a non-indented, non-comment line whose first token
    matches a plain make target name followed by ':'. Recipe lines are
    the following tab-indented lines (continuation lines included).
    """
    targets: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line and not line.startswith(("\t", " ", "#")):
            m = TARGET_LINE_RE.match(line)
            if m:
                name = m.group(1)
                current = name
                targets[name] = []
            continue
        if line.startswith("\t") and current is not None:
            targets[current].append(line)
    return targets


def invoked_targets(recipes: list[str]) -> set[str]:
    """Targets a recipe invokes via $(MAKE) / ${MAKE}."""
    found: set[str] = set()
    for line in recipes:
        found.update(INVOKE_RE.findall(line))
    return found


def is_fanout(recipes: list[str]) -> bool:
    """True when the recipe consists ONLY of $(MAKE) lines — an umbrella."""
    return bool(recipes) and all(FANOUT_LINE_RE.match(line) for line in recipes)


def batch_coverage_violations(text: str, excluded: dict[str, str] | None = None) -> list[str]:
    """Every test-batch-* target (minus exclusions) reachable from test-batch-all.

    ``excluded`` defaults to the module-level allowlist; the unit pins pass
    their own so the fixtures stay hermetic.
    """
    excluded = EXCLUDED_FROM_BATCH_ALL if excluded is None else excluded
    targets = parse_makefile(text)
    graph = {t: invoked_targets(recipes) for t, recipes in targets.items()}

    violations: list[str] = []
    if BATCH_ALL not in graph:
        return [f"{BATCH_ALL}: target not defined in Makefile"]

    reachable: set[str] = set()
    stack = list(graph[BATCH_ALL])
    while stack:
        t = stack.pop()
        if t not in reachable:
            reachable.add(t)
            stack.extend(graph.get(t, ()))

    memo: dict[str, bool] = {}

    def covered(t: str) -> bool:
        if t in memo:
            return memo[t]
        if t in reachable:
            memo[t] = True
            return True
        kids = graph.get(t, set())
        if is_fanout(targets.get(t, [])) and kids and all(covered(k) for k in kids):
            memo[t] = True
            return True
        memo[t] = False
        return False

    for t in sorted(graph):
        if not t.startswith("test-batch-") or t == BATCH_ALL:
            continue
        if t in excluded:
            continue
        if not covered(t):
            violations.append(
                f"{t}: defined but not reachable from {BATCH_ALL} "
                "(not invoked by test-batch-all and not a covered fan-out umbrella)"
            )

    for t in sorted(excluded):
        if t not in graph:
            violations.append(f"{t}: listed in EXCLUDED_FROM_BATCH_ALL but not defined in Makefile")

    return violations


def ci_job_counts() -> tuple[int, int]:
    """(total CI jobs, reusable workflow count).

    Scope mirrors the parity comment's parenthetical: ci.yml + e2e.yml +
    every workflow whose trigger map carries ``workflow_call``.
    """
    jobs = 0
    reusable = 0
    for f in sorted(WORKFLOWS_DIR.glob("*.yml")):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        on = doc.get("on") or doc.get(True) or {}
        is_wc = isinstance(on, dict) and "workflow_call" in on
        if f.name in ("ci.yml", "e2e.yml") or is_wc:
            jobs += len(doc.get("jobs") or {})
        if is_wc:
            reusable += 1
    return jobs, reusable


def makefile_target_counts(text: str) -> tuple[int, int]:
    """(batch targets, CI-parity targets) as the parity comment defines them."""
    targets = parse_makefile(text)
    batch = sum(1 for t in targets if t.startswith("test-batch-") and t != BATCH_ALL)
    parity = (1 if "test-ci" in targets else 0) + sum(
        1 for t in targets if t.startswith("test-ci-")
    )
    return batch, parity


def parity_comment_violations(
    text: str, jobs: int, reusable: int, batch: int, parity: int
) -> list[str]:
    """The CI-Makefile parity note block must state the DERIVED numbers.

    The derived values are passed in so the unit pins stay hermetic;
    ``main()`` computes them from the tree (``ci_job_counts`` +
    ``makefile_target_counts``).
    """
    violations: list[str] = []
    block_m = re.search(r"# ── CI-Makefile parity note.*?(?=\n# ── [A-Za-z])", text, re.S)
    if not block_m:
        return ["CI-Makefile parity note comment block missing or malformed"]
    block = block_m.group(0)

    jobs_m = re.search(
        r"CI has (\d+) jobs \(ci\.yml \+ e2e\.yml \+ (\d+) reusable workflows\)",
        block,
    )
    if not jobs_m:
        violations.append(
            'parity note: expected "CI has {jobs} jobs (ci.yml + e2e.yml + '
            f'{reusable} reusable workflows)" — not found; derived jobs={jobs}'
        )
    else:
        if int(jobs_m.group(1)) != jobs:
            violations.append(f"parity note: states {jobs_m.group(1)} CI jobs; derived {jobs}")
        if int(jobs_m.group(2)) != reusable:
            violations.append(
                f"parity note: states {jobs_m.group(2)} reusable workflows; derived {reusable}"
            )

    parity_m = re.search(r"provides (\d+) CI-parity targets \+ (\d+) batch targets", block)
    if not parity_m:
        violations.append(
            'parity note: expected "provides {parity} CI-parity targets + '
            f'{batch} batch targets" — not found; derived parity={parity}, batch={batch}'
        )
    else:
        if int(parity_m.group(1)) != parity:
            violations.append(
                f"parity note: states {parity_m.group(1)} CI-parity targets; derived {parity}"
            )
        if int(parity_m.group(2)) != batch:
            violations.append(
                f"parity note: states {parity_m.group(2)} batch targets; derived {batch}"
            )

    return violations


def main() -> int:
    text = MAKEFILE.read_text(encoding="utf-8")
    jobs, reusable = ci_job_counts()
    batch, parity = makefile_target_counts(text)
    violations = batch_coverage_violations(text) + parity_comment_violations(
        text, jobs, reusable, batch, parity
    )
    if violations:
        print("GATE-43 (makefile batch parity): violations found")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        "GATE-43 (makefile batch parity): clean — "
        f"all {batch} batch targets covered (excluded: {len(EXCLUDED_FROM_BATCH_ALL)}); "
        f"parity note {jobs}/{reusable} CI, {parity} parity, {batch} batch"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
