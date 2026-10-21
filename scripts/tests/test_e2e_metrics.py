"""TDD tests for scripts/e2e_metrics.py.

These tests define the required behavior of the E2E metrics baseline script.
They use deterministic fixtures in scripts/tests/fixtures/{python,typescript}/.

Run:
    pytest scripts/tests/test_e2e_metrics.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from e2e_metrics import (
    aggregate_metrics,
    count_python_metrics,
    count_typescript_metrics,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PY_SWALLOWS = FIXTURES / "python" / "fixture_swallows.py"
PY_CLEAN = FIXTURES / "python" / "fixture_clean.py"
PY_ORM_STATUS = FIXTURES / "python" / "fixture_orm_status.py"
PY_UNITTEST_STYLE = FIXTURES / "python" / "fixture_unittest_style.py"
TS_SKIPS = FIXTURES / "typescript" / "fixture_skips.spec.ts"
TS_PAGEERROR = FIXTURES / "typescript" / "fixture_pageerror.spec.ts"
TS_VERIFY_API = FIXTURES / "typescript" / "fixture_verify_api.spec.ts"


# --------------------------------------------------------------------- Python


class TestPythonMetrics:
    def test_swallows_fixture_counts(self):
        m = count_python_metrics(PY_SWALLOWS)
        assert m["except_exception_pass"] == 2, (
            "Expected exactly 2 bare/except-Exception + pass swallows; "
            "comments and handlers with real bodies must be excluded."
        )
        assert m["orm_query"] == 0
        assert m["status_code_assertion"] == 0
        assert m["test_skip_call"] == 0

    def test_clean_fixture_counts(self):
        m = count_python_metrics(PY_CLEAN)
        assert m == {
            "except_exception_pass": 0,
            "orm_query": 0,
            "status_code_assertion": 0,
            "test_skip_call": 0,
        }

    def test_orm_status_fixture_counts(self):
        m = count_python_metrics(PY_ORM_STATUS)
        assert m["except_exception_pass"] == 0
        assert m["orm_query"] == 3, (
            "Should count Asset.objects.get, Asset.objects.filter, Dataset.objects.create"
        )
        assert m["status_code_assertion"] == 3, "Should count == 201, == 200, != 500"
        assert m["test_skip_call"] == 1, "pytest.skip() should count"

    def test_unittest_style_status_assertions(self):
        """unittest.TestCase style `self.assertEqual(resp.status_code, N)` must count."""
        m = count_python_metrics(PY_UNITTEST_STYLE)
        assert m["except_exception_pass"] == 0
        assert m["status_code_assertion"] == 4, (
            "assertEqual, assertNotEqual, assertIn, assertGreaterEqual each "
            "reference .status_code and must count"
        )
        assert m["test_skip_call"] == 1, "self.skipTest() counts"
        assert m["orm_query"] == 0

    def test_syntax_error_file_is_reported_not_swallowed(self, tmp_path: Path):
        bad = tmp_path / "broken.py"
        bad.write_text("def f(:\n    pass\n")
        with pytest.raises(SyntaxError):
            count_python_metrics(bad)


# --------------------------------------------------------------------- TypeScript


class TestTypescriptMetrics:
    @pytest.fixture(autouse=True)
    def _ensure_node_available(self):
        try:
            subprocess.run(["node", "--version"], check=True, capture_output=True, timeout=10)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("node not available on PATH — TypeScript metrics cannot be tested")

    def test_skips_fixture_counts(self):
        m = count_typescript_metrics([TS_SKIPS])[str(TS_SKIPS)]
        assert m["test_skip_true"] == 3
        assert m["page_on_pageerror"] == 0
        assert m["page_request_call"] == 0
        assert m["verify_via_api_call"] == 0

    def test_pageerror_fixture_counts(self):
        m = count_typescript_metrics([TS_PAGEERROR])[str(TS_PAGEERROR)]
        assert m["page_on_pageerror"] == 2
        assert m["test_skip_true"] == 0

    def test_verify_api_fixture_counts(self):
        m = count_typescript_metrics([TS_VERIFY_API])[str(TS_VERIFY_API)]
        assert m["page_request_call"] == 3
        assert m["verify_via_api_call"] == 1

    def test_batch_all_three(self):
        # All fixtures in one invocation — ensures the Node helper handles batches
        results = count_typescript_metrics([TS_SKIPS, TS_PAGEERROR, TS_VERIFY_API])
        assert set(results.keys()) == {str(TS_SKIPS), str(TS_PAGEERROR), str(TS_VERIFY_API)}


# --------------------------------------------------------------------- Aggregation


class TestAggregation:
    def test_aggregate_sums_python(self):
        result = aggregate_metrics(
            python_files=[PY_SWALLOWS, PY_CLEAN, PY_ORM_STATUS],
            typescript_files=[],
        )
        py = result["pytest"]
        assert py["except_exception_pass_count"] == 2
        assert py["orm_query_count"] == 3
        assert py["status_code_assertion_count"] == 3
        assert py["test_skip_call_count"] == 1

    def test_aggregate_by_file_python(self):
        result = aggregate_metrics(
            python_files=[PY_SWALLOWS, PY_CLEAN],
            typescript_files=[],
        )
        by_file = result["pytest"]["except_exception_pass_by_file"]
        # Paths are normalised to repo-relative so diffs are portable
        expected_key = "scripts/tests/fixtures/python/fixture_swallows.py"
        clean_key = "scripts/tests/fixtures/python/fixture_clean.py"
        assert by_file[expected_key] == 2, f"got keys: {list(by_file)}"
        assert clean_key not in by_file, "Files with zero count must be omitted"

    def test_aggregate_sums_typescript(self):
        try:
            subprocess.run(["node", "--version"], check=True, capture_output=True, timeout=10)
        except (FileNotFoundError, subprocess.CalledProcessError):
            pytest.skip("node not available")

        result = aggregate_metrics(
            python_files=[],
            typescript_files=[TS_SKIPS, TS_PAGEERROR, TS_VERIFY_API],
        )
        pw = result["playwright"]
        assert pw["test_skip_true_count"] == 3
        assert pw["page_on_pageerror_count"] == 2
        assert pw["page_request_call_count"] == 3
        assert pw["verify_via_api_call_count"] == 1

    def test_output_schema_has_version_and_timestamp(self):
        result = aggregate_metrics(python_files=[PY_CLEAN], typescript_files=[])
        assert result["schema_version"] == 1
        assert "generated_at" in result
        # timestamp is ISO-8601
        from datetime import datetime

        datetime.fromisoformat(result["generated_at"])


# --------------------------------------------------------------------- CLI


class TestCLI:
    def test_cli_outputs_valid_json(self, tmp_path: Path):
        out = tmp_path / "metrics.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "e2e_metrics.py"),
                "--pytest-dir",
                str(FIXTURES / "python"),
                "--playwright-dir",
                str(FIXTURES / "typescript"),
                "--output",
                str(out),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        data = json.loads(out.read_text())
        assert data["schema_version"] == 1
        assert data["pytest"]["except_exception_pass_count"] == 2
        assert data["pytest"]["orm_query_count"] == 3
        # Playwright counts are gated on node availability; omit strict assertion
