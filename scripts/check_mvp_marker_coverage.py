#!/usr/bin/env python3
"""
Phase 260.B Acceptance #5 — marker-coverage lint.

The nightly CLI/SDK regression workflow at
``.github/workflows/cli-sdk-nightly-regression.yml`` runs
``pytest -m mvp --strict-markers``. Tests without the ``@pytest.mark.mvp``
marker are silently skipped.

If a future engineer adds a new auth/SSO/cookie test (or an existing one
loses its marker via a refactor) the nightly run could go green for 14
consecutive days while a real regression hides behind an unmarked file.
That would defeat the entire 14-day production-flip gate.

This script enforces the invariant: every CLI/SDK test file under the
auth/SSO/cookie surface MUST carry the marker. Run it locally with
``python3 scripts/check_mvp_marker_coverage.py``; the nightly workflow
runs it as a required step before launching the regression suites.

Exits 0 (clean) or 1 (any uncovered file).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Test directories whose contents are scoped to the cookie/auth nightly
# regression gate. Add a directory here ONLY if every test under it must
# run nightly; do NOT add general-purpose test dirs (they have their own
# CI gates).
SCOPED_TEST_DIRS = [
    REPO_ROOT / "cli" / "tests" / "use_cases",
    REPO_ROOT / "sdk" / "python" / "tests" / "use_cases",
]

# Filenames inside the scoped dirs that the cookie-rollout gate
# specifically depends on. Anything matching one of these globs MUST
# carry ``pytest.mark.mvp``. Other tests in the same directory may or
# may not be MVP-tagged — that's the caller's choice.
REQUIRED_FILE_PATTERNS = [
    re.compile(r"test_login\.py$"),
    re.compile(r"test_logout\.py$"),
    re.compile(r"test_logout_all\.py$"),
    re.compile(r"test_refresh.*\.py$"),
    re.compile(r"test_sso.*\.py$"),
    re.compile(r"test_me.*\.py$"),
    re.compile(r"test_cookie.*\.py$"),
    re.compile(r"test_password_reset.*\.py$"),
    re.compile(r"test_account_lockout.*\.py$"),
    # Phase 260.B uses the consolidated `test_auth_lifecycle.py` for
    # login/logout/refresh coverage (rather than separate files), so
    # treat it as required for the cookie gate.
    re.compile(r"test_auth_lifecycle\.py$"),
]

#: Pytest marker pattern. Accepts both ``pytestmark = pytest.mark.mvp``
#: and ``@pytest.mark.mvp`` decorator forms.
MARKER_RE = re.compile(
    r"(?:pytestmark\s*=\s*pytest\.mark\.mvp"
    r"|pytestmark\s*=\s*\[?[^\]]*pytest\.mark\.mvp"
    r"|@pytest\.mark\.mvp)",
    re.MULTILINE,
)


def _file_requires_marker(path: Path) -> bool:
    name = path.name
    return any(pat.search(name) for pat in REQUIRED_FILE_PATTERNS)


def _file_has_marker(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(MARKER_RE.search(text))


def main() -> int:
    missing: list[Path] = []
    scanned = 0

    for scoped_dir in SCOPED_TEST_DIRS:
        if not scoped_dir.exists():
            print(
                f"::warning::Expected scoped test dir not found: "
                f"{scoped_dir.relative_to(REPO_ROOT)}"
            )
            continue
        for test_file in sorted(scoped_dir.rglob("test_*.py")):
            if not _file_requires_marker(test_file):
                continue
            scanned += 1
            if not _file_has_marker(test_file):
                missing.append(test_file)

    if missing:
        print(
            "::error::Phase 260.B nightly marker coverage FAILED — the "
            "following auth/SSO/cookie test files lack pytest.mark.mvp "
            "and would be silently skipped by the nightly regression "
            "suite (defeats the 14-day cookie-flip gate):",
            file=sys.stderr,
        )
        for path in missing:
            print(f"  - {path.relative_to(REPO_ROOT)}", file=sys.stderr)
        print(
            "\nFix: add `pytestmark = pytest.mark.mvp` at the top of "
            "each file (after imports), or apply `@pytest.mark.mvp` to "
            "every test function. Then re-run this script.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Phase 260.B marker coverage: {scanned} scoped test file(s) "
        f"checked; all carry pytest.mark.mvp."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
