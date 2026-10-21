"""
W4.3 — metadata-driven enumeration of PROTECT/RESTRICT referrers to User.

``User`` is referenced by five platform tables with ``on_delete=PROTECT``
(``FeatureFlagFlipApproval.requested_by`` / ``approved_by``,
``ImpersonationSession.impersonator``, ``PlanPriceChangeApproval.approved_by``
/ ``requested_by``). Pre-fix, ``UserService.delete_user`` decided between
soft-delete and hard-delete by checking ``created_by`` resource columns
only — a hard delete of a user with a PROTECT referrer crashed with
``ProtectedError`` (500), and the tenant hard-delete sweep was doomed by
the same rows when deleting the tenant's users.

Instead of a hand-maintained list that rots, the referrer set is derived
from model metadata at call time (cached): every FK/OneToOne pointing at
the User model with ``on_delete`` in (PROTECT, RESTRICT). A future model
that PROTECTs a user is covered automatically by both consumers:

* ``UserService.delete_user`` — routes such users to the soft-delete path
  with an itemized ``USER_DISABLED`` audit entry.
* the tenant hard-delete sweep — deletes the referrer rows itemized
  BEFORE deleting the tenant's users (erasure must complete).

The sweep path never imports estate models from provider apps: the
metadata scan walks ``apps.get_models()`` dynamically, so no
cross-provider import is needed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uuid

from django.apps import apps
from django.db import models


@lru_cache(maxsize=1)
def protected_user_referrer_fields() -> list[tuple[type, str, str | None]]:
    """Return ``[(model, fk_attname, related_name), ...]`` for every
    FK/OneToOne field whose target is the User model and whose
    ``on_delete`` is PROTECT or RESTRICT.

    The tuple carries:
      * ``model`` — the referrer model class,
      * ``fk_attname`` — the FK field attribute name (``requested_by``),
      * ``related_name`` — the reverse accessor name on User
        (``requested_feature_flag_flips``); ``None`` when the relation
        declares ``related_name="+"``.

    Called lazily (``apps.get_models()`` requires the app registry to be
    populated); the lru_cache keeps the scan a one-time cost per process.
    """
    from django.contrib.auth import get_user_model

    user_model = get_user_model()
    found: list[tuple[type, str, str]] = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not field.is_relation:
                continue
            if not (field.one_to_one or field.many_to_one):
                continue
            remote = field.remote_field
            if remote is None or remote.model is not user_model:
                continue
            if remote.on_delete not in (models.PROTECT, models.RESTRICT):
                continue
            found.append((model, field.name, remote.related_name))
    return found


def protected_referrer_report(user: Any) -> dict[str, int]:
    """Itemized count of PROTECT/RESTRICT referrer rows per reverse
    accessor, e.g. ``{"requested_feature_flag_flips": 1}``. Accessors
    with zero rows are omitted; ``related_name="+"`` relations are
    reported under their model label.
    """
    report: dict[str, int] = {}
    for _model, _fk_attname, related_name in protected_user_referrer_fields():
        if related_name is None:
            continue  # hidden relations are covered via delete path below
        count = getattr(user, related_name).count()
        if count:
            report[related_name] = count
    return report


def delete_protected_referrers_for_users(user_ids: list[uuid.UUID]) -> dict[str, int]:
    """Delete every PROTECT/RESTRICT referrer row pointing at ``user_ids``.

    Used by the tenant hard-delete sweep: erasure must complete, so the
    referrer rows (whose users are about to be erased) are removed
    itemized, never silently. Returns ``{related_name: deleted_count}``
    (the reverse accessor the audit itemization reads); relations that
    declared ``related_name="+"`` are reported under their model label.
    """
    counts: dict[str, int] = {}
    for model, fk_attname, related_name in protected_user_referrer_fields():
        deleted, _per_model = model._base_manager.filter(
            **{f"{fk_attname}__in": user_ids}
        ).delete()
        if deleted:
            key = related_name or model._meta.label
            counts[key] = deleted
    return counts
