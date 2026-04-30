"""
Phase 227 Wave 1 (227.L6.2) — MigrationCheckpoint table for resumable
bulk operations.

The Wave 3 self-healing migration (which re-normalizes ODPS contracts
using the new outputPorts walker) processes thousands of rows. Without
checkpointing, a kill mid-run would force a full re-process — and worse,
a partial double-process if the second run hadn't filtered out
already-completed rows. This table is the unit of resumption: one row
per (migration_name, contract_id) tuple, written transactionally with
the contract update.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0022_alter_contract_validation_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="MigrationCheckpoint",
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
                    "migration_name",
                    models.CharField(
                        db_index=True,
                        help_text=(
                            "Logical migration name (operator-supplied "
                            "via the ``--checkpoint-table`` flag). "
                            "Becomes the partition key for resumability."
                        ),
                        max_length=255,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("done", "Done"),
                            ("failed", "Failed"),
                            ("in_progress", "In Progress"),
                        ],
                        db_index=True,
                        default="done",
                        help_text=(
                            "Per-contract outcome. ``done`` = success "
                            "(skip on resume); ``failed`` = error "
                            "captured (skip on resume); "
                            "``in_progress`` = reserved."
                        ),
                        max_length=16,
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        help_text=(
                            "Truncated exception message when "
                            "``status='failed'``. ``None`` for "
                            "``done`` rows."
                        ),
                        null=True,
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="When this row was inserted (UTC).",
                    ),
                ),
                (
                    "contract",
                    models.ForeignKey(
                        help_text="Contract being processed",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="migration_checkpoints",
                        to="contracts.contract",
                    ),
                ),
            ],
            options={
                "db_table": "migration_checkpoints",
                "ordering": ["-completed_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="migrationcheckpoint",
            constraint=models.UniqueConstraint(
                fields=("migration_name", "contract"),
                name="unique_checkpoint_per_migration_per_contract",
            ),
        ),
        migrations.AddIndex(
            model_name="migrationcheckpoint",
            index=models.Index(
                fields=["migration_name", "status"],
                name="checkpoint_mig_status_idx",
            ),
        ),
    ]
