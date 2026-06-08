"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("hub_auth", "0001_initial"),
        ("hub_auth", "0002_rename_api_keys_tenant_user_idx_api_keys_tenant__fbfac6_idx_and_more"),
        ("hub_auth", "0003_apikey_rate_limit_per_hour"),
        ("hub_auth", "0004_apikey_tier_revoked_at"),
        ("hub_auth", "0005_rename_api_keys_tier_id_idx_api_keys_tier_id_811cbc_idx"),
        ("hub_auth", "0006_refreshtoken_family_loginattempt"),
        ("hub_auth", "0007_backfill_refresh_token_expires_at"),
        ("hub_auth", "0008_customer_billing_fields"),
        ("hub_auth", "0009_refreshtoken_tenant_id"),
        ("hub_auth", "0010_enable_rls_impersonation_sessions"),
        ("hub_auth", "0011_add_api_key_rotation_reminder_field"),
        ("hub_auth", "0012_merge_20260513_1157"),
        ("hub_auth", "0013_merge"),
    ]

    operations = [
    ]
