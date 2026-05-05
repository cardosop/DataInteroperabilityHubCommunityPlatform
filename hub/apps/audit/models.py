"""
Audit Logging Models

Immutable audit event logging for compliance and security.
"""
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.exceptions import PermissionDenied

User = get_user_model()


class ActiveAuditEventManager(models.Manager):
    """Default manager that excludes archived events from queries."""

    def get_queryset(self):
        return super().get_queryset().filter(is_archived=False)


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
    full_details_json = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Restricted original details. Access ONLY via get_full_details(actor) "
            "with TENANT_ADMIN guard."
        ),
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the event occurred (UTC)"
    )
    is_archived = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event has been archived by the retention policy",
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this event was archived (UTC)",
    )

    # Default manager excludes archived events; use all_objects for admin ops.
    objects = ActiveAuditEventManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "audit_events"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["actor_user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "timestamp"]),
            models.Index(fields=["timestamp"]),  # For retention queries
            models.Index(fields=["is_archived", "timestamp"]),  # For archival queries
        ]
        # Prevent updates and deletes
        default_permissions = ()  # No default permissions (read-only)
    
    def __str__(self):
        return f"{self.action} on {self.resource_type} by {self.actor_user.email if self.actor_user else 'SYSTEM'}"
    
    def save(self, *args, **kwargs):
        """Override save to prevent updates (append-only)"""
        if self.pk and AuditEvent.all_objects.filter(pk=self.pk).exists():
            raise ValueError("Audit events are immutable and cannot be updated")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Override delete to prevent deletion"""
        raise ValueError("Audit events are immutable and cannot be deleted")

    def get_full_details(self, actor_user) -> dict:
        """Return full details for authorized actors only."""
        if actor_user is None:
            raise PermissionDenied("TENANT_ADMIN role is required")
        event_tenant = getattr(self, "tenant", None)
        if event_tenant is None:
            raise PermissionDenied("TENANT_ADMIN role is required")

        actor_tenant = getattr(actor_user, "tenant", None)
        actor_tenant_id = getattr(actor_tenant, "id", None)
        if actor_tenant_id != event_tenant.id:
            raise PermissionDenied("TENANT_ADMIN role is required")

        has_tenant_admin = bool(
            actor_user.user_roles.filter(
                role__tenant=event_tenant,
                role__name="TENANT_ADMIN",
            ).exists()
        )
        if not has_tenant_admin:
            raise PermissionDenied("TENANT_ADMIN role is required")
        return self.full_details_json if self.full_details_json is not None else self.details_json


# Phase 228 (REQ-LIN-007, 228.0.19) — canonical lineage audit-action codes.
#
# The ``action`` field on ``AuditEvent`` is a free-form CharField, so the
# operational invariant we ship here is a NAMED CONSTANT registry: every
# call site references these constants instead of inlining the string,
# so a typo can't produce two divergent histories of "the same action".
# Pinned by ``test_lineage_audit_codes.py`` which asserts the four
# Phase 228 codes exist and are the only ``LINEAGE_*`` values defined.

LINEAGE_VIEWED = "LINEAGE_VIEWED"
LINEAGE_VIEWED_CROSS_TENANT = "LINEAGE_VIEWED_CROSS_TENANT"
LINEAGE_EDGE_CREATED = "LINEAGE_EDGE_CREATED"
LINEAGE_EDGE_DELETED = "LINEAGE_EDGE_DELETED"
# Phase 228 F5 (REQ-LIN-F5-001 / DoD-G7) — emitted on every successful
# point-in-time lineage query (`?as_of=` or `?version=`).
LINEAGE_SNAPSHOT_QUERIED = "LINEAGE_SNAPSHOT_QUERIED"
# Phase 228 X (REQ-LIN-X-004 / 228.X.4.3) — emitted when a cross-
# region lineage view is gated by the data-residency check + the
# request carried explicit consent. Lets a compliance auditor
# answer "did somebody view EU lineage from a US viewer with
# consent — and when?".
LINEAGE_VIEWED_CROSS_REGION_CONSENTED = "LINEAGE_VIEWED_CROSS_REGION_CONSENTED"

# Phase 228 F4 (REQ-LIN-F4-003) — OpenLineage ingest-key admin
# audit-action codes. Same registry pattern as the lineage codes
# above so a typo in the call-site fails the
# ``test_lineage_audit_codes.py`` constants test.
OPENLINEAGE_KEY_CREATED = "OPENLINEAGE_KEY_CREATED"
OPENLINEAGE_KEY_REVOKED = "OPENLINEAGE_KEY_REVOKED"
OPENLINEAGE_KEY_ROTATED = "OPENLINEAGE_KEY_ROTATED"
# Phase 228 F4 (REQ-LIN-F4-003 spec scenario "Quarterly rotation grace") —
# fired the FIRST time a graced (post-rotation, pre-expiry) key is used
# to authenticate. Once-per-key emission so a busy producer doesn't
# generate one audit row per request; the field
# ``OpenLineageIngestApiKey.grace_audit_emitted_at`` is the latch.
OPENLINEAGE_KEY_GRACE_USED = "OPENLINEAGE_KEY_GRACE_USED"

# Phase 230.8 (REQ-SEM-FED-001) — SPARQL federation audit codes.
# - SEMANTIC_FEDERATED_QUERY: emitted on every federated SERVICE call
#   (including timeouts + DENIED).  Carries target_url + SHA-256 query
#   hash + response_time_ms in details_json so an auditor can answer
#   "did tenant T query partner P with what shape, when, and was it
#   slow".
# - SEMANTIC_FEDERATION_ALLOWLIST_ADD / _REMOVE: emitted on
#   TenantSparqlEndpoint mutations.  Allowlist changes are a security
#   event — auditor must reconstruct the allowlist state at any past
#   point in time from the audit log alone (defence-in-depth against
#   silent allowlist drift).
SEMANTIC_FEDERATED_QUERY = "SEMANTIC_FEDERATED_QUERY"
SEMANTIC_FEDERATION_ALLOWLIST_ADD = "SEMANTIC_FEDERATION_ALLOWLIST_ADD"
SEMANTIC_FEDERATION_ALLOWLIST_REMOVE = "SEMANTIC_FEDERATION_ALLOWLIST_REMOVE"

# Phase 230.2 (REQ-SEM-EXPORT-001) — bulk RDF export audit code.
# Emitted on every successful export with byte-count, format, and
# tenant in details_json. Rejected exports (400/413/429) do NOT
# emit (matches the LDN inbound pattern — failed attempts surface
# in structured logs, not as audit rows).
SEMANTIC_EXPORT = "SEMANTIC_EXPORT"

# Phase 230.3 (REQ-SEM-TOMBSTONE-001) — tombstone lifecycle audit
# code. Emitted on Asset retire / Contract delete / Dataset archive
# AND on the GDPR-purge path. ``details_json`` carries the
# tombstoned IRI + reason (asset_retired / contract_deleted /
# dataset_archived / gdpr_purge).
SEMANTIC_TOMBSTONE = "SEMANTIC_TOMBSTONE"

# Phase 230.10 (REQ-SEM-ONTO-001) — custom ontology lifecycle audit
# codes. UPLOAD covers BOTH successful and validation-failed
# attempts (per audit-fix GAP-A — INVALID rows are persisted with
# validation_errors populated; the audit row distinguishes via
# ``details_json.validation_status``). ACTIVATE / DEACTIVATE fire
# on PATCH is_active transitions.
SEMANTIC_ONTOLOGY_UPLOAD = "SEMANTIC_ONTOLOGY_UPLOAD"
SEMANTIC_ONTOLOGY_ACTIVATE = "SEMANTIC_ONTOLOGY_ACTIVATE"
SEMANTIC_ONTOLOGY_DEACTIVATE = "SEMANTIC_ONTOLOGY_DEACTIVATE"

# Phase 230.12 (REQ-SEM-LDN-001/003) — W3C LDN audit codes.
# INBOUND fires on accepted notifications only (rejected requests
# — 401/413/429 — do NOT emit per spec).
# OUTBOUND fires per delivery attempt (successful + failed retries).
# SUBSCRIPTION_CREATED fires on LdnSubscription.objects.create.
SEMANTIC_LDN_INBOUND = "SEMANTIC_LDN_INBOUND"
SEMANTIC_LDN_OUTBOUND = "SEMANTIC_LDN_OUTBOUND"
SEMANTIC_LDN_SUBSCRIPTION_CREATED = "SEMANTIC_LDN_SUBSCRIPTION_CREATED"

# Phase 230.13 (REQ-SEM-GQL-001) — GraphQL-LD endpoint audit code.
# Emitted on every authenticated GraphQL query (success + failure).
# Carries SHA-256 of the query text in details_json.query_sha256
# (the body is NOT stored — GraphQL queries can carry user-supplied
# input that may contain PII).  Resolver-level outcome
# (SUCCESS/DEPTH_EXCEEDED/COMPLEXITY_EXCEEDED/TIMEOUT/THROTTLED) is
# captured in details_json.outcome.
SEMANTIC_GRAPHQL_QUERY = "SEMANTIC_GRAPHQL_QUERY"

LINEAGE_AUDIT_ACTIONS: tuple[str, ...] = (
    LINEAGE_VIEWED,
    LINEAGE_VIEWED_CROSS_TENANT,
    LINEAGE_VIEWED_CROSS_REGION_CONSENTED,
    LINEAGE_EDGE_CREATED,
    LINEAGE_EDGE_DELETED,
    LINEAGE_SNAPSHOT_QUERIED,
    OPENLINEAGE_KEY_CREATED,
    OPENLINEAGE_KEY_REVOKED,
    OPENLINEAGE_KEY_ROTATED,
    OPENLINEAGE_KEY_GRACE_USED,
    SEMANTIC_FEDERATED_QUERY,
    SEMANTIC_FEDERATION_ALLOWLIST_ADD,
    SEMANTIC_FEDERATION_ALLOWLIST_REMOVE,
    SEMANTIC_GRAPHQL_QUERY,
)

# Phase 230.14.12 — canonical registry of all SEMANTIC_* audit
# action codes added across Phase 230 sub-phases. Pinned by a
# constants test (mirror of LINEAGE_AUDIT_ACTIONS) so a future
# rename or accidental delete fails CI rather than silently
# drifting the audit-trail vocabulary.
SEMANTIC_AUDIT_ACTIONS: tuple[str, ...] = (
    SEMANTIC_EXPORT,
    SEMANTIC_TOMBSTONE,
    SEMANTIC_FEDERATED_QUERY,
    SEMANTIC_FEDERATION_ALLOWLIST_ADD,
    SEMANTIC_FEDERATION_ALLOWLIST_REMOVE,
    SEMANTIC_ONTOLOGY_UPLOAD,
    SEMANTIC_ONTOLOGY_ACTIVATE,
    SEMANTIC_ONTOLOGY_DEACTIVATE,
    SEMANTIC_LDN_INBOUND,
    SEMANTIC_LDN_OUTBOUND,
    SEMANTIC_LDN_SUBSCRIPTION_CREATED,
    SEMANTIC_GRAPHQL_QUERY,
)

