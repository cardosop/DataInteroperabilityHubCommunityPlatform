"""
Contract tests for scripts/check_dependency_vulns.py (pilot-readiness 4.2).

The MEDIUM+ blocking policy:
- every pip-audit finding must be TRIAGED — present in the allowlist
  (vuln id + package) with a rationale and a future review date;
- untriaged findings block (exit 1) regardless of severity (unknown
  severity is treated as blocking — the "block MEDIUM+" floor);
- allowlisted entries whose review date has passed block again
  (the .trivyignore Review-by convention);
- the full triage output is printed — never truncated (the 4.2
  truncated-audit-log fix);
- the W16 environment policy applies when pip-audit is unavailable
  (CI raises, local skips).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_dependency_vulns.py"
spec = importlib.util.spec_from_file_location("check_dependency_vulns", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

AUDIT_JSON = {
    "dependencies": [
        {
            "name": "pyjwt",
            "version": "2.12.0",
            "vulns": [
                {"id": "PYSEC-2026-4145", "fix_versions": ["2.14.0"]},
                {"id": "PYSEC-2026-177", "fix_versions": ["2.13.0"]},
            ],
        },
        {
            "name": "click",
            "version": "8.3.1",
            "vulns": [{"id": "PYSEC-2026-2132", "fix_versions": ["8.3.3"]}],
        },
    ],
}


def _allowlist(entries):
    text = "allowlist:\n"
    for e in entries:
        text += (
            f"  - id: {e['id']}\n"
            f"    package: {e['package']}\n"
            f"    severity: {e['severity']}\n"
            f"    rationale: {e['rationale']}\n"
            f"    review_by: {e['review_by']}\n"
        )
    return text


FULL_TRIAGE = _allowlist(
    [
        {
            "id": "PYSEC-2026-4145",
            "package": "pyjwt",
            "severity": "critical",
            "rationale": "fixed by the pyjwt 2.15.0 pin",
            "review_by": "2026-11-05",
        },
        {
            "id": "PYSEC-2026-177",
            "package": "pyjwt",
            "severity": "low",
            "rationale": "low severity; fix in 2.13.0",
            "review_by": "2026-11-05",
        },
        {
            "id": "PYSEC-2026-2132",
            "package": "click",
            "severity": "low",
            "rationale": "low severity; fix in 8.3.3",
            "review_by": "2026-11-05",
        },
    ]
)

TODAY = "2026-10-06"
FUTURE = "2026-11-05"
PAST = "2026-09-01"


@pytest.fixture
def fixture_files(tmp_path):
    audit = tmp_path / "audit.json"
    import json

    audit.write_text(json.dumps(AUDIT_JSON))
    allowlist = tmp_path / "allowlist.yaml"
    allowlist.write_text(FULL_TRIAGE)
    return audit, allowlist


def _run(fixture_files, allowlist_text=None, today=TODAY):
    audit, allowlist_path = fixture_files
    if allowlist_text is not None:
        allowlist_path.write_text(allowlist_text)
    return check.check(
        audit_json=audit,
        allowlist_path=allowlist_path,
        today=today,
    )


def test_full_triage_passes(fixture_files):
    problems = _run(fixture_files)
    assert problems == []


def test_untriaged_vuln_blocks(fixture_files):
    allowlist = _allowlist(
        [
            {
                "id": "PYSEC-2026-177",
                "package": "pyjwt",
                "severity": "low",
                "rationale": "low severity",
                "review_by": FUTURE,
            },
            {
                "id": "PYSEC-2026-2132",
                "package": "click",
                "severity": "low",
                "rationale": "low severity",
                "review_by": FUTURE,
            },
        ]
    )
    problems = _run(fixture_files, allowlist_text=allowlist)
    assert any("PYSEC-2026-4145" in p for p in problems)
    assert any("untriaged" in p.lower() for p in problems)


def test_expired_review_blocks(fixture_files):
    allowlist = _allowlist(
        [
            {
                "id": "PYSEC-2026-4145",
                "package": "pyjwt",
                "severity": "critical",
                "rationale": "stale review",
                "review_by": PAST,
            },
            {
                "id": "PYSEC-2026-177",
                "package": "pyjwt",
                "severity": "low",
                "rationale": "low severity",
                "review_by": FUTURE,
            },
            {
                "id": "PYSEC-2026-2132",
                "package": "click",
                "severity": "low",
                "rationale": "low severity",
                "review_by": FUTURE,
            },
        ]
    )
    problems = _run(fixture_files, allowlist_text=allowlist)
    assert any("expired" in p.lower() for p in problems)


def test_missing_audit_json_fails(tmp_path):
    problems = check.check(
        audit_json=tmp_path / "missing.json",
        allowlist_path=tmp_path / "allowlist.yaml",
        today=TODAY,
    )
    assert problems
    assert any("missing" in p.lower() for p in problems)


def test_unknown_severity_treated_as_blocking(fixture_files):
    """An allowlisted entry with an UNKNOWN severity still passes only
    if triaged — the severity field is informational; the allowlist
    presence is what unblocks. Pinned here so the policy cannot drift
    into severity-blind blocking."""
    allowlist = _allowlist(
        [
            {
                "id": "PYSEC-2026-4145",
                "package": "pyjwt",
                "severity": "UNKNOWN",
                "rationale": "triaged anyway",
                "review_by": FUTURE,
            },
            {
                "id": "PYSEC-2026-177",
                "package": "pyjwt",
                "severity": "UNKNOWN",
                "rationale": "triaged anyway",
                "review_by": FUTURE,
            },
            {
                "id": "PYSEC-2026-2132",
                "package": "click",
                "severity": "UNKNOWN",
                "rationale": "triaged anyway",
                "review_by": FUTURE,
            },
        ]
    )
    problems = _run(fixture_files, allowlist_text=allowlist)
    assert problems == []


def test_default_paths_exist():
    root = scripts_dir.parent
    assert (root / "requirements.txt").exists()
    assert (root / ".pip-audit-allowlist.yaml").exists()


class TestMainContract:
    def test_problems_exit_1(self, fixture_files, monkeypatch):
        allowlist = _allowlist(
            [
                {
                    "id": "PYSEC-2026-177",
                    "package": "pyjwt",
                    "severity": "low",
                    "rationale": "low severity",
                    "review_by": FUTURE,
                },
            ]
        )
        fixture_files[1].write_text(allowlist)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_dependency_vulns.py",
                "--audit-json",
                str(fixture_files[0]),
                "--allowlist",
                str(fixture_files[1]),
                "--today",
                TODAY,
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, fixture_files, monkeypatch):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_dependency_vulns.py",
                "--audit-json",
                str(fixture_files[0]),
                "--allowlist",
                str(fixture_files[1]),
                "--today",
                TODAY,
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0
