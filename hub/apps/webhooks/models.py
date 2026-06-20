"""
Webhook Models

Models for webhook subscriptions and delivery tracking.
"""

import hashlib
import hmac
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .encryption import decrypt_secret, encrypt_secret


class WebhookStatus(models.TextChoices):
    """Webhook subscription status"""

    ACTIVE = "ACTIVE", "Active"
    PAUSED = "PAUSED", "Paused"
    DISABLED = "DISABLED", "Disabled"


class WebhookEventType(models.TextChoices):
    """Webhook event types.

    Phase 230.AUDIT.12 / D273.8 — DECIDED: NO ``semantic.*`` webhook
    event types in Phase 230. Semantic surface (export, tombstone,
    federation, ontology, LDN, GraphQL, memento, inference) is
    AUDIT-ONLY for now — every state transition emits an
    ``AuditEvent`` (see ``hub/apps/audit/models.py::SEMANTIC_AUDIT_ACTIONS``)
    but does NOT fan out as a webhook delivery. Rationale:

      1. Semantic state transitions are high-volume (LDN inbound on
         a busy tenant can hit the rate limit cap of 10 req/min/IP,
         times N partner keys; outbound delivery fans out per
         subscription). Adding webhook delivery on top would multiply
         the per-event work by the subscriber count.
      2. The Phase 230.12 LDN outbound surface IS the semantic-events
         webhook by another name — partners subscribe via
         ``LdnSubscription`` rather than ``Webhook``. Two parallel
         delivery paths would diverge.
      3. No customer has asked for ``semantic.*`` webhooks. Revisit
         when one does — at that point the webhook surface should
         reuse the LDN outbound infrastructure (signed deliveries,
         exponential back-off, dead-letter) rather than build a
         second delivery pipeline.

    DO NOT extend this enum with ``semantic.*`` values without
    revisiting D273.8.
    """

    # Contract events
    CONTRACT_CREATED = "contract.created", "Contract Created"
    CONTRACT_UPDATED = "contract.updated", "Contract Updated"
    CONTRACT_DELETED = "contract.deleted", "Contract Deleted"
    # Phase 227 Wave 3 (227.W3.4) — batched migration summary.
    # Emitted once per ``--apply`` batch per affected tenant by the
    # ``renormalize_contracts`` management command, instead of one
    # ``contract.updated`` per healed row (which would storm
    # subscribers on a million-row migration).
    CONTRACT_BATCH_RENORMALIZED = (
        "contract.batch_renormalized",
        "Contract Batch Re-normalized",
    )

    # Asset events
    ASSET_CREATED = "asset.created", "Asset Created"
    ASSET_UPDATED = "asset.updated", "Asset Updated"
    ASSET_ACTIVATED = "asset.activated", "Asset Activated"

    # Ingestion events
    INGESTION_COMPLETED = "ingestion.completed", "Ingestion Completed"
    INGESTION_FAILED = "ingestion.failed", "Ingestion Failed"

    # Quality events
    QUALITY_CHECK_COMPLETED = "quality.check.completed", "Quality Check Completed"
    COMPLIANCE_CHECK_COMPLETED = "compliance.check.completed", "Compliance Check Completed"
    # Phase 231.4 — tenant-subscribable completion (scrubbed payload). Distinct from
    # ``compliance.check.completed`` (internal bus / legacy catalog).
    COMPLIANCE_COMPLETED = "compliance.completed", "Compliance Run Completed"

    # Version events
    VERSION_CREATED = "version.created", "Version Created"
    VERSION_UPDATED = "version.updated", "Version Updated"

    # ODPS events
    ODPS_CREATED = "odps.created", "ODPS Created"
    ODPS_UPDATED = "odps.updated", "ODPS Updated"
    ODPS_DELETED = "odps.deleted", "ODPS Deleted"
    ODPS_NORMALIZED = "odps.normalized", "ODPS Normalized"
    ODPS_LINKED = "odps.linked", "ODPS Linked"
    ODPS_UNLINKED = "odps.unlinked", "ODPS Unlinked"
    ODPS_EXPORT_STARTED = "odps.export.started", "ODPS Export Started"
    ODPS_EXPORT_COMPLETED = "odps.export.completed", "ODPS Export Completed"
    ODPS_EXPORT_FAILED = "odps.export.failed", "ODPS Export Failed"

    # Mesh events
    MESH_DOMAIN_CREATED = "mesh.domain.created", "Mesh Domain Created"
    MESH_DOMAIN_UPDATED = "mesh.domain.updated", "Mesh Domain Updated"
    MESH_POLICY_APPLIED = "mesh.policy.applied", "Mesh Policy Applied"
    MESH_COMPLIANCE_CHECKED = "mesh.compliance.checked", "Mesh Compliance Checked"
    MESH_TOPOLOGY_UPDATED = "mesh.topology.updated", "Mesh Topology Updated"
    MESH_HEALTH_STATUS_CHANGED = "mesh.health.status_changed", "Mesh Health Status Changed"

    # Virtualization events
    VIRTUALIZATION_DATASET_CREATED = "virtualization.dataset.created", "Virtual Dataset Created"
    VIRTUALIZATION_QUERY_EXECUTION_STARTED = (
        "virtualization.query.execution.started",
        "Query Execution Started",
    )
    VIRTUALIZATION_QUERY_EXECUTION_PROGRESS = (
        "virtualization.query.execution.progress",
        "Query Execution Progress",
    )
    VIRTUALIZATION_QUERY_EXECUTION_COMPLETED = (
        "virtualization.query.execution.completed",
        "Query Execution Completed",
    )
    VIRTUALIZATION_QUERY_EXECUTION_FAILED = (
        "virtualization.query.execution.failed",
        "Query Execution Failed",
    )

    # File events (Phase 260.7.G — closes pass-3 B3-14)
    # Phase 0 audit (260.7.G.1) confirmed zero ``fire_webhook`` calls in
    # ``hub/apps/files/`` pre-260.7.G — file events were emitted to the
    # internal event bus only (file.created/updated/deleted/uploaded/
    # downloaded via ``FileEventPublisher``) and never fanned out as
    # webhooks. ``file.purged`` is the FIRST file event registered for
    # external webhook subscription. Distinct semantic from ``file.deleted``:
    #   * ``file.deleted`` (NOT registered for webhooks) — soft-delete:
    #     status flips to DELETING, file enters grace window, blob still
    #     in S3, blob fetch still works for the grace duration.
    #   * ``file.purged`` (THIS event) — hard-delete after grace: S3
    #     object deleted, DB row gone, ``Dataset.file_id`` SET_NULL,
    #     linked datasets transitioned to RETIRED via the pre_delete
    #     signal. External subscribers should run cleanup that wasn't
    #     safe during the grace window (cascading deletes in CRM /
    #     downstream warehouses, archive-to-cold-storage triggers).
    FILE_PURGED = "file.purged", "File Purged"

    # Phase 233.4 — Operator-initiated test event.
    #
    # ``webhook.test`` is a SYSTEM event type, NOT a tenant data event.
    # It is fired exclusively by the ``POST /webhooks/{id}/test/``
    # endpoint when an operator clicks "Test webhook" in the UI. Every
    # webhook IMPLICITLY accepts ``webhook.test`` regardless of its
    # ``event_types`` list — see ``Webhook.subscribes_to_event_type``
    # for the universal-subscription contract. Operators do not need
    # to add ``webhook.test`` to a webhook's subscriptions for the
    # test endpoint to work.
    #
    # Replaces the pre-233.4 implementation that mis-emitted
    # ``asset.created`` from the test endpoint, which silently failed
    # for any webhook not subscribed to ``asset.created``.
    WEBHOOK_TEST = "webhook.test", "Webhook Test"

    # Billing events (Phase 116A.9)
    BILLING_REPORT_GENERATED = "billing.report.generated", "Billing Report Generated"
    BILLING_REPORT_SENT = "billing.report.sent", "Billing Report Sent"
    # Phase 240.5.A — DQ run completion billing event.  Wire-stable
    # string MUST equal ``hub.apps.billing.event_types.DQ_RUN_COMPLETED``;
    # adding the entry here makes the event subscribable by tenants
    # via the public ``POST /api/v1/webhooks/`` endpoint (the
    # serializer validates against ``WebhookEventType.choices``).
    BILLING_DQ_RUN_COMPLETED = "billing.dq.run.completed", "Billing DQ Run Completed"

    # ML events (Phase 114C.6)
    ML_MODEL_REGISTERED = "ml.model.registered", "ML Model Registered"
    ML_MODEL_DEPLOYED = "ml.model.deployed", "ML Model Deployed"
    ML_MODEL_ARCHIVED = "ml.model.archived", "ML Model Archived"
    ML_TRAINING_STARTED = "ml.training.started", "ML Training Started"
    ML_TRAINING_COMPLETED = "ml.training.completed", "ML Training Completed"
    ML_TRAINING_FAILED = "ml.training.failed", "ML Training Failed"
    ML_INFERENCE_EXECUTED = "ml.inference.executed", "ML Inference Executed"

    # Transformation events (Phase 115C.2)
    TRANSFORMATION_COMPLETED = "transformation.completed", "Transformation Completed"
    TRANSFORMATION_FAILED = "transformation.failed", "Transformation Failed"

    # Phase 232.1 — consent management webhooks
    CONSENT_GRANTED = "consent.granted", "Consent Granted"
    CONSENT_REVOKED = "consent.revoked", "Consent Revoked"

    # Phase 232.2 — DSAR workflow webhooks
    DSAR_SUBMITTED = "dsar.submitted", "DSAR Submitted"
    DSAR_STATUS_CHANGED = "dsar.status.changed", "DSAR Status Changed"
    DSAR_FULFILLED = "dsar.fulfilled", "DSAR Fulfilled"
    DSAR_REJECTED = "dsar.rejected", "DSAR Rejected"
    DSAR_SLA_WARNING = "dsar.sla.warning", "DSAR SLA Warning"
    DSAR_SLA_CRITICAL = "dsar.sla.critical", "DSAR SLA Critical"
    DSAR_SLA_ESCALATED = "dsar.sla.escalated", "DSAR SLA Escalated"
    DSAR_SLA_SUSPENDED = "dsar.sla.suspended", "DSAR SLA Suspended (legal hold)"

    # Phase 232.8 — compliance closeout webhooks (tenant-subscribable; wire emitters per subsystem rollout).
    BREACH_INCIDENT_OPENED = "breach.incident.opened", "Breach Incident Opened"
    BREACH_NOTIFICATION_SENT = "breach.notification.sent", "Breach Notification Sent"
    DPIA_CREATED = "dpia.created", "DPIA Created"
    DPIA_STATUS_CHANGED = "dpia.status.changed", "DPIA Status Changed"
    DPIA_REVIEW_DECISION = "dpia.review.decision", "DPIA Review Decision"
    ROPA_GENERATED = "ropa.generated", "RoPA Register Generated"
    PROCESSOR_AGREEMENT_EXPIRING = (
        "processor_agreement.expiring",
        "Expiring Processor Agreement Window",
    )
    PROCESSOR_AGREEMENT_EXPIRED = "processor_agreement.expired", "Processor Agreement Expired"
    # Phase 275.E.3d — warehouse connectivity webhook events.
    WAREHOUSE_CONNECTION_CREATED = "warehouse.connection.created", "Warehouse Connection Created"
    WAREHOUSE_CONNECTION_UPDATED = "warehouse.connection.updated", "Warehouse Connection Updated"
    WAREHOUSE_CONNECTION_DELETED = "warehouse.connection.deleted", "Warehouse Connection Deleted"
    WAREHOUSE_EXPORT_COMPLETED = "warehouse.export.completed", "Warehouse Export Completed"
    WAREHOUSE_EXPORT_FAILED = "warehouse.export.failed", "Warehouse Export Failed"
    WAREHOUSE_SHARE_ACCESSED = "warehouse.share.accessed", "Warehouse Share Accessed"
    WAREHOUSE_CONNECTION_TEST_FAILED = (
        "warehouse.connection.test_failed",
        "Warehouse Connection Test Failed",
    )
    WAREHOUSE_SCHEMA_DRIFT_DETECTED = (
        "warehouse.schema.drift_detected",
        "Warehouse Schema Drift Detected",
    )

    @classmethod
    def get_phase232_subsystem_event_types(cls) -> list[str]:
        """Stable list for Phase 232 programme docs, SDK, and serializer regression tests."""
        return [
            str(cls.CONSENT_GRANTED),
            str(cls.CONSENT_REVOKED),
            str(cls.DSAR_SUBMITTED),
            str(cls.DSAR_STATUS_CHANGED),
            str(cls.DSAR_FULFILLED),
            str(cls.BREACH_INCIDENT_OPENED),
            str(cls.BREACH_NOTIFICATION_SENT),
            str(cls.DPIA_CREATED),
            str(cls.DPIA_STATUS_CHANGED),
            str(cls.DPIA_REVIEW_DECISION),
            str(cls.ROPA_GENERATED),
            str(cls.PROCESSOR_AGREEMENT_EXPIRING),
            str(cls.PROCESSOR_AGREEMENT_EXPIRED),
            str(cls.COMPLIANCE_COMPLETED),
        ]

    @classmethod
    def get_transformation_event_types(cls) -> list[str]:
        """Get all transformation event type values."""
        return [
            str(cls.TRANSFORMATION_COMPLETED),
            str(cls.TRANSFORMATION_FAILED),
        ]

    @classmethod
    def is_transformation_event_type(cls, event_type: str | tuple) -> bool:
        """Check if an event type is a transformation event."""
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        elif hasattr(event_type, "value"):
            event_type = event_type.value
        return event_type in cls.get_transformation_event_types()

    @classmethod
    def get_billing_event_types(cls) -> list[str]:
        """Get all billing event type values."""
        return [
            str(cls.BILLING_REPORT_GENERATED),
            str(cls.BILLING_REPORT_SENT),
            str(cls.BILLING_DQ_RUN_COMPLETED),
        ]

    @classmethod
    def is_billing_event_type(cls, event_type: str | tuple) -> bool:
        """Check if an event type is a billing event."""
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        elif hasattr(event_type, "value"):
            event_type = event_type.value
        return event_type in cls.get_billing_event_types()

    @classmethod
    def get_odps_event_types(cls) -> list[str]:
        """
        Get all ODPS event type values.

        Returns:
            List of ODPS event type string values
        """
        # For TextChoices, we need to get the actual string values
        # The enum members can be converted to strings, or we can use the choices
        return [
            str(cls.ODPS_CREATED),  # Convert enum member to string
            str(cls.ODPS_UPDATED),
            str(cls.ODPS_DELETED),
            str(cls.ODPS_NORMALIZED),
            str(cls.ODPS_LINKED),
            str(cls.ODPS_UNLINKED),
            str(cls.ODPS_EXPORT_STARTED),
            str(cls.ODPS_EXPORT_COMPLETED),
            str(cls.ODPS_EXPORT_FAILED),
        ]

    @classmethod
    def is_odps_event_type(cls, event_type: str | tuple) -> bool:
        """
        Check if an event type is an ODPS event.

        Args:
            event_type: Event type string, tuple, or enum value to check

        Returns:
            True if the event type is an ODPS event, False otherwise
        """
        # Extract string value if event_type is a tuple (enum choice tuple)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        # Extract string value if event_type is an enum
        elif hasattr(event_type, "value"):
            event_type = event_type.value
        return event_type in cls.get_odps_event_types()

    @classmethod
    def get_mesh_event_types(cls) -> list[str]:
        """
        Get all mesh event type values.

        Returns:
            List of mesh event type string values
        """
        return [
            str(cls.MESH_DOMAIN_CREATED),
            str(cls.MESH_DOMAIN_UPDATED),
            str(cls.MESH_POLICY_APPLIED),
            str(cls.MESH_COMPLIANCE_CHECKED),
            str(cls.MESH_TOPOLOGY_UPDATED),
            str(cls.MESH_HEALTH_STATUS_CHANGED),
        ]

    @classmethod
    def is_mesh_event_type(cls, event_type: str | tuple) -> bool:
        """
        Check if an event type is a mesh event.

        Args:
            event_type: Event type string, tuple, or enum value to check

        Returns:
            True if the event type is a mesh event, False otherwise
        """
        # Extract string value if event_type is a tuple (enum choice tuple)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        # Extract string value if event_type is an enum
        elif hasattr(event_type, "value"):
            event_type = event_type.value
        return event_type in cls.get_mesh_event_types()

    @classmethod
    def get_virtualization_event_types(cls) -> list[str]:
        """
        Get all virtualization event type values.

        Returns:
            List of virtualization event type string values
        """
        return [
            str(cls.VIRTUALIZATION_DATASET_CREATED),
            str(cls.VIRTUALIZATION_QUERY_EXECUTION_STARTED),
            str(cls.VIRTUALIZATION_QUERY_EXECUTION_PROGRESS),
            str(cls.VIRTUALIZATION_QUERY_EXECUTION_COMPLETED),
            str(cls.VIRTUALIZATION_QUERY_EXECUTION_FAILED),
        ]

    @classmethod
    def is_virtualization_event_type(cls, event_type: str | tuple) -> bool:
        """
        Check if an event type is a virtualization event.

        Args:
            event_type: Event type string, tuple, or enum value to check

        Returns:
            True if the event type is a virtualization event, False otherwise
        """
        # Extract string value if event_type is a tuple (enum choice tuple)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]
        # Extract string value if event_type is an enum
        elif hasattr(event_type, "value"):
            event_type = event_type.value
        return event_type in cls.get_virtualization_event_types()


