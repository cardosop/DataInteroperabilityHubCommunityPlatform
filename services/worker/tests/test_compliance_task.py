"""
Tests for services/worker/tasks/compliance.py — Phase 19.12.2

Validates:
  - compliance_scan_job runs the full pipeline and writes COMPLETED to Redis
  - compliance_scan_job writes FAILED to Redis and re-raises on exception
  - Error sanitisation strips card / SSN / email patterns
  - _get_redis_client resolution order (env vars → django_rq fallback)
  - Result key helper produces the expected Redis key
  - Task is importable at its canonical dotted path

All compliance_engine internals (PIIDetector, PolicyEngine, etc.) are
stubbed so the test suite has no dependency on the compliance-service
source tree.

pandas and pyarrow ARE imported at module level here because:
  1. compliance_scan_job imports them as deferred intra-function imports.
  2. Python 3.12's unittest.mock.patch.dict takes a full snapshot of
     sys.modules at __enter__ time and CLEARS + RESTORES the entire dict
     at __exit__ time.  Any module imported *inside* a patch.dict block
     that was not already in sys.modules at block entry is deleted when
     the block exits.  Without these pre-imports, the first test that
     calls compliance_scan_job imports pandas/numpy inside the block;
     subsequent tests see them missing from sys.modules and the deferred
     `import pandas` inside the task fails with
     "numpy: cannot load module more than once per process".
  3. Both packages are present in the worker Docker image (requirements.txt)
     so this adds no new runtime dependency.
"""
from __future__ import annotations

import base64
import importlib
import json
import os
import sys
import types
from unittest.mock import MagicMock, patch

import pandas as _pd_preload  # noqa: F401,E501
import pyarrow as _pa_preload  # noqa: F401,E501
import pytest


# -------------------------------------------------------------------
# Helpers to build a minimal compliance_engine stub tree
# -------------------------------------------------------------------

def _make_finding(
    column: str = "email",
    category: str = "EMAIL_ADDRESS",
):
    f = MagicMock()
    f.column_name = column
    f.pii_category = category
    return f


def _make_policy_decision(
    allowed: bool = True,
    status: str = "PASS",
    issues: list | None = None,
    cross_border_regulations: list | None = None,
    localization_regulations: list | None = None,
    estimated_affected_rows: int = 0,
):
    d = MagicMock()
    d.allowed = allowed
    d.status = status
    d.issues = issues or []
    d.cross_border_regulations = cross_border_regulations or []
    d.localization_regulations = localization_regulations or []
    d.estimated_affected_rows = estimated_affected_rows
    return d


def _stub_compliance_engine():
    """Inject a minimal compliance_engine stub into sys.modules."""
    finding = _make_finding()
    decision = _make_policy_decision()

    pii_detector_mock = MagicMock()
    pii_detector_mock.detect_pii.return_value = [finding]

    risk_calc_mock = MagicMock()
    risk_calc_mock.calculate_risk_score.return_value = 0.1
    risk_level_mock = MagicMock()
    risk_level_mock.value = "LOW"
    risk_calc_mock.determine_risk_level.return_value = risk_level_mock

    policy_mock = MagicMock()
    policy_mock.evaluate.return_value = decision

    report_gen_mock = MagicMock()
    report_gen_mock.generate_report.return_value = {
        "overall_status": "PASS",
        "risk_level": "LOW",
        "allowed_to_store": True,
        "applicable_regulations": ["GDPR"],
    }

    PIIDetector_cls = MagicMock(return_value=pii_detector_mock)
    RiskCalculator_cls = MagicMock(return_value=risk_calc_mock)
    PolicyEngine_cls = MagicMock(return_value=policy_mock)
    ComplianceReport_cls = MagicMock(return_value=report_gen_mock)
    PolicyDecision_cls = MagicMock

    engine_mod = types.ModuleType("compliance_engine")
    engine_mod.PIIDetector = PIIDetector_cls
    engine_mod.RiskCalculator = RiskCalculator_cls
    engine_mod.PolicyEngine = PolicyEngine_cls
    engine_mod.PolicyDecision = PolicyDecision_cls
    engine_mod.ComplianceReport = ComplianceReport_cls

    audit_mod = types.ModuleType("audit_logger")
    audit_logger_inst = MagicMock()
    audit_mod.AuditLogger = MagicMock(return_value=audit_logger_inst)

    return (
        engine_mod,
        audit_mod,
        report_gen_mock.generate_report.return_value,
    )


