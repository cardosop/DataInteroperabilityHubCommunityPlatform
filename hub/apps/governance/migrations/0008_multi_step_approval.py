"""
Phase 272.4 — add PENDING_NEXT_APPROVER to AccessRequestStatus.

This is an AlterField on the choices — a no-op at the SQL level
(choices are enforced only in Python/Django), so no RunSQL needed.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0007_access_request_comment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accessrequest",
            name="status",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("PENDING", "Pending"),
                    ("PENDING_NEXT_APPROVER", "Pending Next Approver"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("EXPIRED", "Expired"),
                    ("REVOKED", "Revoked"),
                ],
                default="PENDING",
                help_text="Access request status",
            ),
        ),
    ]
