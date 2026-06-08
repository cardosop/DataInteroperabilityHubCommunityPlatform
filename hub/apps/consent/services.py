"""Consent grant/revoke orchestration (audit + webhook fan-out)."""

from __future__ import annotations
from typing import Any, Dict, Mapping, Optional

import structlog
from django.db import transaction
from django.utils import timezone

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.utils import create_audit_event
from hub.apps.consent.models import ConsentPurpose, ConsentRecord, ConsentRecordStatus
from hub.apps.consent.signing import (
    compute_proof_hmac,
    get_signing_key_ring_for_tenant,
    verify_proof_hmac,
)
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context
from hub.apps.users.models import User

logger = structlog.get_logger(__name__)


class ConsentService:
    service_name = "consent"

    def verify_record_integrity(self, record: ConsentRecord) -> bool:
        ring = get_signing_key_ring_for_tenant(str(record.tenant_id))
        ok, _ = verify_proof_hmac(
            proof_hex=record.proof_hmac,
            tenant_id=str(record.tenant_id),
            user_id=str(record.user_id),
            purpose_id=str(record.purpose_id),
            payload=record.canonical_payload,
            key_ring=ring,
        )
        return ok

    @transaction.atomic
    def grant(
        self,
        *,
        tenant: Tenant,
        user: User,
        purpose: ConsentPurpose,
        payload: Mapping[str, Any],
        actor_user: Optional[User] = None,
        request=None,
    ) -> ConsentRecord:
        if str(purpose.tenant_id) != str(tenant.id):
            raise ValidationError("Purpose belongs to a different tenant.", code="TENANT_MISMATCH")
        if not purpose.is_active:
            raise ValidationError("Purpose is not active.", code="PURPOSE_INACTIVE")

        key_ring = get_signing_key_ring_for_tenant(str(tenant.id))
        if not key_ring:
            raise ValidationError(
                "No consent signing keys configured for this tenant.",
                code="SIGNING_KEYS_MISSING",
            )

        proof = compute_proof_hmac(
            key=key_ring[0],
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            purpose_id=str(purpose.id),
            payload=payload,
        )

        # RLS: consent tables require app.current_tenant_id (middleware is absent on
        # auth/register and other bootstrap paths). Nested atomic matches tenant_context.
        with tenant_context(str(tenant.id)):
            existing = ConsentRecord.objects.filter(
                tenant=tenant, user=user, purpose=purpose
            ).first()
            if (
                existing
                and existing.status == ConsentRecordStatus.GRANTED
                and existing.proof_hmac == proof
            ):
                return existing

            # 277.B.086 — snapshot the purpose version so we can detect stale grants later
            purpose_version = (
                int(payload.get("purpose_version", 0))
                if "purpose_version" in payload
                else purpose.version
            )
            record, _created = ConsentRecord.objects.update_or_create(
                tenant=tenant,
                user=user,
                purpose=purpose,
                defaults={
                    "status": ConsentRecordStatus.GRANTED,
                    "granted_at": timezone.now(),
                    "revoked_at": None,
                    "canonical_payload": dict(payload),
                    "proof_hmac": proof,
                    "signing_key_index": 0,
                    "purpose_version_at_grant": purpose_version,
                },
            )

            create_audit_event(
                resource_type="CONSENT_RECORD",
                action=audit_event_types.CONSENT_GRANTED,
                actor_user=actor_user or user,
                tenant=tenant,
                resource_id=str(record.id),
                details={
                    "purpose_id": str(purpose.id),
                    "purpose_key": purpose.key,
                    "purpose_version": purpose.version,
                    "purpose_version_at_grant": purpose_version,
                    "user_id": str(user.id),
                    "record_id": str(record.id),
                },
                request=request,
            )

            transaction.on_commit(
                lambda rid=str(record.id), tid=str(tenant.id): _publish_granted_webhook(
                    record_id=rid, tenant_id=tid
                )
            )

            return record

    @transaction.atomic
    def revoke(
        self,
        *,
        tenant: Tenant,
        record: ConsentRecord,
        actor_user: User,
        request=None,
    ) -> ConsentRecord:
        subject = record.user
        if str(record.tenant_id) != str(tenant.id):
            raise ValidationError("Record not in tenant.", code="TENANT_MISMATCH")
        if str(actor_user.id) != str(subject.id):
            if not (
                getattr(actor_user, "is_platform_admin", False)
                or _user_has_any_role(actor_user, tenant, ("TENANT_ADMIN", "DPO"))
            ):
                raise ValidationError("Cannot revoke another user's consent.", code="FORBIDDEN")

        key_ring = get_signing_key_ring_for_tenant(str(tenant.id))
        if record.proof_hmac:
            ok, _ = verify_proof_hmac(
                proof_hex=record.proof_hmac,
                tenant_id=str(record.tenant_id),
                user_id=str(record.user_id),
                purpose_id=str(record.purpose_id),
                payload=record.canonical_payload,
                key_ring=key_ring,
            )
            if not ok:
                raise ValidationError(
                    "Consent proof verification failed (tampered or stale keys).",
                    code="PROOF_VERIFICATION_FAILED",
                )

        with tenant_context(str(tenant.id)):
            record.status = ConsentRecordStatus.REVOKED
            record.revoked_at = timezone.now()
            record.save(update_fields=["status", "revoked_at", "updated_at"])

            create_audit_event(
                resource_type="CONSENT_RECORD",
                action=audit_event_types.CONSENT_REVOKED,
                actor_user=actor_user,
                tenant=tenant,
                resource_id=str(record.id),
                details={
                    "purpose_id": str(record.purpose_id),
                    "user_id": str(subject.id),
                },
                request=request,
            )

            transaction.on_commit(
                lambda rid=str(record.id), tid=str(tenant.id): _publish_revoked_webhook(
                    record_id=rid, tenant_id=tid
                )
            )
        return record

    # ── 277.B.086 — version-aware reconsent detection ────────────────────

    @classmethod
    def check_user_needs_reconsent(
        cls,
        *,
        user: User,
        tenant: Tenant,
    ) -> bool:
        """Return True if any of the user's active grants are stale (version < purpose.version)."""
        stale = cls.get_stale_purposes_for_user(user=user, tenant=tenant)
        return len(stale) > 0

    @classmethod
    def get_stale_purposes_for_user(
        cls,
        *,
        user: User,
        tenant: Tenant,
    ) -> list[dict[str, Any]]:
        """Return list of stale purposes (grant version < current version) for re-prompt."""
        from django.db.models import F

        with tenant_context(str(tenant.id)):
            stale_records = ConsentRecord.objects.filter(
                tenant=tenant,
                user=user,
                status=ConsentRecordStatus.GRANTED,
                purpose__is_active=True,
                purpose_version_at_grant__lt=F("purpose__version"),
            ).select_related("purpose")

            result: list[dict[str, Any]] = []
            for rec in stale_records:
                result.append({
                    "purpose_id": str(rec.purpose_id),
                    "purpose_key": rec.purpose.key,
                    "purpose_name": rec.purpose.name,
                    "granted_version": rec.purpose_version_at_grant,
                    "current_version": rec.purpose.version,
                    "record_id": str(rec.id),
                })
            return result


