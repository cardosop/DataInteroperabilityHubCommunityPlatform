# Phase 228 F4 (DoD self-audit second-pass) — additive-only:
# * AddField grace_audit_emitted_at on OpenLineageIngestApiKey
#   (latch for the once-per-key OPENLINEAGE_KEY_GRACE_USED audit
#   event; pins REQ-LIN-F4-003 spec scenario "Quarterly rotation
#   grace").
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0011_openlineage_inbound_and_retry"),
    ]

    operations = [
        migrations.AddField(
            model_name="openlineageingestapikey",
            name="grace_audit_emitted_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Set to the moment the first grace-period authentication "
                    "fired the OPENLINEAGE_KEY_GRACE_USED audit event. NULL = "
                    "the key has never authenticated inside its grace window. "
                    "Once non-NULL, subsequent grace-period authentications are "
                    "NOT audited (the spec scenario only requires the audit "
                    "trail capture grace USAGE, not every grace request)."
                ),
                null=True,
            ),
        ),
    ]
