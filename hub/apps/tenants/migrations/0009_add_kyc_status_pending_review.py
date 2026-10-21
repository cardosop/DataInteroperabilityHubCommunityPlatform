# Generated migration for feat1 2.3.1: add KYCStatus.PENDING_REVIEW

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0008_add_tenant_usage_summary"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="kyc_status",
            field=models.CharField(
                choices=[
                    ("UNVERIFIED", "Unverified"),
                    ("PENDING_REVIEW", "Pending review"),
                    ("VERIFIED", "Verified"),
                ],
                default="UNVERIFIED",
                help_text="KYC verification status: UNVERIFIED, PENDING_REVIEW (submission with provider), or VERIFIED",
                max_length=20,
            ),
        ),
    ]
