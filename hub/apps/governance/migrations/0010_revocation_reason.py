"""
Phase 272.6 — AccessRequest.revocation_reason.

TextField, nullable but enforced at the API (revoke endpoint requires
a non-empty reason body, returning 400 ``revocation_reason_required``
when missing).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0009_access_policy_approval_chain"),
    ]

    operations = [
        migrations.AddField(
            model_name="accessrequest",
            name="revocation_reason",
            field=models.TextField(
                null=True,
                blank=True,
                help_text="Reason for revocation (required at API)",
            ),
        ),
    ]
