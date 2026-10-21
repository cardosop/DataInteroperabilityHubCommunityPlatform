# Phase 230.13 (REQ-SEM-GQL-002) — additive-only:
# AddField semantic_graphql_ld_enabled (BooleanField, default=False) on
# Tenant.  Default False — feature is sold as a paid add-on AND
# carries DoS surface area; flipping the flag opts a tenant in.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0029_tenant_semantic_search_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_graphql_ld_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.13 (REQ-SEM-GQL-002) — when True, "
                    "/api/v1/semantic/graphql accepts GraphQL-LD "
                    "queries from this tenant's authenticated users "
                    "(subject to the depth/complexity/timeout/"
                    "throttle caps).  When False the endpoint "
                    "returns 403."
                ),
            ),
        ),
    ]
