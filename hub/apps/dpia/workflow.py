"""DPIA workflow transitions — Phase 232.5."""

from __future__ import annotations
from typing import Any, Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.dpia.models import Dpia, DpiaStatus, ResidualRiskLevel
from hub.apps.dpia.services.review_due import default_next_review_due
from hub.apps.tenants.models import Tenant


def _ensure_dpia_feature(tenant: Tenant) -> None:
    if not getattr(tenant, "compliance_dpia_enabled", False):
        raise ValidationError("DPIA capability is disabled for this tenant.")


@transaction.atomic
def submit_dpia(*, dpia: Dpia, actor) -> Dpia:
    """DRAFT → IN_REVIEW."""
    _ensure_dpia_feature(dpia.tenant)
    if dpia.status != DpiaStatus.DRAFT:
        raise ValidationError("Only DRAFT assessments can be submitted.")
    dpia.status = DpiaStatus.IN_REVIEW
    dpia.save(update_fields=["status", "updated_at"])
    create_audit_event(
        resource_type="DPIA",
        action=event_types.DPIA_SUBMITTED,
        actor_user=actor,
        tenant=dpia.tenant,
        resource_id=dpia.id,
        details={"title": dpia.title, "version": dpia.version},
    )
    return dpia


@transaction.atomic
def review_dpia(
    *,
    dpia: Dpia,
    actor,
    outcome: str,
    risk_residual: str = "",
    dpo_summary: str = "",
) -> Dpia:
    """IN_REVIEW / REQUIRES_CONSULTATION → terminal status or re-queue."""
    _ensure_dpia_feature(dpia.tenant)
    if dpia.status not in (DpiaStatus.IN_REVIEW, DpiaStatus.REQUIRES_CONSULTATION):
        raise ValidationError("Assessment is not in a reviewable state.")

    if outcome not in (
        DpiaStatus.APPROVED,
        DpiaStatus.REJECTED,
        DpiaStatus.REQUIRES_CONSULTATION,
    ):
        raise ValidationError("Invalid review outcome.")

    now = timezone.now()
    dpia.reviewed_by = actor
    dpia.reviewed_at = now
    if risk_residual:
        valid = {c[0] for c in ResidualRiskLevel.choices}
        if risk_residual not in valid:
            raise ValidationError("Invalid residual risk level.")
        dpia.risk_residual = risk_residual
    dpia.dpo_summary = dpo_summary or dpia.dpo_summary

    if outcome == DpiaStatus.REJECTED:
        dpia.status = DpiaStatus.REJECTED
        dpia.next_review_due_at = None
    elif outcome == DpiaStatus.REQUIRES_CONSULTATION:
        dpia.status = DpiaStatus.REQUIRES_CONSULTATION
        dpia.next_review_due_at = None
    elif outcome == DpiaStatus.APPROVED:
        # GDPR Art 36 — residual HIGH typically requires supervisory consultation.
        if dpia.risk_residual == ResidualRiskLevel.HIGH:
            dpia.status = DpiaStatus.REQUIRES_CONSULTATION
            dpia.next_review_due_at = None
        else:
            dpia.status = DpiaStatus.APPROVED
            dpia.next_review_due_at = default_next_review_due(now)
            _supersede_prior_approved(dpia)
    else:  # pragma: no cover — guarded above
        raise ValidationError("Invalid review outcome.")

    dpia.save(
        update_fields=[
            "status",
            "risk_residual",
            "dpo_summary",
            "reviewed_by",
            "reviewed_at",
            "next_review_due_at",
            "updated_at",
        ]
    )
    create_audit_event(
        resource_type="DPIA",
        action=event_types.DPIA_REVIEW_DECISION,
        actor_user=actor,
        tenant=dpia.tenant,
        resource_id=dpia.id,
        details={
            "outcome": dpia.status,
            "risk_residual": dpia.risk_residual,
        },
    )
    return dpia


def _supersede_prior_approved(dpia: Dpia) -> None:
    if not dpia.asset_id:
        return
    qs = Dpia.objects.filter(
        tenant=dpia.tenant,
        asset_id=dpia.asset_id,
        status=DpiaStatus.APPROVED,
    ).exclude(pk=dpia.pk)
    n = qs.update(status=DpiaStatus.SUPERSEDED)
    if n:
        create_audit_event(
            resource_type="DPIA",
            action=event_types.DPIA_SUPERSEDED,
            tenant=dpia.tenant,
            resource_id=dpia.id,
            details={"superseded_count": n, "asset_id": str(dpia.asset_id)},
        )


@transaction.atomic
def complete_consultation(*, dpia: Dpia, actor, approve: bool) -> Dpia:
    """REQUIRES_CONSULTATION → APPROVED or back to IN_REVIEW for further edits."""
    _ensure_dpia_feature(dpia.tenant)
    if dpia.status != DpiaStatus.REQUIRES_CONSULTATION:
        raise ValidationError("Assessment does not require consultation completion.")
    if approve:
        dpia.status = DpiaStatus.APPROVED
        dpia.next_review_due_at = default_next_review_due(timezone.now())
        _supersede_prior_approved(dpia)
    else:
        dpia.status = DpiaStatus.IN_REVIEW
        dpia.next_review_due_at = None
    dpia.save(update_fields=["status", "next_review_due_at", "updated_at"])
    create_audit_event(
        resource_type="DPIA",
        action=event_types.DPIA_REVIEW_DECISION,
        actor_user=actor,
        tenant=dpia.tenant,
        resource_id=dpia.id,
        details={"consultation_complete": True, "approved": approve},
    )
    return dpia


@transaction.atomic
def create_follow_on_version(*, dpia: Dpia, actor, title: Optional[str] = None) -> Dpia:
    """Create a new DRAFT version after an approved / closed cycle."""
    _ensure_dpia_feature(dpia.tenant)
    if dpia.status not in (
        DpiaStatus.APPROVED,
        DpiaStatus.REJECTED,
        DpiaStatus.SUPERSEDED,
    ):
        raise ValidationError("Only terminal rows can spawn a new version.")
    next_v = (
        Dpia.objects.filter(tenant=dpia.tenant, asset_id=dpia.asset_id)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
        or dpia.version
    )
    next_v = max(next_v, dpia.version) + 1
    clone = Dpia.objects.create(
        tenant=dpia.tenant,
        asset=dpia.asset,
        title=title or f"{dpia.title} (v{next_v})",
        regime=dpia.regime,
        status=DpiaStatus.DRAFT,
        version=next_v,
        previous_version=dpia,
        wizard_payload=dict(dpia.wizard_payload or {}),
        created_by=actor,
    )
    create_audit_event(
        resource_type="DPIA",
        action=event_types.DPIA_CREATED,
        actor_user=actor,
        tenant=clone.tenant,
        resource_id=clone.id,
        details={"from_version": str(dpia.id), "version": next_v},
    )
    return clone


def diff_wizard_payloads(
    current: dict[str, Any], previous: Optional[dict[str, Any]]
) -> dict[str, Any]:
    """Structural diff for wizard JSON (shallow key-level)."""
    prev = previous or {}
    keys = sorted(set(current.keys()) | set(prev.keys()))
    changes: list[dict[str, Any]] = []
    for k in keys:
        if current.get(k) != prev.get(k):
            changes.append(
                {
                    "field": k,
                    "before": prev.get(k),
                    "after": current.get(k),
                }
            )
    return {"changed_keys": changes, "previous_key_count": len(prev), "current_key_count": len(current)}