class DeliveryStatus(models.TextChoices):
    """Webhook delivery status.

    Phase 233.3 — ``RATE_LIMITED`` (REQ-WH-RL-003): TERMINAL state for a
    delivery that exceeded the tenant's per-minute outbound budget. The
    retry scheduler SHALL NOT pick up RATE_LIMITED rows; subsequent event
    emissions create fresh delivery rows that are gated independently
    by the rate-limit counter at their own attempt time.
    """

    PENDING = "PENDING", "Pending"
    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    DEAD_LETTER = "DEAD_LETTER", "Dead Letter"
    RATE_LIMITED = "RATE_LIMITED", "Rate Limited"


class Webhook(models.Model):
    """
    Webhook subscription model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="webhooks",
        help_text="Tenant this webhook belongs to",
    )
    name = models.CharField(max_length=255, help_text="Webhook name/description")
    url = models.URLField(max_length=2048, help_text="Webhook delivery URL")
    secret = models.CharField(
        max_length=255, help_text="Webhook secret for HMAC signature (encrypted)"
    )
    event_types = models.JSONField(default=list, help_text="List of event types to subscribe to")
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.choices,
        default=WebhookStatus.ACTIVE,
        help_text="Webhook status",
    )
    max_retries = models.IntegerField(default=5, help_text="Maximum number of delivery retries")
    retry_intervals = models.JSONField(
        default=list, help_text="Retry intervals in seconds: [1, 5, 30, 300, 1800]"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_webhooks",
        null=True,
        blank=True,
        help_text="User who created the webhook",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhooks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "event_types"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.url})"

    @property
    def decrypted_secret(self) -> str:
        """Return the plaintext secret, decrypting if stored encrypted."""
        return decrypt_secret(self.secret)

    def clean(self):
        """Validate webhook configuration"""
        super().clean()

        # Normalize event types - convert enum tuples to string values and deduplicate
        if self.event_types:
            normalized_event_types = []
            seen = set()
            valid_event_types = [choice[0] for choice in WebhookEventType.choices]
            for event_type in self.event_types:
                # Extract string value from different input types
                if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                    event_type_value = event_type[0]
                elif isinstance(event_type, WebhookEventType):
                    event_type_value = getattr(event_type, "value", str(event_type))
                else:
                    event_type_value = str(event_type)

                # Validate
                if event_type_value not in valid_event_types:
                    raise ValidationError(f"Invalid event type: {event_type_value}")

                # Deduplicate
                if event_type_value not in seen:
                    seen.add(event_type_value)
                    normalized_event_types.append(event_type_value)

            self.event_types = normalized_event_types

        # Validate event types
        if not self.event_types:
            raise ValidationError("At least one event type must be specified")

        # Validate retry intervals
        if not self.retry_intervals:
            self.retry_intervals = [1, 5, 30, 300, 1800]  # Default: 1s, 5s, 30s, 5m, 30m

        if len(self.retry_intervals) != self.max_retries:
            raise ValidationError(
                f"Number of retry intervals ({len(self.retry_intervals)}) "
                f"must match max_retries ({self.max_retries})"
            )

    def save(self, *args, **kwargs):
        """Override save to encrypt secret and normalise event_types."""
        # Encrypt secret at rest before persisting (11.4)
        if self.secret:
            self.secret = encrypt_secret(self.secret)

        # Set defaults before normalization
        if not self.retry_intervals:
            self.retry_intervals = [1, 5, 30, 300, 1800]  # Default: 1s, 5s, 30s, 5m, 30m

        if not self.max_retries:
            self.max_retries = 5

        # Normalize event types before saving (deduplicate + validate)
        if self.event_types:
            normalized_event_types = []
            seen = set()
            valid_event_types = [choice[0] for choice in WebhookEventType.choices]
            for event_type in self.event_types:
                if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                    event_type_value = event_type[0]
                elif isinstance(event_type, WebhookEventType):
                    event_type_value = getattr(event_type, "value", str(event_type))
                else:
                    event_type_value = str(event_type)

                if event_type_value in valid_event_types and event_type_value not in seen:
                    seen.add(event_type_value)
                    normalized_event_types.append(event_type_value)

            self.event_types = normalized_event_types

        # Call full_clean to ensure validation (after setting defaults)
        self.full_clean()
        super().save(*args, **kwargs)

    def generate_signature(self, payload: str) -> str:
        """Generate HMAC-SHA256 signature using the decrypted secret."""
        return hmac.new(
            self.decrypted_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def subscribes_to_odps_events(self) -> bool:
        """
        Check if this webhook subscribes to any ODPS events.

        Returns:
            True if webhook subscribes to at least one ODPS event, False otherwise
        """
        odps_event_types = WebhookEventType.get_odps_event_types()
        # event_types should be normalized to strings in clean(), but handle both cases
        for event_type in self.event_types:
            # Extract string value from different input types
            if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
                event_type_value = event_type[0]
            elif isinstance(event_type, WebhookEventType):
                event_type_value = getattr(event_type, "value", str(event_type))
            else:
                event_type_value = str(event_type)

            if event_type_value in odps_event_types:
                return True
        return False

    def subscribes_to_event_type(self, event_type: str) -> bool:
        """
        Check if this webhook subscribes to a specific event type.

        Args:
            event_type: Event type string to check (or tuple to extract value from)

        Returns:
            True if webhook subscribes to the event type, False otherwise

        Phase 233.4 — Universal-subscription contract for ``webhook.test``.
        ``webhook.test`` is a SYSTEM event type fired by the operator-facing
        ``POST /webhooks/{id}/test/`` endpoint. Every webhook implicitly
        accepts ``webhook.test`` regardless of its declared ``event_types``
        list. This is by design: an operator clicking "Test webhook"
        expects the delivery to land regardless of which event types the
        webhook subscribes to. The alternative — requiring the operator to
        add ``webhook.test`` to the subscription list — would surface as
        a confusing UX bug ("why does my Test button do nothing?").
        """
        # Extract string value from different input types
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type_value = event_type[0]
        elif isinstance(event_type, WebhookEventType):
            event_type_value = getattr(event_type, "value", str(event_type))
        else:
            event_type_value = str(event_type)

        # Phase 233.4 — universal subscription for the system test event.
        # See class docstring for ``WEBHOOK_TEST`` for the contract rationale.
        if event_type_value == WebhookEventType.WEBHOOK_TEST.value:
            return True

        # event_types should be normalized to strings in clean(), but handle both cases
        # Also check if stored values are enums and normalize them
        for stored_type in self.event_types:
            if isinstance(stored_type, WebhookEventType):
                stored_value = getattr(stored_type, "value", str(stored_type))
            else:
                stored_value = str(stored_type)

            if stored_value == event_type_value:
                return True

        return False

    @classmethod
    def filter_by_odps_events(cls, queryset=None):
        """
        Filter webhooks that subscribe to ODPS events.

        Args:
            queryset: Optional queryset to filter (defaults to all webhooks)

        Returns:
            QuerySet of webhooks that subscribe to at least one ODPS event
        """
        from django.db.models import Q

        if queryset is None:
            queryset = cls.objects.all()

        odps_event_types = WebhookEventType.get_odps_event_types()

        # Build query to check if any ODPS event type is in the event_types JSON field
        # For JSONField arrays, __contains checks if the array contains the value (not a list)
        query = Q()
        for event_type in odps_event_types:
            query |= Q(event_types__contains=event_type)

        return queryset.filter(query)

    @classmethod
    def filter_by_event_type(cls, event_type: str | tuple, queryset=None):
        """
        Filter webhooks that subscribe to a specific event type.

        Args:
            event_type: Event type string or tuple to filter by
            queryset: Optional queryset to filter (defaults to all webhooks)

        Returns:
            QuerySet of webhooks that subscribe to the specified event type
        """
        if queryset is None:
            queryset = cls.objects.all()

        # Extract string value if it's a tuple (enum value)
        if isinstance(event_type, (tuple, list)) and len(event_type) > 0:
            event_type = event_type[0]

        # For JSONField arrays, __contains checks if the array contains the value (not a list)
        return queryset.filter(event_types__contains=event_type)


class WebhookDelivery(models.Model):
    """
    Webhook delivery tracking model.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="deliveries",
        help_text="Webhook subscription",
    )
    event_type = models.CharField(
        max_length=100, help_text="Event type that triggered the delivery"
    )
    payload = models.JSONField(help_text="Webhook payload (event data)")
    signature = models.CharField(max_length=64, help_text="HMAC signature of the payload")
    #: Phase 233.1 — public key_id of the WebhookSigningKey used to sign this
    #: delivery. Pinned at trigger-time so the X-Meshant-Signature-Key-Id
    #: header survives async dispatch even if rotation happens between
    #: trigger and delivery (REQ-WH-ROT-002). NULL on legacy deliveries
    #: that pre-date the rolling-key feature; in that case the header is
    #: omitted and subscribers fall back to legacy single-key verification.
    signing_key_uuid = models.UUIDField(
        null=True,
        blank=True,
        help_text="Public key_id used to sign (X-Meshant-Signature-Key-Id header).",
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        help_text="Delivery status",
    )
    attempt_number = models.IntegerField(default=0, help_text="Current attempt number (0-indexed)")
    http_status_code = models.IntegerField(
        null=True, blank=True, help_text="HTTP status code from delivery attempt"
    )
    response_body = models.TextField(
        null=True, blank=True, help_text="Response body from delivery attempt"
    )
    error_message = models.TextField(
        null=True, blank=True, help_text="Error message if delivery failed"
    )
    delivered_at = models.DateTimeField(null=True, blank=True, help_text="When delivery succeeded")
    next_retry_at = models.DateTimeField(
        null=True, blank=True, help_text="When to retry delivery (if failed)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "webhook_deliveries"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "status"]),
            models.Index(fields=["webhook", "next_retry_at"]),
            models.Index(fields=["status", "next_retry_at"]),
        ]

    @property
    def retry_count(self) -> int:
        """Number of retries attempted so far (alias for ``attempt_number``).

        ``attempt_number`` is 0-indexed: 0 = first attempt, 1 = first retry, etc.
        This property provides a more readable alias for tests and monitoring.
        """
        return self.attempt_number

    @property
    def attempts(self) -> int:
        """Total attempts including the initial delivery (attempt_number + 1)."""
        return self.attempt_number + 1

    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} ({self.status})"


