"""
Audit Logging Models

Immutable audit event logging for compliance and security.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class AuditEvent(models.Model):
    """
    Audit Event model for immutable audit logging.
    
    All critical actions are logged as audit events for compliance and security.
    Events are append-only and cannot be modified or deleted.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
        help_text="Tenant this event belongs to (null for platform-level events)"
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audited_actions",
        null=True,
        blank=True,
        help_text="User who performed the action (null for system events)"
    )
    resource_type = models.CharField(
        max_length=50,
        help_text="Type of resource (e.g., TENANT, USER, CONTRACT, ASSET, AUTH)"
    )
    resource_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the resource (null for resource-less events)"
    )
    action = models.CharField(
        max_length=100,
        help_text="Action performed (e.g., CREATED, UPDATED, DELETED, LOGIN, LOGOUT)"
    )
    result = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILURE", "Failure"),
            ("WARNING", "Warning"),
        ],
        default="SUCCESS",
        help_text="Result of the action"
    )
    details_json = models.JSONField(
        default=dict,
        help_text="Additional details as JSON (no PII allowed)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the event occurred (UTC)"
    )
    
    class Meta:
        db_table = "audit_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["actor_user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["timestamp"]),  # For retention queries
        ]
        # Prevent updates and deletes
        default_permissions = ()  # No default permissions (read-only)
    
    def __str__(self):
        return f"{self.action} on {self.resource_type} by {self.actor_user.email if self.actor_user else 'SYSTEM'}"
    
    def save(self, *args, **kwargs):
        """Override save to prevent updates (append-only)"""
        if self.pk and AuditEvent.objects.filter(pk=self.pk).exists():
            raise ValueError("Audit events are immutable and cannot be updated")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion"""
        raise ValueError("Audit events are immutable and cannot be deleted")

