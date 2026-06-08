"""Merge conflicting migration leaves (0095 already resolved 0057+0060+0094 divergence; all earlier deps are now ancestors of 0095)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0095_merge"),
    ]

    operations = [
    ]
