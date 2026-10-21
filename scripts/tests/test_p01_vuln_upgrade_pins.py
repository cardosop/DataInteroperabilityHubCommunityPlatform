"""
P0-1 (close-oss-release-conditions, H-3) — the vulnerability-upgrade pin.

Root cause pinned here: the 4.2 triage (2026-10-06) upgraded the venv and
wrote `.pip-audit-allowlist.yaml` header claims that the pin bumps had
shipped, but the pin-file changes never landed in
``requirements.txt`` / ``requirements-core.txt`` — so
``pip-audit -r requirements.txt`` kept resolving the OLD versions and
GATE-47 stayed RED with the 5 H-3 advisories UNTRIAGED:

  * pyjwt             PYSEC-2026-4152 (fix 2.14.0),
                      PYSEC-2026-4183 (fix 2.15.0)
  * strawberry-graphql
                      PYSEC-2026-4302 (fix 0.327.2),
                      PYSEC-2026-4303 (fix 0.326.1)
  * weasyprint        PYSEC-2026-4311 (fix 70.0)

The pin has two legs, no mocks:

1. **Static contract** — the fixed pins are present (and the old pins
   absent) in BOTH requirement files, kept in sync, and the 5 advisory
   ids are NOT triage-allowlisted (they are FIXED, not residual — a
   re-added allowlist row would be a dead entry and a drift signal).
2. **Live leg (W16-gated)** — the real GATE-47 checker runs a real
   pip-audit against requirements.txt and the 5 advisories leave the
   UNTRIAGED set, i.e. the gate itself is green (P0-1's acceptance).

The companion pin bumps (requests 2.33.0, cryptography 46.0.7,
databricks-sql-connector >=4.0,<5.0) are pinned too — they are part of
the same root fix: the 4.2 triage claimed them shipped while the pin
file never moved, and GATE-47 cannot be green without them.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS.parent))

from envpolicy import skip_or_fail

_spec = importlib.util.spec_from_file_location(
    "check_dependency_vulns", SCRIPTS.parent / "check_dependency_vulns.py"
)
assert _spec is not None, "check_dependency_vulns.py must load"
assert _spec.loader is not None, "check_dependency_vulns.py must carry a loader"
check_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_mod)

REQUIREMENTS = REPO_ROOT / "requirements.txt"
REQUIREMENTS_CORE = REPO_ROOT / "requirements-core.txt"
ALLOWLIST = REPO_ROOT / ".pip-audit-allowlist.yaml"

# The H-3 five-advisory set (2026-10-18 measurement).
P01_ADVISORY_IDS = (
    "PYSEC-2026-4152",
    "PYSEC-2026-4183",
    "PYSEC-2026-4302",
    "PYSEC-2026-4303",
    "PYSEC-2026-4311",
)

# package -> spec suffix the pin file MUST carry (both requirement files).
TARGET_PINS = {
    "PyJWT": "==2.15.0",
    "strawberry-graphql": "[django]==0.327.2",
    "WeasyPrint": "==70.0",
    "requests": "==2.33.0",
    "cryptography": "==46.0.7",
    "databricks-sql-connector": ">=4.0,<5.0",
}

# package -> spec fragment the pin file MUST NOT carry anywhere.
OLD_PIN_FRAGMENTS = {
    "PyJWT": "==2.12.0",
    "strawberry-graphql": "==0.312.3",
    "WeasyPrint": "<70.0",
    "requests": "==2.32.4",
    "cryptography": "==46.0.5",
    "databricks-sql-connector": ">=3.0,<4.0",
}


def _dep_specs(path: Path) -> dict[str, str]:
    """Parse a requirements file into {package: version-spec}.

    Env-marker suffixes (``; python_version ...``) are stripped; comment
    lines and ``-r`` includes are ignored. A later line wins (the
    requirements-convention: the operative pin is the last one).
    """
    specs: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        package = line.split(";", 1)[0].strip()
        name = package.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0]
        name = name.split(">", 1)[0].split("<", 1)[0].split("~=", 1)[0]
        name = name.split("!=", 1)[0].split("[", 1)[0]
        name = name.strip()
        if not name:
            continue
        specs[name] = package
    return specs


class TestP01PinContract:
    """Static contract: the pin files carry the fixed versions (no mocks)."""

    def test_target_pins_present_in_both_files(self):
        for path in (REQUIREMENTS, REQUIREMENTS_CORE):
            specs = _dep_specs(path)
            for name, target in TARGET_PINS.items():
                assert specs.get(name) == f"{name}{target}", (
                    f"{path.name}: expected pin `{name}{target}`, found {specs.get(name)!r}"
                )

    def test_old_pins_absent_from_both_files(self):
        for path in (REQUIREMENTS, REQUIREMENTS_CORE):
            specs = _dep_specs(path)
            for name, old in OLD_PIN_FRAGMENTS.items():
                got = specs.get(name, "")
                assert old not in got, f"{path.name}: the pre-P0-1 pin `{name}{old}` is back"

    def test_core_file_stays_in_sync_with_requirements(self):
        """requirements-core.txt is a derived subset — the P0-1 pins must
        agree across both files or the core install drifts."""
        req = _dep_specs(REQUIREMENTS)
        core = _dep_specs(REQUIREMENTS_CORE)
        for name, target in TARGET_PINS.items():
            assert core.get(name) == req.get(name) == f"{name}{target}"

    def test_p01_advisories_are_not_allowlisted(self):
        """The 5 advisories are FIXED by the pins — they must not sit in
        the triage allowlist as residual rows (that would be a dead entry
        and would mean the pin bump was silently reverted). Only triage
        ENTRIES count — the header's historical record may mention the
        ids (it does, citing this pin)."""
        problems, entries = check_mod._load_allowlist(ALLOWLIST)
        assert problems == [], f"allowlist must parse: {problems}"
        for pid in P01_ADVISORY_IDS:
            assert not any(key.startswith(f"{pid}:") for key in entries), (
                f"{pid} is allowlisted — the pin bump must have been "
                f"reverted; the allowlist row is a dead entry"
            )


class TestP01LiveGate:
    """Live leg (W16): the real GATE-47 run has no untriaged P0-1 advisory."""

    @staticmethod
    def _pip_audit_available() -> bool:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip_audit", "--version"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def test_live_gate_p01_advisories_leave_untriaged_set(self):
        if not self._pip_audit_available():
            skip_or_fail("pip-audit is not installed (P0-1 live pin)")
        audit_json = check_mod._run_pip_audit(REQUIREMENTS)
        problems = check_mod.check(
            audit_json=audit_json,
            allowlist_path=ALLOWLIST,
            today=date.today().isoformat(),
        )
        for pid in P01_ADVISORY_IDS:
            assert not any(pid in problem for problem in problems), (
                f"{pid} is still in the gate output: {problems}"
            )
        # P0-1 acceptance: GATE-47 itself is green — every pip-audit
        # finding is triaged, none of them the P0-1 advisory set.
        assert problems == [], f"GATE-47 not green: {problems}"
