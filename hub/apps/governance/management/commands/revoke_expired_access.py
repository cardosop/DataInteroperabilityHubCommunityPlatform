"""
Management command to revoke expired access requests.

Transitions APPROVED access requests past their expires_at to REVOKED,
creates audit events for each revocation, and revokes linked marketplace
entitlements.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from hub.apps.audit.utils import create_audit_event
from hub.apps.governance.models import AccessRequest, AccessRequestStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Revoke expired APPROVED access requests"

    def handle(self, *args, **options):
        now = timezone.now()

        expired_requests = AccessRequest.objects.filter(
            status=AccessRequestStatus.APPROVED,
            expires_at__lt=now,
            expires_at__isnull=False,
        )

        count = expired_requests.count()
        if count == 0:
            self.stdout.write("No expired access requests found.")
            return

        revoked = 0
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
                        from hub.apps.marketplace.entitlement_utils import revoke_entitlement_for_order
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

        self.stdout.write(
            self.style.SUCCESS(f"Revoked {revoked} expired access request(s).")
        )
