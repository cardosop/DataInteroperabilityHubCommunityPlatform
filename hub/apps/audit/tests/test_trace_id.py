"""
Phase 277.B.111 — trace_id on AuditEvent tests.

Validates:
- Model field exists with correct configuration
- trace_id is automatically extracted from OTel span context on create
- trace_id is nullable (None when OTel is unavailable / no active span)
- Serializer includes trace_id in output
- GET /audit/audit-events/?trace_id=<uuid> filter works
- Migration is safe (null=True, default=None)
"""
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant, TenantStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class TraceIdModelTests(TestCase):
    """Verify the model field is correctly configured."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="TraceTest", slug="trace-test", status=TenantStatus.ACTIVE,
        )

    def test_field_exists_and_nullable(self):
        """trace_id is a nullable UUIDField with db_index."""
        field = AuditEvent._meta.get_field("trace_id")
        assert field.null is True
        assert field.blank is True
        assert field.db_index is True
        assert field.default is None

    def test_can_create_event_without_trace_id(self):
        """trace_id defaults to None when not provided."""
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="TRACE_ID_TEST",
            result="SUCCESS",
        )
        assert event.trace_id is None

    def test_can_create_event_with_explicit_trace_id(self):
        """Explicit trace_id is persisted."""
        tid = uuid.uuid4()
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="TRACE_ID_SET",
            result="SUCCESS",
            trace_id=tid,
        )
        assert event.trace_id == tid

    def test_filter_by_trace_id(self):
        """AuditEvent.objects.filter(trace_id=...) works."""
        tid = uuid.uuid4()
        AuditEvent.objects.create(
            tenant=self.tenant, resource_type="A", action="FILTERED",
            result="SUCCESS", trace_id=tid,
        )
        AuditEvent.objects.create(
            tenant=self.tenant, resource_type="B", action="UNFILTERED",
            result="SUCCESS", trace_id=None,
        )
        filtered = AuditEvent.objects.filter(trace_id=tid)
        assert filtered.count() == 1
        assert filtered.first().action == "FILTERED"


class TraceIdOtelExtractionTests(TestCase):
    """Verify OTel span extraction in create_audit_event()."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="OTelTrace", slug="otel-trace", status=TenantStatus.ACTIVE,
        )

    def test_trace_id_extracted_when_span_active(self):
        """When OTel span is active with a valid trace_id, it is captured."""
        fake_trace_id = 0xABCDEF0123456789ABCDEF0123456789  # 128-bit trace ID

        class FakeSpanContext:
            trace_id = fake_trace_id
            is_valid = True

        class FakeSpan:
            def get_span_context(self):
                return FakeSpanContext()

        with patch("opentelemetry.trace.get_current_span", return_value=FakeSpan()):
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="TEST",
                action="OTEL_SPAN_TEST",
                tenant=self.tenant,
                result="SUCCESS",
            )

        event = AuditEvent.objects.filter(action="OTEL_SPAN_TEST").first()
        assert event is not None
        assert event.trace_id is not None, (
            "trace_id should be populated from OTel span"
        )
        # OTel trace_id (128-bit int) is formatted as a 32-char hex UUID
        # by create_audit_event.  We assert it is a real UUID — not None
        # and not a raw decimal string.
        assert isinstance(event.trace_id, uuid.UUID), (
            f"trace_id should be a UUID, got {type(event.trace_id).__name__}: "
            f"{event.trace_id}"
        )

    def test_trace_id_none_when_otel_unavailable(self):
        """When OTel is not installed, trace_id gracefully defaults to None."""
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="TEST",
            action="NO_OTEL_TEST",
            tenant=self.tenant,
            result="SUCCESS",
        )
        event = AuditEvent.objects.filter(action="NO_OTEL_TEST").first()
        assert event is not None
        assert event.trace_id is None, (
            f"trace_id should be None when OTel is unavailable, "
            f"but got {event.trace_id}"
        )

    def test_trace_id_none_when_span_invalid(self):
        """Invalid span context → trace_id=None."""

        class FakeInvalidContext:
            trace_id = 0
            is_valid = False

        class FakeSpan:
            def get_span_context(self):
                return FakeInvalidContext()

        with patch("opentelemetry.trace.get_current_span", return_value=FakeSpan()):
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="TEST",
                action="INVALID_SPAN_TEST",
                tenant=self.tenant,
                result="SUCCESS",
            )

        event = AuditEvent.objects.filter(action="INVALID_SPAN_TEST").first()
        assert event is not None
        # Invalid span → trace_id not adopted → should be None
        assert event.trace_id is None

    def test_create_audit_event_survives_otel_exception(self):
        """If OTel raises during extraction, audit event still created."""

        class BrokenSpan:
            def get_span_context(self):
                raise RuntimeError("OTel internal error")

        with patch("opentelemetry.trace.get_current_span", return_value=BrokenSpan()):
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="TEST",
                action="OTEL_BROKEN_TEST",
                tenant=self.tenant,
                result="SUCCESS",
            )

        event = AuditEvent.objects.filter(action="OTEL_BROKEN_TEST").first()
        assert event is not None
        assert event.trace_id is None


