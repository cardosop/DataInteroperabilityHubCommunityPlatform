"""Canonical IRI construction (Phase 226 G7a; moved to core in Phase 313.1).

Single source of truth for the platform's canonical Linked Data IRI shape.
Every place in the backend that needs to reference "the URL where this
resource is dereferenceable as JSON-LD" MUST go through this module so
that a change to ``SEMANTIC_BASE_IRI`` propagates everywhere atomically.

Phase 313.1: moved from ``hub/apps/semantic/iri.py`` into core so the free
core serializers (assets/datasets/contracts) no longer import the paid
semantic app. ``hub.apps.semantic.iri`` re-exports this module for
compatibility.

Contract:

    canonical_iri_for("asset", "<uuid>") ==
        f"{settings.SEMANTIC_BASE_IRI}/id/asset/<uuid>"

The base IRI is read fresh on every call (no module-level cache) so that
``override_settings`` in tests and runtime config reloads both work.

The 303 dereferencing handler in `hub/urls.py`:semantic_id_view (and the
fallback at `hub/apps/semantic/services.py`:533) resolve incoming
`/api/v1/semantic/id/<type>/<id>` requests to this exact IRI as the
``Location`` header. The end-to-end guard in
`frontend/e2e/fixtures/verifySemantic.ts` asserts the round-trip — a
PR that drifts the IRI shape on either side fails ≥ 1 spec immediately.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings

if TYPE_CHECKING:
    from collections.abc import Iterable
    from uuid import UUID

# Canonical resource-type slugs. These match the path segment used by the
# 303 handler (`/api/v1/semantic/id/<type>/<id>`) and the JSON-LD context
# at `/api/v1/semantic/context.jsonld`. Adding a new resource type means
# adding it here AND wiring the matching dereference branch upstream —
# the unit test in `hub/apps/semantic/tests/test_iri.py` enumerates them.
SUPPORTED_RESOURCE_TYPES: frozenset[str] = frozenset(
    {
        "asset",
        "dataset",
        "contract",
        "semantic_resource",
        "field",
        "dq_run",
        "compliance_run",
        "listing",
    }
)


def _resolve_base() -> str:
    """Return the configured SEMANTIC_BASE_IRI with any trailing slash stripped.

    Falls back to the same default used by `hub/apps/semantic/services.py`
    so the unit tests for fallback behaviour stay green when settings are
    not overridden.
    """
    base = getattr(settings, "SEMANTIC_BASE_IRI", "https://hub.example.com")
    if not isinstance(base, str) or not base:
        # Defensive: settings.SEMANTIC_BASE_IRI is required to be a string;
        # fall through to the public-domain default rather than build a
        # garbage IRI that confuses downstream consumers.
        base = "https://hub.example.com"
    return base.rstrip("/")


def canonical_iri_for(resource_type: str, resource_id: str | UUID) -> str:
    """Build the canonical IRI for a resource.

    Args:
        resource_type: One of `SUPPORTED_RESOURCE_TYPES` (case-sensitive).
            Callers MUST normalise to lower-case before calling.
        resource_id: UUID or its string form. UUIDs are coerced to str to
            keep the IRI shape stable regardless of input type.

    Returns:
        IRI string `{SEMANTIC_BASE_IRI}/id/{resource_type}/{resource_id}`.

    Raises:
        ValueError: when `resource_type` is empty or `resource_id` is empty.
            Unknown but non-empty types are tolerated (forward-compat with
            new types added by callers ahead of this registry); the unit
            test still asserts every type in `SUPPORTED_RESOURCE_TYPES`
            produces a well-formed IRI.
    """
    if not resource_type:
        raise ValueError("canonical_iri_for: resource_type must be non-empty")
    rid = str(resource_id) if resource_id is not None else ""
    if not rid:
        raise ValueError("canonical_iri_for: resource_id must be non-empty")
    return f"{_resolve_base()}/id/{resource_type}/{rid}"


def canonical_iris_for_batch(resource_type: str, resource_ids: Iterable[str | UUID]) -> list[str]:
    """Vectorised counterpart to `canonical_iri_for`.

    Useful when a serializer has to emit IRIs for a list of nested ids
    (e.g. the contracts list on an asset detail). Reads the base IRI
    exactly once for the batch.
    """
    base = _resolve_base()
    out: list[str] = []
    for rid in resource_ids:
        rid_str = str(rid) if rid is not None else ""
        if not rid_str:
            raise ValueError("canonical_iris_for_batch: empty resource_id in batch")
        out.append(f"{base}/id/{resource_type}/{rid_str}")
    return out
