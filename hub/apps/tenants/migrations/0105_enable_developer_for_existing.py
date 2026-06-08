# Generated migration: enable developer_enabled for all existing tenants.
#
# The developer_enabled flag exists on the Tenant model (Phase 286)
# but was never gated in the developer views.  Before adding the gate,
# we must enable the flag for all existing tenants so the capability
# check doesn't break existing API consumers.
#
# Deployment ordering: this migration MUST run BEFORE the code deploy
# that adds the capability check to PluginViewSet and
# SDKDocumentationViewSet.

from django.db import migrations


def enable_developer_for_existing(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    # Tenant uses default_manager_name="all_objects", so the historical
    # model in a RunPython context may not expose ".objects".  Use
    # _default_manager to be safe regardless of manager naming.
    updated = Tenant._default_manager.all().update(developer_enabled=True)
    # Logged at migration-apply time for audit trail.
    print(f"  Enabled developer_enabled for {updated} existing tenants.")


def noop_reverse(apps, schema_editor):
    # Reverse is a no-op: re-disabling the flag for tenants that may
    # now depend on it would cause a production outage.  The flag was
    # previously unenforced so reverting to False is unsafe.
    pass


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ("tenants", "0104_limitdimension_and_more"),
    ]

    operations = [
        migrations.RunPython(
            enable_developer_for_existing,
            reverse_code=noop_reverse,
        ),
    ]
