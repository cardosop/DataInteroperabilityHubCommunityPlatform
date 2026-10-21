"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0001_initial"),
        ("integrations", "0002_alter_marketplaceconnection_config_and_more"),
        ("integrations", "0003_marketplacesyncjob_updated_at"),
        ("integrations", "0004_marketplacemapping"),
        ("integrations", "0013_enable_rls_integrations"),
    ]

    operations = [
    ]