# ---------------------------------------------------------------------------
# Phase 233.1 — Rolling-key signature window
#
# Pins REQ-WH-ROT-001 (multi-key window invariant), REQ-WH-ROT-002 (key-id
# header), REQ-WH-ROT-003 (atomic rotation API), REQ-WH-ROT-004 (hourly cron
# transition), REQ-WH-ROT-005 (idempotent backfill), REQ-WH-ROT-006 (audit).
# See ``openspec/changes/preprod01/specs/webhook-signing-rotation/spec.md``.
# ---------------------------------------------------------------------------


class WebhookSigningKeyStatus(models.TextChoices):
    """Lifecycle states for a webhook signing key.

    ACTIVE   — used to sign new outbound deliveries (at most one per webhook).
    RETIRING — kept for the 24h subscriber overlap window; signs nothing.
    RETIRED  — terminal; auto-pruned 7 days after ``retired_at``.
    """

    ACTIVE = "ACTIVE", "Active"
    RETIRING = "RETIRING", "Retiring"
    RETIRED = "RETIRED", "Retired"


class WebhookSigningKey(models.Model):
    """One row per (webhook, lifecycle-state) signing-key triple.

    The platform maintains a rolling 3-key window per webhook:
    one ACTIVE + up to two RETIRING + N RETIRED (auto-pruned after 7d).
    See ``WebhookSigningKey.objects.active_for(webhook)`` for the canonical
    helper used by the delivery path; rotation is owned by
    ``WebhookViewSet.rotate_secret``.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name="signing_keys",
        help_text="Parent webhook this key signs deliveries for.",
    )

    #: Subscriber-visible identifier surfaced via the ``X-Meshant-Signature-Key-Id``
    #: header (REQ-WH-ROT-002). UUID v4; canonical 36-char hyphenated form.
    key_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text="Public key identifier (sent in delivery header).",
    )

    #: KMS-wrapped HMAC secret. Reuses ``hub.apps.webhooks.encryption`` so the
    #: rotation feature inherits the same at-rest encryption contract as the
    #: legacy ``Webhook.secret`` column.
    secret_encrypted = models.CharField(
        max_length=4096,
        help_text="Encrypted HMAC secret (KMS or Fernet wrapper).",
    )

    status = models.CharField(
        max_length=10,
        choices=WebhookSigningKeyStatus.choices,
        default=WebhookSigningKeyStatus.ACTIVE,
        help_text="Lifecycle state — see WebhookSigningKeyStatus.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    #: Stamped when the key transitions out of ACTIVE. NULL while ACTIVE;
    #: ``now() + 24h`` when RETIRING; the actual transition timestamp when
    #: the cron flips RETIRING → RETIRED.
    retired_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the key transitions out of ACTIVE (24h overlap target).",
    )

    class Meta:
        db_table = "webhook_signing_keys"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["webhook", "status"]),
            models.Index(fields=["status", "retired_at"]),
        ]
        constraints = [
            # REQ-WH-ROT-001 invariant: at most ONE row per webhook with
            # status='ACTIVE'. Partial unique index — RETIRING / RETIRED
            # rows never collide regardless of count.
            models.UniqueConstraint(
                fields=["webhook"],
                condition=models.Q(status="ACTIVE"),
                name="webhook_signing_keys_one_active_per_webhook",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.webhook_id}/{self.key_id} ({self.status})"

    @property
    def decrypted_secret(self) -> str:
        """Return the plaintext secret, decrypting on demand."""
        return decrypt_secret(self.secret_encrypted)

    def generate_signature(self, payload: str) -> str:
        """HMAC-SHA256 of ``payload`` using this key's decrypted secret.

        Mirrors ``Webhook.generate_signature`` so the delivery-path can
        switch from ``webhook.generate_signature`` to
        ``signing_key.generate_signature`` without changing the wire format.
        """
        return hmac.new(
            self.decrypted_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @classmethod
    def active_for(cls, webhook: "Webhook") -> "WebhookSigningKey | None":
        """Return the single ACTIVE signing key for ``webhook``, or ``None``.

        The partial unique index guarantees at most one ACTIVE row per
        webhook (REQ-WH-ROT-001), so ``filter().first()`` is correct
        here without an ``ORDER BY``. Returning ``None`` lets the
        delivery path fall back to the legacy ``Webhook.secret`` column
        for any in-flight webhook that pre-dates migration 0005.
        """
        return cls.objects.filter(
            webhook=webhook,
            status=WebhookSigningKeyStatus.ACTIVE,
        ).first()
