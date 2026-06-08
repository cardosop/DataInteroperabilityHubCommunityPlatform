"""
Phase 275.A.3 — add ``Asset.warehouse_connection`` FK to support LIVE_QUERY
assets backed by an external warehouse (Snowflake / BigQuery / Databricks /
Athena).

Companion to the model field declared at
``hub/apps/assets/models.py::Asset.warehouse_connection``. Nullable + blank so
existing rows (which are all non-LIVE_QUERY) don't need a backfill. The FK is
SET_NULL on warehouse deletion so removing a warehouse connection does not
cascade-delete assets that were once configured against it; the asset's
``data_strategy`` enum carries the operational state.

Depends on warehouses.0001_initial which creates the ``WarehouseConnection``
table this column points to.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0020_asset_processors_m2m"),
        ("warehouses", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="warehouse_connection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="assets",
                to="warehouses.warehouseconnection",
                help_text="Warehouse connection for LIVE_QUERY assets",
            ),
        ),
    ]