def _reload_task_module(extra_env: dict | None = None):
    """
    Load (or reload) services.worker.tasks.compliance with
    compliance_engine and audit_logger stubs active.
    """
    engine_mod, audit_mod, _ = _stub_compliance_engine()

    stubs = {
        "compliance_engine": engine_mod,
        "audit_logger": audit_mod,
    }

    # Remove cached version so import picks up stubs.
    for key in list(sys.modules):
        if "services.worker.tasks.compliance" in key:
            del sys.modules[key]

    env_patch = extra_env or {}
    with (
        patch.dict(sys.modules, stubs),
        patch.dict(os.environ, env_patch),
    ):
        spec_path = os.path.join(
            os.path.dirname(__file__), "..", "tasks", "compliance.py",
        )
        spec = importlib.util.spec_from_file_location(
            "services.worker.tasks.compliance", spec_path,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod, engine_mod, audit_mod


# -------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------

@pytest.fixture()
def task_module():
    mod, _, _ = _reload_task_module()
    return mod


@pytest.fixture()
def csv_payload():
    """Minimal CSV payload with one email column."""
    import io
    buf = io.StringIO("email\ntest@example.com\n")
    b64 = base64.b64encode(buf.getvalue().encode()).decode()
    return {
        "file_content_b64": b64,
        "file_format": "csv",
        "tenant_id": "tenant-abc",
        "applicable_regulations": ["GDPR"],
        "legal_basis": "consent",
        "retention_seconds": 86400,
        "correlation_id": "corr-123",
        "actor": "user-1",
        "filename": "data.csv",
    }


# -------------------------------------------------------------------
# Result key helper
# -------------------------------------------------------------------

class TestResultKey:
    def test_prefix_and_job_id(self, task_module):
        assert (
            task_module._result_key("abc-123")
            == "compliance:result:abc-123"
        )

    def test_empty_job_id(self, task_module):
        assert task_module._result_key("") == "compliance:result:"


# -------------------------------------------------------------------
# _write_result
# -------------------------------------------------------------------

class TestWriteResult:
    def test_sets_json_with_ttl(self, task_module):
        redis_mock = MagicMock()
        task_module._write_result(
            redis_mock,
            "job-1",
            {"status": "COMPLETED", "job_id": "job-1", "result": {}},
        )
        redis_mock.set.assert_called_once()
        key, value = redis_mock.set.call_args[0]
        assert key == "compliance:result:job-1"
        parsed = json.loads(value)
        assert parsed["status"] == "COMPLETED"
        assert parsed["job_id"] == "job-1"
        assert "result" in parsed
        assert (
            redis_mock.set.call_args[1]["ex"]
            == task_module.RESULT_TTL_SECONDS
        )

    def test_swallows_redis_error(self, task_module, caplog):
        """Redis SET failure must not propagate."""
        redis_mock = MagicMock()
        redis_mock.set.side_effect = ConnectionError("redis down")
        import logging
        with caplog.at_level(logging.ERROR):
            task_module._write_result(
                redis_mock, "job-2", {"status": "COMPLETED"},
            )
        # Should not raise
        assert any(
            "result_write_failed" in m for m in caplog.messages
        )


# -------------------------------------------------------------------
# _get_redis_client resolution order
# -------------------------------------------------------------------

class TestGetRedisClient:
    def test_uses_redis_queue_url_first(self, task_module):
        with patch.dict(
            os.environ,
            {"REDIS_QUEUE_URL": "redis://localhost:6379/1"},
            clear=False,
        ):
            with patch("redis.from_url") as mock_from_url:
                mock_from_url.return_value = MagicMock()
                task_module._get_redis_client()
                mock_from_url.assert_called_once_with(
                    "redis://localhost:6379/1",
                    decode_responses=False,
                    socket_connect_timeout=5,
                )

    def test_falls_back_to_rq_redis_url(self, task_module):
        env = {
            k: v for k, v in os.environ.items()
            if k != "REDIS_QUEUE_URL"
        }
        env["RQ_REDIS_URL"] = "redis://localhost:6379/2"
        with patch.dict(os.environ, env, clear=True):
            with patch("redis.from_url") as mock_from_url:
                mock_from_url.return_value = MagicMock()
                task_module._get_redis_client()
                # Verify URL AND connection params match
                mock_from_url.assert_called_once_with(
                    "redis://localhost:6379/2",
                    decode_responses=False,
                    socket_connect_timeout=5,
                )

    def test_falls_back_to_django_rq(self, task_module):
        """When no URL env var is set, falls back to
        django_rq.get_connection."""
        env = {
            k: v for k, v in os.environ.items()
            if k not in (
                "REDIS_QUEUE_URL", "RQ_REDIS_URL", "REDIS_URL",
            )
        }
        fake_conn = MagicMock()
        django_rq_mock = MagicMock()
        django_rq_mock.get_connection.return_value = fake_conn

        with (
            patch.dict(os.environ, env, clear=True),
            patch.dict(sys.modules, {"django_rq": django_rq_mock}),
        ):
            result = task_module._get_redis_client()
            assert result is fake_conn
            django_rq_mock.get_connection.assert_called_once_with(
                "job_default",
            )

    def test_raises_when_no_redis_available(self, task_module):
        """When no env var and django_rq fails, RuntimeError."""
        env = {
            k: v for k, v in os.environ.items()
            if k not in (
                "REDIS_QUEUE_URL", "RQ_REDIS_URL", "REDIS_URL",
            )
        }
        django_rq_mock = MagicMock()
        django_rq_mock.get_connection.side_effect = ImportError(
            "no django_rq",
        )

        with (
            patch.dict(os.environ, env, clear=True),
            patch.dict(sys.modules, {"django_rq": django_rq_mock}),
            pytest.raises(RuntimeError, match="No Redis URL found"),
        ):
            task_module._get_redis_client()


# -------------------------------------------------------------------
# compliance_scan_job — success path
# -------------------------------------------------------------------

class TestComplianceScanJobSuccess:
    def _run(self, csv_payload, engine_mod, task_mod,
             audit_mod=None):
        if audit_mod is None:
            _, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()
        with (
            patch.object(
                task_mod, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
        ):
            result = task_mod.compliance_scan_job(
                "job-xyz", csv_payload,
            )
        return result, redis_mock

    def test_returns_complete_report_dict(
        self, task_module, csv_payload,
    ):
        """Return value includes all report fields."""
        engine_mod, _, _ = _stub_compliance_engine()
        result, _ = self._run(csv_payload, engine_mod, task_module)
        assert result["overall_status"] == "PASS"
        assert result["risk_level"] == "LOW"
        assert result["allowed_to_store"] is True
        assert result["applicable_regulations"] == ["GDPR"]

    def test_writes_completed_to_redis(
        self, task_module, csv_payload,
    ):
        engine_mod, _, _ = _stub_compliance_engine()
        _, redis_mock = self._run(
            csv_payload, engine_mod, task_module,
        )

        redis_mock.set.assert_called_once()
        key, value = redis_mock.set.call_args[0]
        assert key == "compliance:result:job-xyz"
        payload = json.loads(value)
        assert payload["status"] == "COMPLETED"
        assert payload["job_id"] == "job-xyz"
        assert payload["result"]["overall_status"] == "PASS"

    def test_result_ttl_is_3600(self, task_module, csv_payload):
        engine_mod, _, _ = _stub_compliance_engine()
        _, redis_mock = self._run(
            csv_payload, engine_mod, task_module,
        )
        ttl = redis_mock.set.call_args[1]["ex"]
        assert ttl == 3600

    def test_pipeline_receives_correct_data(
        self, task_module, csv_payload,
    ):
        """Each pipeline stage receives output from the
        previous stage, not arbitrary data."""
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()
        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
        ):
            task_module.compliance_scan_job(
                "job-xyz", csv_payload,
            )

        pii_inst = engine_mod.PIIDetector.return_value
        risk_inst = engine_mod.RiskCalculator.return_value
        policy_inst = engine_mod.PolicyEngine.return_value
        report_inst = engine_mod.ComplianceReport.return_value

        # Each stage called exactly once
        pii_inst.detect_pii.assert_called_once()
        risk_inst.calculate_risk_score.assert_called_once()
        risk_inst.determine_risk_level.assert_called_once()
        policy_inst.evaluate.assert_called_once()
        report_inst.generate_report.assert_called_once()

        # Data flows: detect_pii output → risk_calc input
        findings = pii_inst.detect_pii.return_value
        risk_args = risk_inst.calculate_risk_score.call_args[0]
        assert risk_args[0] is findings

        # risk_score → determine_risk_level
        risk_score = risk_inst.calculate_risk_score.return_value
        level_args = risk_inst.determine_risk_level.call_args[0]
        assert level_args[0] is risk_score

        # findings + risk_score → policy.evaluate
        eval_args = policy_inst.evaluate.call_args[0]
        assert eval_args[0] is findings
        assert eval_args[1] is risk_score

        # generate_report receives correct kwargs
        report_kwargs = report_inst.generate_report.call_args[1]
        assert report_kwargs["findings"] is findings
        assert report_kwargs["risk_score"] is risk_score
        assert report_kwargs["allowed_to_store"] is True
        assert report_kwargs["compliance_status"] == "PASS"

    def test_audit_logger_receives_all_fields(
        self, task_module, csv_payload,
    ):
        """Audit log receives correct values for all kwargs."""
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()
        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
        ):
            task_module.compliance_scan_job("job-xyz", csv_payload)

        audit_inst = audit_mod.AuditLogger.return_value
        audit_inst.log_scan.assert_called_once()
        kw = audit_inst.log_scan.call_args[1]
        assert kw["action"] == "scan_file_worker"
        assert kw["tenant_id"] == "tenant-abc"
        assert kw["actor"] == "user-1"
        assert kw["correlation_id"] == "corr-123"
        assert kw["filename"] == "data.csv"
        assert kw["rows_scanned"] == 1  # 1 data row in CSV
        assert kw["columns_scanned"] == 1  # 1 column
        assert kw["risk_level"] == "LOW"
        assert kw["allowed"] is True
        assert isinstance(kw["duration_ms"], int)
        assert kw["duration_ms"] >= 0
        assert kw["regulations_triggered"] == ["GDPR"]

    def test_formats_csv_json_jsonl(self, task_module):
        """csv, json, jsonl all parse without error."""
        formats = {
            "csv": b"col\nval\n",
            "json": b'[{"col": "val"}]',
            "jsonl": b'{"col": "val"}\n',
        }

        engine_mod, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()

        for fmt, content in formats.items():
            b64 = base64.b64encode(content).decode()
            payload = {
                "file_content_b64": b64,
                "file_format": fmt,
            }
            with (
                patch.object(
                    task_module, "_get_redis_client",
                    return_value=redis_mock,
                ),
                patch.dict(sys.modules, {
                    "compliance_engine": engine_mod,
                    "audit_logger": audit_mod,
                }),
            ):
                result = task_module.compliance_scan_job(
                    f"job-{fmt}", payload,
                )
            assert result is not None, (
                f"Expected result for format {fmt}"
            )
            assert "overall_status" in result, (
                f"Report missing overall_status for {fmt}"
            )

    def test_parquet_format_supported(self, task_module):
        """Parquet format parses correctly."""
        import io
        import pandas as pd
        df = pd.DataFrame({"col": ["val"]})
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        b64 = base64.b64encode(buf.getvalue()).decode()
        payload = {
            "file_content_b64": b64,
            "file_format": "parquet",
        }

        engine_mod, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()

        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
        ):
            result = task_module.compliance_scan_job(
                "job-parquet", payload,
            )
        assert result is not None
        assert "overall_status" in result


