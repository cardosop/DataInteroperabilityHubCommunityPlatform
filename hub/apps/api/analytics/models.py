"""
API Analytics Models

Models for tracking API usage metrics.
"""

import uuid

from django.conf import settings
from django.db import models


class APIUsageMetric(models.Model):
    """
    Model for tracking API usage metrics.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="api_usage_metrics",
        help_text="Tenant this metric belongs to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="api_usage_metrics",
        null=True,
        blank=True,
        help_text="User who made the request",
    )
    endpoint_path = models.CharField(max_length=500, help_text="API endpoint path")
    method = models.CharField(max_length=10, help_text="HTTP method")
    status_code = models.IntegerField(help_text="HTTP status code")
    latency_ms = models.FloatField(
        null=True, blank=True, help_text="Request latency in milliseconds"
    )
    request_size_bytes = models.IntegerField(
        null=True, blank=True, help_text="Request size in bytes"
    )
    response_size_bytes = models.IntegerField(
        null=True, blank=True, help_text="Response size in bytes"
    )
    api_version = models.CharField(max_length=20, default="v1", help_text="API version used")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_usage_metrics"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "endpoint_path", "created_at"]),
            models.Index(fields=["tenant", "method", "created_at"]),
            models.Index(fields=["tenant", "status_code", "created_at"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.method} {self.endpoint_path} - {self.status_code}"
