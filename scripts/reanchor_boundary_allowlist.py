#!/usr/bin/env python3
"""
GATE-29 allowlist maintenance — re-anchor drifted path:line entries.

The allowlist keys violations by exact ``path:line``; file churn shifts
lines and the anchors rot (the W0.4b drill surfaced 171 drifted anchors
plus 27 never-allowlisted sites). This tool:

- for every violation whose PATH already has allowlist entries, moves
  that path's anchor(s) to the current violation line(s) — the audit
  reason is preserved (the entry predates the drift; only the line
  moved);
- removes dead anchors (entries whose path no longer produces any
  violation — the import left the file);
- reports NEW sites (violations whose path has no allowlist entry) for
  manual root-fixing (the lazy-import seam) or audited addition.

The ratchet is respected: the rewritten list never grows — moved anchors
keep the count; dead anchors shrink it; new sites are reported, never
auto-added.

Usage: python scripts/reanchor_boundary_allowlist.py [--apply]
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

_GATE_SPEC = importlib.util.spec_from_file_location(
    "g29", _ROOT / "scripts/check_core_boundary.py"
)
_gate = importlib.util.module_from_spec(_GATE_SPEC)
_GATE_SPEC.loader.exec_module(_gate)

ALLOWLIST = _ROOT / "scripts/core_boundary_allowlist.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the re-anchored list")
    args = parser.parse_args()

    paid, _ = _gate._read_paid_modules(_ROOT / "hub/apps/manifest.py")
    violations = _gate.collect_violations(_ROOT, [_gate._normalise(m) for m in paid])
    allowlist = {
        line.split(":", 2)[0] + ":" + line.split(":", 2)[1]: line.split(":", 2)[2]
        for line in ALLOWLIST.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    unallowed = [v for v in violations if v.key() not in allowlist]

    # Only entries that do NOT match a current violation can be moved or
    # dead.  An entry matching a live violation exactly is HEALTHY and
    # must stay untouched — the pre-W7.1 version tracked every entry in
    # by_path and then reported the never-popped (i.e. exactly-matched)
    # entries as "dead anchors removed", DESTROYING valid entries on
    # every --apply run.
    live_keys = {v.key() for v in violations}
    by_path: dict[str, list[str]] = {}
    for key in sorted(allowlist):
        if key in live_keys:
            continue
        path, _line = key.split(":", 1)
        by_path.setdefault(path, []).append(key)

    moved: list[tuple[str, str, str]] = []
    dead: list[str] = []
    new_sites: list[str] = []
    for violation in unallowed:
        path = violation.key().split(":", 1)[0]
        if path in by_path and by_path[path]:
            old = by_path[path].pop(0)
            moved.append((old, violation.key(), allowlist[old]))
            allowlist.pop(old, None)
            allowlist[violation.key()] = moved[-1][2]
        else:
            new_sites.append(violation.key())

    for path, leftover in by_path.items():
        for key in leftover:
            dead.append(key)
            allowlist.pop(key, None)

    print(f"violations {len(violations)} | re-anchored {len(moved)} | "
          f"dead anchors removed {len(dead)} | new sites {len(new_sites)}")
    for old, new, reason in moved:
        print(f"  move {old} -> {new}")
    for key in dead:
        print(f"  dead  {key}")
    for key in new_sites:
        print(f"  NEW   {key}  (root-fix or audited entry)")

    if args.apply:
        header = (
            "# GATE-29 core/paid boundary allowlist — audited transitional entries.\n"
            "# Format: path:lineno:reason (exact match; the CI ratchet asserts this\n"
            "# list only ever SHRINKS). Every entry is Phase 313.2 long-tail work.\n"
        )
        body = "".join(f"{key}:{reason}\n" for key, reason in sorted(allowlist.items()))
        ALLOWLIST.write_text(header + body)
        print(f"rewrote {ALLOWLIST} ({len(allowlist)} entries)")


if __name__ == "__main__":
    main()
