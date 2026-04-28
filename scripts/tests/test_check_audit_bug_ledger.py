"""TDD tests for scripts/check_audit_bug_ledger.py.

Implements the validator behind 226.H — the bug-fix bandwidth meta-track.

Three concerns, one script:

1. **process** (226.H.process) — Every audit-exposed bug must have a
   ticket + owner + expiry within 48 h of the surfacing PR landing.
   Default expiry is 14 days from `surfaced_at`.

2. **gate**    (226.H.gate)    — `audit-exposed bug awaiting fix` is the
   recognised skip-reason prefix; the validator publishes the canonical
   prefix string + 15 % threshold so the skip-counter can consume them
   without duplicating constants.

3. **close**   (226.H.close)   — End-of-cycle: the audit-bug skip count
   must be ≤ 3 (residual long-tail) AND no open bug may be past expiry
   without an extension review covering today's date.

Run (stdlib-only; ignores project pytest.ini to stay isolated, mirroring
test_check_skip_counter.py):

    pytest -c /dev/null scripts/tests/test_check_audit_bug_ledger.py -v
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(REPO_ROOT))

from check_audit_bug_ledger import (  # noqa: E402
    AUDIT_BUG_SKIP_REASON_PREFIX,
    DEFAULT_CATEGORY_THRESHOLD,
    DEFAULT_EXPIRY_DAYS,
    DEFAULT_RESIDUAL_MAX,
    DEFAULT_TICKET_GRACE_HOURS,
    bug_is_past_expiry,
    check_close,
    check_process,
    count_category_skips,
    effective_expiry,
    load_ledger,
    main,
    validate_schema,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)


def _ledger(*, bugs: list[dict] | None = None, **overrides) -> dict:
    """Build a valid ledger document, with overrides for negative tests."""
    base = {
        "schema_version": 1,
        "skip_reason_prefix": AUDIT_BUG_SKIP_REASON_PREFIX,
        "default_expiry_days": DEFAULT_EXPIRY_DAYS,
        "process": {"ticket_grace_period_hours": DEFAULT_TICKET_GRACE_HOURS},
        "cycle": {
            "name": "preprod01-audit-landing",
            "started_at": "2026-04-24",
            "residual_max": DEFAULT_RESIDUAL_MAX,
        },
        "bugs": bugs if bugs is not None else [],
    }
    base.update(overrides)
    return base


def _bug(
    *,
    id: str = "AUDIT-BUG-001",
    surfaced_at: datetime | str = NOW - timedelta(days=1),
    expiry: str | None = None,
    extensions: list[dict] | None = None,
    status: str = "open",
    closed_at: str | None = None,
    ticket: str = "https://github.com/x/y/issues/1",
    owner: str = "@cardosop",
    surfaced_by_pr: str = "PR-123",
    title: str = "Stub bug",
    **overrides,
) -> dict:
    if isinstance(surfaced_at, datetime):
        surfaced_at_str = surfaced_at.isoformat().replace("+00:00", "Z")
    else:
        # Allow tests to inject deliberately-malformed strings (e.g. "garbage")
        # so they can verify the schema validator catches them.
        surfaced_at_str = surfaced_at
    bug = {
        "id": id,
        "title": title,
        "ticket": ticket,
        "owner": owner,
        "surfaced_by_pr": surfaced_by_pr,
        "surfaced_at": surfaced_at_str,
        "expiry": expiry,
        "status": status,
        "skip_reason_examples": [],
        "extensions": extensions if extensions is not None else [],
        "closed_at": closed_at,
        "closed_by_pr": None,
    }
    bug.update(overrides)
    return bug


def _write_ledger(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Schema validation (foundation for all three gates)
# ---------------------------------------------------------------------------


class TestValidateSchema:
    def test_valid_empty_ledger_passes(self):
        problems = validate_schema(_ledger())
        assert problems == []

    def test_valid_with_one_bug_passes(self):
        problems = validate_schema(_ledger(bugs=[_bug()]))
        assert problems == []

    def test_missing_schema_version_fails(self):
        doc = _ledger()
        del doc["schema_version"]
        problems = validate_schema(doc)
        assert any("schema_version" in p for p in problems)

    def test_unknown_schema_version_fails(self):
        problems = validate_schema(_ledger(schema_version=99))
        assert any("schema_version" in p for p in problems)

    def test_wrong_skip_reason_prefix_fails(self):
        problems = validate_schema(_ledger(skip_reason_prefix="something else"))
        # The prefix is canonical — drift would silently break the gate.
        assert any("skip_reason_prefix" in p for p in problems)

    def test_duplicate_bug_ids_fail(self):
        problems = validate_schema(
            _ledger(bugs=[_bug(id="AUDIT-BUG-001"), _bug(id="AUDIT-BUG-001")])
        )
        assert any("duplicate" in p.lower() and "AUDIT-BUG-001" in p for p in problems)

    def test_bug_missing_required_field_fails(self):
        bug = _bug()
        del bug["owner"]
        problems = validate_schema(_ledger(bugs=[bug]))
        assert any("owner" in p for p in problems)

    def test_invalid_status_fails(self):
        problems = validate_schema(_ledger(bugs=[_bug(status="weird")]))
        assert any("status" in p for p in problems)

    def test_closed_bug_must_have_closed_at(self):
        problems = validate_schema(
            _ledger(bugs=[_bug(status="closed", closed_at=None)])
        )
        assert any("closed_at" in p for p in problems)

    def test_extension_must_have_required_fields(self):
        problems = validate_schema(
            _ledger(bugs=[_bug(extensions=[{"reason": "bad shape"}])])
        )
        # Missing extended_at / new_expiry / approver
        assert any("extension" in p.lower() for p in problems)

    # --- Tightened validation: dates must be parseable, not just present ---

    def test_unparseable_surfaced_at_fails(self):
        problems = validate_schema(_ledger(bugs=[_bug(surfaced_at="garbage")]))
        assert any("surfaced_at" in p and "parse" in p.lower() for p in problems)

    def test_unparseable_explicit_expiry_fails(self):
        problems = validate_schema(_ledger(bugs=[_bug(expiry="last tuesday")]))
        assert any("expiry" in p and "parse" in p.lower() for p in problems)

    def test_unparseable_closed_at_fails(self):
        problems = validate_schema(_ledger(bugs=[_bug(
            status="closed",
            closed_at="not-a-date",
        )]))
        assert any("closed_at" in p and "parse" in p.lower() for p in problems)

    def test_extension_dates_must_be_parseable(self):
        problems = validate_schema(_ledger(bugs=[_bug(extensions=[{
            "extended_at": "garbage",
            "new_expiry": "also-garbage",
            "approver": "@x",
            "reason": "y",
        }])]))
        assert any("extended_at" in p and "parse" in p.lower() for p in problems)
        assert any("new_expiry" in p and "parse" in p.lower() for p in problems)

    def test_backwards_extension_fails(self):
        # An extension whose new_expiry is *before* extended_at is nonsense:
        # an extension is by definition forward-in-time. Catching this in
        # schema validation means the close gate doesn't have to defend
        # against logically-broken data.
        problems = validate_schema(_ledger(bugs=[_bug(extensions=[{
            "extended_at": "2026-05-01",
            "new_expiry": "2026-04-15",
            "approver": "@x",
            "reason": "y",
        }])]))
        assert any("new_expiry" in p and "before" in p.lower() for p in problems)

    # --- Tightened validation: numeric fields have sensible ranges ---

    def test_negative_residual_max_fails(self):
        doc = _ledger(cycle={
            "name": "bad-cycle",
            "started_at": "2026-04-24",
            "residual_max": -1,
        })
        problems = validate_schema(doc)
        assert any("residual_max" in p and ("negative" in p.lower() or "0" in p) for p in problems)

    def test_negative_grace_period_fails(self):
        doc = _ledger(process={"ticket_grace_period_hours": -5})
        problems = validate_schema(doc)
        assert any("ticket_grace_period_hours" in p for p in problems)

    def test_zero_default_expiry_days_fails(self):
        doc = _ledger(default_expiry_days=0)
        problems = validate_schema(doc)
        assert any("default_expiry_days" in p for p in problems)

    def test_negative_default_expiry_days_fails(self):
        doc = _ledger(default_expiry_days=-3)
        problems = validate_schema(doc)
        assert any("default_expiry_days" in p for p in problems)

    # --- skip_reason_examples must use the canonical prefix ---

    def test_skip_reason_examples_must_use_canonical_prefix(self):
        # If a bug declares "examples" of how it gets skipped that don't
        # actually start with the canonical prefix, the gate won't count
        # those skips. That's a contract violation we should fail loudly on.
        problems = validate_schema(_ledger(bugs=[_bug(
            skip_reason_examples=["wrong prefix: AUDIT-BUG-001 — detail"]
        )]))
        assert any(
            "skip_reason_examples" in p and "prefix" in p.lower()
            for p in problems
        )

    def test_skip_reason_examples_with_canonical_prefix_passes(self):
        problems = validate_schema(_ledger(bugs=[_bug(
            skip_reason_examples=[
                f"{AUDIT_BUG_SKIP_REASON_PREFIX}: AUDIT-BUG-001 — detail"
            ]
        )]))
        assert problems == []


# ---------------------------------------------------------------------------
# effective_expiry / bug_is_past_expiry — pure helpers
# ---------------------------------------------------------------------------


class TestEffectiveExpiry:
    def test_falls_back_to_default_when_unset(self):
        bug = _bug(surfaced_at=NOW - timedelta(days=1), expiry=None)
        eff = effective_expiry(bug, default_days=DEFAULT_EXPIRY_DAYS)
        # surfaced_at + 14 days
        assert eff.date() == (NOW - timedelta(days=1) + timedelta(days=14)).date()

    def test_uses_explicit_expiry(self):
        bug = _bug(expiry="2026-06-01")
        eff = effective_expiry(bug, default_days=DEFAULT_EXPIRY_DAYS)
        assert eff.date() == datetime(2026, 6, 1).date()

    def test_extension_overrides_explicit_expiry(self):
        # Latest covering extension wins.
        bug = _bug(
            expiry="2026-05-01",
            extensions=[
                {
                    "extended_at": "2026-04-30",
                    "new_expiry": "2026-05-15",
                    "approver": "@reviewer",
                    "reason": "backend capacity",
                }
            ],
        )
        eff = effective_expiry(bug, default_days=DEFAULT_EXPIRY_DAYS)
        assert eff.date() == datetime(2026, 5, 15).date()

    def test_latest_extension_wins(self):
        bug = _bug(
            expiry="2026-05-01",
            extensions=[
                {
                    "extended_at": "2026-04-30",
                    "new_expiry": "2026-05-15",
                    "approver": "@a",
                    "reason": "x",
                },
                {
                    "extended_at": "2026-05-14",
                    "new_expiry": "2026-05-29",
                    "approver": "@b",
                    "reason": "y",
                },
            ],
        )
        eff = effective_expiry(bug, default_days=DEFAULT_EXPIRY_DAYS)
        assert eff.date() == datetime(2026, 5, 29).date()


class TestBugIsPastExpiry:
    def test_open_bug_before_expiry_is_not_past(self):
        bug = _bug(surfaced_at=NOW - timedelta(days=1))
        assert not bug_is_past_expiry(bug, now=NOW, default_days=DEFAULT_EXPIRY_DAYS)

    def test_open_bug_after_expiry_is_past(self):
        bug = _bug(surfaced_at=NOW - timedelta(days=20))  # default 14 → past
        assert bug_is_past_expiry(bug, now=NOW, default_days=DEFAULT_EXPIRY_DAYS)

    def test_closed_bug_is_never_past_expiry(self):
        bug = _bug(
            surfaced_at=NOW - timedelta(days=30),
            status="closed",
            closed_at="2026-04-20T00:00:00Z",
        )
        assert not bug_is_past_expiry(bug, now=NOW, default_days=DEFAULT_EXPIRY_DAYS)

    def test_extension_keeps_bug_in_window(self):
        bug = _bug(
            surfaced_at=NOW - timedelta(days=20),
            extensions=[
                {
                    "extended_at": (NOW - timedelta(days=1)).date().isoformat(),
                    "new_expiry": (NOW + timedelta(days=5)).date().isoformat(),
                    "approver": "@reviewer",
                    "reason": "carry-over to next cycle",
                }
            ],
        )
        assert not bug_is_past_expiry(bug, now=NOW, default_days=DEFAULT_EXPIRY_DAYS)


# ---------------------------------------------------------------------------
# 226.H.process — every bug ticketed/owned/expiry'd within 48 h
# ---------------------------------------------------------------------------


class TestCheckProcess:
    def test_passes_when_ledger_complete(self):
        bug = _bug(surfaced_at=NOW - timedelta(hours=2))
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        assert passed is True
        assert any("[ok]" in m for m in msgs)

    def test_passes_when_grace_period_not_yet_elapsed(self):
        # Ticket missing — but we are still within the 48 h window.
        bug = _bug(surfaced_at=NOW - timedelta(hours=10), ticket="")
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        assert passed is True
        assert any("grace" in m.lower() for m in msgs)

    def test_fails_when_ticket_missing_after_grace(self):
        bug = _bug(surfaced_at=NOW - timedelta(hours=72), ticket="")
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        assert passed is False
        assert any("ticket" in m.lower() and "[FAIL]" in m for m in msgs)

    def test_fails_when_owner_missing_after_grace(self):
        bug = _bug(surfaced_at=NOW - timedelta(hours=72), owner="")
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        assert passed is False
        assert any("owner" in m.lower() and "[FAIL]" in m for m in msgs)

    def test_fails_when_expiry_unresolvable(self):
        bug = _bug(surfaced_at=NOW - timedelta(hours=72), expiry="not-a-date")
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        assert passed is False
        assert any("expiry" in m.lower() and "[FAIL]" in m for m in msgs)

    def test_closed_bugs_not_subject_to_process_gate(self):
        bug = _bug(
            surfaced_at=NOW - timedelta(days=30),
            ticket="",
            owner="",
            status="closed",
            closed_at="2026-04-20T00:00:00Z",
        )
        passed, msgs = check_process(_ledger(bugs=[bug]), now=NOW)
        # Closed bugs are out of scope: don't fail the gate just because the
        # ticket/owner fields were never backfilled before closure.
        assert passed is True

    def test_grace_period_is_configurable_via_ledger(self):
        # ticket_grace_period_hours = 1 — bug surfaced 2h ago is past grace.
        doc = _ledger(
            bugs=[_bug(surfaced_at=NOW - timedelta(hours=2), ticket="")],
            process={"ticket_grace_period_hours": 1},
        )
        passed, _ = check_process(doc, now=NOW)
        assert passed is False


# ---------------------------------------------------------------------------
# 226.H.gate — counts skip events by audit-bug prefix
# ---------------------------------------------------------------------------


class TestCountCategorySkips:
    def test_returns_zero_for_no_matches(self):
        counts = {"S3 not reachable": 5, "Semantic not importable": 2}
        assert count_category_skips(counts, AUDIT_BUG_SKIP_REASON_PREFIX) == 0

    def test_sums_all_matching_reasons(self):
        counts = {
            "audit-exposed bug awaiting fix: AUDIT-BUG-001": 2,
            "audit-exposed bug awaiting fix: AUDIT-BUG-002 — extra detail": 3,
            "S3 not reachable": 4,
        }
        assert count_category_skips(counts, AUDIT_BUG_SKIP_REASON_PREFIX) == 5

    def test_prefix_match_is_case_sensitive(self):
        # Reason strings should be normalised; we don't want fuzzy matches.
        counts = {"Audit-Exposed Bug Awaiting Fix: BUG-001": 3}
        assert count_category_skips(counts, AUDIT_BUG_SKIP_REASON_PREFIX) == 0


# ---------------------------------------------------------------------------
# 226.H.close — end-of-cycle close gate
# ---------------------------------------------------------------------------


class TestCheckClose:
    def test_passes_with_clean_ledger_and_no_skips(self):
        passed, msgs = check_close(
            _ledger(),
            skip_counts={},
            now=NOW,
        )
        assert passed is True

    def test_fails_when_skip_count_above_residual(self):
        counts = {f"audit-exposed bug awaiting fix: B{i}": 1 for i in range(5)}
        passed, msgs = check_close(_ledger(), skip_counts=counts, now=NOW)
        assert passed is False
        assert any("residual" in m.lower() and "[FAIL]" in m for m in msgs)

    def test_passes_at_exactly_residual_max(self):
        counts = {"audit-exposed bug awaiting fix: AUDIT-BUG-001": 3}
        passed, _ = check_close(_ledger(), skip_counts=counts, now=NOW)
        assert passed is True

    def test_fails_when_open_bug_is_past_expiry(self):
        bug = _bug(surfaced_at=NOW - timedelta(days=20))  # > 14 d default
        passed, msgs = check_close(
            _ledger(bugs=[bug]), skip_counts={}, now=NOW,
        )
        assert passed is False
        assert any("past expiry" in m.lower() and "AUDIT-BUG-001" in m for m in msgs)

    def test_passes_when_past_expiry_is_extended(self):
        bug = _bug(
            surfaced_at=NOW - timedelta(days=20),
            extensions=[
                {
                    "extended_at": (NOW - timedelta(days=1)).date().isoformat(),
                    "new_expiry": (NOW + timedelta(days=5)).date().isoformat(),
                    "approver": "@reviewer",
                    "reason": "backend dependency",
                }
            ],
        )
        passed, _ = check_close(_ledger(bugs=[bug]), skip_counts={}, now=NOW)
        assert passed is True

    def test_residual_max_is_configurable(self):
        # cycle.residual_max = 1 — any 2 skips is a fail.
        doc = _ledger(cycle={
            "name": "test-cycle",
            "started_at": "2026-04-24",
            "residual_max": 1,
        })
        counts = {"audit-exposed bug awaiting fix: AUDIT-BUG-001": 2}
        passed, _ = check_close(doc, skip_counts=counts, now=NOW)
        assert passed is False


# ---------------------------------------------------------------------------
# load_ledger + CLI entrypoint
# ---------------------------------------------------------------------------


class TestLoadLedger:
    def test_loads_valid_json(self, tmp_path: Path):
        path = _write_ledger(tmp_path / "audit-bugs.json", _ledger(bugs=[_bug()]))
        doc = load_ledger(path)
        assert doc["schema_version"] == 1
        assert len(doc["bugs"]) == 1

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_ledger(tmp_path / "missing.json")

    def test_malformed_json_raises_with_path(self, tmp_path: Path):
        path = tmp_path / "audit-bugs.json"
        path.write_text("not-json")
        with pytest.raises(ValueError) as exc:
            load_ledger(path)
        assert str(path) in str(exc.value)


class TestCLI:
    def test_process_mode_exits_zero_on_clean_ledger(
        self, tmp_path: Path, capsys
    ):
        path = _write_ledger(
            tmp_path / "ledger.json",
            _ledger(bugs=[_bug(surfaced_at=NOW - timedelta(hours=2))]),
        )
        code = main([
            "--mode", "process",
            "--ledger", str(path),
            "--now", NOW.isoformat(),
        ])
        assert code == 0
        out = capsys.readouterr().out
        assert "[ok]" in out

    def test_process_mode_exits_nonzero_on_missing_ticket(
        self, tmp_path: Path, capsys
    ):
        path = _write_ledger(
            tmp_path / "ledger.json",
            _ledger(bugs=[_bug(
                surfaced_at=NOW - timedelta(hours=72),
                ticket="",
            )]),
        )
        code = main([
            "--mode", "process",
            "--ledger", str(path),
            "--now", NOW.isoformat(),
        ])
        assert code == 1
        assert "[FAIL]" in capsys.readouterr().out

    def test_close_mode_reads_skip_artifact_dir(self, tmp_path: Path, capsys):
        # 4 events: above the default residual_max of 3.
        skip_dir = tmp_path / "test-results"
        skip_dir.mkdir()
        events = [
            {"test": f"t{i}", "reason": f"audit-exposed bug awaiting fix: AUDIT-BUG-001 case-{i}"}
            for i in range(4)
        ]
        (skip_dir / "skip-events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n"
        )
        path = _write_ledger(tmp_path / "ledger.json", _ledger())
        code = main([
            "--mode", "close",
            "--ledger", str(path),
            "--artifact-dir", str(skip_dir),
            "--now", NOW.isoformat(),
        ])
        assert code == 1
        out = capsys.readouterr().out
        assert "residual" in out.lower()

    def test_validate_mode_runs_schema_only(self, tmp_path: Path, capsys):
        path = _write_ledger(tmp_path / "ledger.json", _ledger())
        code = main([
            "--mode", "validate",
            "--ledger", str(path),
        ])
        assert code == 0

    def test_validate_mode_fails_on_bad_schema(self, tmp_path: Path, capsys):
        path = tmp_path / "ledger.json"
        path.write_text(json.dumps({"schema_version": 99, "bugs": []}))
        code = main([
            "--mode", "validate",
            "--ledger", str(path),
        ])
        assert code == 1

    def test_emit_gate_config_prints_canonical_constants(self, capsys):
        # The skip-counter consumes these — they must be programmatically
        # discoverable so the CI step can pass them through without drift.
        code = main(["--mode", "emit-gate-config"])
        assert code == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["skip_reason_prefix"] == AUDIT_BUG_SKIP_REASON_PREFIX
        assert payload["category_threshold"] == DEFAULT_CATEGORY_THRESHOLD


# ---------------------------------------------------------------------------
# Canonical helper for test authors emitting audit-bug skips
# ---------------------------------------------------------------------------
#
# Without this helper, a test author writing
#     pytest.skip("audit exposed bug AUDIT-BUG-001")    # missing hyphen
# silently bypasses the gate. The canonical-prefix constant is the contract
# between the ledger, the gate, and the test code; the helper makes
# adherence trivial.


class TestAuditBugSkipHelper:
    """The helper lives at tests/e2e/_guards/_skip_counter.py so that test
    authors can `from tests.e2e._guards import audit_bug_skip_reason` and
    pass the result to `pytest.skip(...)`.

    The cross-validation tests below assert that the prefix constant in
    `_skip_counter.py` matches the one in `check_audit_bug_ledger.py` —
    drift between them would silently disable the gate.
    """

    def test_helper_returns_canonical_prefix(self):
        from tests.e2e._guards._skip_counter import audit_bug_skip_reason
        reason = audit_bug_skip_reason("AUDIT-BUG-001")
        assert reason.startswith(AUDIT_BUG_SKIP_REASON_PREFIX)
        assert "AUDIT-BUG-001" in reason

    def test_helper_includes_optional_detail(self):
        from tests.e2e._guards._skip_counter import audit_bug_skip_reason
        reason = audit_bug_skip_reason(
            "AUDIT-BUG-001", "tenant switch not audited"
        )
        assert reason.startswith(AUDIT_BUG_SKIP_REASON_PREFIX)
        assert "AUDIT-BUG-001" in reason
        assert "tenant switch not audited" in reason

    def test_helper_rejects_empty_bug_id(self):
        from tests.e2e._guards._skip_counter import audit_bug_skip_reason
        with pytest.raises(ValueError):
            audit_bug_skip_reason("")
        with pytest.raises(ValueError):
            audit_bug_skip_reason("   ")

    def test_helper_rejects_id_without_audit_bug_prefix(self):
        # "AUDIT-BUG-001" is the canonical id form. A plain "1" or
        # "Issue#42" is too easy to typo into something the close gate
        # can't link back to a ledger entry.
        from tests.e2e._guards._skip_counter import audit_bug_skip_reason
        with pytest.raises(ValueError):
            audit_bug_skip_reason("42")
        with pytest.raises(ValueError):
            audit_bug_skip_reason("Issue#42")

    def test_prefix_matches_canonical_source_of_truth(self):
        """Cross-check: both modules MUST agree on the prefix string.

        If a future edit changes either constant in isolation, this
        test fails immediately and points at the contract violation.
        """
        from tests.e2e._guards._skip_counter import (
            AUDIT_BUG_SKIP_REASON_PREFIX as RECORDER_PREFIX,
        )
        assert RECORDER_PREFIX == AUDIT_BUG_SKIP_REASON_PREFIX

    def test_helper_output_matches_ledger_recognised_format(self):
        """End-to-end: a reason produced by the helper IS counted by the
        ledger validator's category-counting helper.

        This is the contract that protects 226.H.gate from drift.
        """
        from tests.e2e._guards._skip_counter import audit_bug_skip_reason
        reason = audit_bug_skip_reason("AUDIT-BUG-001", "demo")
        counts = {reason: 5}
        assert count_category_skips(
            counts, AUDIT_BUG_SKIP_REASON_PREFIX
        ) == 5

    def test_recorder_to_close_gate_pipeline(self, tmp_path: Path):
        """Full pipeline: record_skip(audit_bug_skip_reason(...)) →
        skip-events.jsonl → close gate aggregation. This is the
        end-to-end contract that 226.H.close depends on.
        """
        import os
        from tests.e2e._guards._skip_counter import (
            audit_bug_skip_reason,
            record_skip,
        )

        # Override the artifact path to write inside the test's tmp_path.
        artifact = tmp_path / "test-results" / "skip-events.jsonl"
        os.environ["PYTEST_SKIP_EVENTS_PATH"] = str(artifact)
        try:
            for i in range(4):
                record_skip(
                    nodeid=f"tests/e2e/test_x.py::test_{i}",
                    reason=audit_bug_skip_reason(
                        "AUDIT-BUG-001", f"case {i}"
                    ),
                )
        finally:
            del os.environ["PYTEST_SKIP_EVENTS_PATH"]

        # Write a minimal ledger and run the close gate via main().
        ledger_path = _write_ledger(tmp_path / "ledger.json", _ledger())
        code = main([
            "--mode", "close",
            "--ledger", str(ledger_path),
            "--artifact-dir", str(tmp_path / "test-results"),
            "--now", NOW.isoformat(),
        ])
        # 4 skips > the default residual_max=3 → close gate fails.
        assert code == 1
