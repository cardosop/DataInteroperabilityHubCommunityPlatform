"""
Management command to revoke expired access requests.

Transitions APPROVED access requests past their expires_at to REVOKED,
creates audit events for each revocation, and revokes linked marketplace
entitlements.

Phase 270.B.2.2 — additionally transitions PENDING access requests past
the tenant's ``access_request_pending_sla_days`` threshold to EXPIRED,
with per-tenant iteration via the admin DB (BYPASSRLS) and
``tenant_context`` for correct RLS scoping.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Revoke expired APPROVED access requests and expire stale PENDING requests by SLA"

    def handle(self, *args, **options):
        now = timezone.now()
        revoked = 0
        total_expired = 0

        # ── Legacy path: APPROVED + past expires_at → REVOKED ──
        expired_requests = AccessRequest.objects.filter(
            status=AccessRequestStatus.APPROVED,
            expires_at__lt=now,
            expires_at__isnull=False,
        )

        approved_count = expired_requests.count()
        if approved_count > 0:
            with transaction.atomic():
                # Note: we do NOT select_related("order") here because
                # "order" is a nullable FK and Postgres forbids FOR UPDATE
                # on the nullable side of an outer join.
                for request in expired_requests.select_for_update().select_related(
                    "tenant", "requested_by"
                ):
                    request.status = AccessRequestStatus.REVOKED
                    request.save(update_fields=["status", "updated_at"])

                    # Cascade to marketplace entitlement
                    if request.order:
                        try:
                            from hub.apps.marketplace.entitlement_utils import (
                                revoke_entitlement_for_order,
                            )

                            revoke_entitlement_for_order(
                                request.order, reason="Governance access expired"
                            )
                        except Exception:
                            logger.warning(
                                "Failed to revoke entitlement for order %s",
                                request.order_id,
                            )

                    create_audit_event(
                        resource_type="ACCESS_REQUEST",
                        action="ACCESS_EXPIRED_REVOKED",
                        tenant=request.tenant,
                        resource_id=str(request.id),
                        details={
                            "requested_by": str(request.requested_by_id),
                            "expires_at": request.expires_at.isoformat(),
                            "revoked_at": now.isoformat(),
                        },
                    )
                    revoked += 1

        # ── Phase 270.B.2.2: PENDING + over SLA → EXPIRED ──
        # Enumerate active tenants via the admin DB alias (BYPASSRLS) so
        # the enumeration itself is not filtered by RLS policies, then
        # process each tenant inside tenant_context so that AccessRequest
        # RLS policies scope reads and writes to the correct tenant.
        from hub.apps.tenants.request_tenant import tenant_context

        # Enumerate via the default connection, which in management commands
        # runs as meshant_admin (BYPASSRLS) per DATABASES["admin"] in settings.
        # Do NOT use .using("admin") here — in tests, that opens a separate
        # connection that cannot see uncommitted transaction data from TestCase.
        active_tenants = Tenant.objects.filter(status="ACTIVE")

        for tenant in active_tenants:
            sla_days = tenant.access_request_pending_sla_days
            cutoff = now - timedelta(days=sla_days)

            with tenant_context(tenant.id):
                with transaction.atomic():
                    # Explicit tenant= filter is load-bearing: in test
                    # environments RLS policies may not be active, so
                    # the query would otherwise sweep PENDING requests
                    # from ALL tenants on every iteration, causing
                    # cross-tenant data leakage and wrong audit payloads.
                    stale = AccessRequest.objects.filter(
                        tenant=tenant,
                        status=AccessRequestStatus.PENDING,
                        created_at__lt=cutoff,
                    ).select_for_update()

                    for ar in stale:
                        age_days = (now - ar.created_at).total_seconds() / 86400

                        ar.status = AccessRequestStatus.EXPIRED
                        ar.save(update_fields=["status", "updated_at"])

                        create_audit_event(
                            resource_type="ACCESS_REQUEST",
                            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
                            tenant=tenant,
                            resource_id=str(ar.id),
                            details={
                                "previous_status": AccessRequestStatus.PENDING,
                                "sla_days": sla_days,
                                "age_days": round(age_days, 2),
                                "access_request_id": str(ar.id),
                                "tenant_id": str(tenant.id),
                            },
                        )
                        total_expired += 1

        if revoked == 0 and total_expired == 0:
            self.stdout.write("No expired access requests found.")
            return

        if revoked > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Revoked {revoked} expired access request(s)."
                )
            )
        if total_expired > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Expired {total_expired} pending access request(s) by SLA."
                )
            )
