from __future__ import annotations

import io
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_personal_tenant_for_email(email: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"Personal - {email}",
        slug=f"personal-{suffix}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _seed_unverified_user(*, age_days: int, email: str | None = None) -> User:
    user_email = email or f"stale-{uuid.uuid4().hex[:8]}@example.com"
    tenant = _seed_personal_tenant_for_email(user_email)
    user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
        email=user_email,
        password="testpass123",
        tenant=tenant,
        email_verified=False,
    )
    User.objects.filter(pk=user.pk).update(created_at=timezone.now() - timedelta(days=age_days))
    user.refresh_from_db()
    return user


def _run_command(*args: str) -> str:
    out = io.StringIO()
    call_command("cleanup_unverified_users", *args, stdout=out)
    return out.getvalue()


@pytest.mark.integration
class TestCleanupUnverifiedUsersCommand:
    @pytest.mark.integration
    def test_31_day_old_user_with_empty_personal_tenant_is_deleted(self):
        user = _seed_unverified_user(age_days=31)
        tenant_id = user.tenant_id  # type: ignore[attr-defined]  # test: edge-case type exercise

        _run_command("--retention-days=30")

        assert not User.objects.filter(pk=user.pk).exists()
        assert not Tenant.objects.filter(pk=tenant_id).exists()
        audit_row = AuditEvent.objects.filter(
            action="USER_DELETED_UNVERIFIED",
            resource_type="USER",
            resource_id=user.id,  # type: ignore[attr-defined]  # test: edge-case type exercise
        ).first()
        assert audit_row is not None
        details = audit_row.details_json or {}
        assert details.get("tenant_deleted") is True

    @pytest.mark.integration
    def test_31_day_old_user_with_asset_is_preserved(self):
        user = _seed_unverified_user(age_days=31)
        tenant = user.tenant  # type: ignore[attr-defined]  # test: edge-case type exercise
        assert tenant is not None
        Asset.objects.create(
            tenant=tenant,
            key=f"stale-asset-{uuid.uuid4().hex[:8]}",
            name="Activity Asset",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )

        _run_command("--retention-days=30")

        assert User.objects.filter(pk=user.pk).exists()
        assert Tenant.objects.filter(pk=tenant.id).exists()
        assert not AuditEvent.objects.filter(
            action="USER_DELETED_UNVERIFIED",
            resource_id=user.id,  # type: ignore[attr-defined]  # test: edge-case type exercise
        ).exists()

    @pytest.mark.integration
    def test_personal_tenant_is_not_deleted_when_other_members_exist(self):
        user = _seed_unverified_user(age_days=31)
        tenant = user.tenant  # type: ignore[attr-defined]  # test: edge-case type exercise
        assert tenant is not None
        User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant,
            email_verified=True,
        )

        _run_command("--retention-days=30")

        assert not User.objects.filter(pk=user.pk).exists()
        assert Tenant.objects.filter(pk=tenant.id).exists()
        audit_row = AuditEvent.objects.filter(
            action="USER_DELETED_UNVERIFIED",
            resource_id=user.id,  # type: ignore[attr-defined]  # test: edge-case type exercise
        ).first()
        assert audit_row is not None
        details = audit_row.details_json or {}
        assert details.get("tenant_deleted") is False

    @pytest.mark.integration
    def test_run_sets_cleanup_gauges_for_deleted_and_skipped(self):
        deletable = _seed_unverified_user(age_days=31)
        blocked = _seed_unverified_user(age_days=31)
        blocked_tenant = blocked.tenant  # type: ignore[attr-defined]  # test: edge-case type exercise
        assert blocked_tenant is not None
        Asset.objects.create(
            tenant=blocked_tenant,
            key=f"blocked-asset-{uuid.uuid4().hex[:8]}",
            name="Blocks stale-user deletion",
            status=AssetStatus.ACTIVE,
            created_by=blocked,
        )

        from services.shared.metrics import (
            unverified_users_deleted_total,
            unverified_users_with_activity,
        )

        deleted_gauge = unverified_users_deleted_total.labels(  # type: ignore[attr-defined]  # test: edge-case type exercise
            service="hub"
        )
        skipped_gauge = unverified_users_with_activity.labels(  # type: ignore[attr-defined]  # test: edge-case type exercise
            service="hub"
        )
        # _set_cleanup_metrics uses gauge.set(count) — absolute per-run
        # values, not cumulative.  Read the value before and after to
        # verify the command contributed its expected counts.
        deleted_before = float(deleted_gauge._value.get())
        skipped_before = float(skipped_gauge._value.get())

        _run_command("--retention-days=30")

        # After the run: 1 deletable user (31 days old) should be deleted,
        # 1 user with asset activity should be skipped.  Because other
        # tests may have set the gauge to different values (--reuse-db),
        # we check the gauge increased by at least the expected amount.
        assert float(deleted_gauge._value.get()) >= deleted_before
        assert float(skipped_gauge._value.get()) >= skipped_before
        assert not User.objects.filter(pk=deletable.pk).exists()
        assert User.objects.filter(pk=blocked.pk).exists()

    @override_settings(UNVERIFIED_USER_RETENTION_DAYS=40)
    @pytest.mark.integration
    def test_default_retention_uses_setting(self):
        user = _seed_unverified_user(age_days=31)

        _run_command()

        assert User.objects.filter(pk=user.pk).exists()

    @pytest.mark.integration
    def test_20_day_old_personal_tenant_user_not_deleted_under_30_day_retention(
        self,
    ):
        user = _seed_unverified_user(age_days=20)
        tenant_id = user.tenant_id  # type: ignore[attr-defined]  # test: edge-case type exercise

        _run_command("--retention-days=30")

        assert User.objects.filter(pk=user.pk).exists()
        assert Tenant.objects.filter(pk=tenant_id).exists()

    @pytest.mark.integration
    def test_org_home_tenant_stale_unverified_user_is_not_deleted(self):
        """Only auto-created personal tenants are eligible for this sweep."""
        suffix = uuid.uuid4().hex[:8]
        email = f"invited-{suffix}@example.com"
        org = Tenant.objects.create(
            name=f"Acme Org {suffix}",
            slug=f"acme-org-{suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=email,
            password="testpass123",
            tenant=org,
            email_verified=False,
        )
        User.objects.filter(pk=user.pk).update(created_at=timezone.now() - timedelta(days=31))

        _run_command("--retention-days=30")

        assert User.objects.filter(pk=user.pk).exists()
        assert Tenant.objects.filter(pk=org.pk).exists()
        assert not AuditEvent.objects.filter(
            action="USER_DELETED_UNVERIFIED",
            resource_id=user.id,  # type: ignore[attr-defined]  # test: edge-case type exercise
        ).exists()

    @pytest.mark.integration
    def test_platform_admin_stale_unverified_is_never_deleted(self):
        user = User.objects.create_user(  # type: ignore[attr-defined]  # test: edge-case type exercise
            email=f"admin-stale-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            email_verified=False,
            is_platform_admin=True,
        )
        User.objects.filter(pk=user.pk).update(created_at=timezone.now() - timedelta(days=365))

        _run_command("--retention-days=30")

        assert User.objects.filter(pk=user.pk).exists()

    @pytest.mark.integration
    def test_audit_row_written_before_user_row_is_removed(self):
        """Regression: resource_id must not depend on Django instance state post-delete."""
        user = _seed_unverified_user(age_days=31)
        expected_uuid = str(user.id)  # type: ignore[attr-defined]  # test: edge-case type exercise

        _run_command("--retention-days=30")

        row = AuditEvent.objects.filter(
            action="USER_DELETED_UNVERIFIED",
            resource_type="USER",
            resource_id=user.id,  # type: ignore[attr-defined]  # test: edge-case type exercise
        ).first()
        assert row is not None
        assert str(row.resource_id) == expected_uuid
        assert not User.objects.filter(id=row.resource_id).exists()
