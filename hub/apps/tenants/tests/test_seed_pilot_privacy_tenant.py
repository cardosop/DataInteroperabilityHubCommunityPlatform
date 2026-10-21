"""
pilot-readiness 3.3 — seed_pilot_privacy_tenant management command tests.

The command provisions the dev-estate pilot tenant (``pilot-co``) for
the privacy pack runs: compliance gates ON, a TENANT_ADMIN author and a
DPO reviewer with REAL role separation, and one ACTIVE asset carrying
processing purposes + retention so the RoPA generation has real content.
Idempotent (fetch-or-create by deterministic id) — the shared E2E DB is
rebuilt from a template, so every row must survive re-runs.

R1 (oss-release-remediation W0.10): the command must honor the RLS
contract (CLAUDE.md) — cross-tenant rows through ``DATABASES["admin"]``
(BYPASSRLS) and tenant-scoped writes inside ``tenant_context(...)``.
Pinned by ``TestRlsContract`` below.
"""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from hub.apps.assets.models import Asset
from hub.apps.consent.models import ConsentPurpose
from hub.apps.governance.models import RetentionPolicy
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserRole

PILOT_SLUG = "pilot-co"
ADMIN_EMAIL = "pilot_admin@example.com"
DPO_EMAIL = "pilot_dpo@example.com"
ASSET_KEY = "pilot-crm"


class TestRlsContract:
    """R1 (W0.10): the RLS contract pins — source-level, so a regression
    that drops the context or the admin connection fails here."""

    COMMAND = (
        Path(__file__).resolve().parent.parent
        / "management"
        / "commands"
        / "seed_pilot_privacy_tenant.py"
    )

    def test_tenant_scoped_work_runs_inside_tenant_context(self):
        src = self.COMMAND.read_text()
        assert "with tenant_context(str(PILOT_TENANT_ID)):" in src, (
            "the seeder writes tenant-scoped rows (users, roles, "
            "memberships, asset, purposes, retention) outside "
            "tenant_context — under an RLS-armed database those writes "
            "are invisible or denied (the naked cross-tenant connection "
            "is the R1 violation)"
        )

    def test_cross_tenant_rows_use_the_admin_connection(self):
        src = self.COMMAND.read_text()
        assert 'Tenant.objects.using("admin")' in src, (
            "the Tenant row itself is not fetched through the admin "
            "connection (meshant_admin, BYPASSRLS) — the CLAUDE.md "
            "management-command contract"
        )
        assert 'TenantPlan.objects.using("admin")' in src, (
            "the platform plan is not fetched through the admin "
            "connection — a tenant-scoped connection has no business "
            "reading platform rows"
        )


def _run_seed() -> str:
    out = StringIO()
    call_command("seed_pilot_privacy_tenant", stdout=out)
    return out.getvalue()


# W0.10 (R1): plain pytest FUNCTIONS, not Django TestCase subclasses — the
# command now writes through the admin alias inside tenant_context, and the
# Django TestCase machinery's teardown (check_constraints → is_usable on a
# closed cross-alias connection) breaks on it (psycopg2 "connection already
# closed"). The proven repo pattern for cross-alias tests
# (test_admin_impersonate_phase_235_4.py) is plain functions under
# transaction=True.
@pytest.mark.django_db(transaction=True)
def test_creates_pilot_tenant_with_compliance_gates():
    _run_seed()
    tenant = Tenant.objects.get(slug=PILOT_SLUG)
    assert tenant.status == "ACTIVE"
    assert tenant.kyc_status == KYCStatus.VERIFIED
    assert tenant.compliance_dpia_enabled is True
    assert tenant.compliance_ropa_enabled is True
    assert tenant.compliance_processor_agreements_enabled is True
    assert tenant.onboarding_completed_at is not None
    assert tenant.plan is not None


@pytest.mark.django_db(transaction=True)
def test_creates_role_separated_users():
    _run_seed()
    admin = User.objects.get(email=ADMIN_EMAIL)
    dpo = User.objects.get(email=DPO_EMAIL)
    assert admin.tenant.slug == PILOT_SLUG
    assert dpo.tenant.slug == PILOT_SLUG
    admin_roles = set(
        UserRole.objects.filter(user=admin).values_list("role__name", flat=True)
    )
    dpo_roles = set(UserRole.objects.filter(user=dpo).values_list("role__name", flat=True))
    assert "TENANT_ADMIN" in admin_roles
    assert "DPO" in dpo_roles
    assert "DPO" not in admin_roles
    assert admin.email_verified is True
    assert dpo.email_verified is True
    assert admin.check_password("TestPass123")
    assert dpo.check_password("TestPass123")


@pytest.mark.django_db(transaction=True)
def test_creates_asset_with_purposes_and_retention():
    _run_seed()
    tenant = Tenant.objects.get(slug=PILOT_SLUG)
    asset = Asset.objects.get(tenant=tenant, key=ASSET_KEY)
    assert asset.status == "ACTIVE"
    assert asset.categories_of_subjects
    assert asset.recipient_categories
    purposes = list(asset.processing_purposes.all())
    assert len(purposes) >= 1
    assert purposes[0].tenant_id == tenant.id
    policies = RetentionPolicy.objects.filter(tenant=tenant, asset=asset)
    assert policies.count() >= 1
    assert policies.first().policy_type == "TIME_BASED"


@pytest.mark.django_db(transaction=True)
def test_idempotent():
    _run_seed()
    _run_seed()
    tenant = Tenant.objects.get(slug=PILOT_SLUG)
    assert Tenant.objects.filter(slug=PILOT_SLUG).count() == 1
    assert User.objects.filter(email=ADMIN_EMAIL).count() == 1
    assert User.objects.filter(email=DPO_EMAIL).count() == 1
    assert Asset.objects.filter(tenant=tenant, key=ASSET_KEY).count() == 1
    assert ConsentPurpose.objects.filter(tenant=tenant).count() == 1
    assert RetentionPolicy.objects.filter(tenant=tenant).count() == 1


@pytest.mark.django_db(transaction=True)
def test_second_run_flips_nothing_off():
    """Re-running after the gates were flipped OFF re-asserts them — the
    shared DB is wiped by peer sessions, so the seeder is the durable
    re-provisioning path."""
    _run_seed()
    tenant = Tenant.objects.get(slug=PILOT_SLUG)
    tenant.compliance_ropa_enabled = False
    tenant.save(update_fields=["compliance_ropa_enabled", "updated_at"])
    _run_seed()
    tenant.refresh_from_db()
    assert tenant.compliance_ropa_enabled is True
