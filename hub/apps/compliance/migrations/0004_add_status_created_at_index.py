"""Phase 92.2 — Add (status, created_at) composite index to ComplianceRun.

Optimises queries that filter by run status and sort/filter by creation time
(e.g. "show all FAILED runs in the last 24 hours").
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0003_compliancerun_v2_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="compliancerun",
            index=models.Index(
                fields=["status", "created_at"],
                name="idx_complrun_st_created",
            ),
        ),
    ]
