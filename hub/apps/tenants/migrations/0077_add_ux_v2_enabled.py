# Phase 278.0.3 — per-tenant UX v2 activation gate.
# Mirrors the Phase 271.1.2 connect_enabled rollout discipline:
#   - Migration backfills False on existing tenants
#   - Model default callable returns True for new tenants
from django.db import migrations, models

import hub.apps.tenants.models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0076_merge_20260513_1157"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="ux_v2_enabled",
            field=models.BooleanField(
                default=hub.apps.tenants.models._default_ux_v2_enabled,
                help_text=(
                    "Phase 278.0.3 — per-tenant UX v2 activation gate. "
                    "False on existing tenants; True on new tenants. "
                    "Controls whether the SPA renders v2 component surfaces."
                ),
            ),
        ),
    ]
