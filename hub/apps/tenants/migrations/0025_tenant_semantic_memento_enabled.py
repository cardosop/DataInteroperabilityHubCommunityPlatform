# Phase 230.4 (REQ-SEM-MEMENTO-001) — additive: tenant-level toggle for
# Memento (Accept-Datetime) versioned retrieval.  Default False so the
# feature stays dark for existing tenants until ops flips the flag per
# tenant + global ``SEMANTIC_MEMENTO_ENABLED=True``.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0024_tenant_data_residency_and_redaction"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_memento_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.4 (REQ-SEM-MEMENTO-001) — when True, semantic "
                    "resource updates produce versioned snapshots and the "
                    "dereference endpoint honours Accept-Datetime. Gated by "
                    "the global SEMANTIC_MEMENTO_ENABLED setting in addition."
                ),
            ),
        ),
    ]
