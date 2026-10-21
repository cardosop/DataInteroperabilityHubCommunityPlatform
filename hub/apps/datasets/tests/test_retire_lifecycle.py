"""
Phase 260.4.A — dataset retire lifecycle contract tests.

End-to-end coverage for ``POST /datasets/{id}/retire/`` (the new retire
action), the ``include_retired`` queryset filter, the
``DATASET_RETIRED`` audit emission, the per-tenant
``dataset_retain_after_retire_days`` retention flag, and the cleanup
management command that hard-deletes retired datasets past the
retention window.

Doctrine: real Django ORM + auth backends, no mocks. Tests run inside
the standard test stack with Postgres + tenant fixture from
``DatasetsAPITestBase``.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from io import StringIO
from typing import cast

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset, DatasetStatus
from hub.apps.datasets.tests.test_base import DatasetsAPITestBase
from hub.apps.datasets.views import DatasetViewSet
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)


def _make_dataset(self) -> Dataset:
    """Helper — minimal Dataset row tied to the test base's tenant + file."""
    return Dataset.objects.create(
        tenant=self.tenant,
        file=self.file,
        format="CSV",
        schema_json={"fields": []},
        sample_data_json=[],
        row_count=0,
        created_by=self.user,
    )


class DatasetRetireEndpointTest(DatasetsAPITestBase):
    """Happy-path retire + state-machine + audit emission."""

    def setUp(self) -> None:
        super().setUp()
        self.dataset = _make_dataset(self)

    @pytest.mark.integration
    def test_retire_active_dataset_returns_200_and_flips_to_RETIRED(self) -> None:
        before = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_RETIRED,
            resource_id=str(self.dataset.id),
        ).count()

        resp = self.client.post(f"/api/v1/datasets/{self.dataset.id}/retire/")
        assert resp.status_code == status.HTTP_200_OK, resp.content

        self.dataset.refresh_from_db()
        assert self.dataset.status == DatasetStatus.RETIRED
        assert self.dataset.retired_at is not None

        # Response payload echoes the new state so the client doesn't
        # need a follow-up GET.
        assert resp.data["status"] == DatasetStatus.RETIRED
        assert resp.data["retired_at"] is not None

        # Exactly one audit row landed for this retire.
        after = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_RETIRED,
            resource_id=str(self.dataset.id),
        )
        assert after.count() == before + 1
        details = after.latest("timestamp").details_json or {}
        assert details.get("dataset_id") == str(self.dataset.id)
        assert "name" in details or "format" in details

    @pytest.mark.integration
    def test_retire_already_retired_returns_409_DATASET_ALREADY_RETIRED(self) -> None:
        self.dataset.status = DatasetStatus.RETIRED
        self.dataset.retired_at = timezone.now()
        self.dataset.save(update_fields=["status", "retired_at", "updated_at"])

        resp = self.client.post(f"/api/v1/datasets/{self.dataset.id}/retire/")
        assert resp.status_code == status.HTTP_409_CONFLICT
        # Error envelope shape parity with the rest of the API.
        body = resp.data
        code = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
        assert code == "DATASET_ALREADY_RETIRED" or body.get("code") == "DATASET_ALREADY_RETIRED"

    @pytest.mark.integration
    def test_retire_404_for_unknown_dataset(self) -> None:
        missing = uuid.uuid4()
        resp = self.client.post(f"/api/v1/datasets/{missing}/retire/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_retire_cross_tenant_returns_404_and_emits_no_audit(self) -> None:
        other = Tenant.objects.create(
            name=f"other-retire-{uuid.uuid4().hex[:8]}",
            slug=f"other-retire-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(other)
        from hub.apps.files.models import File

        other_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=other,
            name="other.csv",
            content_type="text/csv",
            size=1,
            storage_path=f"{other.id}/other.csv",
        )
        other_dataset = Dataset.objects.create(
            tenant=other,
            file=other_file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
        )

        before = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_RETIRED,
        ).count()
        resp = self.client.post(f"/api/v1/datasets/{other_dataset.id}/retire/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        after = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_RETIRED,
        ).count()
        assert after == before, "cross-tenant probe must NOT create an audit row"

    @pytest.mark.integration
    def test_retire_repeat_call_returns_409(self) -> None:
        """A second SEQUENTIAL retire returns 409 (idempotent contract).

        Note: this does NOT exercise the ``select_for_update`` branch —
        sequential calls land after the first transaction commits, so
        the second read sees ``status=RETIRED`` via the standard query
        path. Concurrent-call coverage lives in
        :meth:`test_retire_select_for_update_blocks_concurrent_writers`
        below (R1 GAP-D fix — the original name promised concurrency
        the test didn't actually exercise).
        """
        first = self.client.post(f"/api/v1/datasets/{self.dataset.id}/retire/")
        assert first.status_code == status.HTTP_200_OK
        second = self.client.post(f"/api/v1/datasets/{self.dataset.id}/retire/")
        assert second.status_code == status.HTTP_409_CONFLICT

    # Concurrency contract is exercised by
    # ``DatasetRetireConcurrencyTest`` further down in this module —
    # threading tests must run under ``TransactionTestCase`` so each
    # thread's connection can SEE the committed seed data; under the
    # outer ``TestCase`` atomic the seed is invisible cross-thread.