def _user_has_any_role(user: User, tenant: Tenant, names: tuple[str, ...]) -> bool:
    from hub.apps.users.models import UserRole

    return UserRole.objects.filter(
        user=user,
        tenant=tenant,
        role__name__in=names,
    ).exists()


def _publish_granted_webhook(*, record_id: str, tenant_id: str) -> None:
    try:
        from hub.apps.consent.models import ConsentRecord
        from hub.apps.consent.webhook_emission import publish_consent_granted

        with tenant_context(tenant_id):
            row = ConsentRecord.objects.filter(pk=record_id).first()
        if row:
            publish_consent_granted(row)
    except Exception as exc:
        logger.warning(
            "consent_granted_webhook_failed",
            record_id=record_id,
            error=str(exc),
            exc_info=True,
        )


def _publish_revoked_webhook(*, record_id: str, tenant_id: str) -> None:
    try:
        from hub.apps.consent.models import ConsentRecord
        from hub.apps.consent.webhook_emission import publish_consent_revoked

        with tenant_context(tenant_id):
            row = ConsentRecord.objects.filter(pk=record_id).first()
        if row:
            publish_consent_revoked(row)
    except Exception as exc:
        logger.warning(
            "consent_revoked_webhook_failed",
            record_id=record_id,
            error=str(exc),
            exc_info=True,
        )


def dashboard_summary(*, tenant: Tenant) -> Dict[str, Any]:
    """Aggregate counts for DPO / tenant-admin dashboard (RLS-safe read path)."""
    from django.db.models import Count, Q

    with tenant_context(str(tenant.id)):
        purposes = ConsentPurpose.objects.filter(tenant=tenant)
        rows = []
        for p in purposes:
            stats = ConsentRecord.objects.filter(tenant=tenant, purpose=p).aggregate(
                granted=Count("id", filter=Q(status=ConsentRecordStatus.GRANTED)),
                revoked=Count("id", filter=Q(status=ConsentRecordStatus.REVOKED)),
            )
            rows.append(
                {
                    "purpose_id": str(p.id),
                    "purpose_key": p.key,
                    "name": p.name,
                    "active_grants": stats["granted"],
                    "revoked_records": stats["revoked"],
                }
            )
    return {"purposes": rows}
