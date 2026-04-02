"""
Management command to downgrade expired KYC verifications.

Transitions VERIFIED tenants past their kyc_expires_at to PENDING_REVIEW.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.tenants.models import KYCStatus, Tenant


class Command(BaseCommand):
    help = "Downgrade expired KYC verifications to PENDING_REVIEW"

    def handle(self, *args, **options):
        now = timezone.now()

        expired_tenants = Tenant.objects.filter(
            kyc_status=KYCStatus.VERIFIED,
            kyc_expires_at__lt=now,
            kyc_expires_at__isnull=False,
        )

        count = expired_tenants.count()
        if count == 0:
            self.stdout.write("No expired KYC verifications found.")
            return

        updated = expired_tenants.update(kyc_status=KYCStatus.PENDING_REVIEW)

        self.stdout.write(
            self.style.SUCCESS(f"Downgraded {updated} tenant(s) to PENDING_REVIEW.")
        )