@pytest.mark.xdist_group("serial")
class DatasetRetireConcurrencyTest(TransactionTestCase):
    """Phase 260.4.A.R1 GAP-D — actual concurrency coverage for retire.

    Lives in a ``TransactionTestCase`` (rather than reusing
    ``DatasetsAPITestBase`` / ``TestCase``) so the seed Dataset row
    is COMMITTED before the worker threads run; otherwise each
    thread's connection sees an empty table and both retires 404 —
    the test would never reach the row-lock contention it's meant
    to prove. Mirrors the
    :class:`hub.apps.datasets.tests.test_file_handle_purpose.DatasetCreateConcurrencyTest`
    pattern.
    """

    def setUp(self) -> None:
        super().setUp()

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from hub.apps.files.models import File, FileScanStatus, FileStatus
        from hub.apps.users.models import UserStatus

        User = get_user_model()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Retire Concurrency {uid}",
            slug=f"retire-concurrency-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"retire-conc-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        from hub.apps.testing.role_support import ensure_user_has_data_provider_role

        ensure_user_has_data_provider_role(self.user)

        file_id = uuid.uuid4()
        self.file = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="retire-concurrency.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/retire-concurrency.csv",
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_retire_select_for_update_blocks_concurrent_writers(self) -> None:
        """Two threads call retire on the same dataset simultaneously.

        Postgres serialises them via ``select_for_update``: the first
        commits with status=RETIRED, the second sees the new state and
        returns 409 — never two 200s, never a double audit row.
        """
        import threading

        from rest_framework.test import APIClient

        client_a = APIClient()
        client_a.force_authenticate(user=self.user)
        client_b = APIClient()
        client_b.force_authenticate(user=self.user)

        results: list[int] = []
        barrier = threading.Barrier(2)
        results_lock = threading.Lock()

        def attempt(client) -> None:
            barrier.wait()
            response = client.post(f"/api/v1/datasets/{self.dataset.id}/retire/")
            with results_lock:
                results.append(response.status_code)

        thread_a = threading.Thread(target=attempt, args=(client_a,))
        thread_b = threading.Thread(target=attempt, args=(client_b,))
        thread_a.start()
        thread_b.start()
        thread_a.join(timeout=30)
        thread_b.join(timeout=30)

        assert sorted(results) == [200, 409], (
            f"Expected one 200 + one 409 from concurrent retire, got {sorted(results)}"
        )

        rows = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_RETIRED,
            resource_id=str(self.dataset.id),
        )
        assert rows.count() == 1, (
            f"Expected exactly one DATASET_RETIRED audit row, got {rows.count()}"
        )


