"""Phase 53 (53.6): Add performance index for user tenant+created_at queries."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0009_userrole_tenant_unique_constraint"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(
                fields=["tenant", "created_at"],
                name="users_tenant_created_idx",
            ),
        ),
    ]
