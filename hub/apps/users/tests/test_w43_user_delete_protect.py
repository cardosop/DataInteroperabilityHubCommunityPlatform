"""
W4.3 / E8 — user-delete PROTECT pre-checks.

``delete_user`` decides between soft-delete (DISABLED) and hard-delete by
checking whether the user "has resources" (created_by on Asset/Dataset/
Contract/File). The check ignored the PROTECT referrers —
``FeatureFlagFlipApproval.requested_by`` / ``approved_by``,
``ImpersonationSession.impersonator``, ``PlanPriceChangeApproval.requested_by`` /
``approved_by`` — so a hard delete of such a user crashed with
``ProtectedError`` (500) instead of the documented soft-delete contract.

The pre-check must enumerate ALL PROTECT/RESTRICT referrers (via model
metadata so future referrers are covered automatically) and route the
user through the soft-delete path with an itemized ``USER_DISABLED``
audit entry.

No mocks — real users, real referrer rows, real audit events.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Tenant {uid}", slug=f"ud-tenant-{uid}")


def _make_user(tenant: Tenant, *, prefix: str = "u") -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{prefix}-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _delete_user(target: User, actor: User):
    from hub.apps.users.services import UserService

    service = UserService(tenant_id=str(target.tenant_id), user_id=str(actor.id))
    return service.delete_user(
        user_id=str(target.id),
        tenant_id=str(target.tenant_id),
        actor_user_id=str(actor.id),
    )


def _user_disabled_audit(target: User) -> AuditEvent | None:
    return (
        AuditEvent.objects.filter(action="USER_DISABLED", resource_id=str(target.id))
        .order_by("-timestamp")
        .first()
    )


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------


class TestUserDeleteProtectedReferrers:
    def test_feature_flag_approval_referrer_forces_soft_delete(self):
        from hub.apps.tenants.models import FeatureFlagFlipApproval
        from hub.apps.users.models import UserStatus

        tenant = _make_tenant()
        target = _make_user(tenant)
        actor = _make_user(tenant, prefix="admin")
        FeatureFlagFlipApproval.objects.create(
            tenant=tenant,
            flag="sensitive_flag_x",
            requested_value=True,
            requested_by=target,
        )

        soft_deleted = _delete_user(target, actor)

        assert (
            soft_deleted is True
        ), "a user with a PROTECT referrer must take the soft-delete path"
        target.refresh_from_db()
        assert target.status == UserStatus.DISABLED
        audit = _user_disabled_audit(target)
        assert audit is not None
        referrers = (audit.details_json or {}).get("protected_referrers", {})
        assert referrers.get("requested_feature_flag_flips") == 1

    def test_impersonation_session_referrer_forces_soft_delete(self):
        from hub.apps.tenants.models import ImpersonationSession
        from hub.apps.users.models import UserStatus

        tenant = _make_tenant()
        target = _make_user(tenant)
        actor = _make_user(tenant, prefix="admin")
        ImpersonationSession.objects.create(
            impersonator=target,
            impersonated_user=actor,
            impersonator_tenant=tenant,
            impersonated_tenant=tenant,
            started_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
            max_minutes=60,
        )

        soft_deleted = _delete_user(target, actor)

        assert soft_deleted is True
        target.refresh_from_db()
        assert target.status == UserStatus.DISABLED
        audit = _user_disabled_audit(target)
        assert audit is not None
        referrers = (audit.details_json or {}).get("protected_referrers", {})
        assert referrers.get("impersonation_sessions_started") == 1

    def test_price_change_approval_referrer_forces_soft_delete(self):
        from hub.apps.tenants.models import PlanPriceChangeApproval, TenantPlan
        from hub.apps.users.models import UserStatus

        tenant = _make_tenant()
        target = _make_user(tenant)
        actor = _make_user(tenant, prefix="admin")
        plan = TenantPlan.objects.create(
            slug=f"plan-{uuid.uuid4().hex[:8]}",
            name=f"Plan {uuid.uuid4().hex[:8]}",
            tier="FREE",
            limits_json={},
            is_active=True,
        )
        PlanPriceChangeApproval.objects.create(
            requested_by=target,
            tenant_plan=plan,
            old_price_cents=100,
            new_price_cents=200,
        )

        soft_deleted = _delete_user(target, actor)

        assert soft_deleted is True
        target.refresh_from_db()
        assert target.status == UserStatus.DISABLED
        audit = _user_disabled_audit(target)
        assert audit is not None
        referrers = (audit.details_json or {}).get("protected_referrers", {})
        assert referrers.get("requested_price_changes") == 1

    def test_clean_user_still_hard_deleted(self):
        """Contract guard: without resources or PROTECT referrers the user
        is hard-deleted (return False, row gone) — the pre-check must not
        force soft-delete for everyone."""
        tenant = _make_tenant()
        target = _make_user(tenant)
        actor = _make_user(tenant, prefix="admin")

        soft_deleted = _delete_user(target, actor)

        assert soft_deleted is False
        assert not User.objects.filter(pk=target.pk).exists()
