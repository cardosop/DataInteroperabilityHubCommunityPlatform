"""TDD suite for GATE-40 — ``scripts/check_skip_expiry.py`` (Phase T.5 / W17).

The contract under test:

Annotation format (documented in the gate docstring):
  ``TICKET=<id> EXPIRES=<YYYY-MM-DD>`` inside the reason string of every
  ``skip``/``fixme``/``xfail`` site; placeholder-bodied tests carry the
  same tokens in a leading comment inside the body.

Gate semantics:
  * EXPIRED annotated sites (EXPIRES before today) FAIL always — even if
    baselined. Scaffold debt must never silently re-activate.
  * UNANNOTATED sites are counted per bucket and ratcheted: growth over the
    committed baseline fails (the W8.1 falsifiability standard applies —
    a RED fixture proves the gate bites on its target class).
  * Annotated, unexpired sites are owned debt — clean.
  * Placeholder-bodied tests (comment-only bodies, and the Phase-105
    export-existence stub class) are counted as debt even when annotated.

No mocks: synthetic files written to real temp dirs, scanned by the real
scanner; the real-repo assertions run against the committed baseline.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_skip_expiry as gate

TODAY = datetime.now(UTC).date()
PAST = (TODAY - timedelta(days=30)).isoformat()
FUTURE = (TODAY + timedelta(days=365)).isoformat()
ANNOT = f"TICKET=PREPRO01-1 EXPIRES={FUTURE}"
EXPIRED_ANNOT = f"TICKET=PREPRO01-1 EXPIRES={PAST}"


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def baseline(tmp_path: Path, counts: dict[str, int]) -> Path:
    payload = {"generated_at": datetime.now(UTC).isoformat(), **counts}
    b = tmp_path / "baseline.json"
    b.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return b


def run_scan(tmp_path: Path):
    """Run the gate's analyze step over tmp_path and return the report."""
    return gate.analyze_roots(
        python_roots=[str(tmp_path / "py")],
        ts_roots=[str(tmp_path / "ts")],
    )


# ── Python skip-site extraction ──────────────────────────────────────────────


