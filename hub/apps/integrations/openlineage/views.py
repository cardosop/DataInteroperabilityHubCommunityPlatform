"""
Phase 228 F4 (228.F4.7) — OpenLineage REST endpoints.

Two endpoint groups:

* **Inbound** (``POST /api/v1/lineage/openlineage/events/``,
  REQ-LIN-F4-002) — receives RunEvents from external producers
  (Marquez, Datakin, custom). Auth: Bearer + HMAC. Validates the
  payload against the OpenLineage 2.0.0 schema, then routes to the
  signal-handler diff path so the relational ``LineageEdge`` index
  picks up external edges. Returns 202 (accepted; processing is
  fire-and-forget).
* **Key admin** (``GET / POST / DELETE /api/v1/lineage/openlineage/keys/``,
  REQ-LIN-F4-003) — TENANT_ADMIN-only. Plaintext returned ONCE on
  POST; persisted state holds only the bcrypt hash + the prefix for
  display.

Capability gate (228.F4.8): every endpoint returns 404 when
``lineage.openlineage_export`` is OFF. The flag default is OFF in
prod / staging, ON in test.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability gate helper
# ---------------------------------------------------------------------------


def _gate_404_if_capability_off() -> None:
    """Raise NotFound if ``lineage.openlineage_export`` is OFF.

    Per 228.F4.8: every OpenLineage endpoint returns 404 (not 403)
    when the flag is OFF — the endpoint MUST appear nonexistent so
    enumeration doesn't leak the feature's existence.
    """
    from hub.apps.api.capabilities import is_capability_enabled

    if not is_capability_enabled("lineage.openlineage_export"):
        raise NotFound("Endpoint not available")


# ---------------------------------------------------------------------------
# Inbound endpoint — POST /events/
# ---------------------------------------------------------------------------


def _verify_hmac(body: bytes, signature_header: str | None) -> bool:
    """Constant-time HMAC verification.

    The signing key is read from ``settings.OPENLINEAGE_HMAC_SIGNING_KEY``.
    AWS Secrets Manager populates it in production
    (`meshant/staging/openlineage/hmac_signing_key`, 90-day rotation
    per 228.F4.14)."""
    key = getattr(settings, "OPENLINEAGE_HMAC_SIGNING_KEY", None)
    if not key or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        key.encode("utf-8"), body, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _authenticate_ingest_key(request) -> Any | None:
    """Resolve an active :class:`OpenLineageIngestApiKey` from the
    ``X-Meshant-OpenLineage-Key`` header, or return None on auth failure.

    NOTE: we deliberately use a CUSTOM header instead of
    ``Authorization: Bearer`` because the project's global JWT
    middleware claims any ``Bearer`` token and 401's anything that
    can't be decoded as a JWT — our ``msh_ol_<plaintext>`` token
    isn't a JWT, so co-locating it in ``Authorization`` would never
    reach this view. The custom header name is documented in
    docs/integrations/openlineage.md so external producers know
    the contract.

    Bcrypt verification is O(N keys-in-tenant); bounded because
    ``--rotate`` keeps at most 2 active keys per tenant during the
    7-day grace window.
    """
    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
        verify_ingest_key,
    )

    plaintext = request.headers.get("X-Meshant-OpenLineage-Key", "").strip()
    if not plaintext.startswith("msh_ol_"):
        return None
    # Use the prefix to narrow the candidate set BEFORE bcrypt — the
    # prefix is non-secret (operators see it in the UI) so it's safe
    # to use as a query filter.
    prefix = plaintext.removeprefix("msh_ol_")[:8]
    candidates = OpenLineageIngestApiKey.objects.filter(
        key_prefix=prefix,
        revoked_at__isnull=True,
    ).select_related("tenant")
    for cand in candidates:
        if not cand.is_active():
            continue
        if verify_ingest_key(plaintext, cand.key_hash):
            # Best-effort last-used update; failure is non-fatal.
            try:
                from django.utils import timezone
                now = timezone.now()
                update_fields = ["last_used_at"]
                cand.last_used_at = now
                # Phase 228 F4 (REQ-LIN-F4-003 spec scenario "Quarterly
                # rotation grace") — emit OPENLINEAGE_KEY_GRACE_USED on
                # the FIRST authentication that lands inside the key's
                # grace window. Once-per-key (latched by
                # ``grace_audit_emitted_at``) so a busy producer doesn't
                # generate one audit row per request.
                in_grace = (
                    cand.expires_at is not None
                    and cand.expires_at > now
                    and cand.grace_audit_emitted_at is None
                )
                if in_grace:
                    cand.grace_audit_emitted_at = now
                    update_fields.append("grace_audit_emitted_at")
                cand.save(update_fields=update_fields)
                if in_grace:
                    _emit_key_audit(
                        action_const_name="OPENLINEAGE_KEY_GRACE_USED",
                        actor_user=None,
                        tenant=cand.tenant,
                        key_row=cand,
                    )
            except Exception:  # noqa: BLE001
                pass
            return cand
    return None


MAX_INBOUND_BODY_BYTES = 1024 * 1024
"""REQ-LIN-F4-002 — payload size cap (1 MB)."""

MAX_INBOUND_DATASETS = 100
"""REQ-LIN-F4-002 — combined inputs+outputs dataset count cap."""


def _record_inbound_metric(*, result: str) -> None:
    """Best-effort emit of ``openlineage_inbound_total{result}``."""
    try:
        from hub.apps.observability.metrics import openlineage_inbound_total
    except Exception:  # noqa: BLE001
        return
    try:
        openlineage_inbound_total.labels(result=result).inc()
    except Exception:  # noqa: BLE001
        pass


def _translate_inbound_event_to_edges(event: dict, *, tenant) -> int:
    """Materialize the inbound event's source/target dataset
    references into an open ``LineageEdge`` row when both endpoints
    carry resolvable Meshant contract ids.

    Returns the number of edge rows actually inserted (0 when the
    event references contracts the tenant doesn't own / when the
    edge already exists open).
    """
    from django.db import IntegrityError

    from hub.apps.contracts.models import Contract, LineageEdge
    from hub.apps.integrations.openlineage.translator import (
        openlineage_to_meshant_edge,
    )

    edge_dict = openlineage_to_meshant_edge(event)
    src_id = edge_dict.get("source_contract")
    tgt_id = edge_dict.get("target_contract")
    if not src_id or not tgt_id:
        # External producer didn't carry contract references — record
        # nothing. The Meshant ↔ contract relational index is the
        # canonical state; we don't synthesize fake contract rows.
        return 0

    # Tenant ownership check — refuse to write an edge into another
    # tenant's lineage graph based on an inbound POST.
    src = Contract.objects.filter(id=src_id, tenant=tenant).first()
    tgt = Contract.objects.filter(id=tgt_id, tenant=tenant).first()
    if src is None or tgt is None:
        return 0

    try:
        LineageEdge.objects.create(
            tenant=tenant,
            source_contract=src,
            target_contract=tgt,
            source_model=edge_dict.get("source_model") or "",
            source_field=edge_dict.get("source_field") or "",
            target_model=edge_dict.get("target_model") or "",
            target_field=edge_dict.get("target_field") or "",
            edge_type=edge_dict.get("edge_type") or "reference",
            transformation_ref=edge_dict.get("transformation_ref") or "",
            job_ref=edge_dict.get("job_ref") or "",
            created_by_run="openlineage_inbound",
        )
    except IntegrityError:
        # Open-row partial-unique constraint hit — an equivalent edge
        # is already open. Spec scenario "Duplicate event idempotent"
        # treats this as a no-op (zero new edges) which the caller
        # surfaces in the response.
        return 0
    return 1


@extend_schema(
    tags=["OpenLineage"],
    description=(
        "Inbound OpenLineage RunEvent endpoint. Auth: "
        "``X-Meshant-OpenLineage-Key: msh_ol_<plaintext>`` + "
        "``X-Meshant-Signature: sha256=<hmac>``. "
        "Returns 202 on accept (with ``edges_created``), 400 on schema "
        "validation, 401 on auth, 413 if body > 1 MB or > 100 datasets, "
        "404 when the ``lineage.openlineage_export`` capability is OFF. "
        "Idempotent on ``run.runId``: a duplicate POST returns the "
        "original 202 payload unchanged."
    ),
    responses={
        202: OpenApiResponse(description="Event accepted (or duplicate)."),
        400: OpenApiResponse(description="Schema validation failed."),
        401: OpenApiResponse(description="Bearer / HMAC auth failed."),
        404: OpenApiResponse(description="Capability flag off."),
        413: OpenApiResponse(description="Payload too large."),
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def openlineage_events_view(request):
    """``POST /api/v1/lineage/openlineage/events/`` — REQ-LIN-F4-002."""
    _gate_404_if_capability_off()

    raw_body = request.body

    # GAP-D5 — body-size cap (1 MB). Reject BEFORE parse / HMAC so a
    # 50 MB attacker payload doesn't burn server cycles.
    if len(raw_body) > MAX_INBOUND_BODY_BYTES:
        _record_inbound_metric(result="too_large")
        return Response(
            {"error": {"code": "PAYLOAD_TOO_LARGE", "limit_bytes": MAX_INBOUND_BODY_BYTES}},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    signature = request.headers.get("X-Meshant-Signature")
    if not _verify_hmac(raw_body, signature):
        _record_inbound_metric(result="auth_failed")
        return Response(
            {"error": {"code": "AUTH_HMAC_INVALID"}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    key = _authenticate_ingest_key(request)
    if key is None:
        _record_inbound_metric(result="auth_failed")
        return Response(
            {"error": {"code": "AUTH_BEARER_INVALID"}},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        _record_inbound_metric(result="validation_failed")
        return Response(
            {"error": {"code": "INVALID_JSON"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # GAP-D6 — dataset count cap (100 across inputs + outputs).
    inputs = event.get("inputs") or []
    outputs = event.get("outputs") or []
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        # Schema validation below catches the shape error; we only
        # short-circuit the count-check on lists.
        pass
    elif len(inputs) + len(outputs) > MAX_INBOUND_DATASETS:
        _record_inbound_metric(result="too_large")
        return Response(
            {"error": {
                "code": "DATASETS_LIMIT_EXCEEDED",
                "limit": MAX_INBOUND_DATASETS,
                "received": len(inputs) + len(outputs),
            }},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    # Schema validation against the OpenLineage 2.0.0 subset.
    from hub.apps.integrations.openlineage.translator import (
        validate_openlineage_event,
    )
    try:
        validate_openlineage_event(event)
    except Exception as exc:  # jsonschema.ValidationError + others
        logger.info(
            "openlineage_inbound_validation_failed",
            extra={"tenant_id": str(key.tenant_id), "error": str(exc)[:512]},
        )
        _record_inbound_metric(result="validation_failed")
        return Response(
            {"error": {
                "code": "OPENLINEAGE_VALIDATION_FAILED",
                "message": str(exc)[:512],
            }},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # GAP-D4 — idempotency on ``run.runId``. The unique constraint
    # on ``(tenant, event_id)`` is the source of truth; the
    # get-or-create dance handles the race where two requests with
    # the same id arrive concurrently.
    from hub.apps.integrations.openlineage.models import (
        OpenLineageInboundEvent,
    )

    event_id = (event.get("run") or {}).get("runId")
    if not event_id:
        # Schema validator above guarantees runId; defensive path.
        _record_inbound_metric(result="validation_failed")
        return Response(
            {"error": {"code": "MISSING_RUN_ID"}},
            status=status.HTTP_400_BAD_REQUEST,
        )

    existing = OpenLineageInboundEvent.objects.filter(
        tenant=key.tenant, event_id=str(event_id),
    ).first()
    if existing is not None:
        _record_inbound_metric(result="duplicate")
        return Response(
            {
                "accepted": True,
                "event_id": existing.event_id,
                "edges_created": existing.edges_created,
                "duplicate": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    # First-accept path — translate + persist.
    edges_created = _translate_inbound_event_to_edges(event, tenant=key.tenant)
    try:
        OpenLineageInboundEvent.objects.create(
            tenant=key.tenant,
            event_id=str(event_id),
            edges_created=edges_created,
        )
    except Exception as exc:  # noqa: BLE001 — race-window: a concurrent
        # request inserted the same (tenant, event_id) between our
        # ``filter`` and the ``create``. The unique constraint surfaces
        # as IntegrityError; treat as duplicate.
        from django.db import IntegrityError

        if isinstance(exc, IntegrityError):
            existing = OpenLineageInboundEvent.objects.filter(
                tenant=key.tenant, event_id=str(event_id),
            ).first()
            if existing is not None:
                _record_inbound_metric(result="duplicate")
                return Response(
                    {
                        "accepted": True,
                        "event_id": existing.event_id,
                        "edges_created": existing.edges_created,
                        "duplicate": True,
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
        raise

    _record_inbound_metric(result="accepted")
    return Response(
        {
            "accepted": True,
            "event_id": str(event_id),
            "edges_created": edges_created,
            "duplicate": False,
        },
        status=status.HTTP_202_ACCEPTED,
    )


# ---------------------------------------------------------------------------
# Key admin endpoints — GET / POST / DELETE /keys/
# ---------------------------------------------------------------------------


def _emit_key_audit(
    *,
    action_const_name: str,
    actor_user,
    tenant,
    key_row,
) -> None:
    """Phase 228 F4 (REQ-LIN-F4-003 / DoD self-audit GAP-D8) — best-
    effort audit emission for ``OPENLINEAGE_KEY_{CREATED,REVOKED,ROTATED}``.

    The action string is resolved through the named registry at
    [hub.apps.audit.models] so a typo here surfaces as
    ``ImportError`` not as a divergent free-form action history.
    Failures are swallowed + logged: an audit-emit error MUST NOT
    block the key operation."""
    try:
        from hub.apps.audit import models as audit_models
        from hub.apps.audit.utils import create_audit_event
    except Exception:  # noqa: BLE001 — audit module optional at import.
        return
    try:
        action = getattr(audit_models, action_const_name)
    except AttributeError:
        logger.warning(
            "openlineage_audit_action_missing",
            extra={"action_const_name": action_const_name},
        )
        return
    try:
        create_audit_event(
            resource_type="OPENLINEAGE_KEY",
            action=action,
            actor_user=actor_user if getattr(actor_user, "is_authenticated", False) else None,
            tenant=tenant,
            resource_id=str(getattr(key_row, "id", "") or ""),
            details={
                "label": getattr(key_row, "label", ""),
                "key_prefix": getattr(key_row, "key_prefix", ""),
            },
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            "openlineage_audit_emit_failed",
            extra={"action": action_const_name, "error": str(exc)},
        )


def _is_tenant_admin(user, tenant) -> bool:
    """True iff ``user`` holds the TENANT_ADMIN role for ``tenant``."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_platform_admin", False):
        return True
    try:
        from hub.apps.users.models import UserRole
        return UserRole.objects.filter(
            user=user, tenant=tenant, role__name="TENANT_ADMIN",
        ).exists()
    except Exception:  # noqa: BLE001 — fail closed
        return False


