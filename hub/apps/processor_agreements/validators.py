"""SSRF + agreement-type validation (Phase 232.6.4 / 232.6.9)."""

from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ValidationError

from hub.apps.security.url_validators import SSRFGuard, SSRFViolationError

_SHA256_HEX = re.compile(r"^[a-f0-9]{64}$", re.IGNORECASE)


def normalize_document_uri(raw: str) -> str:
    v = (raw or "").strip()
    return v


def validate_document_uri_for_agreement(uri: str) -> str:
    """Raise ValidationError if ``uri`` is missing or fails :class:`SSRFGuard`."""
    cleaned = normalize_document_uri(uri)
    if not cleaned:
        raise ValidationError("document_uri is required for a recorded agreement.")
    try:
        SSRFGuard.validate(cleaned, allowlist=None)
    except SSRFViolationError as exc:
        raise ValidationError(str(exc)) from exc
    return cleaned


def validate_document_hash_hex(value: str) -> str:
    v = (value or "").strip().lower()
    if not v:
        raise ValidationError("document_hash is required (SHA-256 hex of agreement bytes).")
    if not _SHA256_HEX.fullmatch(v):
        raise ValidationError("document_hash must be a 64-character lowercase hex SHA-256 digest.")
    return v


def validate_agreement_metadata_for_type(
    *,
    agreement_type: str,
    expires_on: Any,
    jurisdiction_region: str,
    registration_reference: str,
    transfer_mechanism_summary: str,
) -> None:
    """Agreement-type-specific required fields (232.6.9)."""
    from hub.apps.processor_agreements.models import ProcessorAgreementType

    region = (jurisdiction_region or "").strip().upper()
    reg_ref = (registration_reference or "").strip()
    xfer = (transfer_mechanism_summary or "").strip()

    if agreement_type == ProcessorAgreementType.BAA:
        if expires_on is None:
            raise ValidationError(
                {"expires_on": "BAA agreements require an explicit expiry/renewal date."}
            )
        if region and region != "US":
            raise ValidationError(
                {
                    "jurisdiction_region": (
                        "BAA agreements are US HIPAA constructs; use region US or leave blank."
                    )
                }
            )
    elif agreement_type == ProcessorAgreementType.SCC:
        if len(xfer) < 8:
            raise ValidationError(
                {
                    "transfer_mechanism_summary": (
                        "SCC agreements require a transfer mechanism summary "
                        "(e.g. 2021 SCC module + transfer context)."
                    )
                }
            )
    elif agreement_type == ProcessorAgreementType.BCR:
        if len(reg_ref) < 4:
            raise ValidationError(
                {
                    "registration_reference": (
                        "BCR agreements require a registration / approval reference."
                    )
                }
            )


def drf_validate_webhook_style_url(value: str) -> None:
    """DRF helper — reuse webhook SSRF rules for optional Processor.website."""
    from hub.apps.webhooks.ssrf_guard import validate_webhook_url

    v = normalize_document_uri(value)
    if not v:
        return
    validate_webhook_url(v, raise_as_validation_error=True)


def normalize_subprocessors_declared(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationError("sub_processors_declared must be a list of objects.")
    out: list[dict[str, Any]] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValidationError(
                f"sub_processors_declared[{i}] must be an object with at least a name."
            )
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValidationError(f"sub_processors_declared[{i}].name is required.")
        row = {"name": name}
        if item.get("details"):
            row["details"] = str(item["details"])[:2000]
        out.append(row)
    return sorted(out, key=lambda x: x["name"].lower())