class TestPythonSkipExtraction:
    def test_annotated_mark_skip_is_clean(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.skip(reason="legacy [{ANNOT}]")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 0
        assert report["expired"] == []

    def test_expired_mark_skip_is_reported(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.skip(reason="legacy [{EXPIRED_ANNOT}]")\ndef test_x():\n    assert True\n',
        )
        report = run_scan(tmp_path)
        assert len(report["expired"]) == 1
        assert "test_a.py" in report["expired"][0]["file"]

    def test_unannotated_mark_skip_counted(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skip(reason="legacy debt")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 1

    def test_pytest_skip_call_counted(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\ndef test_x():\n    pytest.skip("service down")\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 1

    def test_skipif_counted_separately(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skipif(True, reason="needs network")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skipif_sites"]["unannotated"] == 1
        assert report["python_skip_sites"]["unannotated"] == 0

    def test_annotated_xfail_is_clean(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.xfail(reason="known [{ANNOT}]")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 0

    def test_ticket_missing_is_unannotated(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.skip(reason="legacy [EXPIRES={FUTURE}]")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 1

    def test_expiry_missing_is_unannotated(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skip(reason="legacy [TICKET=PREPRO01-1]")\ndef test_x():\n    pass\n',
        )
        report = run_scan(tmp_path)
        assert report["python_skip_sites"]["unannotated"] == 1


# ── TS skip-site extraction ──────────────────────────────────────────────────


class TestTsSkipExtraction:
    def test_annotated_test_skip_is_clean(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", f"test.skip(true, 'not implemented [{ANNOT}]');\n")
        report = run_scan(tmp_path)
        assert report["ts_skip_sites"]["unannotated"] == 0

    def test_expired_test_skip_reported(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", f"test.skip(true, 'not implemented [{EXPIRED_ANNOT}]');\n")
        report = run_scan(tmp_path)
        assert len(report["expired"]) == 1

    def test_unannotated_test_skip_counted(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", "test.skip(true, 'UC journey not yet implemented');\n")
        report = run_scan(tmp_path)
        assert report["ts_skip_sites"]["unannotated"] == 1

    def test_fixme_counted(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", "test.fixme(true, 'flaky');\n")
        report = run_scan(tmp_path)
        assert report["ts_skip_sites"]["unannotated"] == 1

    def test_conditional_skip_with_reason_counted(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", "test.skip(process.env.CI === '1', 'env-only');\n")
        report = run_scan(tmp_path)
        assert report["ts_skip_sites"]["unannotated"] == 1

    def test_describe_skip_counted(self, tmp_path):
        write(tmp_path, "ts/x.spec.ts", "test.describe.skip('whole suite', () => {});\n")
        report = run_scan(tmp_path)
        assert report["ts_skip_sites"]["unannotated"] == 1


# ── Placeholder detection ────────────────────────────────────────────────────


class TestPythonPlaceholders:
    def test_comment_only_body_is_placeholder(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            "def test_x():\n    # everything below is TODO\n    # assert something\n    pass\n",
        )
        report = run_scan(tmp_path)
        assert report["python_placeholder_tests"]["total"] == 1

    def test_pass_only_body_is_placeholder(self, tmp_path):
        write(tmp_path, "py/test_a.py", "def test_x():\n    pass\n")
        report = run_scan(tmp_path)
        assert report["python_placeholder_tests"]["total"] == 1

    def test_real_body_is_not_placeholder(self, tmp_path):
        write(tmp_path, "py/test_a.py", "def test_x():\n    assert 1 + 1 == 2\n")
        report = run_scan(tmp_path)
        assert report["python_placeholder_tests"]["total"] == 0

    def test_annotated_placeholder_is_not_unannotated(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            f"def test_x():\n    # {ANNOT}\n    # real E2E pending backend\n    pass\n",
        )
        report = run_scan(tmp_path)
        assert report["python_placeholder_tests"]["total"] == 1
        assert report["python_placeholder_tests"]["unannotated"] == 0

    def test_expired_annotated_placeholder_fails(self, tmp_path):
        write(tmp_path, "py/test_a.py", f"def test_x():\n    # {EXPIRED_ANNOT}\n    pass\n")
        report = run_scan(tmp_path)
        assert len(report["expired"]) == 1


class TestTsPlaceholders:
    def test_comment_only_body_is_placeholder(self, tmp_path):
        write(
            tmp_path,
            "ts/x.spec.ts",
            "it('does things', () => {\n"
            "  // const x = await api();\n"
            "  // expect(x).toBeDefined();\n"
            "});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 1

    def test_export_existence_stub_is_placeholder(self, tmp_path):
        write(
            tmp_path,
            "ts/x.spec.ts",
            "import * as m from './mod';\n"
            "it('exports useThing', () => {\n"
            "  expect(typeof m.useThing).toBe('function');\n"
            "});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 1

    def test_tautology_assertion_body_is_placeholder(self, tmp_path):
        # The W17 evidence class: sdk/js e2e.test.ts "ready for real E2E"
        # bodies — commented-out real calls + expect(true).toBe(true).
        write(
            tmp_path,
            "ts/x.spec.ts",
            "it('does the journey', async () => {\n"
            "  // const created = await api.create({ ... });\n"
            "  // expect(created.id).not.toBeUndefined();\n"
            "  expect(true).toBe(true); // Placeholder assertion\n"
            "});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 1

    def test_real_expectation_is_not_placeholder(self, tmp_path):
        write(
            tmp_path,
            "ts/x.spec.ts",
            "it('asserts a value', () => {\n  expect(2 + 2).toBe(4);\n});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 0

    def test_real_assertion_is_not_placeholder(self, tmp_path):
        write(
            tmp_path,
            "ts/x.spec.ts",
            "it('formats', () => {\n"
            "  const result = formatCurrency(999, 'USD');\n"
            "  expect(result).toContain('9.99');\n"
            "});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 0

    def test_annotated_ts_placeholder_is_not_unannotated(self, tmp_path):
        write(
            tmp_path,
            "ts/x.spec.ts",
            f"it('does things', () => {{\n  // {ANNOT}\n  // real E2E pending\n}});\n",
        )
        report = run_scan(tmp_path)
        assert report["ts_placeholder_tests"]["total"] == 1
        assert report["ts_placeholder_tests"]["unannotated"] == 0


# ── Ratchet + expiry semantics ───────────────────────────────────────────────


class TestRatchetSemantics:
    def test_growth_over_baseline_fails(self, tmp_path):
        b = baseline(tmp_path, {"python_skip_sites": 0})
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skip(reason="new unannotated debt")\ndef test_x():\n    assert True\n',
        )
        assert gate.verify(run_scan(tmp_path), b, today=TODAY) != 0

    def test_within_baseline_passes(self, tmp_path):
        b = baseline(
            tmp_path,
            {
                "python_skip_sites": 1,
                "ts_skip_sites": 0,
                "python_skipif_sites": 0,
                "python_placeholder_tests": 0,
                "ts_placeholder_tests": 0,
            },
        )
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skip(reason="legacy debt")\ndef test_x():\n    assert True\n',
        )
        assert gate.verify(run_scan(tmp_path), b, today=TODAY) == 0

    def test_expired_fails_even_under_baseline(self, tmp_path):
        b = baseline(
            tmp_path,
            {
                "python_skip_sites": 1,
                "ts_skip_sites": 0,
                "python_skipif_sites": 0,
                "python_placeholder_tests": 0,
                "ts_placeholder_tests": 0,
            },
        )
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.skip(reason="legacy [{EXPIRED_ANNOT}]")\ndef test_x():\n    assert True\n',
        )
        # Annotated → not in the unannotated count → no growth; the expiry
        # must still fail the gate.
        assert gate.verify(run_scan(tmp_path), b, today=TODAY) != 0

    def test_annotated_sites_do_not_grow_the_bucket(self, tmp_path):
        b = baseline(
            tmp_path,
            {
                "python_skip_sites": 1,
                "ts_skip_sites": 0,
                "python_skipif_sites": 0,
                "python_placeholder_tests": 0,
                "ts_placeholder_tests": 0,
            },
        )
        write(
            tmp_path,
            "py/test_a.py",
            f'import pytest\n@pytest.mark.skip(reason="owned [{ANNOT}]")\ndef test_x():\n    assert True\n',
        )
        assert gate.verify(run_scan(tmp_path), b, today=TODAY) == 0


# ── Debt reporting ───────────────────────────────────────────────────────────


class TestDebtReport:
    def test_debt_count_sums_unannotated_and_placeholders(self, tmp_path):
        write(
            tmp_path,
            "py/test_a.py",
            'import pytest\n@pytest.mark.skip(reason="legacy debt")\ndef test_a():\n    assert True\n'
            "def test_b():\n    pass\n",
        )
        report = run_scan(tmp_path)
        assert report["debt"] == 2  # 1 unannotated skip + 1 placeholder
