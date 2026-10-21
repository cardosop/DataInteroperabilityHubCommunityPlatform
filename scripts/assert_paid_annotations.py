#!/usr/bin/env python3
"""W7.2 (D5) — paid-annotation scrub assertion.

The public tree's traceability registries must carry the PAID column and
its markers (public metadata, never a secret — the sanitize pass must
not strip it).  Called by publish_tree.sh (after sanitize) and by
build_public_tree_preview.sh (after the working-tree overlay).

Usage: python scripts/assert_paid_annotations.py <built-tree-root>
"""

from __future__ import annotations

import sys
from pathlib import Path

REGISTRIES = ("docs/USER_JOURNEYS.md", "docs/USE_CASES.md")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    staging = Path(sys.argv[1])
    for registry in REGISTRIES:
        path = staging / registry
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if "| PAID |" not in content:
            print(
                f"W7.2 scrub assertion failed: {registry} lost its PAID column",
                file=sys.stderr,
            )
            return 1
        if " PAID |" not in content:
            print(
                f"W7.2 scrub assertion failed: {registry} lost its PAID markers",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
