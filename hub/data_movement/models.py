"""285.6.2 — Data Movement models (lightweight — dlt manages its own state)."""
from django.db import models


class DataMovementConfig(models.Model):
    """Per-tenant configuration for dlt data movement."""

    tenant = models.OneToOneField(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="data_movement_config",
    )
    dlt_dev_mode = models.BooleanField(
        default=False,
        help_text="Enable dlt dev mode for this tenant (skips schema evolution)",
    )
    max_parallel_pipelines = models.PositiveSmallIntegerField(
        default=5,
        help_text="Max concurrent dlt pipelines per tenant",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "data_movement"
        db_table = "data_movement_config"
