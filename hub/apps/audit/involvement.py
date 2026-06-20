"""
Phase 225.3.2 — "user is directly involved in a resource" predicate.

A user is considered involved with a resource when **any** of the following
holds:

1. They are an administrator (``is_platform_admin`` flag, the named
   ``PLATFORM_ADMIN``/``TENANT_ADMIN``/``AUDITOR`` roles) — admins always
   bypass the involvement filter by policy.
2. They were the ``actor_user`` on at least one :class:`AuditEvent` for
   that ``(resource_type, resource_id)`` pair — i.e. the audit trail
   already records their participation.
3. They are the *owner* of the underlying resource, evaluated by a
   small per-resource-type registry below (``Asset.created_by``,
   ``Contract.created_by``, etc.). The registry stays narrow on purpose:
   each entry is a single indexed lookup, and unknown resource types fall
   back to the actor check alone.

Returns a boolean — callers decide whether to 403 or return an empty list.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Union

from django.db.models import Q

from hub.apps.audit.models import AuditEvent

# ``get_request_tenant_id`` returns a string (header value) while some
# callers pass a parsed UUID — accept both. Django's ORM normalises either.
TenantId = Union[str, uuid.UUID]

# Admins who should always bypass the involvement filter. Must stay in
# lockstep with ``AUDIT_READ_ROLES`` in ``hub.apps.audit.views`` — separated
# here to avoid an import cycle when ``views`` reaches back into this module.
ADMIN_ROLE_NAMES = frozenset({"TENANT_ADMIN", "AUDITOR", "PLATFORM_ADMIN"})


def _user_has_admin_role(user) -> bool:
    if getattr(user, "is_platform_admin", False):
        return True
    has_role = getattr(user, "has_role", None)
    if callable(has_role):
        return bool(has_role(*ADMIN_ROLE_NAMES))
    return False


# ---------------------------------------------------------------------------
# Resource ownership registry
# ---------------------------------------------------------------------------
#
# Each resolver receives the parsed ``uuid.UUID`` resource_id and the user,
# and returns True iff the user is the direct owner of that resource. We
# import models lazily (inside the resolver) because ``audit`` loads early
# during Django's app registry initialisation and pulling in asset /
# contract models at module import time risks ordering issues.


def _asset_owner(resource_id: uuid.UUID, user) -> bool:
    from hub.apps.assets.models import Asset

    return Asset.objects.filter(id=resource_id, created_by_id=user.id).exists()


def _contract_owner(resource_id: uuid.UUID, user) -> bool:
    from hub.apps.contracts.models import Contract

    return Contract.objects.filter(id=resource_id, created_by_id=user.id).exists()


def _order_owner(resource_id: uuid.UUID, user) -> bool:
    from hub.apps.marketplace.models import Order

    return Order.objects.filter(id=resource_id, created_by_id=user.id).exists()


def _access_request_owner(resource_id: uuid.UUID, user) -> bool:
    from hub.apps.governance.models import AccessRequest

    return AccessRequest.objects.filter(id=resource_id, requested_by_id=user.id).exists()


#: resource_type → callable(uuid, user) → bool.
#: Resource types absent here still work — they fall back to the actor-only
#: branch of ``user_is_involved``. Add new entries sparingly: each resolver
#: runs an extra indexed query per request.
OWNERSHIP_RESOLVERS: dict[str, Callable[[uuid.UUID, object], bool]] = {
    "ASSET": _asset_owner,
    "CONTRACT": _contract_owner,
    "ORDER": _order_owner,
    "ACCESS_REQUEST": _access_request_owner,
}


def user_is_involved(
    user,
    *,
    resource_type: str,
    resource_id: uuid.UUID,
    tenant_id: TenantId | None = None,
) -> bool:
    """Return True if *user* is involved with the given resource."""
    if _user_has_admin_role(user):
        return True

    # Actor branch: the user's participation is recorded on the audit trail.
    actor_qs = AuditEvent.objects.filter(
        resource_type=resource_type,
        resource_id=resource_id,
        actor_user_id=user.id,
    )
    if tenant_id is not None:
        actor_qs = actor_qs.filter(Q(tenant_id=tenant_id) | Q(tenant__isnull=True))
    if actor_qs.exists():
        return True

    # Ownership branch: consult the resource-type registry.
    resolver = OWNERSHIP_RESOLVERS.get(resource_type)
    if resolver is None:
        return False
    try:
        return bool(resolver(resource_id, user))
    except Exception:
        # A resource type we registered but the model layer threw on —
        # treat as "not involved" rather than 500. Misconfiguration here
        # should never leak data.
        return False
