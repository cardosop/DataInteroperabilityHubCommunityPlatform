"""
Phase 250.5.A.2 (D250.3) — opt-in federated import.

Additive-only migration: adds ``Tenant.federated_import_enabled``
(BooleanField, default=False) to every existing row. The default is
False so the deploy doesn't silently enable the federated-import code
path for tenants who never asked for it. The corresponding gate at
``DiscoveryService.create_federated_asset_with_contracts`` refuses
calls when the effective tenant has the flag False and emits the
``FEDERATED_IMPORT_REJECTED`` audit row.

Non-breaking: the field has a Python-level default AND a DB-level
default (False), so back-fill of existing rows is automatic on the
``ALTER TABLE`` and no explicit ``UPDATE tenants SET ...`` is needed.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0035_tenant_auto_activate_flag"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="federated_import_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 250.5.A.2 (D250.3) — when True, this tenant "
                    "may import federated assets from configured "
                    "marketplace connections. Default False so existing "
                    "tenants are unchanged by the phase deploy; opt-in "
                    "is required to activate the federated-import code "
                    "path."
                ),
            ),
        ),
    ]
