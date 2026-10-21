"""
Contract tests for scripts/check_smoke_report.py (pilot-readiness 2.4,
GATE-44).

The pilot-live-verification spec requires a written smoke report that
lists every exercised path, its result, any API-shape mismatches, and
open gaps — and the masked-reporting requirement says NO credential
material may appear in it. The checker enforces both: section/structure
completeness and a REAL secret scan against the operator's env file
(the exact values, not just token-looking patterns — the check is
falsifiable against the live .env.test).
"""

import importlib.util
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_smoke_report.py"
spec = importlib.util.spec_from_file_location("check_smoke_report", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

MINIMAL_REPORT = """# Pilot Live-Verification Smoke Report

## Exercised paths

| # | Surface / path | Result |
|---|---|---|
| 1 | clusters/list | PASS |
| 2 | oidc/v1/token | PASS |
| 3 | sql/warehouses | PASS |
| 4 | GetCallerIdentity | PASS |
| 5 | hub-files | PASS |
| 6 | test-connectors-e2e | 12 skipped / 0 failed |
| 7 | TestDatabricksLiveIntegration | 2 passed |
| 8 | execute_dlt_ingestion | processed=1 |
| 9 | dbt run | PASS=1 |
| 10 | pilot_dbt_23 | view read back |
| 11 | DatabricksCostLedger | 1 row |

## Results summary

all green

## API-shape mismatches

none in this fixture

## Gaps

none in this fixture
"""


@pytest.fixture
def report(tmp_path):
    p = tmp_path / "report.md"
    p.write_text(MINIMAL_REPORT)
    return p


@pytest.fixture
def envfile(tmp_path):
    p = tmp_path / "env.test"
    p.write_text("TOKEN_PRESENT_SECRET=superdupersecretvalue123\n")
    return p


def test_valid_report_passes(report, envfile):
    assert check.check(report, envfile) == []


def test_missing_section_fails_naming_it(report, envfile):
    text = report.read_text().replace("## Gaps", "## Missing")
    report.write_text(text)
    problems = check.check(report, envfile)
    assert problems
    assert any("## Gaps" in p for p in problems)


def test_missing_exercised_path_fails_naming_it(report, envfile):
    text = report.read_text().replace("execute_dlt_ingestion", "the_old_spine")
    report.write_text(text)
    problems = check.check(report, envfile)
    assert any("execute_dlt_ingestion" in p for p in problems)


def test_a_leaked_env_secret_fails_the_masked_reporting_contract(
    report, envfile, tmp_path
):
    # The REAL check: the exact secret value from the env file must be
    # caught in the report — the masked-reporting rule, falsifiable.
    text = report.read_text().replace(
        "all green", "all green, key=superdupersecretvalue123"
    )
    report.write_text(text)
    problems = check.check(report, envfile)
    assert any("masked-reporting" in p for p in problems)
    assert any(
        "superdupersecretvalue123" not in p for p in problems
    ), "the checker must not echo the leaked value back"


def test_short_values_of_nonsensitive_keys_are_not_flagged(report, tmp_path):
    # A bucket NAME (8 chars) in the report is an identifier, not a
    # credential — only sensitive-named keys and long values are scanned.
    envfile = tmp_path / "env.test"
    envfile.write_text("AWS_STORAGE_BUCKET_NAME=hub-files\n")
    assert check.check(report, envfile) == []


def test_long_values_from_any_key_are_scanned(report, tmp_path):
    # Long values are secrets in practice (rotated creds, SA JSON) even
    # when the key name is not sensitive.
    envfile = tmp_path / "env.test"
    envfile.write_text("SOME_HOST=verylonghostnameidentifier.example.internal\n")
    text = report.read_text().replace(
        "all green", "all green, verylonghostnameidentifier.example.internal"
    )
    report.write_text(text)
    problems = check.check(report, envfile)
    assert any("masked-reporting" in p for p in problems)


def test_identifier_valued_config_keys_are_not_treated_as_secrets(report, tmp_path):
    # A class constant such as the declared re-scope class MUST be
    # nameable in the report; an identifier-valued config key is not a
    # credential.
    envfile = tmp_path / "env.test"
    envfile.write_text(
        "PILOT_BUDGET_CAPS_RESCOPE=free-edition-no-billing\nSOME_REGION=eu-central-1\n"
    )
    text = report.read_text().replace(
        "all green", "all green, class free-edition-no-billing in eu-central-1"
    )
    report.write_text(text)
    assert check.check(report, envfile) == []


def test_the_same_value_on_a_sensitive_key_is_still_flagged(report, tmp_path):
    # The exemption is key-name-based: the identical value on a
    # credential key is still a leak.
    envfile = tmp_path / "env.test"
    envfile.write_text("SOME_TOKEN=free-edition-no-billing\n")
    text = report.read_text().replace("all green", "all green, free-edition-no-billing")
    report.write_text(text)
    problems = check.check(report, envfile)
    assert any("masked-reporting" in p for p in problems)


def test_an_account_id_literal_fails_the_redaction_contract(report, envfile):
    # C1 (oss-release-remediation W0.9): customer-identifying data — a
    # 12-digit AWS-account-ID literal must be caught by the masked scan
    # (and never echoed back).
    text = report.read_text().replace("all green", "all green, account=123456789012")
    report.write_text(text)
    problems = check.check(report, envfile)
    assert any("account-ID" in p for p in problems)
    assert all(
        "123456789012" not in p for p in problems
    ), "the checker must not echo the identifier back"


def test_redacted_placeholders_pass(report, envfile):
    # The C1 redaction form (placeholder, value only in the env file) is
    # the contract's expected output and must stay clean.
    text = report.read_text().replace(
        "all green",
        "all green, account=<redacted-account-id> (value lives in .env.test)",
    )
    report.write_text(text)
    assert check.check(report, envfile) == []


def test_short_number_runs_are_not_account_ids(report, envfile):
    # Counts and metrics legitimately carry digits (trip_count=21932,
    # 2.459955 dbu) — only a full 12-digit run is the identifier class.
    text = report.read_text().replace(
        "all green", "all green, count=21932 dbu=2.459955"
    )
    report.write_text(text)
    assert check.check(report, envfile) == []


def test_default_paths_exist():
    # The canonical artifacts ship in the repo: the report and the
    # operator env file the gate scans by default.
    root = scripts_dir.parent
    assert (root / "docs/runbooks/PILOT_SMOKE_REPORT.md").exists()
    assert (root / ".env.test").exists()


class TestMainContract:
    def test_problems_exit_1(self, report, envfile, monkeypatch, capsys):
        text = report.read_text().replace("## Gaps", "## Missing")
        report.write_text(text)
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_smoke_report.py",
                "--report",
                str(report),
                "--env-file",
                str(envfile),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, report, envfile, monkeypatch, capsys):
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_smoke_report.py",
                "--report",
                str(report),
                "--env-file",
                str(envfile),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0
