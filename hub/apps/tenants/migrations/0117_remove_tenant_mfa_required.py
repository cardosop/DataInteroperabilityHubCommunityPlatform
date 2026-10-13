"""
oss-release-remediation W1.7 (R2-S12) — drop ``Tenant.mfa_required``.

The flag was a claim without enforcement: ``hub/apps/auth/mfa.py`` (the
TOTP library) had ZERO consumers — nothing ever checked this field or
verified a TOTP. A tenant "enabling MFA" via this flag changed nothing
at runtime. The remediation decision (design.md, remove-claim now):
delete the dead library AND the misleading flag, and make the docs
state reality. Reversible — Django derives the reverse automatically
(re-add the BooleanField with its historical default, False).
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0116_tenant_databricks_ml_assets_enabled"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="tenant",
            name="mfa_required",
        ),
    ]
