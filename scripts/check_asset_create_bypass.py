#!/usr/bin/env python3
"""
Phase 250.1.G — CI gate banning new direct ``Asset.objects.create(...)`` /
``Asset(...)`` callers outside the canonical ``AssetService`` entry point.

Why this exists
---------------
B2-13 audit ([docs/audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md])
catalogued **9 production direct-creation sites** that bypass the Phase
250.1.A fail-closed workflow. Each is a hole in the gate ordering: the
re-sequence (gates BEFORE persistence) only matters if every Asset row
goes through ``AssetService.create_via_workflow(...)``.

This script is the persistent guard: it baselines the 9 known sites
(allowing them while migration is in progress per Phase 250.1.G) and
**fails CI on any NEW direct caller** outside the allow-list.

How it works
------------
1. Walks the AST of every ``hub/apps/**/*.py`` file (excluding tests +
   migrations).
2. For each ``ast.Call`` node, checks whether the callable is
   ``Asset.objects.create`` or a positional ``Asset(...)`` constructor.
3. If yes AND the file is NOT in the allow-list, emits an offence.
4. Allow-list captures the 9 known sites + the canonical
   ``hub/apps/assets/services.py`` entry point + ``hub/apps/assets/models.py``
   (where the model itself lives + factory methods may exist).

The allow-list shrinks as Phase 250.1.G migrates each site through
``AssetService.create_via_workflow(...)``. When all 9 sites are
migrated, the allow-list narrows to the canonical service module only;
new callers are flagged automatically.

Exemption
---------
Lines with ``# pragma: asset-create-direct-allowed`` are exempted (use
sparingly — every exemption is technical debt against the Phase 250.1.A
invariant).

Usage
-----
::

    python scripts/check_asset_create_bypass.py [path...]

Default scan: ``hub/apps``.

Exit codes
----------
* 0 — no new bypass; allow-list-only sites unchanged.
* 1 — new bypass detected; offence printed in ``file:line: <message>`` format.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Allow-list — Phase 250.1.G migration targets.
# ---------------------------------------------------------------------------
#
# Each entry is a (file_path, max_allowed_count) tuple. ``max_allowed_count``
# is the number of direct-create call sites the file is grandfathered for.
# When migration removes a site, decrement the count; when count reaches 0,
# remove the entry from the allow-list (or convert to a hard-zero sentinel).
#
# Source: docs/audit-reports/b2-13-direct-asset-create-callers-2026-05-03.md
_ALLOWLIST: dict[str, int] = {
    # Canonical service module — direct-create is BY DESIGN here; the whole
    # point of AssetService.create_via_workflow() is to hide direct-create
    # behind a gate-aware service entry point.
    "hub/apps/assets/services.py": 99,  # unbounded; service module is allowed.
    # The model module itself MAY use direct-create in factory methods.
    "hub/apps/assets/models.py": 5,
    # Phase 250.1.G migration targets — count matches the audit report.
    "hub/apps/scheduled_ingestion/ingestion.py": 1,
    "hub/apps/orchestration/workflows/contract_creation.py": 1,
    "hub/apps/orchestration/workflows/product_creation.py": 1,
    "hub/apps/orchestration/workflows/asset_creation.py": 1,
    "hub/apps/orchestration/workflows/transformation_pipeline.py": 1,
    "hub/apps/orchestration/workflows/scheduled_ingestion.py": 1,
    "hub/apps/assets/views_optimized.py": 1,
    "hub/apps/integrations/services/discovery_service.py": 1,
    "hub/apps/integrations/_services_legacy.py": 5,  # legacy; multiple may exist.
}

_DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("hub/apps",)
_EXCLUDE_DIR_PARTS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "tests",
        "test",
        "migrations",
        ".tox",
        ".venv",
        "venv",
    }
)

_PRAGMA_ALLOWED = "asset-create-direct-allowed"


@dataclass(frozen=True)
class Offence:
    file: str
    line: int
    pattern: str

    def render(self) -> str:
        return (
            f"{self.file}:{self.line}: E[ASSET-CREATE-001] "
            f"direct '{self.pattern}' detected outside the canonical "
            f"AssetService entry point. Phase 250.1.A invariant: every "
            f"Asset row MUST be created via "
            f"AssetService.create_via_workflow(...) so compliance + DQ "
            f"gates run BEFORE persistence. Refactor this caller, or — "
            f"if intentional and safe — annotate the line with "
            f"'# pragma: {_PRAGMA_ALLOWED}'."
        )


def _is_asset_create_call(node: ast.Call) -> str | None:
    """Return the matched pattern label if ``node`` is a direct-create
    call site; else None."""
    func = node.func
    # Asset.objects.create(...) → Attribute(value=Attribute(value=Name('Asset'), attr='objects'), attr='create')
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "create"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "objects"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "Asset"
    ):
        return "Asset.objects.create"
    # Asset(...) at top-level — Name('Asset')
    if isinstance(func, ast.Name) and func.id == "Asset":
        # Filter out type annotations (rare; if a Call's parent is annotation
        # context we'd miss; AST doesn't make that easy without parent links).
        return "Asset(...)"
    return None


def _iter_python_files(roots: Iterable[str]) -> Iterable[Path]:
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            yield root_path
            continue
        for path in root_path.rglob("*.py"):
            if any(part in _EXCLUDE_DIR_PARTS for part in path.parts):
                continue
            yield path


def _line_has_exemption(text: str, line_no: int) -> bool:
    """True if the line at ``line_no`` (1-indexed) contains the exemption
    pragma OR if the immediately-preceding line carries it."""
    lines = text.splitlines()
    if line_no - 1 < len(lines) and _PRAGMA_ALLOWED in lines[line_no - 1]:
        return True
    if line_no - 2 >= 0 and _PRAGMA_ALLOWED in lines[line_no - 2]:
        return True
    return False


def scan_file(path: Path) -> list[Offence]:
    """Return offences (post-allow-list filtering) for one file."""
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []

    raw_hits: list[Offence] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        pattern = _is_asset_create_call(node)
        if pattern is None:
            continue
        if _line_has_exemption(text, node.lineno):
            continue
        raw_hits.append(
            Offence(
                file=str(path),
                line=node.lineno,
                pattern=pattern,
            )
        )

    if not raw_hits:
        return []

    # Apply allow-list: a file may have up to N grandfathered hits. Anything
    # beyond N is an offence. Allow-list lookup uses the relative path.
    rel_path = str(path).replace("\\", "/")
    allowed = 0
    for entry, count in _ALLOWLIST.items():
        if rel_path.endswith(entry):
            allowed = count
            break

    if len(raw_hits) <= allowed:
        return []
    # Offences are the hits BEYOND the allow-list count. Sort by line for
    # deterministic reporting.
    return sorted(raw_hits, key=lambda h: h.line)[allowed:]


def main(argv: list[str]) -> int:
    paths = argv[1:] or list(_DEFAULT_SCAN_ROOTS)
    offences: list[Offence] = []
    for py_file in _iter_python_files(paths):
        offences.extend(scan_file(py_file))

    if offences:
        print(
            f"❌ Phase 250.1.G — found {len(offences)} new direct "
            f"Asset-creation call site(s) outside AssetService:",
            file=sys.stderr,
        )
        for off in sorted(offences, key=lambda o: (o.file, o.line)):
            print(off.render())
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
