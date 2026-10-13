#!/usr/bin/env python3
"""Core-mode test-scope checker (Phase T.2 / W14 — merge-gate coverage truth).

``make test-core`` (and the ci.yml ``test-core`` job) run the backend with
``-m "not e2e and not integration and not requires_* ..."``. What they
deselect IS the published scope of "core-mode green" — and the T.2 audit
found the publication was WRONG in both directions:

* six service-dependency markers (``requires_aws``, ``requires_clamav``,
  ``requires_gcp``, ``requires_redis``, ``requires_snowflake``,
  ``odh_inference``) were IN USE by 9 test files but ABSENT from the
  expression — those tests silently RAN in core mode;
* two expression terms (``requires_fuseki``, ``requires_stripe``) had
  zero users — stale scope claims.

This checker pins the truth machine-checkably, in both directions:

1. every deselection-family marker actually in use in ``hub/apps`` test
   files must appear in the expression (no silent runs);
2. every ``not X`` expression term must be a family marker actually in
   use (no stale terms);
3. the Makefile.core target and the ci.yml job must deselect the SAME
   set (W2.1 single-source class).

It also PRINTS the canonical coverage numbers (marked-file counts +
commits ahead of main) so the published record is generated, not recited.

Exit 0 clean, 1 violations.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE_CORE = REPO_ROOT / "Makefile.core"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUBLIC_CI_CORE_YML = (
    REPO_ROOT / "scripts" / "publish_public_overlay" / ".github" / "workflows" / "ci-core.yml"
)

# Markers whose presence means the test needs the FULL stack (or a paid
# service) and must be deselected from the core job. This is the
# deselection family the -m expression is checked against.
DESELECTION_FAMILY = frozenset(
    {
        "integration",
        "e2e",
        "benchmark",
        "performance",
        "network",
        "requires_aws",
        "requires_clamav",
        "requires_fuseki",
        "requires_gcp",
        "requires_prefect",
        "requires_redis",
        "requires_services",
        "requires_snowflake",
        "requires_stripe",
        "odh_inference",
    }
)

_MARKER_RE = re.compile(r"pytest\.mark\.([a-z_0-9]+)")
_M_EXPR_RE = re.compile(r"-m\s+(?:\"([^\"]*)\"|'([^']*)')")


def parse_deselected_terms(expression: str) -> set[str]:
    """Return the marker names a ``-m "not a and not b ..."`` expression
    deselects. Terms that are not ``not <marker>`` are ignored."""
    # Accept the full ``-m "..."`` form (as extracted from the Makefile /
    # workflow) or the bare quoted expression.
    body = expression.strip()
    body = re.sub(r"^-m\s*", "", body)
    body = body.strip().strip('"').strip("'")
    terms: set[str] = set()
    for raw_part in re.split(r"\s+and\s+", body):
        part = raw_part.strip()
        if part.startswith("not "):
            marker = part[4:].strip()
            if marker and marker not in ("or", "and"):
                terms.add(marker)
    return terms


def markers_in_use(files: dict[str, str]) -> set[str]:
    """All pytest markers referenced by the given {path: source} test files."""
    used: set[str] = set()
    for source in files.values():
        used.update(m.group(1) for m in _MARKER_RE.finditer(source))
    return used


def _extract_expression_from_makefile(source: str) -> str:
    match = _M_EXPR_RE.search(source)
    return match.group(0) if match else ""


def _extract_expression_from_workflow(source: str) -> str:
    """The -m expression of the test-core JOB (the workflow carries other
    -m usages — e.g. ``-m rls`` — which must not be confused with it)."""
    match = re.search(r"^\s{2}test-core:.*?(?=^\s{2}\S|\Z)", source, flags=re.M | re.S)
    if not match:
        return ""
    job_block = match.group(0)
    m_expr = _M_EXPR_RE.search(job_block)
    return m_expr.group(0) if m_expr else ""


def collect_scope_violations(sources: dict[str, str], files: dict[str, str]) -> list[str]:
    """Check the scope publications against the marker inventory."""
    violations: list[str] = []

    # Extract every source's expression (Makefile + workflow forms share
    # the same regex shape; the public overlay workflow uses the same
    # run-block layout as ci.yml).
    expressions: dict[str, str] = {}
    for name, source in sources.items():
        if name == "Makefile.core":
            expressions[name] = _extract_expression_from_makefile(source)
        else:
            expressions[name] = _extract_expression_from_workflow(source)
    for name, expr in expressions.items():
        if not expr:
            violations.append(f"{name} has no -m expression")

    term_sets = {name: parse_deselected_terms(expr) for name, expr in expressions.items() if expr}
    reference = next(iter(term_sets.values()), set())
    for name, terms in term_sets.items():
        if terms != reference:
            violations.append(
                f"{name} deselects a DIFFERENT marker set than the others: "
                f"only-here={sorted(terms - reference)}, missing={sorted(reference - terms)}"
            )

    used = markers_in_use(files)
    expression_terms: set[str] = set().union(*term_sets.values()) if term_sets else set()

    # Direction 1: every family marker in use must be deselected.
    for marker in sorted(used & DESELECTION_FAMILY - expression_terms):
        violations.append(
            f"marker '{marker}' is in use but NOT deselected by the -m "
            "expression — its tests silently run in core mode"
        )

    # Direction 2: every expression term must be a family marker in use.
    for term in sorted(expression_terms):
        if term not in DESELECTION_FAMILY:
            violations.append(f"expression term '{term}' is not a deselection-family marker")
        elif term not in used:
            violations.append(f"expression term '{term}' deselects no test — stale scope claim")

    return violations


def real_marker_files() -> dict[str, str]:
    """{relative path: source} of every hub/apps test file."""
    files: dict[str, str] = {}
    for path in (REPO_ROOT / "hub" / "apps").rglob("test_*.py"):
        if "/migrations/" in str(path):
            continue
        try:
            files[str(path.relative_to(REPO_ROOT))] = path.read_text(
                encoding="utf-8", errors="ignore"
            )
        except OSError:
            continue
    return files


def load_real_sources() -> dict[str, str]:
    sources = {
        "Makefile.core": MAKEFILE_CORE.read_text(encoding="utf-8"),
        "ci.yml": CI_YML.read_text(encoding="utf-8"),
    }
    # The public overlay's ci-core.yml is a THIRD copy of the scope — it
    # ships with the OSS tree and drifted once already.
    if PUBLIC_CI_CORE_YML.exists():
        sources["public ci-core.yml"] = PUBLIC_CI_CORE_YML.read_text(encoding="utf-8")
    return sources


def _report_counts(files: dict[str, str]) -> None:
    used = markers_in_use(files)
    family_used = used & DESELECTION_FAMILY
    per_marker = {
        marker: sum(1 for source in files.values() if f"pytest.mark.{marker}" in source)
        for marker in sorted(family_used)
    }
    core_gated = sum(1 for source in files.values() if "HUB_CORE_ONLY" in source)
    print("CORE-SCOPE: deselection-family marker usage (hub/apps test files):")
    for marker, count in per_marker.items():
        print(f"  {marker}: {count}")
    print(f"  HUB_CORE_ONLY-gated files: {core_gated}")
    commits = subprocess.run(
        ["git", "rev-list", "--count", "main..HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if commits.returncode == 0 and commits.stdout.strip():
        print(f"  commits ahead of main: {commits.stdout.strip()}")


def main() -> int:
    sources = load_real_sources()
    files = real_marker_files()
    violations = collect_scope_violations(sources, files)
    if violations:
        print(f"CORE-SCOPE: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("CORE-SCOPE: clean — the -m expression matches the marker inventory.")
    _report_counts(files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