# -------------------------------------------------------------------
# compliance_scan_job — failure path
# -------------------------------------------------------------------

class TestComplianceScanJobFailure:
    def test_writes_failed_status_on_exception(
        self, task_module, csv_payload,
    ):
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        engine_mod.PIIDetector.return_value.detect_pii.side_effect = (
            RuntimeError("detector exploded")
        )
        redis_mock = MagicMock()

        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
            pytest.raises(RuntimeError),
        ):
            task_module.compliance_scan_job(
                "job-fail", csv_payload,
            )

        redis_mock.set.assert_called_once()
        key, value = redis_mock.set.call_args[0]
        assert key == "compliance:result:job-fail"
        payload = json.loads(value)
        assert payload["status"] == "FAILED"
        assert payload["job_id"] == "job-fail"
        assert "error" in payload
        assert payload["error"] == "detector exploded"

    def test_sanitises_pii_in_error_before_redis_write(
        self, task_module, csv_payload,
    ):
        """Error messages with PII patterns are sanitised before
        being written to Redis."""
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        pii_error = (
            "Failed processing alice@example.com "
            "card 4111 1111 1111 1111"
        )
        engine_mod.PIIDetector.return_value.detect_pii.side_effect = (
            RuntimeError(pii_error)
        )
        redis_mock = MagicMock()

        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
            pytest.raises(RuntimeError),
        ):
            task_module.compliance_scan_job(
                "job-pii", csv_payload,
            )

        value = redis_mock.set.call_args[0][1]
        stored_error = json.loads(value)["error"]
        assert "alice@example.com" not in stored_error
        assert "4111" not in stored_error
        assert "[EMAIL]" in stored_error
        assert "[CARD]" in stored_error

    def test_reraises_exception_for_rq(
        self, task_module, csv_payload,
    ):
        """Exception must propagate so RQ marks the job failed."""
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        engine_mod.PIIDetector.return_value.detect_pii.side_effect = (
            ValueError("boom")
        )
        redis_mock = MagicMock()

        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
            pytest.raises(ValueError, match="boom"),
        ):
            task_module.compliance_scan_job(
                "job-reraise", csv_payload,
            )

    def test_unsupported_format_raises(self, task_module):
        payload = {
            "file_content_b64": base64.b64encode(b"data").decode(),
            "file_format": "xml",
        }
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        redis_mock = MagicMock()

        with (
            patch.object(
                task_module, "_get_redis_client",
                return_value=redis_mock,
            ),
            patch.dict(sys.modules, {
                "compliance_engine": engine_mod,
                "audit_logger": audit_mod,
            }),
            pytest.raises(
                ValueError, match="Unsupported file_format",
            ),
        ):
            task_module.compliance_scan_job(
                "job-badformat", payload,
            )


