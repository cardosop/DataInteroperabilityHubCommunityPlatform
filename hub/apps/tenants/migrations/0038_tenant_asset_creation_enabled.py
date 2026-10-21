"""
Phase 250.6.A.1 (D250.17) — per-tenant asset-creation kill switch.

Additive-only migration: adds ``Tenant.asset_creation_enabled``
(BooleanField, default=True) to every existing row. The default is
True so the deploy doesn't accidentally freeze any customer's asset
creation. The corresponding gate at the asset views refuses calls
when the effective tenant has the flag False with HTTP 403 +
``code="ASSET_CREATION_DISABLED"``.

Non-breaking: the field has a Python-level default AND a DB-level
default (True), so back-fill of existing rows is automatic on the
``ALTER TABLE`` and no explicit ``UPDATE tenants SET ...`` is needed.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0037_tenant_federated_import_classification_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="asset_creation_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 250.6.A.1 (D250.17) — when True (default), "
                    "this tenant may create assets via POST /assets/ "
                    "and POST /assets/data-first/. Default TRUE so "
                    "existing tenants are unaffected by the kill-"
                    "switch deploy; ops flips to False to freeze "
                    "creation under investigation. New tenants created "
                    "via onboarding START at False until onboarding "
                    "completes (separate code path)."
                ),
            ),
        ),
    ]
