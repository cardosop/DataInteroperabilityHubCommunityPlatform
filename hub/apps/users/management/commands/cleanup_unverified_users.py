from __future__ import annotations
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


DEFAULT_UNVERIFIED_USER_RETENTION_DAYS: int = 30
_PERSONAL_TENANT_SLUG_PREFIX = "personal-"


def _is_auto_created_personal_tenant(*, user, tenant) -> bool:
    if tenant is None:
        return False
    expected_name = f"Personal - {user.email}"
    return bool(
        tenant.slug.startswith(_PERSONAL_TENANT_SLUG_PREFIX)
        and tenant.name == expected_name
    )


def _tenant_has_non_trivial_activity(*, tenant) -> bool:
    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract
    from hub.apps.datasets.models import Dataset

    return (
        Asset.objects.filter(tenant=tenant).exists()
        or Dataset.objects.filter(tenant=tenant).exists()
        or Contract.objects.filter(tenant=tenant).exists()
    )


def _should_delete_personal_tenant_after_user_delete(
    *,
    tenant,
    deleting_user_id,
) -> bool:
    from hub.apps.users.models import User, UserTenantMembership

    has_other_primary_users = User.objects.filter(tenant=tenant).exclude(
        pk=deleting_user_id
    ).exists()
    if has_other_primary_users:
        return False
    has_other_memberships = (
        UserTenantMembership.objects.filter(tenant=tenant)
        .exclude(user_id=deleting_user_id)
        .exists()
    )
    if has_other_memberships:
        return False
    return not _tenant_has_non_trivial_activity(tenant=tenant)


def _emit_user_deleted_unverified_audit(
    *,
    user_id: str,
    user_email: str,
    tenant,
    retention_days: int,
    tenant_deleted: bool,
) -> None:
    from hub.apps.audit import event_types as audit_event_types
    from hub.apps.audit.utils import create_audit_event

    create_audit_event(
        resource_type="USER",
        action=audit_event_types.USER_DELETED_UNVERIFIED,
        actor_user=None,
        tenant=None if tenant_deleted else tenant,
        resource_id=user_id,
        result="SUCCESS",
        details={
            "user_id": user_id,
            "user_email": user_email,
            "tenant_id": str(tenant.id) if tenant is not None else None,
            "retention_days": retention_days,
            "tenant_deleted": tenant_deleted,
        },
    )


def _set_cleanup_metrics(*, deleted_count: int, skipped_with_activity_count: int) -> None:
    try:
        from services.shared.metrics import (
            unverified_users_deleted_total,
            unverified_users_with_activity,
        )  # type: ignore[attr-defined]  # prometheus_client Gauge.labels().set() — attr chain not visible to mypy
    except ImportError:
        return

    unverified_users_deleted_total.labels(service="hub").set(  # type: ignore[attr-defined]  # prometheus_client Gauge.labels().set() chain
        deleted_count
    )
    unverified_users_with_activity.labels(service="hub").set(  # type: ignore[attr-defined]  # prometheus_client Gauge.labels().set() chain
        skipped_with_activity_count
    )


class Command(BaseCommand):
    help = (
        "Delete stale unverified self-service (personal-tenant) registrations "
        "older than the retention threshold and cascade-delete empty personal "
        "tenants."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=None,
            help=(
                "Override retention threshold in days. Defaults to "
                "UNVERIFIED_USER_RETENTION_DAYS (or 30)."
            ),
        )

    def handle(self, *args, **opts):
        from hub.apps.users.models import User

        retention_days = self._resolve_retention_days(
            explicit_days=opts.get("retention_days")
        )
        cutoff = timezone.now() - timedelta(days=retention_days)
        candidates = (
            User.objects.filter(
                email_verified=False,
                created_at__lt=cutoff,
                is_platform_admin=False,
            )
            .select_related("tenant")
            .order_by("created_at")
        )

        deleted_count = 0
        skipped_with_activity_count = 0
        deleted_tenants_count = 0

        for user in candidates.iterator(chunk_size=200):
            tenant = user.tenant
            if not _is_auto_created_personal_tenant(user=user, tenant=tenant):
                continue

            if _tenant_has_non_trivial_activity(tenant=tenant):
                skipped_with_activity_count += 1
                continue

            with transaction.atomic():
                user_id_str = str(user.id)
                user_email = user.email
                delete_personal_tenant = _should_delete_personal_tenant_after_user_delete(
                    tenant=tenant,
                    deleting_user_id=user.id,
                )
                _emit_user_deleted_unverified_audit(
                    user_id=user_id_str,
                    user_email=user_email,
                    tenant=tenant,
                    retention_days=retention_days,
                    tenant_deleted=delete_personal_tenant,
                )
                user.delete()
                if delete_personal_tenant:
                    tenant.delete()
                    deleted_tenants_count += 1

            deleted_count += 1

        _set_cleanup_metrics(
            deleted_count=deleted_count,
            skipped_with_activity_count=skipped_with_activity_count,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "cleanup_unverified_users complete: "
                f"deleted_users={deleted_count} "
                f"skipped_with_activity={skipped_with_activity_count} "
                f"deleted_personal_tenants={deleted_tenants_count} "
                f"retention_days={retention_days}"
            )
        )

    def _resolve_retention_days(self, *, explicit_days: Optional[int]) -> int:
        if explicit_days is not None:
            return int(explicit_days)
        configured_days = getattr(
            settings,
            "UNVERIFIED_USER_RETENTION_DAYS",
            DEFAULT_UNVERIFIED_USER_RETENTION_DAYS,
        )
        return int(configured_days)
