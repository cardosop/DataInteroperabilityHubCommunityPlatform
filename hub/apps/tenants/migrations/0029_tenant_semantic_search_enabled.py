# Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — additive-only:
# AddField semantic_search_enabled (BooleanField, default=False) on
# Tenant.  Default False so the existing search behaviour is preserved
# until the operator opts a tenant in.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0028_tenant_semantic_ldn_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_search_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.11 (REQ-SEM-SEARCH-EXPAND-001) — when "
                    "True, search requests with ?semantic=true expand "
                    "the user's query via tenant ontology relations. "
                    "When False the ?semantic flag is a no-op "
                    "(existing search semantics preserved)."
                ),
            ),
        ),
    ]
