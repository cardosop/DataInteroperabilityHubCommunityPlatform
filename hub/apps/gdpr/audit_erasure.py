"""
GDPR Article 17 — scrub audit rows that reference an erased user.

AuditEvent rows are append-only (save() forbids updates) but compliance
requires stripping direct identifiers. Updates use QuerySet.update() so the
ORM immutability guard on save() does not apply.

Phase 1: rows where ``actor_user`` is the target — scrub ``details_json`` /
``full_details_json`` PII keys (same contract as ``ErasureService``) plus
replace duplicate user-id keys with ``[deleted]``, then null ``actor_user_id``.

Phase 2: rows where another actor logged the target's id in JSON keys —
scrub only those id keys (and matching ``user_email`` when it equals the
target's email).
"""
from __future__ import annotations
import logging
import uuid
from typing import Any

from django.db.models import Q

logger = logging.getLogger(__name__)

GDPR_AUDIT_USER_ID_REDACTED: str = "[deleted]"

_PII_KEYS_TO_SCRUB: tuple[str, ...] = (
    "actor_email",
    "user_email",
    "email",
    "display_name",
    "name",
    "phone",
    "ip_address",
    "user_agent",
    "remote_addr",
    "x_forwarded_for",
)
_PII_SENTINEL: str = "deleted@deleted.local"

_AUDIT_USER_ID_JSON_KEYS: tuple[str, ...] = (
    "actor_user_id",
    "user_id",
    "subject_user_id",
    "initiated_by",
)


def _redact_user_ids_in_mapping(
    data: dict[str, Any],
    *,
    uid_str: str,
) -> tuple[dict[str, Any], bool]:
    out = dict(data)
    changed = False
    for key in _AUDIT_USER_ID_JSON_KEYS:
        if key in out and out[key] is not None and str(out[key]) == uid_str:
            out[key] = GDPR_AUDIT_USER_ID_REDACTED
            changed = True
    return out, changed


def _redact_pii_keys_in_mapping(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    out = dict(data)
    changed = False
    for pii_key in _PII_KEYS_TO_SCRUB:
        if pii_key in out:
            out[pii_key] = _PII_SENTINEL
            changed = True
    return out, changed


def _merge_detail_scrub(
    details: dict[str, Any] | None,
    full_details: dict[str, Any] | None,
    *,
    uid_str: str,
    user_email: str | None,
    apply_pii_scrub: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, bool]:
    d = dict(details or {})
    changed = False

    d, ch2 = _redact_user_ids_in_mapping(d, uid_str=uid_str)
    changed |= ch2

    if apply_pii_scrub:
        d, ch3 = _redact_pii_keys_in_mapping(d)
        changed |= ch3

    # Scrub ``user_email`` to the GDPR sentinel whenever the audit
    # row references this subject — either because ``user_email``
    # exact-matches the subject's real address (the original
    # Phase-1 contract) OR because the row's ``user_id`` /
    # ``subject_user_id`` already matched the subject (in which
    # case the email IS for the same subject regardless of literal
    # value). The id-match branch closes a real-world hole:
    # ``audit/utils.py:redact_string`` partially masks emails at
    # audit-create time (``foo@example.com`` →
    # ``fo***@example.com``), so the exact-match guard alone never
    # fires for those rows and PII leaks through erasure.
    if "user_email" in d and (
        (user_email and str(d.get("user_email")) == user_email)
        or ch2
    ):
        d["user_email"] = _PII_SENTINEL
        changed = True

    fd_out: dict[str, Any] | None = None
    if full_details is not None and isinstance(full_details, dict):
        fd = dict(full_details)
        fd, ch4 = _redact_user_ids_in_mapping(fd, uid_str=uid_str)
        changed |= ch4
        if apply_pii_scrub:
            fd, ch5 = _redact_pii_keys_in_mapping(fd)
            changed |= ch5
        if "user_email" in fd and (
            (user_email and str(fd.get("user_email")) == user_email)
            or ch4
        ):
            fd["user_email"] = _PII_SENTINEL
            changed = True
        fd_out = fd
    elif full_details is not None:
        fd_out = full_details

    return d, fd_out, changed


def scrub_audit_events_for_gdpr_user_target(*, user) -> int:
    """
    Scrub audit events for a user targeted by Article 17 erasure.

    Callers that anonymize ``User.email`` (e.g. ``ErasureService``) must invoke
    this **before** changing the subject's email so Phase-2 JSON
    ``user_email`` equality matches the real address.

    Returns the number of audit rows updated.
    """
    from hub.apps.audit.models import AuditEvent

    uid_str = str(user.id)
    user_email = getattr(user, "email", None)

    updated = 0

    # Phase 1 — actor was the erased user (full PII scrub on details).
    qs_actor = AuditEvent.all_objects.filter(actor_user_id=user.id)
    for event in qs_actor.iterator(chunk_size=200):
        d, fd, _ = _merge_detail_scrub(
            event.details_json,
            event.full_details_json,
            uid_str=uid_str,
            user_email=user_email,
            apply_pii_scrub=True,
        )
        upd: dict[str, Any] = {
            "details_json": d,
            "actor_user_id": None,
        }
        if fd is not None:
            upd["full_details_json"] = fd
        AuditEvent.all_objects.filter(pk=event.pk).update(**upd)
        updated += 1

    # Phase 2 — another actor; JSON still references the user's id or email.
    jq = Q()
    for key in _AUDIT_USER_ID_JSON_KEYS:
        jq |= Q(**{f"details_json__{key}": uid_str})
        jq |= Q(**{f"full_details_json__{key}": uid_str})

    qs_other = (
        AuditEvent.all_objects.filter(jq)
        .exclude(actor_user_id=user.id)
        .distinct()
    )
    for event in qs_other.iterator(chunk_size=200):
        d, fd, changed = _merge_detail_scrub(
            event.details_json,
            event.full_details_json,
            uid_str=uid_str,
            user_email=user_email,
            apply_pii_scrub=False,
        )
        if changed:
            upd: dict[str, Any] = {"details_json": d}
            if fd is not None:
                upd["full_details_json"] = fd
            AuditEvent.all_objects.filter(pk=event.pk).update(**upd)
            updated += 1

    return updated


def scrub_audit_events_for_gdpr_user_id(*, user_id: str | uuid.UUID) -> int:
    """Load User then scrub; raises User.DoesNotExist if missing."""
    from hub.apps.users.models import User

    user = User.objects.get(pk=user_id)
    return scrub_audit_events_for_gdpr_user_target(user=user)
