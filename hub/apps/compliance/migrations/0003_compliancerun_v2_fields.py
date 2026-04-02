# Generated migration — 19.10.1: v2 compliance fields + QUEUED status

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0002_alter_compliancerun_risk_level"),
    ]

    operations = [
        # QUEUED added to status choices; max_length unchanged (20 covers all values)
        migrations.AlterField(
            model_name="compliancerun",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("QUEUED", "Queued"),
                    ("RUNNING", "Running"),
                    ("SUCCEEDED", "Succeeded"),
                    ("FAILED", "Failed"),
                ],
                default="PENDING",
                help_text=(
                    "Compliance run status: "
                    "PENDING, QUEUED, RUNNING, SUCCEEDED, FAILED"
                ),
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="compliancerun",
            name="cross_border_alert",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text=(
                    "Cross-border data transfer alert "
                    "from compliance service v2"
                ),
            ),
        ),
        migrations.AddField(
            model_name="compliancerun",
            name="localisation_alert",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text=(
                    "Data localisation requirement alert "
                    "from compliance service v2"
                ),
            ),
        ),
        migrations.AddField(
            model_name="compliancerun",
            name="legal_basis_violations",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text=(
                    "Legal basis violations reported by compliance service v2"
                ),
            ),
        ),
        migrations.AddField(
            model_name="compliancerun",
            name="metadata_json",
            field=models.JSONField(
                blank=True,
                null=True,
                help_text=(
                    'Async job tracking metadata: '
                    '{"job_id": "...", "poll_url": "..."}'
                ),
            ),
        ),
    ]