class DatasetListIncludeRetiredFilterTest(DatasetsAPITestBase):
    """``GET /datasets/?include_retired=true`` opt-in for retired rows."""

    def setUp(self) -> None:
        super().setUp()
        # An active and a retired dataset for the same tenant.
        self.active = _make_dataset(self)
        self.retired = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="JSON",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            status=DatasetStatus.RETIRED,
            retired_at=timezone.now() - timedelta(days=1),
            created_by=self.user,
        )

    def _ids(self, resp) -> set[str]:
        return {row["id"] for row in (resp.data.get("results") or [])}

    @pytest.mark.integration
    def test_default_list_omits_retired(self) -> None:
        resp = self.client.get("/api/v1/datasets/")
        assert resp.status_code == status.HTTP_200_OK
        ids = self._ids(resp)
        assert str(self.active.id) in ids
        assert str(self.retired.id) not in ids

    @pytest.mark.integration
    def test_include_retired_true_returns_both(self) -> None:
        resp = self.client.get("/api/v1/datasets/?include_retired=true")
        assert resp.status_code == status.HTTP_200_OK
        ids = self._ids(resp)
        assert str(self.active.id) in ids
        assert str(self.retired.id) in ids

    @pytest.mark.integration
    def test_include_retired_garbage_value_falls_back_to_default(self) -> None:
        resp = self.client.get("/api/v1/datasets/?include_retired=banana")
        assert resp.status_code == status.HTTP_200_OK
        ids = self._ids(resp)
        # Non-truthy value behaves like default (retired hidden).
        assert str(self.retired.id) not in ids


