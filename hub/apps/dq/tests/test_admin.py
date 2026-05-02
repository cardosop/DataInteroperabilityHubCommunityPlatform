"""
Phase 240.5.B.1 / 240.5.B.2 — Django admin tests.

Pins the admin contract for the four DQ models:

* :class:`DQRun`, :class:`DQAnomaly`, :class:`DQTrend`,
  :class:`DQAlertingRule` are all registered with the default
  ``django.contrib.admin.site``.
* Every ModelAdmin declares ``list_display``, ``search_fields``,
  ``list_filter``, and includes ``details_json`` (or the
  model-specific JSON field) in ``readonly_fields``.
* Soft-delete-aware admins (``DQRun``, ``DQAnomaly``,
  ``DQTrend``) use the ``all_objects`` manager so the changelist
  shows soft-deleted rows — admins MUST be able to recover
  rows the SoftDeleteManager hides from the regular API.
* ``DQRunAdmin``, ``DQAnomalyAdmin``, and ``DQTrendAdmin`` expose
  a ``restore`` admin action that flips ``is_deleted=False`` on
  the selected rows.

Tests use real Django models + the real ``AdminSite`` registry —
no mocks. Each assertion targets a property a future maintainer
might break (e.g. accidentally swapping ``all_objects`` back to
``objects`` would surface as a failing changelist test).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib import admin as django_admin
from django.utils import timezone

from hub.apps.dq.models import (
    DQAlertingRule,
    DQAnomaly,
    DQEngine,
    DQRun,
    DQRunStatus,
    DQTrend,
)
from hub.apps.dq.tests.test_base import DQAPITransactionTestBase


pytestmark = pytest.mark.django_db(transaction=True)


# ────────────────────────────────────────────────────────────────────
# Registry — every model is registered exactly once
# ────────────────────────────────────────────────────────────────────


class DQAdminRegistryTests(DQAPITransactionTestBase):
    """Pins that 240.5.B.1's four models are registered."""

    def test_dq_run_is_registered(self):
        self.assertIn(
            DQRun, django_admin.site._registry,
            "DQRun must be registered with the default AdminSite "
            "for ops staff to manage runs through the admin UI.",
        )

    def test_dq_anomaly_is_registered(self):
        self.assertIn(DQAnomaly, django_admin.site._registry)

    def test_dq_trend_is_registered(self):
        self.assertIn(DQTrend, django_admin.site._registry)

    def test_dq_alerting_rule_is_registered(self):
        self.assertIn(DQAlertingRule, django_admin.site._registry)


# ────────────────────────────────────────────────────────────────────
# ModelAdmin shape — list_display / search_fields / list_filter /
# readonly_fields
# ────────────────────────────────────────────────────────────────────


class DQAdminShapeTests(DQAPITransactionTestBase):
    """Each ModelAdmin must declare the four spec-required attrs.

    These are the attributes that drive the admin UI's usefulness;
    a ModelAdmin missing them defaults to (id, str(obj)) only —
    which is OK for display but useless for a 1M-row queryset
    where ops staff need to filter and search."""

    def _admin_for(self, model):
        return django_admin.site._registry[model]

    def test_dq_run_admin_has_list_display(self):
        cls = type(self._admin_for(DQRun))
        self.assertTrue(cls.list_display, f"{cls.__name__}.list_display empty")
        self.assertIn("status", cls.list_display)
        self.assertIn("tenant", cls.list_display)

    def test_dq_run_admin_has_search_fields(self):
        cls = type(self._admin_for(DQRun))
        self.assertTrue(cls.search_fields)
        self.assertIn("id", cls.search_fields)

    def test_dq_run_admin_has_list_filter(self):
        cls = type(self._admin_for(DQRun))
        self.assertTrue(cls.list_filter)
        self.assertIn("status", cls.list_filter)

    def test_dq_run_admin_marks_details_json_readonly(self):
        cls = type(self._admin_for(DQRun))
        self.assertIn(
            "details_json", cls.readonly_fields,
            "DQRun.details_json carries metering + engine output; "
            "must be readonly so ops can't accidentally clobber the "
            "DQ run's audit trail.",
        )

    def test_dq_anomaly_admin_marks_metadata_readonly(self):
        cls = type(self._admin_for(DQAnomaly))
        # DQAnomaly's JSON field is ``metadata``, not ``details_json``.
        self.assertIn("metadata", cls.readonly_fields)
        self.assertTrue(cls.list_display)
        self.assertTrue(cls.list_filter)

    def test_dq_trend_admin_marks_metadata_readonly(self):
        cls = type(self._admin_for(DQTrend))
        self.assertIn("metadata", cls.readonly_fields)
        self.assertTrue(cls.list_display)

    def test_dq_alerting_rule_admin_marks_channel_config_readonly(self):
        cls = type(self._admin_for(DQAlertingRule))
        # DQAlertingRule has ``channel_config`` (jsonb) for delivery
        # config — same readonly treatment as the other JSON fields.
        self.assertIn("channel_config", cls.readonly_fields)
        self.assertTrue(cls.list_display)


# ────────────────────────────────────────────────────────────────────
# Soft-delete awareness — admins see deleted rows
# ────────────────────────────────────────────────────────────────────


