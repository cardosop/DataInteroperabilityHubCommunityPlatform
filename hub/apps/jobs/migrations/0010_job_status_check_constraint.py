"""Phase 92.7 — CheckConstraint for Job.status field."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jobs", "0009_failed_job_dlq"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="job",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING", "RUNNING", "COMPLETED",
                        "FAILED", "CANCELLED",
                    ]
                ),
                name="job_status_valid",
            ),
        ),
    ]
