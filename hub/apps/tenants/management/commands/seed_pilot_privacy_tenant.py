"""
pilot-readiness 3.3 — seed the dev-estate pilot tenant for the privacy
pack runs.

The privacy pack (DPIA + RoPA + DPA) runs against a REAL tenant with
REAL role separation: a TENANT_ADMIN author and a DPO reviewer. This
idempotent command provisions ``pilot-co`` with the compliance gates
ON, the two users, and one ACTIVE asset carrying processing purposes +
retention so the RoPA generation has real content instead of gap rows.

Deterministic UUIDs let re-runs fetch-or-create the same rows — the
shared E2E DB is rebuilt from a template and wiped by peer sessions,
so this command is the durable re-provisioning path (mirrors
``seed_smoke_fixtures``).

Usage (in the test stack):
    docker exec hub-test-api python hub/manage.py seed_pilot_privacy_tenant
"""

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.consent.models import ConsentPurpose
from hub.apps.governance.models import (
    RetentionAction,
    RetentionPolicy,
    RetentionPolicyType,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.users.services import UserTenantMembershipService

# Deterministic IDs — referenced by the privacy-pack runner and the pack
# record; fetch-or-create keeps re-runs collision-free.
PILOT_TENANT_ID = uuid.UUID("aaaaaaa1-0001-4001-8001-000000000001")
PILOT_ASSET_ID = uuid.UUID("aaaaaaa2-0002-4002-8002-000000000002")
PILOT_PURPOSE_ID = uuid.UUID("aaaaaaa3-0003-4003-8003-000000000003")
PILOT_RETENTION_ID = uuid.UUID("aaaaaaa4-0004-4004-8004-000000000004")

PILOT_SLUG = "pilot-co"
PILOT_NAME = "Pilot Company (dev estate)"
ADMIN_EMAIL = "pilot_admin@example.com"
DPO_EMAIL = "pilot_dpo@example.com"
PASSWORD = "TestPass123"  # E2E persona convention (ensure_e2e_user_roles)

ASSET_KEY = "pilot-crm"
PURPOSE_KEY = "pilot.data-hosting"


class Command(BaseCommand):
    help = "Seed the pilot privacy-pack tenant (idempotent)."

    def handle(self, *_args, **_options):
        # RLS contract (CLAUDE.md, R1 — W0.10): management commands are
        # cross-tenant by default. Cross-tenant rows — the Tenant row
        # itself and the platform plan — go through DATABASES["admin"]
        # (meshant_admin, BYPASSRLS); every tenant-scoped write runs
        # inside tenant_context(PILOT_TENANT_ID) so the RLS policies see
        # the GUC instead of a naked cross-tenant connection.
        #
        # 1. Pilot tenant — the three compliance gates ON (the DPIA/RoPA/
        # DPA endpoints 403 with *_DISABLED when off).
        tenant, tenant_created = Tenant.objects.using("admin").get_or_create(
            id=PILOT_TENANT_ID,
            defaults={
                "slug": PILOT_SLUG,
                "name": PILOT_NAME,
                "status": TenantStatus.ACTIVE,
                "kyc_status": KYCStatus.VERIFIED,
                "onboarding_completed_at": timezone.now(),
                "compliance_dpia_enabled": True,
                "compliance_ropa_enabled": True,
                "compliance_processor_agreements_enabled": True,
            },
        )
        if tenant_created:
            self.stdout.write(self.style.SUCCESS(f"Created pilot tenant {PILOT_SLUG}."))
        tenant_update_fields = ["updated_at"]
        for flag in (
            "compliance_dpia_enabled",
            "compliance_ropa_enabled",
            "compliance_processor_agreements_enabled",
        ):
            if not getattr(tenant, flag, False):
                setattr(tenant, flag, True)
                tenant_update_fields.append(flag)
        if tenant.kyc_status != KYCStatus.VERIFIED:
            tenant.kyc_status = KYCStatus.VERIFIED
            tenant_update_fields.append("kyc_status")
        if tenant.onboarding_completed_at is None:
            tenant.onboarding_completed_at = timezone.now()
            tenant_update_fields.append("onboarding_completed_at")
        if tenant.status != TenantStatus.ACTIVE:
            tenant.status = TenantStatus.ACTIVE
            tenant_update_fields.append("status")
        # Plan — a platform row, fetched through the admin connection.
        from hub.apps.tenants.models import TenantPlan

        if not tenant.plan:
            pro_plan = (
                TenantPlan.objects.using("admin")
                .filter(slug="pro", is_active=True)
                .first()
            )
            if pro_plan:
                tenant.plan = pro_plan
                tenant_update_fields.append("plan")
        if len(tenant_update_fields) > 1:
            tenant.save(using="admin", update_fields=tenant_update_fields)

        # 2. Everything below is tenant-scoped — run it under the RLS
        # context so the policies apply to the pilot tenant's rows.
        with tenant_context(str(PILOT_TENANT_ID)):
            # Active subscription — TenantSuspensionMiddleware blocks every
            # POST/PUT/PATCH/DELETE with 403 subscription_inactive otherwise
            # (the ensure_e2e_subscription recipe).
            try:
                from hub.apps.billing.test_support import ensure_e2e_tenant_ready
            except (ImportError, RuntimeError):
                from hub.apps.testing.billing_support import (
                    ensure_tenant_has_active_subscription,
                )

                ensure_tenant_has_active_subscription(tenant)
            else:
                ensure_e2e_tenant_ready(tenant)
            self.stdout.write(
                self.style.SUCCESS(f"Pilot tenant {PILOT_SLUG} ready (gates ON).")
            )

            # 3. Role-separated users — the DPIA flow needs a TENANT_ADMIN
            # author and a DPO reviewer (IsDpiaParticipant / IsDpiaReviewer
            # role checks, not the platform-admin bypass).
            membership = UserTenantMembershipService()
            for email, display_name, role_names in (
                (ADMIN_EMAIL, "Pilot Tenant Admin", ("TENANT_ADMIN",)),
                (DPO_EMAIL, "Pilot DPO", ("DPO",)),
            ):
                user, user_created = User.objects.get_or_create(
                    email=email,
                    defaults={
                        "tenant": tenant,
                        "display_name": display_name,
                        "status": UserStatus.ACTIVE,
                        "email_verified": True,
                        "email_verified_at": timezone.now(),
                    },
                )
                if not user_created:
                    user_update_fields = []
                    if user.tenant_id != tenant.id:
                        user.tenant = tenant
                        user_update_fields.append("tenant")
                    if not user.email_verified:
                        user.email_verified = True
                        user.email_verified_at = timezone.now()
                        user_update_fields += ["email_verified", "email_verified_at"]
                    if user_update_fields:
                        user.save(update_fields=user_update_fields)
                if not user.check_password(PASSWORD):
                    user.set_password(PASSWORD)
                    user.save(update_fields=["password"])
                membership.add_membership(user, tenant)
                for role_name in role_names:
                    role, _ = Role.objects.get_or_create(
                        tenant=tenant,
                        name=role_name,
                        defaults={"description": f"Pilot privacy-pack {role_name}"},
                    )
                    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
                self.stdout.write(
                    self.style.SUCCESS(f"User {email} ready ({','.join(role_names)}).")
                )

            # 4. One ACTIVE asset with real processing metadata — the RoPA
            # generator walks assets + purposes + retention; without these
            # the artefact ships gap rows instead of activity content.
            asset, _ = Asset.objects.get_or_create(
                id=PILOT_ASSET_ID,
                defaults={
                    "tenant": tenant,
                    "key": ASSET_KEY,
                    "name": "Pilot CRM dataset",
                    "description": (
                        "Pilot-tenant CRM contact records (dev-estate synthetic fixture)."
                    ),
                    "domain": "sales",
                    "status": AssetStatus.ACTIVE,
                    "categories_of_subjects": ["pilot employees", "prospect contacts"],
                    "recipient_categories": [
                        "pilot analytics team",
                        "pilot sales team",
                    ],
                },
            )
            if asset.status != AssetStatus.ACTIVE:
                asset.status = AssetStatus.ACTIVE
                asset.save(update_fields=["status", "updated_at"])

            purpose, _ = ConsentPurpose.objects.get_or_create(
                id=PILOT_PURPOSE_ID,
                defaults={
                    "tenant": tenant,
                    "key": PURPOSE_KEY,
                    "name": "Pilot data hosting",
                    "description": "Hosting and serving the pilot company's data products.",
                    "retention_days": 1095,
                },
            )
            asset.processing_purposes.add(purpose)

            RetentionPolicy.objects.get_or_create(
                id=PILOT_RETENTION_ID,
                defaults={
                    "tenant": tenant,
                    "asset": asset,
                    "name": "Pilot CRM 3-year retention",
                    "policy_type": RetentionPolicyType.TIME_BASED,
                    "retention_period_days": 1095,
                    "action": RetentionAction.HARD_DELETE,
                },
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Asset {ASSET_KEY} ready (purpose={purpose.key}, retention=1095d)."
                )
            )