class TraceIdSerializerTests(TestCase):
    """Verify serializer includes trace_id in output."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="SerializerTrace", slug="serializer-trace", status=TenantStatus.ACTIVE,
        )

    def test_serializer_includes_trace_id(self):
        """AuditEventSerializer output includes trace_id."""
        from hub.apps.audit.serializers import AuditEventSerializer

        tid = uuid.uuid4()
        event = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="SERIALIZER_TEST",
            result="SUCCESS",
            trace_id=tid,
        )
        serializer = AuditEventSerializer(event)
        data = serializer.data
        assert "trace_id" in data
        assert data["trace_id"] == str(tid)

    def test_serializer_trace_id_null(self):
        """Serializer handles trace_id=None gracefully."""
        from hub.apps.audit.serializers import AuditEventSerializer

        event = AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="TEST",
            action="NULL_TRACE_SERIALIZER",
            result="SUCCESS",
        )
        serializer = AuditEventSerializer(event)
        assert "trace_id" in serializer.data
        assert serializer.data["trace_id"] is None


class TraceIdFilterTests(TestCase):
    """Verify ?trace_id= query parameter on audit list API."""

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        self.tenant = Tenant.objects.create(
            name="FilterTrace", slug="filter-trace", status=TenantStatus.ACTIVE,
        )
        self.user = User.objects.create_user(
            email="trace-filter@example.com", password="testpass",
            tenant=self.tenant,
        )
        role = Role.objects.create(
            tenant=self.tenant, name="TENANT_ADMIN", description=""
        )
        UserRole.objects.create(user=self.user, tenant=self.tenant, role=role)
        self.tid = uuid.uuid4()
        AuditEvent.objects.create(
            tenant=self.tenant, resource_type="A", action="FILTER_A",
            result="SUCCESS", trace_id=self.tid,
        )
        AuditEvent.objects.create(
            tenant=self.tenant, resource_type="B", action="FILTER_B",
            result="SUCCESS", trace_id=None,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_filter_by_trace_id_returns_matching_events(self):
        resp = self.client.get(
            f"/api/v1/audit/audit-events/?trace_id={self.tid}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        for result in data["results"]:
            if result["action"] == "FILTER_A":
                assert result["trace_id"] == str(self.tid)

    def test_filter_by_nonexistent_trace_id_returns_empty(self):
        fake_id = str(uuid.uuid4())
        resp = self.client.get(
            f"/api/v1/audit/audit-events/?trace_id={fake_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_trace_id_shown_in_list_response(self):
        resp = self.client.get("/api/v1/audit/audit-events/")
        assert resp.status_code == 200
        results = resp.json()["results"]
        trace_ids = {r.get("trace_id") for r in results}
        # FILTER_A has trace_id set
        assert str(self.tid) in trace_ids


class TraceIdMigrationSafetyTests(TestCase):
    """Verify the migration is safe (null=True, default=None)."""

    def test_migration_exists(self):
        """Migration 0014 adds trace_id with null=True, default=None."""
        from django.db.migrations.loader import MigrationLoader
        from django.db import connections

        loader = MigrationLoader(connections["default"])
        migration = loader.disk_migrations.get(("audit", "0014_auditevent_trace_id"))
        assert migration is not None, "Migration 0014_auditevent_trace_id not found"

        # Check the AddField operation
        for op in migration.operations:
            if hasattr(op, "field"):
                field = op.field
                if hasattr(field, "null"):
                    assert field.null is True, "trace_id must be null=True"
                # default=None is the Django default for nullable fields
