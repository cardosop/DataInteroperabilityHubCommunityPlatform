# Phase 278.O.1 — FormDraft schema migration.
# Model defined in hub/apps/core/drafts.py (Phase 278.B.4).
# Views in hub/apps/core/draft_views.py call FormDraft.objects.*
# but no migration existed — causing 500s on /api/v1/drafts/.
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_rename_idempotency_tenant_key_method_path_idx_idempotency_tenant__875a5d_idx_and_more"),
        ("tenants", "0077_add_ux_v2_enabled"),
        ("users", "0025_add_saved_views"),
    ]

    operations = [
        migrations.CreateModel(
            name="FormDraft",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "resource_type",
                    models.CharField(
                        help_text="Form resource type, e.g. dpia, contract, asset, breach.",
                        max_length=64,
                    ),
                ),
                (
                    "draft_key",
                    models.CharField(
                        default="default",
                        help_text="Unique key per form, e.g. 'create' or 'edit-<uuid>'.",
                        max_length=128,
                    ),
                ),
                (
                    "data",
                    models.JSONField(
                        default=dict,
                        help_text="The serialized form state as JSON.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="form_drafts",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="form_drafts",
                        to="users.user",
                    ),
                ),
            ],
            options={
                "db_table": "form_drafts",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="formdraft",
            index=models.Index(
                fields=["user", "resource_type"],
                name="form_drafts_user_resource_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="formdraft",
            index=models.Index(
                fields=["tenant", "resource_type"],
                name="form_drafts_tenant_resource_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="formdraft",
            constraint=models.UniqueConstraint(
                fields=["user", "resource_type", "draft_key"],
                name="unique_form_draft_per_user_resource_key",
            ),
        ),
    ]
