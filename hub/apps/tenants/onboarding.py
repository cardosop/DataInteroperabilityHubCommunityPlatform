"""
Phase 250.6.D — Tenant onboarding-completion tracking.

Pure helpers that evaluate the three signals which together
release the per-tenant ``asset_creation_enabled`` kill switch
(landed in 250.6.A) for a freshly-onboarded tenant:

  1. Tenant admin invited — at least one ``UserRole`` row exists
     where ``role.name == "TENANT_ADMIN"`` and ``role.tenant ==
     tenant``. The TENANT_ADMIN role is the canonical "you can
     administer this tenant" grant; without it nobody can flip
     other tenant flags either.

  2. KYC submitted — ``Tenant.kyc_status`` is anything OTHER
     than ``UNVERIFIED``. PENDING_REVIEW (provider hasn't yet
     finished verification) and VERIFIED both count: from the
     onboarding-flow perspective the user TOOK THE STEP, which
     is the gate this signal pins. Production
     ``can_publish_to_marketplace`` still requires VERIFIED, so
     a tenant with PENDING_REVIEW can create + draft assets but
     cannot publish.

  3. Billing setup — at least one ``Subscription`` row exists
     in a status that represents a real billing relationship:
     ``ACTIVE`` (paid plan), ``TRIAL`` (paid plan in trial
     window — Stripe will charge at trial end), or ``PAST_DUE``
     (paid plan with retry-in-progress). ``CANCELED`` /
     ``UNPAID`` / ``INCOMPLETE`` / ``INCOMPLETE_EXPIRED`` do NOT
     count: they represent broken-or-no billing, and the whole
     point of the onboarding gate is to refuse asset creation
     until billing is wired.

The helpers are pure (no caching, no side-effects on
``evaluate_*`` / ``compute_*``) and stateless. The single
side-effecting helper ``mark_onboarding_complete_if_ready``
sets the timestamp + flips ``asset_creation_enabled`` to True
under a transactional savepoint, returning True iff a state
transition occurred so signal-handler callers know whether to
emit the ``ONBOARDING_COMPLETED`` audit event.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

if TYPE_CHECKING:  # pragma: no cover — type-only import to dodge cycles
    from hub.apps.tenants.models import Tenant


_BILLING_ACTIVE_STATES = frozenset(
    {
        "ACTIVE",
        "TRIAL",
        "PAST_DUE",
    }
)
"""Subscription statuses that count as "billing setup complete".

