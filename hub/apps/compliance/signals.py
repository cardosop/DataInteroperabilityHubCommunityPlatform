"""
Phase 231.1 — auto-enqueue compliance intake scan when an Asset is registered.

Phase 231.4 — tenant ``compliance.completed`` webhooks on terminal ``ComplianceRun``.
"""

from __future__ import annotations
import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from hub.apps.assets.models import Asset
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ComplianceRun)
def compliance_run_cache_prior_status(
    sender,
    instance: ComplianceRun,
    **_kwargs,
) -> None:
    """Capture previous status for Phase 231.4 terminal-transition detection."""
    if not instance.pk:
        setattr(instance, "_compliance_prior_status", None)
        return
    try:
        prior = ComplianceRun.objects.only("status").get(pk=instance.pk)
        setattr(instance, "_compliance_prior_status", prior.status)
    except ComplianceRun.DoesNotExist:
        setattr(instance, "_compliance_prior_status", None)


@receiver(post_save, sender=ComplianceRun)
def emit_compliance_completed_webhook_on_terminal_transition(
    sender,
    instance: ComplianceRun,
    created: bool,
    update_fields=None,
    **_kwargs,
) -> None:
    """
    Fire ``compliance.completed`` when a run first reaches SUCCEEDED or FAILED.

    Fail-soft (D231.11): never raise from the signal — scheduling uses
    ``transaction.on_commit``.
    """
    if update_fields is not None:
        meta_only = {"webhook_fired_at", "updated_at"}
        if set(update_fields).issubset(meta_only):
            return

    terminal_statuses = {
        ComplianceRunStatus.SUCCEEDED,
        ComplianceRunStatus.FAILED,
    }
    try:
        if instance.status not in terminal_statuses:
            return
        if instance.webhook_fired_at is not None:
            return
        prior_status = getattr(instance, "_compliance_prior_status", None)
        if not created and prior_status == instance.status:
            return

        if instance.tenant_id is None:
            logger.warning(
                "compliance_completed_webhook_skipped_no_tenant",
                extra={"run_id": str(instance.pk)},
            )
            return

        run_pk = instance.pk
        tenant_pk = instance.tenant_id

        def _emit() -> None:
            from hub.apps.compliance.models import ComplianceRun as CR
            from hub.apps.compliance.webhook_emission import (
                publish_compliance_check_completed,
            )

            stub = CR(pk=run_pk, tenant_id=tenant_pk)
            publish_compliance_check_completed(stub)

        transaction.on_commit(_emit)
    except Exception:
        logger.exception(
            "compliance_completed_webhook_signal_failed",
            extra={
                "run_id": str(instance.pk),
                "tenant_id": str(instance.tenant_id),
            },
        )


@receiver(post_save, sender=ComplianceRun)
def invalidate_marketplace_cache_when_listed_asset_compliance_updates(
    sender,
    instance: ComplianceRun,
    created: bool,
    update_fields=None,
    **_kwargs,
) -> None:
    """
    Bust marketplace listing detail cache when a succeeded asset run may change serialized badge data.

    ``ListingSerializer.latest_compliance_run`` reads from ``asset.compliance_runs``; ``retrieve``
    caches the JSON response. Fail-soft: never raise from the signal.
    """
    if instance.status != ComplianceRunStatus.SUCCEEDED:
        return
    if instance.asset_id is None:
        return
    if update_fields is not None:
        meta_only = {"webhook_fired_at", "updated_at"}
        if set(update_fields).issubset(meta_only):
            return

    asset_pk = instance.asset_id

    def _invalidate() -> None:
        from hub.apps.marketplace.caching import invalidate_marketplace_caches_for_asset

        try:
            invalidate_marketplace_caches_for_asset(asset_pk)
        except Exception:
            logger.exception(
                "marketplace_cache_invalidation_compliance_signal_failed",
                extra={
                    "run_id": str(instance.pk),
                    "asset_id": str(asset_pk),
                },
            )

    try:
        transaction.on_commit(_invalidate)
    except Exception:
        logger.exception(
            "marketplace_cache_invalidation_compliance_signal_schedule_failed",
            extra={"run_id": str(instance.pk)},
        )


@receiver(post_save, sender=Asset)
def enqueue_compliance_intake_scan_on_asset_created(
    sender,
    instance: Asset,
    created: bool,
    **kwargs,
) -> None:
    """Fail-soft (D231.11): never raise from signal — log and continue."""
    if not created:
        return
    try:
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.only("compliance_intake_gate_enabled").get(
            pk=instance.tenant_id,
        )
        if not tenant.compliance_intake_gate_enabled:
            return
        if not instance.created_by_id:
            logger.warning(
                "compliance_intake_signal_skipped_no_created_by",
                extra={
                    "asset_id": str(instance.id),
                    "tenant_id": str(instance.tenant_id),
                },
            )
            return
        from hub.apps.compliance.intake_scan import (
            enqueue_compliance_intake_scan,
        )

        enqueue_compliance_intake_scan(
            str(instance.id),
            str(instance.tenant_id),
        )
    except Exception:
        logger.exception(
            "compliance_intake_asset_signal_failed",
            extra={
                "asset_id": str(instance.id),
                "tenant_id": str(instance.tenant_id),
            },
        )
