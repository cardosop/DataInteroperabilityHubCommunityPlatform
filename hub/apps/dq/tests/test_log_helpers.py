"""
Phase 240.5.F.5 — tests for ``hub.apps.dq.log_helpers._redact``.

Mirrors the dq-service-side ``_redact`` test inventory in
[services/dq-service/tests/test_structured_logging.py] so the Hub
side enforces the SAME redaction contract.  Both sides are pinned to
the same ``_REDACTED_KEYS`` set and the same recursion semantics —
copy-pasted-with-divergence is exactly the kind of bug this test
catches at CI time.

Why a Hub-side mirror at all (vs. just the dq-service one)?
Because the dq-service ``_redact`` lives in a separate codebase
(FastAPI microservice, not Django) — the Hub's ``logger.*`` call
sites in ``hub/apps/dq/{views,services,service_client,alerting,
tasks}.py`` can't import it.  Spec 240.5.F.2 explicitly mandates a
Hub-side helper at ``hub/apps/dq/log_helpers.py``.

Test classes:

* ``TestRedact`` — the helper's structural contract (same shape as
  dq-service's ``TestRedact`` in ``test_structured_logging.py``).
* ``TestRedactedKeysParity`` — pins that the Hub helper redacts AT
  LEAST the same keys as the dq-service one (drift safeguard).
* ``TestLintRuleParity`` — pins that the AST lint script's
  ``_FORBIDDEN_KEYS`` (in ``scripts/check_dq_log_extras.py``) matches
  the helper module's ``_REDACTED_KEYS``.  The script intentionally
  duplicates the key list (so pre-commit's lean env doesn't have to
  import the Hub Django package); this test ensures the duplicates
  never drift apart.  See script docstring at line ~69.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# ---------------------------------------------------------------------------
# Core ``_redact`` semantics — mirror of dq-service test inventory.
# ---------------------------------------------------------------------------


class TestRedact:
    """Phase 240.5.F.2 — Hub logs MUST NOT carry row samples or
    ``details_json`` body content."""

    def test_strips_row_samples_top_level(self):
        from hub.apps.dq.log_helpers import _redact

        payload = {
            "tenant_id": "t-1",
            "row_samples": [{"name": "Jane Doe", "ssn": "111-22-3333"}],
            "row_count": 100,
        }
        out = _redact(payload)
        assert "row_samples" not in out
        assert out["tenant_id"] == "t-1"
        assert out["row_count"] == 100

    def test_strips_sample_value_recursively(self):
        from hub.apps.dq.log_helpers import _redact

        payload = {
            "issues": [
                {
                    "check_id": "null-check",
                    "category": "VALIDITY",
                    "sample_value": "alice@example.com",
                },
                {
                    "check_id": "regex-check",
                    "sample_value": "secret-token",
                },
            ],
            "duration_ms": 42,
        }
        out = _redact(payload)
        for issue in out["issues"]:
            assert "sample_value" not in issue
            assert "check_id" in issue
        assert out["duration_ms"] == 42

    def test_strips_details_json_body(self):
        from hub.apps.dq.log_helpers import _redact

        payload = {
            "details_json": {"row_samples": [{"x": 1}], "extra": "secret"},
            "score": 0.95,
        }
        out = _redact(payload)
        # Whole details_json blob is redacted (body MAY contain PII).
        assert "details_json" not in out
        assert out["score"] == 0.95

    def test_strips_known_pii_bearing_keys(self):
        from hub.apps.dq.log_helpers import _redact

        payload = {
            "file_content": "name,ssn\nAlice,111-22-3333",
            "body": "raw payload text",
            "raw_data": [1, 2, 3],
            "sample_data_json": {"rows": []},
            "tenant_id": "t-1",
        }
        out = _redact(payload)
        for k in ("file_content", "body", "raw_data", "sample_data_json"):
            assert k not in out, f"{k} MUST be redacted"
        # Tenant id is allowed (operational, not PII).
        assert out["tenant_id"] == "t-1"

    def test_preserves_allowed_keys(self):
        from hub.apps.dq.log_helpers import _redact

        # Every key in this payload is operational (counts / scores /
        # ids / timing) — none should be over-redacted.
        payload = {
            "tenant_id": "t-1",
            "dq_run_id": "run-123",
            "profile_key": "intake_basic_gx",
            "engine": "great_expectations",
            "engine_version": "0.18.0",
            "status": "PASS",
            "overall_status": "PASS",
            "duration_ms": 1234,
            "execution_time_seconds": 1.234,
            "quality_score": 0.95,
            "score": 0.95,
            "row_count": 100,
            "total_rows": 100,
            "total_columns": 5,
            "category": "VALIDITY",
            "check_id": "null-check",
            "checks_passed": 7,
            "checks_failed": 1,
            # Hub-side specifics: rule_id / alert_id / channel / asset_id
            # / etc. are operational, never PII.
            "rule_id": "rule-1",
            "alert_id": "alert-deadbeef",
            "channel": "EMAIL",
            "asset_id": "asset-1",
            "dataset_id": "dataset-1",
            "error": "ConnectionRefusedError",
            "error_type": "ConnectionRefusedError",
            "http_status": 500,
            "attempt_number": 3,
        }
        out = _redact(payload)
        for k, v in payload.items():
            assert k in out, f"{k} should be preserved"
            assert out[k] == v

    def test_redact_handles_nested_lists_of_lists(self):
        from hub.apps.dq.log_helpers import _redact

        payload = {
            "groups": [
                {"name": "a", "row_samples": [1, 2]},
                {"name": "b", "issues": [{"sample_value": "x"}]},
            ],
        }
        out = _redact(payload)
        assert "row_samples" not in out["groups"][0]
        assert out["groups"][0]["name"] == "a"
        assert "sample_value" not in out["groups"][1]["issues"][0]

    def test_redact_non_dict_passes_through(self):
        from hub.apps.dq.log_helpers import _redact

        # Strings, ints, lists of scalars MUST pass through unchanged.
        assert _redact("just a string") == "just a string"
        assert _redact(42) == 42
        assert _redact([1, 2, 3]) == [1, 2, 3]
        assert _redact(None) is None
        assert _redact(True) is True

    def test_redact_returns_fresh_dict(self):
        """Mutating the output MUST NOT mutate the input — call sites
        often pass already-built dicts to logging, and a sneaky
        ``mutate-the-shared-dict`` bug would corrupt their state."""
        from hub.apps.dq.log_helpers import _redact

        original = {"tenant_id": "t-1", "row_samples": [1, 2, 3]}
        out = _redact(original)
        out["tenant_id"] = "MUTATED"
        # Original unchanged
        assert original["tenant_id"] == "t-1"
        assert original["row_samples"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Drift safeguard — Hub redacts AT LEAST the same keys as dq-service.
# ---------------------------------------------------------------------------


class TestRedactedKeysParity:
    """Phase 240.5.F audit-fix preventer.

    The Hub helper and the dq-service helper are independent
    implementations (different codebases, different import paths).
    A future PR that adds a new key to one but forgets the other
    would create a one-sided redaction hole.  This test pins the
    Hub redaction set as a SUPERSET of the dq-service one — the
    Hub may redact MORE (more conservative is fine), but it must
    never redact LESS than dq-service.
    """

    DQ_SERVICE_REDACTED_KEYS = {
        "row_samples",
        "sample_value",
        "sample_data_json",
        "file_content",
        "body",
        "raw_data",
        "details_json",
        "data",
    }

    def test_hub_redaction_set_covers_dq_service_set(self):
        from hub.apps.dq.log_helpers import _REDACTED_KEYS

        missing = self.DQ_SERVICE_REDACTED_KEYS - set(_REDACTED_KEYS)
        assert not missing, (
            "Hub `_REDACTED_KEYS` is missing keys that the dq-service "
            f"helper redacts: {sorted(missing)}.  Adding the missing "
            "key here keeps the Hub side at least as conservative as "
            "the microservice side."
        )

    def test_hub_redaction_set_is_a_frozenset_for_immutability(self):
        from hub.apps.dq.log_helpers import _REDACTED_KEYS

        assert isinstance(_REDACTED_KEYS, frozenset), (
            "_REDACTED_KEYS must be frozen to prevent accidental "
            "runtime mutation that could silently widen redaction."
        )


# ---------------------------------------------------------------------------
# Module surface — log_helpers exports a clean, documented API.
# ---------------------------------------------------------------------------


class TestModuleSurface:
    def test_redact_is_publicly_importable(self):
        # The spec wording calls it ``_redact`` (private-by-convention
        # leading underscore — matches dq-service / compliance Phase 19),
        # but it MUST be importable from the package surface for the
        # call-sites to use it.
        from hub.apps.dq.log_helpers import _redact

        assert callable(_redact)

    def test_module_exposes_redacted_keys_constant(self):
        from hub.apps.dq import log_helpers

        assert hasattr(log_helpers, "_REDACTED_KEYS")


# ---------------------------------------------------------------------------
# Phase 240.5.F.4 audit-fix preventer — lint script <-> helper parity.
# ---------------------------------------------------------------------------


def _load_lint_script_module():
    """Dynamically load ``scripts/check_dq_log_extras.py`` as a module
    so its ``_FORBIDDEN_KEYS`` constant is introspectable from this
    test.  We deliberately do NOT add ``scripts/`` to ``sys.path`` —
    the script is intentionally NOT importable by the Hub Django
    package (it's a standalone pre-commit script that imports
    nothing from ``hub.``).

    The module MUST be registered in ``sys.modules`` BEFORE we call
    ``exec_module`` because the script uses ``@dataclass``, which
    resolves type annotations via ``sys.modules[cls.__module__]``;
    skipping the registration raises ``AttributeError: 'NoneType'
    object has no attribute '__dict__'`` at decoration time.
    """
    import sys

    script_path = Path(__file__).resolve().parents[4] / "scripts" / "check_dq_log_extras.py"
    assert script_path.exists(), (
        f"Lint script not found at {script_path}; the parity test "
        "expects it at the canonical location declared in 240.5.F.4."
    )
    module_name = "check_dq_log_extras_for_parity_test"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        # Roll back the registration so a partial-import doesn't
        # leave a half-loaded module in ``sys.modules`` for any
        # subsequent test in the same process.
        sys.modules.pop(module_name, None)
        raise
    return module


class TestLintRuleParity:
    """Phase 240.5.F.4 — the AST lint script and the runtime helper
    have INDEPENDENT copies of the redacted-key list.  This is
    intentional (the script must be importable in pre-commit's lean
    env without the Hub Django package on sys.path), but it creates
    a drift hazard: a future PR adding a key to one but not the other
    leaves the lint either over-aggressive (helper missing key) or
    silently-bypassed (script missing key).

    This test pins the two copies as equal at CI time so the
    docstring claim in ``scripts/check_dq_log_extras.py:69``
    (``parity is pinned by ... TestLintRuleParity``) is actually
    true.
    """

    def test_lint_script_forbidden_keys_match_helper_redacted_keys(self):
        from hub.apps.dq.log_helpers import _REDACTED_KEYS

        script = _load_lint_script_module()
        assert hasattr(script, "_FORBIDDEN_KEYS"), (
            "scripts/check_dq_log_extras.py must export "
            "``_FORBIDDEN_KEYS`` (frozenset of dict keys to ban in "
            "raw ``extra={...}`` payloads)."
        )
        helper_keys = set(_REDACTED_KEYS)
        script_keys = set(script._FORBIDDEN_KEYS)
        assert helper_keys == script_keys, (
            "Drift detected between hub.apps.dq.log_helpers."
            "_REDACTED_KEYS and scripts/check_dq_log_extras.py "
            "_FORBIDDEN_KEYS.\n"
            f"  In helper but not lint script: "
            f"{sorted(helper_keys - script_keys)}\n"
            f"  In lint script but not helper: "
            f"{sorted(script_keys - helper_keys)}\n"
            "Add the missing key(s) to the other side; the lint "
            "rule and the runtime redactor MUST cover the same set "
            "of keys."
        )

    def test_lint_script_forbidden_keys_is_a_frozenset(self):
        script = _load_lint_script_module()
        assert isinstance(script._FORBIDDEN_KEYS, frozenset), (
            "scripts/check_dq_log_extras.py ``_FORBIDDEN_KEYS`` must "
            "be a frozenset to prevent accidental runtime mutation "
            "that could silently widen / narrow the lint rule."
        )
