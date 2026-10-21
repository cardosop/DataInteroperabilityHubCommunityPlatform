"""
Erasure / retention coverage for every row in :data:`PII_HOLDING_REGISTRY`.

Phase 232.8.5 — CI asserts this catalogue's keys match
``registered_model_labels()`` exactly so new PII models cannot ship without an
explicit operational decision (Article 17 path, tenant lifecycle, DSAR module,
or documented legal retention).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

ErasureMechanism = Literal[
    "article_17_erasure_service",
    "user_cascade_delete",
    "tenant_dsar_subject_request",
    "tenant_operational_retention",
    "billing_correlation_retention",
    "infrastructure_webhook",
]


@dataclass(frozen=True, slots=True)
class PIIErasureCoverageEntry:
    """How a PII registry row is handled when a natural person invokes erasure / DSAR."""

    model_label: str
    mechanism: ErasureMechanism
    reference: str


# Keep sorted by model_label (same convention as PII_HOLDING_REGISTRY).
PII_ERASURE_COVERAGE: Final[tuple[PIIErasureCoverageEntry, ...]] = (
    PIIErasureCoverageEntry(
        "audit.AuditEvent",
        "article_17_erasure_service",
        "hub.apps.gdpr.services.ErasureService.execute_erasure — actor_user events: "
        "details_json keys scrubbed; rows retained for accountability.",
    ),
    PIIErasureCoverageEntry(
        "billing.Subscription",
        "billing_correlation_retention",
        "Stripe customer/subscription identifiers are tenant billing records, not user-profile rows; "
        "handled under tenant contract off-boarding / finance retention (not user Article 17 alone).",
    ),
    PIIErasureCoverageEntry(
        "breach.BreachIncident",
        "tenant_operational_retention",
        "Breach register is tenant legal obligation; subject erasure does not auto-delete "
        "incident facts — align with breach counsel retention policy.",
    ),
    PIIErasureCoverageEntry(
        "breach.BreachNotification",
        "tenant_operational_retention",
        "Authority-facing deliverables follow breach retention; coordinate with DSAR if subject "
        "data appears verbatim in rendered bodies.",
    ),
    PIIErasureCoverageEntry(
        "compliance.ComplianceRun",
        "article_17_erasure_service",
        "hub.apps.gdpr.services.ErasureService.execute_erasure — compliance runs keyed by "
        "job.created_by user: JSON columns cleared per Article 17 redaction.",
    ),
    PIIErasureCoverageEntry(
        "dsar.BackupAffectedBySubject",
        "tenant_dsar_subject_request",
        "hub.apps.dsar — backup exemption ledger; erased when DSAR / backup programme completes "
        "operator workflow.",
    ),
    PIIErasureCoverageEntry(
        "dsar.DSARRequest",
        "tenant_dsar_subject_request",
        "hub.apps.dsar — statutory case file; minimisation + retention per DSAR policy after closure.",
    ),
    PIIErasureCoverageEntry(
        "gdpr.DataExportJob",
        "user_cascade_delete",
        "ForeignKey to user; Django CASCADE removes portability rows when user row hard-deleted.",
    ),
    PIIErasureCoverageEntry(
        "gdpr.ErasureRequest",
        "user_cascade_delete",
        "ForeignKey to user; retained audit of erasure itself follows user/tenant purge rules.",
    ),
    PIIErasureCoverageEntry(
        "notifications.UserNotification",
        "user_cascade_delete",
        "FK to user; removed with user CASCADE or anonymised when upstream user anonymised.",
    ),
    PIIErasureCoverageEntry(
        "processor_agreements.Processor",
        "tenant_operational_retention",
        "Tenant Article 28 register; not end-user PII erasure target — delete via tenant admin "
        "governance when off-boarding counterparty.",
    ),
    PIIErasureCoverageEntry(
        "processor_agreements.ProcessorAgreement",
        "tenant_operational_retention",
        "Agreement metadata is tenant legal inventory; manage via processor-agreements lifecycle.",
    ),
    PIIErasureCoverageEntry(
        "users.PasswordHistory",
        "user_cascade_delete",
        "Child of users.User; CASCADE on hard delete.",
    ),
    PIIErasureCoverageEntry(
        "users.User",
        "article_17_erasure_service",
        "Primary subject — hub.apps.gdpr.services.ErasureService.execute_erasure anonymises "
        "profile + related scar paths.",
    ),
    PIIErasureCoverageEntry(
        "users.UserTenantMembership",
        "user_cascade_delete",
        "FK to user; CASCADE removes memberships on hard delete / DSAR-driven user removal.",
    ),
    PIIErasureCoverageEntry(
        "webhooks.Webhook",
        "infrastructure_webhook",
        "Tenant integration endpoint metadata; not personal data of a single requester — rotate via "
        "tenant security operations when personnel change.",
    ),
)


def erasure_coverage_labels() -> tuple[str, ...]:
    return tuple(e.model_label for e in PII_ERASURE_COVERAGE)
