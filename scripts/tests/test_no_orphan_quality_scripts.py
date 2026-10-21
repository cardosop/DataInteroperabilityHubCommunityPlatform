"""W7.4 (oss-release-remediation) — zero-orphan quality-script pins.

Every ``check_*`` / ``lint_*`` / ``audit_*`` / ``verify_*`` script in
scripts/ must be WIRED — referenced from the CI workflow fleet, the
Makefile targets, pre-commit, or another committed file — or ARCHIVED
to archive/scripts-w74/ (the ledger lives in the archive README and in
the W7.4 openspec evidence).  A script that nothing runs is a script
that silently rots; the W12.4 blocking gate will build on this
inventory.

No mocks: the pins run the REAL repo-wide reference scan.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO / "scripts"
ARCHIVE = REPO / "archive" / "scripts-w74"

_EXCLUDE_DIR_PARTS = {
    ".git", "archive", "node_modules", "venv", ".venv", "dist", "site",
    "htmlcov", "__pycache__", "InputDocs",
}
_WIRING_SURFACES = {
    # The canonical wiring surfaces a quality script may appear in.
    ".github/workflows",
    "Makefile",
    "Makefile.core",
    ".pre-commit-config.yaml",
    "scripts",  # script → script references count (e.g. check_dco.sh ← pull_public_pr.sh)
    "docs",
    "conftest.py",
}


def _quality_scripts() -> set[str]:
    return {
        p.name
        for p in list(SCRIPTS.glob("*.py")) + list(SCRIPTS.glob("*.sh"))
        if re.match(r"^(check_|lint_|audit_|verify_)", p.name)
    }


def _repo_texts() -> str:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )
    texts: list[str] = []
    for rel in result.stdout.splitlines():
        path = REPO / rel  # ls-files emits repo-relative paths
        if any(part in _EXCLUDE_DIR_PARTS for part in path.parts):
            continue
        if not any(path.is_relative_to(REPO / s) for s in _WIRING_SURFACES):
            continue
        try:
            texts.append(path.read_text(errors="ignore"))
        except OSError:
            continue
    return "\n".join(texts)


def test_zero_unwired_quality_scripts():
    corpus = _repo_texts()
    unwired = sorted(s for s in _quality_scripts() if s not in corpus)
    assert not unwired, (
        "unwired quality scripts (wire into a target or archive):\n"
        + "\n".join(f"  {s}" for s in unwired)
    )


def test_archived_scripts_left_the_active_tree():
    """Archived scripts must not linger in scripts/."""
    archived = {p.name for p in ARCHIVE.glob("*")} if ARCHIVE.exists() else set()
    active = _quality_scripts()
    lingering = archived & active
    assert not lingering, f"archived scripts still in scripts/: {sorted(lingering)}"


def test_inventory_is_non_empty():
    """Non-vacuity: the fleet actually has quality scripts."""
    assert len(_quality_scripts()) >= 20
