"""
Declarative catalogue of Django models that materially store personal data.

Phase 232.0 scaffolds the registry for GDPR/LGPD programme work (RoPA imports,
purge checklists, field-level inventories). Rows are curated — **automated drift
detection belongs in Phase 232+** lint once model metadata is richer.

Extend this module when introducing new ``tenant_id``-scoped tables that persist
subscriber / customer / employee attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class PIIModelEntry:
    """Single ORM row shape that materially stores personal data."""

    app_label: str
    model_name: str
    fields: tuple[str, ...]
    notes: str


# Keep sorted by (app_label, model_name) to reduce noisy diffs during reviews.
PII_HOLDING_REGISTRY: Final[tuple[PIIModelEntry, ...]] = (
    PIIModelEntry(
        "audit",
        "AuditEvent",
        (
            "actor_user",
            "details_json",
            "full_details_json",
        ),
        "Audit payloads may mirror request metadata; treat as pseudonymous/PII-adjacent.",
    ),
    PIIModelEntry(
        "billing",
        "Subscription",
        (
            "tenant",
            "stripe_customer_id",
            "stripe_subscription_id",
        ),
        "Billing vendor identifiers correlate tenants to individuals/org payers.",
    ),
    PIIModelEntry(
        "breach",
        "BreachIncident",
        ("title", "summary", "details_json", "created_by"),
        "Breach summaries may contain free-text facts about affected individuals.",
    ),
    PIIModelEntry(
        "breach",
        "BreachNotification",
        ("rendered_subject", "rendered_body", "outbound_reference"),
        "Rendered notifications to authorities may restate incident facts.",
    ),
    PIIModelEntry(
        "compliance",
        "ComplianceRun",
        ("column_findings_json", "regulation_mapping_json"),
        "Scan outputs embed column-level detections plus optional sample payloads.",
    ),
    PIIModelEntry(
        "dsar",
        "BackupAffectedBySubject",
        ("subject_email_normalized", "backup_identifier", "notes"),
        "Subjects correlated to immutable backup artefacts for exemption tracking (D232.9).",
    ),
    PIIModelEntry(
        "dsar",
        "DSARRequest",
        (
            "subject_email",
            "subject_name",
            "handler_notes",
            "details_json",
            "linked_user",
        ),
        "Statutory DSAR lifecycle records for identifiable requesters.",
    ),
    PIIModelEntry(
        "gdpr",
        "DataExportJob",
        ("user", "storage_path", "download_url"),
        "Portability artefacts reference the data subject plus export storage locations.",
    ),
    PIIModelEntry(
        "gdpr",
        "ErasureRequest",
        ("user",),
        "Right-to-erasure workflow rows remain attributable to individuals.",
    ),
    PIIModelEntry(
        "notifications",
        "UserNotification",
        ("user", "title", "message"),
        "In-app notification copy is user-specific and often narrative.",
    ),
    PIIModelEntry(
        "processor_agreements",
        "Processor",
        ("name", "legal_name", "website", "notes"),
        "Processor inventory may identify vendors and operational relationships.",
    ),
    PIIModelEntry(
        "processor_agreements",
        "ProcessorAgreement",
        (
            "document_uri",
            "sub_processors_declared",
            "transfer_mechanism_summary",
            "registration_reference",
            "details_json",
        ),
        "Agreement metadata and sub-processor disclosures may restate processing facts.",
    ),
    PIIModelEntry(
        "users",
        "PasswordHistory",
        ("user", "password_hash"),
        "Historical credential digests attributable to individuals; purge with account DSAR flows.",
    ),
    PIIModelEntry(
        "users",
        "User",
        (
            "email",
            "display_name",
            "avatar_url",
            "preferences",
            "invitation_token",
            "password_reset_token",
            "email_verification_token",
        ),
        "Core identity, profile attributes, and hashed artefacts that gate account recovery.",
    ),
    PIIModelEntry(
        "users",
        "UserTenantMembership",
        ("user", "tenant"),
        "Membership graph ties natural persons to organisations they may access.",
    ),
    PIIModelEntry(
        "webhooks",
        "Webhook",
        ("url", "secret", "tenant"),
        "Delivery endpoints + shared secrets fingerprint external systems integrated by people.",
    ),
)


def registered_model_labels() -> tuple[str, ...]:
    """Return immutable ``app_label.ModelName`` tuples for lint/tests."""
    return tuple(f"{e.app_label}.{e.model_name}" for e in PII_HOLDING_REGISTRY)
