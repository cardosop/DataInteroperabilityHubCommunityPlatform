"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("notifications", "0002_rename_email_deli_to_emai_idx_email_deliv_to_emai_5d5179_idx_and_more"),
        ("notifications", "0008_rename_user_notif_user_read_idx_user_notifi_user_id_304d2d_idx_and_more"),
        ("notifications", "0010_enable_rls_user_notifications"),
        ("notifications", "0012_enable_rls_email_deliveries"),
    ]

    operations = [
    ]
