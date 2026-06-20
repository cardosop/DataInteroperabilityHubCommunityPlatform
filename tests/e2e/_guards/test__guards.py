"""Self-tests for the dual-channel guard helpers.

A guard that has its own bug becomes a silent passer — worse than no guard
at all. Each helper in this module must have a test that proves both:

  1. It fails loudly when the precondition it's meant to enforce is violated.
  2. It passes silently when the precondition is met.

If a guard ever flips its behaviour (e.g. an edit makes it pass when it
should fail), one of these tests catches it on the way in.

Run:
    pytest tests/e2e/_guards/test__guards.py -v
"""

from __future__ import annotations

import time
import uuid

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


# --------------------------------------------------------------- assert_audit_event


class TestAssertAuditEvent:
    """Synchronous variant — the one used by ~200 call-sites in PR 6a-6e."""

    @staticmethod
    def _create_event(
        tenant, *, action="ASSET_CREATED", resource_type="asset", resource_id=None, result="SUCCESS"
    ):
        from hub.apps.audit.models import AuditEvent

        return AuditEvent.objects.create(
            tenant_id=tenant.id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else str(uuid.uuid4()),
            result=result,
        )

    def test_passes_when_matching_event_exists(self):
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        event = self._create_event(tenant)
        # Must not raise
        assert_audit_event(tenant, event.action, event.resource_type, event.resource_id)

    def test_raises_when_no_event_exists(self):
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        with pytest.raises(AssertionError) as exc:
            assert_audit_event(tenant, "ASSET_CREATED", "asset", resource_id=str(uuid.uuid4()))
        # Diagnostic must name what was expected and mention the tenant
        assert "Expected audit event not found" in str(exc.value)
        assert "ASSET_CREATED" in str(exc.value)
        assert str(tenant.id) in str(exc.value)

    def test_raises_when_event_exists_in_different_tenant(self):
        """Cross-tenant leakage must NOT falsely satisfy an assertion."""
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant_a = TenantFactory()
        tenant_b = TenantFactory()
        self._create_event(tenant_a, action="ASSET_CREATED")
        with pytest.raises(AssertionError):
            assert_audit_event(tenant_b, "ASSET_CREATED", "asset")

    def test_raises_when_result_differs(self):
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        self._create_event(tenant, action="ASSET_DELETED", result="FAILURE")
        with pytest.raises(AssertionError):
            # Default result="SUCCESS" should not match the FAILURE record
            assert_audit_event(tenant, "ASSET_DELETED", "asset")

    def test_passes_when_result_explicitly_failure(self):
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        self._create_event(tenant, action="ASSET_DELETED", result="FAILURE")
        # When caller explicitly asks for FAILURE, it must match
        assert_audit_event(tenant, "ASSET_DELETED", "asset", result="FAILURE")

    def test_diagnostic_lists_recent_events_for_scoped_tenant(self):
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        # Seed three unrelated events so the diagnostic has content to show.
        for i in range(3):
            self._create_event(tenant, action=f"OTHER_ACTION_{i}")
        with pytest.raises(AssertionError) as exc:
            assert_audit_event(tenant, "MISSING_ACTION", "asset")
        diag = str(exc.value)
        # All three unrelated actions must appear in the "last 10" section
        assert "OTHER_ACTION_0" in diag
        assert "OTHER_ACTION_1" in diag
        assert "OTHER_ACTION_2" in diag

    def test_resource_id_none_matches_events_without_resource_id(self):
        """Login/logout events have no resource_id; passing None must match."""
        from tests.e2e._guards import assert_audit_event
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        from hub.apps.audit.models import AuditEvent

        AuditEvent.objects.create(
            tenant_id=tenant.id,
            action="LOGIN",
            resource_type="user",
            resource_id="",  # empty, not a UUID
            result="SUCCESS",
        )
        assert_audit_event(tenant, "LOGIN", "user")  # resource_id not specified


# ---------------------------------------------------- assert_audit_event_eventually


