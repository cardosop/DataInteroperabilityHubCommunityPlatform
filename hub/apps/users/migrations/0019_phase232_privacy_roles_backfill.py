# Generated manually — Phase 232.0.8 (D232.13).

from django.db import migrations

_ROLE_ROWS = (
    ("TENANT_ADMIN", "Full administrative access within tenant"),
    ("DATA_PROVIDER", "Can create and manage data assets"),
    ("DATA_CONSUMER", "Can request and access data assets"),
    ("AUDITOR", "Read-only access to compliance/DQ reports and audit logs"),
    ("DPO", "Data Protection Officer obligations and privacy programme oversight"),
    ("LEGAL_ADMIN", "Legal bases, contracts, DPAs and regulatory attestations"),
    ("SECURITY_ADMIN", "Security posture, breaches, DPIA artefacts and vendor risk"),
)


def forwards(apps, schema_editor):
    Role = apps.get_model("users", "Role")
    Tenant = apps.get_model("tenants", "Tenant")
    # ``Tenant`` declares ``default_manager_name = "all_objects"`` in
    # its Meta (hub/apps/tenants/models.py:782), so Django's historical
    # model reconstruction does NOT expose ``Tenant.objects`` — only
    # ``Tenant._default_manager`` (which here resolves to
    # ``all_objects``). Using ``_default_manager`` is the canonical
    # Django data-migration idiom and is robust to whatever the live
    # model's default-manager name happens to be.
    for tenant in Tenant._default_manager.all().iterator():
        for role_name, description in _ROLE_ROWS:
            Role._default_manager.get_or_create(
                tenant=tenant,
                name=role_name,
                defaults={"description": description},
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0018_enable_rls_user_tenant_memberships"),
        ("tenants", "0041_tenantconfig_compliance_risk_threshold"),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
