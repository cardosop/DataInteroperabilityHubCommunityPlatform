"""
Management command to ensure E2E test users' tenants have active subscriptions and VERIFIED KYC.

Frontend E2E tests (Playwright) create users via registration API. New tenants
have no subscription; TenantSuspensionMiddleware blocks POST/PUT/PATCH/DELETE
with 403 subscription_inactive. Marketplace publish requires VERIFIED KYC.
This command ensures e2e_test@example.com and e2e_consumer@example.com tenants
have active subscriptions and VERIFIED KYC so asset creation, publish, etc. work.

Run before E2E when using docker-compose.test:
  docker exec hub-test-api python hub/manage.py ensure_e2e_subscription

Or the e2e-detect-api.sh script runs it automatically when API is on port 8001.
"""

from django.core.management.base import BaseCommand

from hub.apps.testing.billing_support import ensure_e2e_tenant_ready
from hub.apps.users.management.commands.ensure_e2e_user_roles import (
    PROFILE_ISOLATION_WORKER_COUNT,
)
from hub.apps.users.models import User

# Must match ensure_e2e_user_roles.E2E_USERS and api/views.E2E_EMAILS
_PROFILE_E2E_EMAILS = tuple(
    f"e2e_profile_w{i}@example.com" for i in range(PROFILE_ISOLATION_WORKER_COUNT)
)
E2E_EMAILS = (
    "e2e_test@example.com",
    "e2e_consumer@example.com",
    "e2e_admin@example.com",
    "e2e_platform@example.com",
    "e2e_auditor@example.com",
    "e2e_cpo@example.com",
    "e2e_developer@example.com",
    "e2e_dmo@example.com",
) + _PROFILE_E2E_EMAILS


class Command(BaseCommand):
    help = "Ensure E2E test users' tenants have active subscriptions"

    def handle(self, *args, **options):
        updated = 0
        for email in E2E_EMAILS:
            user = User.objects.filter(email=email).select_related("tenant").first()
            if not user:
                self.stdout.write(f"  - {email}: user not found (register first via E2E setup)")
                continue
            if not user.tenant_id:
                self.stdout.write(f"  - {email}: no tenant")
                continue
            ensure_e2e_tenant_ready(user.tenant)
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"  ✓ {email}: subscription + KYC ensured"))
        if updated:
            self.stdout.write(
                self.style.SUCCESS(f"Ensured subscription + KYC for {updated} tenant(s)")
            )
        else:
            self.stdout.write("No E2E users found; run E2E setup first to create test user")