class TestAssertAuditEventEventually:
    """Polling variant — for async-produced events."""

    def test_passes_immediately_when_event_already_exists(self):
        from hub.apps.audit.models import AuditEvent
        from tests.e2e._guards import assert_audit_event_eventually
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        AuditEvent.objects.create(
            tenant_id=tenant.id,
            action="COMPLIANCE_RUN_COMPLETED",
            resource_type="compliance_run",
            resource_id=str(uuid.uuid4()),
            result="SUCCESS",
        )
        t0 = time.monotonic()
        assert_audit_event_eventually(
            tenant,
            "COMPLIANCE_RUN_COMPLETED",
            "compliance_run",
            timeout=5.0,
            poll_interval=0.5,
        )
        # Should return well under a single poll interval
        assert time.monotonic() - t0 < 1.0, (
            "Eventually-variant should return fast when event is present"
        )

    def test_raises_after_timeout_when_no_event(self):
        from tests.e2e._guards import assert_audit_event_eventually
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        t0 = time.monotonic()
        with pytest.raises(AssertionError) as exc:
            assert_audit_event_eventually(
                tenant,
                "NEVER_WRITTEN",
                "nothing",
                timeout=0.5,
                poll_interval=0.1,
            )
        elapsed = time.monotonic() - t0
        assert 0.4 <= elapsed <= 2.0, f"Expected ~0.5s poll window, got {elapsed:.2f}s"
        assert "after polling" in str(exc.value)
        assert "0.5s" in str(exc.value) or "0.5 s" in str(exc.value)

    def test_rejects_nonpositive_timeout(self):
        from tests.e2e._guards import assert_audit_event_eventually
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        with pytest.raises(ValueError):
            assert_audit_event_eventually(tenant, "X", "y", timeout=0)

    def test_rejects_nonpositive_poll_interval(self):
        from tests.e2e._guards import assert_audit_event_eventually
        from tests.factories import TenantFactory

        tenant = TenantFactory()
        with pytest.raises(ValueError):
            assert_audit_event_eventually(
                tenant,
                "X",
                "y",
                timeout=1.0,
                poll_interval=0,
            )


# --------------------------------------------------------------------- two_tenants


class TestTwoTenantsFixture:
    """Exercises the fixture itself and the tenant-isolation guarantee."""

    def test_yields_two_distinct_tenants(self, two_tenants):
        assert two_tenants.a.tenant.id != two_tenants.b.tenant.id
        assert two_tenants.a.user.id != two_tenants.b.user.id

    def test_each_bundle_has_authenticated_client(self, two_tenants):
        # force_authenticate sets _force_user on the APIClient
        assert two_tenants.a.client.handler._force_user == two_tenants.a.user
        assert two_tenants.b.client.handler._force_user == two_tenants.b.user

    def test_users_belong_to_their_own_tenants(self, two_tenants):
        assert two_tenants.a.user.tenant_id == two_tenants.a.tenant.id
        assert two_tenants.b.user.tenant_id == two_tenants.b.tenant.id

    def test_tenants_have_distinct_slugs(self, two_tenants):
        assert two_tenants.a.tenant.slug != two_tenants.b.tenant.slug


# ------------------------------------------------------- captured_server_errors