# -------------------------------------------------------------------
# Error sanitisation
# -------------------------------------------------------------------

class TestSanitiseError:
    def test_card_pattern_scrubbed(self, task_module):
        msg = "value 4111 1111 1111 1111 is invalid"
        result = task_module._sanitise_error(msg)
        assert "[CARD]" in result
        assert "4111" not in result

    def test_ssn_pattern_scrubbed(self, task_module):
        msg = "SSN 123-45-6789 not allowed"
        result = task_module._sanitise_error(msg)
        assert "[SSN]" in result
        assert "123-45-6789" not in result

    def test_email_pattern_scrubbed(self, task_module):
        msg = "bad email alice@example.com in payload"
        result = task_module._sanitise_error(msg)
        assert "[EMAIL]" in result
        assert "alice@example.com" not in result

    def test_multiple_pii_patterns_all_scrubbed(self, task_module):
        """Multiple PII patterns in one string all get replaced."""
        msg = (
            "user alice@example.com SSN 123-45-6789 "
            "card 4111 1111 1111 1111"
        )
        result = task_module._sanitise_error(msg)
        assert "[EMAIL]" in result
        assert "[SSN]" in result
        assert "[CARD]" in result
        assert "alice@example.com" not in result
        assert "123-45-6789" not in result
        assert "4111" not in result

    def test_clean_string_unchanged(self, task_module):
        msg = "detector exploded: column 'age' has no PII"
        assert task_module._sanitise_error(msg) == msg

    def test_partial_card_not_scrubbed(self, task_module):
        """Short digit sequences should NOT be scrubbed."""
        msg = "column 1234 is invalid"
        assert task_module._sanitise_error(msg) == msg


# -------------------------------------------------------------------
# Autodiscovery: module importable at canonical dotted path
# -------------------------------------------------------------------

class TestModuleImportability:
    def test_module_loads_at_canonical_path(self):
        """services.worker.tasks.compliance must be importable
        so RQ can resolve the task function by dotted path."""
        engine_mod, audit_mod, _ = _stub_compliance_engine()
        stubs = {
            "compliance_engine": engine_mod,
            "audit_logger": audit_mod,
        }
        for key in list(sys.modules):
            if "services.worker.tasks.compliance" in key:
                del sys.modules[key]

        with patch.dict(sys.modules, stubs):
            project_root = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "..",
                ),
            )
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            import importlib as _il
            mod = _il.import_module(
                "services.worker.tasks.compliance",
            )

        assert callable(mod.compliance_scan_job)

    def test_function_signature(self, task_module):
        import inspect
        sig = inspect.signature(task_module.compliance_scan_job)
        params = list(sig.parameters)
        assert params == ["job_id", "payload"]
