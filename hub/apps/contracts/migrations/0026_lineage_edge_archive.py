# Phase 228 F5 (REQ-LIN-F5-003 / 228.F5.5) — additive-only:
# CreateModel LineageEdgeArchive (cold-tier archive for closed
# LineageEdge rows older than the 12-month hot retention window).
import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0025_lineage_edges"),
        ("tenants", "0023_add_archival_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="LineageEdgeArchive",
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
                    "original_edge_id",
                    models.UUIDField(
                        db_index=True,
                        help_text="``LineageEdge.id`` from the row this entry was archived from.",
                    ),
                ),
                ("source_model", models.CharField(blank=True, default="", max_length=255)),
                ("source_field", models.CharField(blank=True, default="", max_length=255)),
                ("target_model", models.CharField(blank=True, default="", max_length=255)),
                ("target_field", models.CharField(blank=True, default="", max_length=255)),
                (
                    "edge_type",
                    models.CharField(
                        choices=[
                            ("upload", "Upload"),
                            ("transformation", "Transformation"),
                            ("derivation", "Derivation"),
                            ("export", "Export"),
                            ("reference", "Reference"),
                        ],
                        default="reference",
                        max_length=32,
                    ),
                ),
                ("transformation_ref", models.CharField(blank=True, default="", max_length=512)),
                ("job_ref", models.CharField(blank=True, default="", max_length=512)),
                ("valid_from", models.DateTimeField(db_index=True)),
                ("valid_to", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("archived_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("exported_to_s3_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("s3_uri", models.CharField(blank=True, default="", max_length=2048)),
                (
                    "source_contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contracts.contract",
                    ),
                ),
                (
                    "target_contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contracts.contract",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archived_lineage_edges",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Archived Lineage Edge",
                "verbose_name_plural": "Archived Lineage Edges",
                "db_table": "contracts_lineage_edge_archive",
            },
        ),
        migrations.AddIndex(
            model_name="lineageedgearchive",
            index=models.Index(
                fields=["tenant", "valid_to"],
                name="lin_arch_tenant_validto_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lineageedgearchive",
            index=models.Index(
                fields=["archived_at"],
                name="lin_arch_archived_at_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="lineageedgearchive",
            index=models.Index(
                fields=["exported_to_s3_at"],
                name="lin_arch_s3_exported_idx",
            ),
        ),
    ]
