"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dq", "0002_add_anomaly_and_trend_models"),
        ("dq", "0101_merge_20260519_1645"),
        ("dq", "0103_enable_rls_dq_models"),
    ]

    operations = [
    ]
