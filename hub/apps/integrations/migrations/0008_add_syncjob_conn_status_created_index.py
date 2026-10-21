"""Phase 92.2 — Add (connection, status, created_at) composite index to MarketplaceSyncJob.

Optimises queries that filter sync jobs by connection + status and sort by
creation time (e.g. dashboard showing recent FAILED jobs per connection).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0007_add_failure_tracking_fields"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="marketplacesyncjob",
            index=models.Index(
                fields=["connection", "status", "created_at"],
                name="idx_syncjob_conn_st_cr",
            ),
        ),
    ]
