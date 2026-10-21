# Phase 278.P.1 — fix FormDraft UniqueConstraint to include tenant.
# The old constraint (user, resource_type, draft_key) allowed a user
# in multiple tenants to have only ONE draft per resource_type/draft_key
# across ALL tenants. Adding tenant scopes drafts per-tenant.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_form_draft_rls"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="formdraft",
            name="unique_form_draft_per_user_resource_key",
        ),
        migrations.AddConstraint(
            model_name="formdraft",
            constraint=models.UniqueConstraint(
                fields=["user", "tenant", "resource_type", "draft_key"],
                name="unique_form_draft_per_user_tenant_resource_key",
            ),
        ),
    ]
