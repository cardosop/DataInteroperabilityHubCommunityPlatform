"""
Phase 240.5.B.1 / 240.5.B.2 — Django admin for the DQ app.

Registers four ModelAdmins so ops staff can inspect + recover DQ
data through the standard ``/admin/`` UI:

* :class:`DQRunAdmin` — soft-delete-aware (uses ``all_objects``);
  exposes a ``restore`` admin action so deleted rows can be
  recovered without dropping into a Django shell.
* :class:`DQAnomalyAdmin` — same soft-delete pattern.
* :class:`DQTrendAdmin` — same soft-delete pattern.
* :class:`DQAlertingRuleAdmin` — no soft-delete (model is
  hard-delete-only); standard ModelAdmin shape only.

JSON columns (``details_json``, ``checks_json``, ``metadata``,
``channel_config``) are pinned in ``readonly_fields`` so an
errant click in the admin UI can't clobber the audit trail.
"""
from __future__ import annotations

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import DQAlertingRule, DQAnomaly, DQRun, DQTrend


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _restore_soft_deleted(model_cls, queryset):
    """Helper that flips ``is_deleted=False`` and clears ``deleted_at``
    on every row in ``queryset``. Returns the number of rows updated.

    Used by the ``restore`` admin actions registered on the three
    soft-delete-aware ModelAdmins. Goes through ``all_objects``
    (the queryset is already from there in the admin context) so
    we don't accidentally filter out the rows we're trying to
    restore.
    """
    return queryset.update(is_deleted=False, deleted_at=None)


# ---------------------------------------------------------------------------
# DQRun
# ---------------------------------------------------------------------------


@admin.register(DQRun)
class DQRunAdmin(admin.ModelAdmin):
    """ops-facing admin for DQ runs.

    Visibility: shows soft-deleted rows by overriding
    ``get_queryset`` to use ``DQRun.all_objects`` instead of the
    default ``objects`` manager — admins MUST see deleted runs to
    diagnose retention / accidental-delete incidents.
    """

    list_display = (
        "id",
        "tenant",
        "asset",
        "status",
        "overall_status",
        "engine",
        "quality_score",
        "started_at",
        "completed_at",
        "is_deleted",
    )
    list_filter = (
        "status",
        "overall_status",
        "engine",
        "is_deleted",
        "created_at",
    )
    search_fields = (
        "id",
        "tenant__name",
        "tenant__slug",
        "asset__key",
        "asset__name",
        "profile_key",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "started_at",
        "completed_at",
        "deleted_at",
        "checks_json",
        "details_json",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["restore"]

    def get_queryset(self, request):
        """Return ALL rows including soft-deleted.

        Ops needs visibility into deleted rows for incident
        response (e.g. "did the purge job hard-delete this row,
        or is it just soft-deleted and recoverable?"). The
        default manager would hide soft-deleted rows.
        """
        return DQRun.all_objects.get_queryset().select_related(
            "tenant", "asset", "dataset", "file", "job",
        )

    @admin.action(description="Restore selected soft-deleted DQ runs")
    def restore(self, request, queryset):
        """Flip ``is_deleted=False`` + clear ``deleted_at``.

        Idempotent: rows already non-deleted are unaffected. The
        operation goes through ``QuerySet.update`` (single SQL
        UPDATE) so it's atomic and avoids re-saving unrelated
        fields — important on a table that may have signal
        listeners on save.
        """
        updated = _restore_soft_deleted(DQRun, queryset)
        self.message_user(
            request,
            f"Restored {updated} DQ run(s).",
        )


# ---------------------------------------------------------------------------
# DQAnomaly
# ---------------------------------------------------------------------------


@admin.register(DQAnomaly)
class DQAnomalyAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "asset",
        "metric_type",
        "severity",
        "deviation",
        "acknowledged",
        "detected_at",
        "is_deleted",
    )
    list_filter = (
        "severity",
        "metric_type",
        "acknowledged",
        "is_deleted",
        "detected_at",
    )
    search_fields = (
        "id",
        "tenant__name",
        "asset__key",
        "asset__name",
        "metric_type",
        "anomaly_type",
    )
    readonly_fields = (
        "id",
        "detected_at",
        "acknowledged_at",
        "deleted_at",
        "metadata",
    )
    date_hierarchy = "detected_at"
    ordering = ("-detected_at",)
    actions = ["restore"]

    def get_queryset(self, request):
        return DQAnomaly.all_objects.get_queryset().select_related(
            "tenant", "asset", "dataset", "dq_run", "acknowledged_by",
        )

    @admin.action(description="Restore selected soft-deleted anomalies")
    def restore(self, request, queryset):
        updated = _restore_soft_deleted(DQAnomaly, queryset)
        self.message_user(request, f"Restored {updated} anomaly/anomalies.")


# ---------------------------------------------------------------------------
# DQTrend
# ---------------------------------------------------------------------------


@admin.register(DQTrend)
class DQTrendAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "asset",
        "metric_type",
        "direction",
        "current_value",
        "previous_value",
        "change_percent",
        "period_start",
        "is_deleted",
    )
    list_filter = (
        "direction",
        "metric_type",
        "period_type",
        "is_deleted",
        "created_at",
    )
    search_fields = (
        "id",
        "tenant__name",
        "asset__key",
        "asset__name",
        "metric_type",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "deleted_at",
        "metadata",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    actions = ["restore"]

    def get_queryset(self, request):
        return DQTrend.all_objects.get_queryset().select_related(
            "tenant", "asset", "dataset",
        )

    @admin.action(description="Restore selected soft-deleted trends")
    def restore(self, request, queryset):
        updated = _restore_soft_deleted(DQTrend, queryset)
        self.message_user(request, f"Restored {updated} trend(s).")


# ---------------------------------------------------------------------------
# DQAlertingRule (no soft-delete on this model)
# ---------------------------------------------------------------------------


@admin.register(DQAlertingRule)
class DQAlertingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "asset",
        "name",
        "metric_type",
        "comparison_operator",
        "threshold",
        "severity",
        "enabled",
        "last_fired_at",
    )
    list_filter = (
        "severity",
        "metric_type",
        "comparison_operator",
        "enabled",
        "created_at",
    )
    search_fields = (
        "id",
        "tenant__name",
        "asset__key",
        "asset__name",
        "name",
        "description",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "last_alert_id",
        "last_fired_at",
        "channel_config",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