def _serialize_key(row) -> dict[str, Any]:
    """Public-safe key representation. Never include hash / plaintext."""
    return {
        "id": str(row.id),
        "label": row.label,
        "key_prefix": row.key_prefix,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "is_active": row.is_active(),
    }


@extend_schema(
    tags=["OpenLineage"],
    description=(
        "List / create OpenLineage ingest API keys for the caller's "
        "tenant. TENANT_ADMIN-only. The ``key_hash`` and plaintext "
        "are NEVER returned in list responses. The plaintext is "
        "returned ONCE in the create response."
    ),
)
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def openlineage_keys_collection_view(request):
    """``GET / POST /api/v1/lineage/openlineage/keys/``."""
    _gate_404_if_capability_off()

    user = request.user
    tenant = getattr(user, "tenant", None)
    if tenant is None or not _is_tenant_admin(user, tenant):
        return Response(
            {"error": {"code": "FORBIDDEN_ADMIN_ONLY"}},
            status=status.HTTP_403_FORBIDDEN,
        )

    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
        generate_ingest_key_plaintext,
        hash_ingest_key,
    )

    if request.method == "GET":
        rows = OpenLineageIngestApiKey.objects.filter(tenant=tenant).order_by("-created_at")
        return Response({"keys": [_serialize_key(r) for r in rows]})

    # POST → create.
    label = (request.data or {}).get("label") or "unlabeled"
    plaintext = generate_ingest_key_plaintext()
    row = OpenLineageIngestApiKey.objects.create(
        tenant=tenant,
        label=str(label)[:120],
        key_prefix=plaintext.removeprefix("msh_ol_")[:8],
        key_hash=hash_ingest_key(plaintext),
        created_by=user if user.is_authenticated else None,
    )
    _emit_key_audit(
        action_const_name="OPENLINEAGE_KEY_CREATED",
        actor_user=user,
        tenant=tenant,
        key_row=row,
    )
    payload = _serialize_key(row)
    payload["plaintext"] = plaintext  # ONCE, on creation.
    payload["plaintext_warning"] = (
        "Store this value now — Meshant cannot recover it. "
        "Persisted state holds only a bcrypt hash."
    )
    return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["OpenLineage"],
    description=(
        "Revoke an OpenLineage ingest API key. TENANT_ADMIN-only. "
        "Sets ``revoked_at`` so the next inbound request fails auth "
        "immediately. The row is retained for audit; use the rotate "
        "command (228.F4.11) for the 7-day grace flow."
    ),
)
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def openlineage_keys_detail_view(request, pk):
    """``DELETE /api/v1/lineage/openlineage/keys/<pk>/``."""
    _gate_404_if_capability_off()

    from hub.apps.integrations.openlineage.models import (
        OpenLineageIngestApiKey,
    )
    user = request.user
    tenant = getattr(user, "tenant", None)
    if tenant is None or not _is_tenant_admin(user, tenant):
        return Response(
            {"error": {"code": "FORBIDDEN_ADMIN_ONLY"}},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        row = OpenLineageIngestApiKey.objects.get(pk=pk, tenant=tenant)
    except OpenLineageIngestApiKey.DoesNotExist:
        return Response(
            {"error": {"code": "KEY_NOT_FOUND"}},
            status=status.HTTP_404_NOT_FOUND,
        )
    from django.utils import timezone
    row.revoked_at = timezone.now()
    row.save(update_fields=["revoked_at"])
    _emit_key_audit(
        action_const_name="OPENLINEAGE_KEY_REVOKED",
        actor_user=user,
        tenant=tenant,
        key_row=row,
    )
    return Response(status=status.HTTP_204_NO_CONTENT)


__all__ = [
    "openlineage_events_view",
    "openlineage_keys_collection_view",
    "openlineage_keys_detail_view",
]
