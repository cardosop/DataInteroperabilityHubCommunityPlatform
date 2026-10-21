#!/usr/bin/env python3
"""Phase 2.8 — core-e2e selection drift check (static, CI-safe).

Two assertions on the core-only E2E subset:

(a) SELECTION VALIDITY — every entry in ``frontend/e2e/core-only.txt`` is a
    non-empty substring that matches AT LEAST one Playwright spec title
    (the file's own documented ``--list --grep`` validation, made static so
    it runs in lint CI without the Playwright stack).

(b) PAID EXCLUSION — no entry matches the title of a spec whose surface is
    PAID (derived from ``PAID_ROUTE_CAPABILITIES`` in
    ``frontend/src/app/routes/paidRouteGating.ts``, the same source the
    frontend drift tests use). A new paid journey spec can never leak into
    the core e2e run.

Exit 0 clean, 1 on violations.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

CORE_ONLY_LIST = "frontend/e2e/core-only.txt"
PAID_GATING = "frontend/src/app/routes/paidRouteGating.ts"
E2E_DIR = "frontend/e2e"

_TITLE_RE = re.compile(r"test(?:\.describe)?\(\s*['\"]([^'\"]+)['\"]")


def _read_entries(core_only_path: Path) -> list[str]:
    entries: list[str] = []
    for line in core_only_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        entries.append(stripped)
    return entries


def _paid_entries(paid_gating_path: Path) -> list[tuple[str, str]]:
    """(url_prefix, capability) pairs from PAID_ROUTE_CAPABILITIES."""
    source = paid_gating_path.read_text()
    match = re.search(r"PAID_ROUTE_CAPABILITIES[^=]*=\s*\{(.*?)\};", source, re.DOTALL)
    if not match:
        return []
    return re.findall(r"['\"](/[a-z0-9_/-]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", match.group(1))


def _paid_title_terms(entries: list[tuple[str, str]]) -> set[str]:
    """The title-ish words a spec about a paid surface would use.

    Derived from the CAPABILITY VALUES (the semantic source — a path like
    ``/integrations`` maps to ``integrations.marketplace``, so the paid
    signal is "marketplace", NOT "integrations" — the core e2e run has its
    own Jobs/Scheduled/Webhooks integrations specs) plus the non-ambiguous
    prefix segments. A new paid prefix automatically extends the check.
    """
    # Segments that name CORE surfaces too — using them would flag the
    # core-only integrations specs as paid.
    AMBIGUOUS_SEGMENTS = {"integrations"}
    terms: set[str] = set()
    for prefix, capability in entries:
        # Only the capability LEAF is the semantic paid signal —
        # ``integrations.marketplace`` means "marketplace", and its first
        # segment would flag the core Jobs/Scheduled/Webhooks specs.
        leaf = capability.split(".")[-1].replace("_", " ").title()
        terms.add(leaf)
        for segment in prefix.strip("/").split("/"):
            if segment in {"settings", "admin"} | AMBIGUOUS_SEGMENTS:
                continue
            terms.add(segment)
            terms.add(segment.replace("-", " ").title())
            terms.add(segment.replace("_", " ").title())
    return terms


def _spec_titles(e2e_dir: Path) -> list[str]:
    titles: list[str] = []
    for path in e2e_dir.rglob("*.spec.ts"):
        if "node_modules" in path.parts:
            continue
        for match in _TITLE_RE.finditer(path.read_text()):
            titles.append(match.group(1))
    return titles


def collect_violations(root: Path) -> list[str]:
    core_only = root / CORE_ONLY_LIST
    if not core_only.exists():
        return [f"{CORE_ONLY_LIST}: missing"]

    entries = _read_entries(core_only)
    titles = _spec_titles(root / E2E_DIR)
    paid_terms = _paid_title_terms(_paid_entries(root / PAID_GATING))
    paid_titles = [
        title for title in titles if any(term.lower() in title.lower() for term in paid_terms)
    ]

    violations: list[str] = []
    for entry in entries:
        matched = [title for title in titles if entry in title]
        if not matched:
            violations.append(
                f"{CORE_ONLY_LIST}: entry {entry!r} matches NO spec title "
                "(the --list --grep validation would exclude it)"
            )
        leaking = [title for title in paid_titles if entry in title]
        if leaking:
            violations.append(
                f"{CORE_ONLY_LIST}: entry {entry!r} matches PAID-surface spec "
                f"title(s) {leaking} — a paid journey leaked into the core "
                "e2e selection"
            )
    return sorted(violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Core-e2e selection drift check (2.8)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    violations = collect_violations(args.root)
    if violations:
        print(f"CORE-E2E-SELECTION: {len(violations)} violation(s):")
        for entry in violations:
            print(f"  {entry}")
        return 1
    print("CORE-E2E-SELECTION: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