Mirror of ``hub.apps.billing.models.SubscriptionStatus`` value
strings — kept as a frozen set of strings (not the enum) so this
module stays import-cycle-safe and can be evaluated from a
data-migration's frozen-state ORM (where the enum class shape
isn't guaranteed to match the live code).
"""


def _has_tenant_admin(tenant: "Tenant") -> bool:
    """True iff at least one user holds the ``TENANT_ADMIN`` role on this tenant."""
    from hub.apps.users.models import UserRole

    return UserRole.objects.filter(
        tenant=tenant, role__name="TENANT_ADMIN"
    ).exists()


def _has_kyc_submitted(tenant: "Tenant") -> bool:
    """True iff KYC has been submitted (PENDING_REVIEW or VERIFIED)."""
    # Defensive: tenants table allows a string-typed kyc_status, so
    # the safe predicate is "anything other than UNVERIFIED" rather
    # than a positive enum match. This lets us accept future values
    # like REJECTED (if we add one) WITHOUT changing the gate.
    return (tenant.kyc_status or "UNVERIFIED") != "UNVERIFIED"


def _has_billing_setup(tenant: "Tenant") -> bool:
    """True iff a Subscription exists in an active billing state."""
    from hub.apps.billing.models import Subscription

    return Subscription.objects.filter(
        tenant=tenant, status__in=_BILLING_ACTIVE_STATES
    ).exists()


def evaluate_onboarding_completion(tenant: "Tenant") -> bool:
    """Return True iff all three onboarding signals are satisfied.

    Pure: no caching, no DB writes, no side effects. Safe to call
    from a request hot-path; callers that only need the boolean
    answer (e.g. capability response) should prefer this over
    ``compute_onboarding_state`` (which runs the same queries
    and packs the per-signal breakdown — slightly more work).
    """
    if not _has_tenant_admin(tenant):
        return False
    if not _has_kyc_submitted(tenant):
        return False
    if not _has_billing_setup(tenant):
        return False
    return True


def compute_onboarding_state(tenant: "Tenant") -> dict:
    """Return the per-signal breakdown of onboarding state.

    Diagnostic helper. Used by the SPA to render an onboarding
    checklist (admin invited ✓ / KYC submitted ✗ / billing setup ✗)
    and by debugging/admin tooling. Pure — no writes.
    """
    admin = _has_tenant_admin(tenant)
    kyc = _has_kyc_submitted(tenant)
    billing = _has_billing_setup(tenant)
    return {
        "tenant_admin_invited": admin,
        "kyc_submitted": kyc,
        "billing_setup": billing,
        "all_complete": admin and kyc and billing,
    }


def mark_onboarding_complete_if_ready(tenant: "Tenant") -> bool:
    """Set ``onboarding_completed_at`` + release the kill switch when ready.

    Idempotent: if the timestamp is already set, returns False
    without writing. If signals aren't yet satisfied, returns
    False without writing. ONLY when the false→true transition
    actually happens does this return True (so signal-handler
    callers know whether to emit the ``ONBOARDING_COMPLETED``
    audit event — emitting on every signal-fire would flood the
    audit log).

    Side effects on the false→true transition:
      * ``onboarding_completed_at`` ← ``timezone.now()``
      * ``asset_creation_enabled`` ← True (releases the kill switch
        for tenants that started gated; existing tenants already
        have the flag at True so this is a no-op for them).

    Wraps the write in ``transaction.atomic()`` so the timestamp
    + flag flip land together OR not at all. The caller is
    expected to invoke this from inside a
    ``transaction.on_commit`` block (signal-handler convention)
    so the write is observed by other listeners only after the
    triggering transaction commits.
    """
    # Re-read from the DB inside the transaction so we don't race
    # against another worker that just set the timestamp. The cost
    # is one extra SELECT vs. trusting the in-memory instance —
    # cheap insurance against double-completion.
    with transaction.atomic():
        from hub.apps.tenants.models import Tenant as _TenantModel

        # ``select_for_update`` would lock the row; we don't need
        # that strength because the field is one-way ratchet (NULL →
        # timestamp; never reverses). Two concurrent transactions
        # racing to set it would BOTH compute "ready" → BOTH try to
        # write; the second wins via "last-write" semantics, but
        # since both writes set the SAME logical state (timestamp
        # set, flag True), the race is benign. The extra SELECT just
        # avoids re-emitting the audit event when the row is already
        # complete.
        fresh = (
            _TenantModel.objects.filter(pk=tenant.pk)
            .only("id", "onboarding_completed_at")
            .first()
        )
        if fresh is None:
            return False
        if fresh.onboarding_completed_at is not None:
            # Already complete; nothing to do, no audit emission.
            return False

        if not evaluate_onboarding_completion(tenant):
            return False

        now = timezone.now()
        # Use ``update`` to write only the two fields; this avoids
        # firing pre_save / post_save handlers that listen for a
        # broader Tenant change (e.g. KYC audit) — the
        # ONBOARDING_COMPLETED audit event is the source of truth
        # for this transition, emitted by the caller.
        _TenantModel.objects.filter(pk=tenant.pk).update(
            onboarding_completed_at=now,
            asset_creation_enabled=True,
        )

        # Reflect the change on the in-memory instance so the
        # caller (a signal handler usually) can pass it to the
        # audit emitter without an extra refresh_from_db round
        # trip.
        tenant.onboarding_completed_at = now
        tenant.asset_creation_enabled = True
        return True


__all__ = [
    "evaluate_onboarding_completion",
    "compute_onboarding_state",
    "mark_onboarding_complete_if_ready",
]