class DQAdminSoftDeleteTests(DQAPITransactionTestBase):
    """Spec 240.5.B.2: ``DQRunAdmin.get_queryset`` MUST use
    ``all_objects`` so admins can recover soft-deleted rows.

    The default ``SoftDeleteManager`` filters ``is_deleted=False``;
    if the admin used it, ops staff would see exactly the same view
    as the API — useless for incident response (the very reason
    you'd open the admin is because the API is hiding something).
    """

    def setUp(self):
        super().setUp()
        # One live and one soft-deleted DQRun in the same tenant.
        self.live_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )
        self.deleted_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )
        self.deleted_run.soft_delete()

    def _admin_for(self, model):
        return django_admin.site._registry[model]

    def test_dq_run_admin_queryset_includes_soft_deleted(self):
        from django.test import RequestFactory

        admin_obj = self._admin_for(DQRun)
        request = RequestFactory().get("/admin/dq/dqrun/")
        request.user = self.user

        qs = admin_obj.get_queryset(request)
        ids = set(qs.values_list("id", flat=True))

        self.assertIn(
            self.live_run.id, ids,
            "Live (non-deleted) run missing from admin changelist.",
        )
        self.assertIn(
            self.deleted_run.id, ids,
            "Soft-deleted run missing from admin changelist — "
            "DQRunAdmin.get_queryset must use ``all_objects``, not "
            "``objects``, so admins can recover deleted rows.",
        )

    def test_dq_anomaly_admin_queryset_includes_soft_deleted(self):
        """Same contract for ``DQAnomaly`` (also soft-delete-aware)."""
        from django.test import RequestFactory

        # Build a live + a soft-deleted anomaly.
        anomaly_live = DQAnomaly.objects.create(
            tenant=self.tenant,
            metric_type="quality_score",
            expected_value=95.0,
            actual_value=80.0,
            deviation=15.0,
        )
        anomaly_deleted = DQAnomaly.objects.create(
            tenant=self.tenant,
            metric_type="quality_score",
            expected_value=95.0,
            actual_value=70.0,
            deviation=25.0,
        )
        anomaly_deleted.soft_delete()

        admin_obj = self._admin_for(DQAnomaly)
        request = RequestFactory().get("/admin/dq/dqanomaly/")
        request.user = self.user

        ids = set(admin_obj.get_queryset(request).values_list("id", flat=True))
        self.assertIn(anomaly_live.id, ids)
        self.assertIn(anomaly_deleted.id, ids)


# ────────────────────────────────────────────────────────────────────
# Restore admin action
# ────────────────────────────────────────────────────────────────────


class DQAdminRestoreActionTests(DQAPITransactionTestBase):
    """Spec 240.5.B.2: ``DQRunAdmin`` declares a ``restore`` admin
    action that un-deletes soft-deleted rows."""

    def _admin_for(self, model):
        return django_admin.site._registry[model]

    def test_dq_run_admin_declares_restore_action(self):
        admin_obj = self._admin_for(DQRun)
        action_names = (
            list(getattr(admin_obj, "actions", None) or [])
        )
        # ``actions`` may be a list of callables or strings — both
        # forms work in Django. Resolve to a name set.
        resolved_names = {
            getattr(a, "__name__", a) for a in action_names if a is not None
        }
        self.assertIn(
            "restore", resolved_names,
            "DQRunAdmin must declare a `restore` action so ops "
            "can un-delete soft-deleted rows from the changelist. "
            f"Got actions: {resolved_names}",
        )

    def test_restore_action_un_deletes_selected_rows(self):
        """The action MUST flip ``is_deleted=False`` and clear
        ``deleted_at`` on the selected rows."""
        from django.test import RequestFactory

        run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )
        run.soft_delete()
        self.assertTrue(run.is_deleted)
        self.assertIsNotNone(run.deleted_at)

        from django.contrib.messages.storage.fallback import FallbackStorage

        admin_obj = self._admin_for(DQRun)
        request = RequestFactory().post("/admin/dq/dqrun/")
        request.user = self.user

        # ``RequestFactory`` bypasses middleware; admin actions call
        # ``self.message_user`` which calls
        # ``django.contrib.messages.add_message`` which requires
        # ``request._messages`` (normally attached by
        # ``MessageMiddleware``).  Attach a fallback storage backend
        # explicitly — this is the canonical Django docs pattern for
        # testing admin actions outside the request/response stack.
        # The session attr is also required by the storage backend's
        # cookie path, even when nothing reads it back.
        setattr(request, "session", {})
        setattr(request, "_messages", FallbackStorage(request))

        # Resolve the bound or unbound restore method and call it.
        restore_action = None
        for entry in getattr(admin_obj, "actions", None) or []:
            name = getattr(entry, "__name__", entry)
            if name == "restore":
                restore_action = (
                    entry if callable(entry) else getattr(admin_obj, entry)
                )
                break
        self.assertIsNotNone(restore_action, "restore action not resolvable")
        assert restore_action is not None  # narrow for pyright

        queryset = DQRun.all_objects.filter(id=run.id)
        # Django admin actions accept (modeladmin, request, queryset).
        # Bound methods only need (request, queryset).
        try:
            restore_action(request, queryset)
        except TypeError:
            restore_action(admin_obj, request, queryset)

        run.refresh_from_db()
        self.assertFalse(
            run.is_deleted,
            "restore action did not clear is_deleted",
        )
        self.assertIsNone(
            run.deleted_at,
            "restore action did not clear deleted_at",
        )
