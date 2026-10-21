"""
Phase 240.3.E.3 — guard test: SPA must NOT call the deprecated
``/api/v1/quality/`` prefix.

The deprecated alias exists for *external* integrators on the
old prefix; the in-house frontend MUST stay on the canonical
``/api/v1/dq/`` mount. Otherwise we'd ship a Sunset header to our
own UI and confuse our own users.

This test scans the frontend source tree for any string match of
``/api/v1/quality/`` or the relative ``quality/runs/`` form. A
positive match fails the test — at which point either the SPA
needs to be migrated back to ``/api/v1/dq/`` OR this test needs
to be relaxed (with a documented reason).

Real file-system scan; no mocks. Cheap (~5 ms on a warm cache).
"""

from __future__ import annotations

import os
import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
SPA_SRC = REPO_ROOT / "frontend" / "src"

# Regex covers absolute paths and common relative forms. Excludes
# the standalone word ``quality`` (used as a UI grouping in the
# sidebar) by anchoring on a path component.
_FORBIDDEN_PATTERNS = [
    re.compile(r"/api/v1/quality/"),
    re.compile(r"['\"`]quality/(runs|anomalies|trends|scorecards|root[-_]cause)"),
]

# Test files document the dual-mount and are allowed to mention
# the deprecated path. Production code is not.
_ALLOWED_SUFFIXES = (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx")
_ALLOWED_DIR_PARTS = ("__tests__", "/tests/", "/__mocks__/")


class SPAQualityPrefixForbiddenTest(unittest.TestCase):
    """Pins 240.3.E.3: SPA does NOT call ``/api/v1/quality/``."""

    def test_no_deprecated_quality_prefix_in_spa_production_code(self):
        if not SPA_SRC.is_dir():
            self.skipTest(
                f"frontend src tree absent at {SPA_SRC} — running outside "
                "a full checkout (e.g. backend-only CI image)."
            )

        offenders: list[tuple[str, int, str]] = []
        for path in SPA_SRC.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (".ts", ".tsx", ".js", ".jsx"):
                continue
            if path.name.endswith(_ALLOWED_SUFFIXES):
                continue
            posix = path.as_posix()
            if any(part in posix for part in _ALLOWED_DIR_PARTS):
                continue

            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                # Binary-ish file or broken symlink — skip.
                continue

            for line_no, line in enumerate(text.splitlines(), start=1):
                for pat in _FORBIDDEN_PATTERNS:
                    if pat.search(line):
                        offenders.append(
                            (
                                os.path.relpath(path, REPO_ROOT),
                                line_no,
                                line.strip(),
                            )
                        )
                        break

        self.assertEqual(
            offenders,
            [],
            "SPA must use the canonical /api/v1/dq/ prefix; "
            "found references to the deprecated /api/v1/quality/ "
            "alias:\n" + "\n".join(f"  {p}:{ln}: {snippet}" for p, ln, snippet in offenders),
        )
