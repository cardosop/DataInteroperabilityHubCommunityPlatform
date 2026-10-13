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

from hub.apps.tenants.models import KYCStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
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
    *_PROFILE_E2E_EMAILS,
)

# Core per-tenant feature flags the E2E specs exercise (paid-layer flags
# like baas_enabled/ml_enabled stay off — core mode has no such features).
_CORE_E2E_FEATURE_FLAGS = (
    "virtualization_enabled",
    "data_mesh_enabled",
    "transformation_enabled",
    "data_movement_enabled",
    "developer_enabled",
    "pipeline_dependency_enabled",
    # Compliance surfaces the CLI use_cases journeys exercise — the RoPA
    # and DPIA endpoints 403 with ROPA_DISABLED when these are off
    # (measured 2026-09-20 in the cpo journey). The consent/dsar/breach/
    # processor/retention family covers the governance-sub-routes E2E
    # spec (close-test-coverage-gaps 4.4) — core compliance surfaces,
    # not paid-layer flags.
    "compliance_ropa_enabled",
    "compliance_dpia_enabled",
    "compliance_consent_enabled",
    "compliance_dsar_enabled",
    "compliance_breach_enabled",
    "compliance_processor_agreements_enabled",
    "compliance_retention_enforcer_enabled",
)


class Command(BaseCommand):
    help = "Ensure E2E test users' tenants have active subscriptions"

    def handle(self, *_args, **_options):
        updated = 0
        for email in E2E_EMAILS:
            user = User.objects.filter(email=email).select_related("tenant").first()
            if not user:
                self.stdout.write(f"  - {email}: user not found (register first via E2E setup)")
                continue
            if not user.tenant_id:
                self.stdout.write(f"  - {email}: no tenant")
                continue
            # Phase 313.2 — full E2E readiness (subscription + KYC + the
            # e2e-unlimited plan) lives in the billing app; the old
            # facade (hub.apps.testing.billing_support) no longer carries
            # it. Core-only deployments without billing fall back to the
            # subscription hook (covers the suspension middleware only).
            try:
                from hub.apps.billing.test_support import ensure_e2e_tenant_ready
            except (ImportError, RuntimeError):
                ensure_tenant_has_active_subscription(user.tenant)
            else:
                ensure_e2e_tenant_ready(user.tenant)
            tenant_update_fields = ["updated_at"]
            if user.tenant.kyc_status != KYCStatus.VERIFIED:
                user.tenant.kyc_status = KYCStatus.VERIFIED
                tenant_update_fields.append("kyc_status")
            # Core per-tenant feature flags default False (Phase 271.1.2);
            # core E2E specs exercise features behind them — enable for
            # E2E tenants so the real gate evaluates the tested path
            # (e.g. the virtual-dataset detail spec hit
            # 403 VIRTUALIZATION_DISABLED on a fresh stack).
            for flag in _CORE_E2E_FEATURE_FLAGS:
                if not getattr(user.tenant, flag, False):
                    setattr(user.tenant, flag, True)
                    tenant_update_fields.append(flag)
            if len(tenant_update_fields) > 1:
                user.tenant.save(update_fields=tenant_update_fields)
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"  ✓ {email}: subscription + KYC ensured"))
        if updated:
            self.stdout.write(
                self.style.SUCCESS(f"Ensured subscription + KYC for {updated} tenant(s)")
            )
        else:
            self.stdout.write("No E2E users found; run E2E setup first to create test user")