class DatasetRetireThrottleWiringTest(TestCase):
    """``retire`` action uses polling-class caps (NOT init upload caps)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @pytest.mark.integration
    def test_retire_action_does_not_inherit_init_caps(self) -> None:
        view = DatasetViewSet()
        view.action = "retire"
        throttles = view.get_throttles()
        from hub.apps.files.throttles import (
            FileInitTenantThrottle,
            FileInitUserThrottle,
        )

        for t in throttles:
            assert not isinstance(t, FileInitUserThrottle)
            assert not isinstance(t, FileInitTenantThrottle)
        # Retire is a defined attribute on the viewset.
        assert callable(getattr(view, "retire", None))


class TenantRetainAfterRetireDefaultTest(TestCase):
    """``Tenant.dataset_retain_after_retire_days`` default = 90 days."""

    @pytest.mark.integration
    def test_default_is_90_days_on_new_tenant(self) -> None:
        t = Tenant.objects.create(
            name="retain-default",
            slug=f"retain-default-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        try:
            assert t.dataset_retain_after_retire_days == 90
        finally:
            t.delete()

    @pytest.mark.integration
    def test_field_is_a_positive_integer(self) -> None:
        t = Tenant.objects.create(
            name="retain-positive",
            slug=f"retain-positive-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        try:
            t.dataset_retain_after_retire_days = 30
            t.save(update_fields=["dataset_retain_after_retire_days", "updated_at"])
            t.refresh_from_db()
            assert t.dataset_retain_after_retire_days == 30
        finally:
            t.delete()


class CleanupRetiredDatasetsCommandTest(DatasetsAPITestBase):
    """``manage.py cleanup_retired_datasets`` hard-deletes past retention."""

    def setUp(self) -> None:
        super().setUp()
        # Tenant has the default 90-day window.
        self.fresh = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            status=DatasetStatus.RETIRED,
            retired_at=timezone.now() - timedelta(days=10),
            created_by=self.user,
        )
        self.stale = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            status=DatasetStatus.RETIRED,
            retired_at=timezone.now() - timedelta(days=120),
            created_by=self.user,
        )
        self.active = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"fields": []},
            sample_data_json=[],
            row_count=0,
            status=DatasetStatus.ACTIVE,
            created_by=self.user,
        )

    @pytest.mark.integration
    def test_dry_run_deletes_nothing_and_reports_eligible_count(self) -> None:
        out = StringIO()
        call_command("cleanup_retired_datasets", "--dry-run", stdout=out)
        stdout = out.getvalue()
        assert "1" in stdout  # one stale row eligible

        # Nothing deleted.
        assert Dataset.objects.filter(id=self.fresh.id).exists()
        assert Dataset.objects.filter(id=self.stale.id).exists()
        assert Dataset.objects.filter(id=self.active.id).exists()

    @pytest.mark.integration
    def test_default_run_hard_deletes_past_retention_only(self) -> None:
        call_command("cleanup_retired_datasets", stdout=StringIO())
        assert Dataset.objects.filter(id=self.stale.id).exists() is False
        # Fresh retired (within 90-day window) preserved.
        assert Dataset.objects.filter(id=self.fresh.id).exists()
        # Active dataset never touched.
        assert Dataset.objects.filter(id=self.active.id).exists()

    @pytest.mark.integration
    def test_per_tenant_window_overrides_default(self) -> None:
        # Tighten the tenant window so the fresh row (-10d) becomes
        # eligible too — proves the command honours per-tenant config.
        self.tenant.dataset_retain_after_retire_days = 5
        self.tenant.save(update_fields=["dataset_retain_after_retire_days", "updated_at"])

        call_command("cleanup_retired_datasets", stdout=StringIO())
        assert Dataset.objects.filter(id=self.fresh.id).exists() is False
        assert Dataset.objects.filter(id=self.stale.id).exists() is False
        assert Dataset.objects.filter(id=self.active.id).exists()

    @pytest.mark.integration
    def test_R1_GAP_B_emits_audit_row_per_tenant_with_deleted_id_list(self) -> None:
        """The cleanup MUST leave a durable audit trail for compliance."""
        before = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_HARD_DELETED_AFTER_RETENTION,
            tenant=self.tenant,
        ).count()

        call_command("cleanup_retired_datasets", stdout=StringIO())

        rows = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_HARD_DELETED_AFTER_RETENTION,
            tenant=self.tenant,
        )
        # Exactly one summary row landed for this run.
        assert rows.count() == before + 1
        details = rows.latest("timestamp").details_json or {}
        assert details["tenant_id"] == str(self.tenant.id)
        assert details["deleted_count"] == 1  # only ``stale`` is past 90d
        assert details["window_days"] == 90
        # Deleted IDs are recorded for forensic spot-checks.
        deleted_ids = details["deleted_dataset_ids"]
        assert isinstance(deleted_ids, list)
        assert str(self.stale.id) in deleted_ids
        # Fresh + active rows MUST NOT appear in the audit row.
        assert str(self.fresh.id) not in deleted_ids
        assert str(self.active.id) not in deleted_ids

    @pytest.mark.integration
    def test_R1_GAP_B_dry_run_emits_no_audit(self) -> None:
        """``--dry-run`` is read-only end-to-end including audit log."""
        before = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_HARD_DELETED_AFTER_RETENTION,
        ).count()
        call_command("cleanup_retired_datasets", "--dry-run", stdout=StringIO())
        after = AuditEvent.objects.filter(
            action=audit_event_types.DATASET_HARD_DELETED_AFTER_RETENTION,
        ).count()
        assert after == before


class AuditConstantPresenceTest(TestCase):
    """Audit constants exported from ``audit.event_types``."""

    @pytest.mark.integration
    def test_DATASET_RETIRED_self_describes(self) -> None:
        assert audit_event_types.DATASET_RETIRED == "DATASET_RETIRED"
        assert "DATASET_RETIRED" in audit_event_types.__all__

    @pytest.mark.integration
    def test_DATASET_HARD_DELETED_AFTER_RETENTION_self_describes(self) -> None:
        # Phase 260.4.A.R1 GAP-B — automated hard-delete audit constant.
        assert (
            audit_event_types.DATASET_HARD_DELETED_AFTER_RETENTION
            == "DATASET_HARD_DELETED_AFTER_RETENTION"
        )
        assert "DATASET_HARD_DELETED_AFTER_RETENTION" in audit_event_types.__all__


# Suppress unused-imports warnings when subset of cases run.
void = cast("object", (DatasetsAPITestBase, ensure_tenant_has_active_subscription))
