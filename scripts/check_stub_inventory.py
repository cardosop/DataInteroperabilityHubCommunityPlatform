#!/usr/bin/env python3
"""
GATE-61 — Stub/placeholder inventory (oss-release-remediation W12.7).

Every shipped stub/placeholder class has a tracked disposition in
``docs/audits/stub-inventory-2026.md`` (the human evidence) mirrored by
``scripts/stub_inventory_registry.json`` (the machine-checkable rows):

  * ``wired``   — the real implementation shipped; the row cites an
    evidence file that EXISTS and contains the row's marker pattern.
  * ``deleted`` — removed; the row's marker pattern must be ABSENT from
    non-test code (a reintroduction flips the gate RED), or its named
    file must not exist.
  * ``ticket-deferred`` — annotated at the site with ``TICKET=<id>
    EXPIRES=<date>`` (GATE-40-compatible); the row carries those fields
    and the expiry must not have passed.

The gate fails on: an untriaged status, a missing evidence file, a
marker mismatch, a doc that doesn't carry a registry row's ID, or an
expired ticket — zero untriaged rows, honest by construction.

Usage:
  python scripts/check_stub_inventory.py --check
  --root PATH   scan a different tree (planted pins / built public tree)
"""

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_DOC = "docs/audits/stub-inventory-2026.md"
DEFAULT_REGISTRY = "scripts/stub_inventory_registry.json"

# The absent-marker scan runs over non-test hub + frontend source.
_ABSENT_GLOBS = ("hub/**/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx")

_TEST_HINT = ("tests/", ".test.", ".spec.", "__pycache__")


def _is_test_path(rel: str) -> bool:
    return any(hint in rel for hint in _TEST_HINT)


def _scan_absent(root: Path, pattern: str) -> list[str]:
    """Every non-test file whose text matches *pattern* (a regex)."""
    hits = []
    for glob in _ABSENT_GLOBS:
        for path in sorted(root.glob(glob)):
            rel = str(path.relative_to(root))
            if _is_test_path(rel):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(pattern, text):
                hits.append(rel)
    return hits


def check(root: Path, doc_path: Path, registry_path: Path) -> int:
    if not registry_path.is_file():
        print(f"stub inventory: registry missing at {registry_path}")
        return 1
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        rows = payload["rows"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"stub inventory: registry unreadable — {exc}")
        return 1

    doc_text = (
        doc_path.read_text(encoding="utf-8", errors="replace")
        if doc_path.is_file()
        else ""
    )

    violations: list[str] = []
    counts = {"wired": 0, "deleted": 0, "ticket-deferred": 0}
    seen: set[str] = set()

    for row in rows:
        row_id = row.get("id")
        if not row_id:
            violations.append("registry row without an 'id'")
            continue
        if row_id in seen:
            violations.append(f"duplicate registry row {row_id}")
            continue
        seen.add(row_id)

        if row_id not in doc_text:
            violations.append(
                f"{row_id}: the tracked doc {doc_path} does not carry the "
                "row — doc and registry must stay in sync"
            )

        status = row.get("status")
        if status not in counts:
            violations.append(
                f"{row_id}: untriaged status {status!r} — use wired / "
                "deleted / ticket-deferred"
            )
            continue
        counts[status] += 1

        if status == "wired":
            marker = row.get("present_marker")
            evidence = row.get("evidence")
            evidence_path = root / evidence if evidence else None
            if not evidence or not evidence_path.is_file():
                violations.append(
                    f"{row_id}: wired row cites missing evidence file " f"{evidence}"
                )
            elif marker and not re.search(
                marker, evidence_path.read_text(encoding="utf-8", errors="replace")
            ):
                violations.append(
                    f"{row_id}: evidence {evidence} does not contain the "
                    f"wired marker {marker!r}"
                )
        elif status == "deleted":
            marker = row.get("absent_marker")
            absent_file = row.get("absent_file")
            if marker:
                hits = _scan_absent(root, marker)
                if hits:
                    violations.append(
                        f"{row_id}: deleted stub REINTRODUCED — marker "
                        f"{marker!r} matches {hits[0]}"
                    )
            if absent_file and (root / absent_file).is_file():
                violations.append(
                    f"{row_id}: deleted artifact {absent_file} still " "exists"
                )
        else:  # ticket-deferred
            ticket = row.get("ticket")
            expires = row.get("expires")
            if not ticket or not expires:
                violations.append(
                    f"{row_id}: ticket-deferred rows need 'ticket' and "
                    "'expires' (GATE-40-compatible)"
                )
            else:
                try:
                    expiry = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=UTC)
                except ValueError:
                    violations.append(f"{row_id}: bad EXPIRES format {expires!r}")
                else:
                    if expiry.date() < datetime.now(UTC).date():
                        violations.append(
                            f"{row_id}: deferred ticket {ticket} EXPIRED "
                            f"on {expires} — resolve the stub"
                        )
            marker = row.get("present_marker")
            evidence = row.get("evidence")
            evidence_path = root / evidence if evidence else None
            if not evidence or not evidence_path.is_file():
                violations.append(
                    f"{row_id}: deferred row cites missing site {evidence}"
                )
            elif marker and not re.search(
                marker, evidence_path.read_text(encoding="utf-8", errors="replace")
            ):
                violations.append(
                    f"{row_id}: site {evidence} lacks the TICKET= " "annotation"
                )

    if not doc_text:
        violations.append(
            f"the tracked doc {doc_path} is missing — W12.7 requires the "
            "committed inventory"
        )

    if violations:
        print(f"stub inventory: {len(violations)} violation(s):")
        for v in violations:
            print(f"  - {v}")
        return 1

    print(
        "stub inventory clean: "
        f"{counts['wired']} wired, {counts['deleted']} deleted, "
        f"{counts['ticket-deferred']} ticket-deferred "
        f"({len(rows)} rows, zero untriaged)"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="GATE-61 stub inventory")
    parser.add_argument("--check", action="store_true", help="blocking gate")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args()

    root = args.root
    doc_path = root / DEFAULT_DOC
    registry_path = root / DEFAULT_REGISTRY

    if args.check:
        return check(root, doc_path, registry_path)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