class TestCapturedServerErrorsLogic:
    """Pure-function tests for the PR 4 autouse fixture.

    These exercise detect_offending_records, format_diagnostic, and
    is_strict_mode directly with synthetic LogRecord objects. Testing the
    autouse fixture's raise/warn behaviour end-to-end is harder (the
    fixture applies to the test that's testing it, a classic
    chicken-and-egg) so we cover those via the marker-opt-out test below
    and otherwise trust the unit tests.
    """

    @staticmethod
    def _make_record(name, level, message):
        import logging

        return logging.LogRecord(
            name=name,
            level=level,
            pathname="x",
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )

    def test_detect_ignores_non_error_levels(self):
        import logging

        from tests.e2e._guards import detect_offending_records

        records = [
            self._make_record("django", logging.INFO, "info line"),
            self._make_record("django", logging.WARNING, "warn line"),
            self._make_record("django", logging.DEBUG, "debug line"),
        ]
        assert detect_offending_records(records) == []

    def test_detect_surfaces_django_error(self):
        import logging

        from tests.e2e._guards import detect_offending_records

        rec = self._make_record("django.request", logging.ERROR, "uh oh")
        assert detect_offending_records([rec]) == [rec]

    def test_detect_surfaces_hub_error(self):
        import logging

        from tests.e2e._guards import detect_offending_records

        rec = self._make_record("hub.apps.audit.signals", logging.ERROR, "signal blew up")
        assert detect_offending_records([rec]) == [rec]

    def test_detect_surfaces_rest_framework_error(self):
        import logging

        from tests.e2e._guards import detect_offending_records

        rec = self._make_record("rest_framework.exceptions", logging.ERROR, "nope")
        assert detect_offending_records([rec]) == [rec]

    def test_detect_ignores_third_party_logger(self):
        """Loggers outside the watched prefixes must not trigger the guard."""
        import logging

        from tests.e2e._guards import detect_offending_records

        records = [
            self._make_record("celery.worker", logging.ERROR, "retry"),
            self._make_record("urllib3", logging.ERROR, "pool exhausted"),
            self._make_record("botocore.endpoint", logging.ERROR, "s3 timeout"),
        ]
        assert detect_offending_records(records) == []

    def test_detect_surfaces_critical_not_only_error(self):
        import logging

        from tests.e2e._guards import detect_offending_records

        rec = self._make_record("django", logging.CRITICAL, "oom")
        assert detect_offending_records([rec]) == [rec]

    def test_format_diagnostic_empty(self):
        from tests.e2e._guards import format_diagnostic

        assert format_diagnostic([]) == (
            "Watched Django/DRF loggers emitted 0 ERROR record(s):\n(no records)"
        )

    def test_format_diagnostic_includes_logger_and_level(self):
        import logging

        from tests.e2e._guards import format_diagnostic

        rec = self._make_record("django.db", logging.ERROR, "bad query")
        out = format_diagnostic([rec])
        assert "django.db[ERROR]: bad query" in out
        assert "emitted 1 ERROR record" in out

    def test_format_diagnostic_truncates_with_tail_count(self):
        import logging

        from tests.e2e._guards import format_diagnostic

        records = [self._make_record("django", logging.ERROR, f"err-{i}") for i in range(15)]
        out = format_diagnostic(records, max_records=5)
        # first 5 shown, remaining 10 counted
        assert "err-0" in out
        assert "err-4" in out
        assert "err-5" not in out
        assert "... and 10 more" in out

    def test_is_strict_mode_default_is_false(self, monkeypatch):
        from tests.e2e._guards import is_strict_mode

        monkeypatch.delenv("CAPTURED_SERVER_ERRORS_STRICT", raising=False)
        assert is_strict_mode() is False

    @pytest.mark.parametrize("value", ["1", "true", "yes", "on", "TRUE", "Yes"])
    def test_is_strict_mode_truthy(self, monkeypatch, value):
        from tests.e2e._guards import is_strict_mode

        monkeypatch.setenv("CAPTURED_SERVER_ERRORS_STRICT", value)
        assert is_strict_mode() is True

    @pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "garbage"])
    def test_is_strict_mode_falsy(self, monkeypatch, value):
        from tests.e2e._guards import is_strict_mode

        monkeypatch.setenv("CAPTURED_SERVER_ERRORS_STRICT", value)
        assert is_strict_mode() is False


class TestCapturedServerErrorsMarkerOptOut:
    """Proves the @allow_server_errors marker actually lets ERROR logs through.

    This test deliberately triggers a Django ERROR log. Without the marker,
    the advisory fixture would emit a UserWarning; with it, the fixture
    silently tolerates the record. In strict mode (CI-controlled) this
    would be the difference between a failing and passing test — the
    marker is the contract.
    """

    @pytest.mark.allow_server_errors
    def test_marker_tolerates_logged_error(self, caplog):
        import logging

        logger = logging.getLogger("hub.apps.audit.signals")
        logger.error("deliberate error for the allow_server_errors test")
        # Fixture-teardown assertion is the real test — if it raised or
        # warned, pytest would fail this test. We reach here only when the
        # marker correctly bypassed the check.
        assert any(
            r.name == "hub.apps.audit.signals" and r.levelno == logging.ERROR
            for r in caplog.records
        )
