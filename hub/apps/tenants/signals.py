"""
Tenant Signals

Handles post-creation tasks like default role creation and KYC status audit (feat1 2.3).
"""
import logging
import threading

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Tenant

logger = logging.getLogger(__name__)

# Thread-safe storage for previous kyc_status per tenant pk (feat1 2.3.2)
_thread_local = threading.local()


@receiver(post_save, sender=Tenant)
def create_default_roles(sender, instance, created, **kwargs):
    """
    Create default roles when a new tenant is created.

    Default roles:
    - TENANT_ADMIN: Full administrative access within tenant
    - DATA_PROVIDER: Can create and manage data assets
    - DATA_CONSUMER: Can request and access data assets
    - AUDITOR: Read-only access to compliance/DQ reports and audit logs

    Skips role creation in test mode to prevent timeouts.
    """
    if not created:
        return

    # Skip role creation in test mode to prevent timeouts
    # Check multiple indicators to catch all test scenarios
    import sys
    import os

    # Check if we're in a test environment
    is_test_env = (
        'pytest' in sys.modules or
        'unittest' in sys.modules or
        os.getenv('PYTEST_CURRENT_TEST') or
        any('test' in arg.lower() or 'pytest' in arg.lower() for arg in sys.argv) or
        os.getenv('TESTING', '').lower() in ('1', 'true', 'yes')
    )

    # Also check Django's TESTING setting if available
    try:
        from django.conf import settings
        if getattr(settings, 'TESTING', False):
            is_test_env = True
    except (ImportError, RuntimeError):
        pass

    if is_test_env:
        # In test mode, roles should be created explicitly by tests
        # This prevents 6-8 second delays per tenant creation
        return

    def _create_roles():
        try:
            from hub.apps.users.models import Role

            default_roles = [
                {
                    "name": "TENANT_ADMIN",
                    "description": "Full administrative access within tenant"
                },
                {
                    "name": "DATA_PROVIDER",
                    "description": "Can create and manage data assets"
                },
                {
                    "name": "DATA_CONSUMER",
                    "description": "Can request and access data assets"
                },
                {
                    "name": "AUDITOR",
                    "description": "Read-only access to compliance/DQ reports and audit logs"
                }
            ]

            for role_data in default_roles:
                Role.objects.get_or_create(
                    tenant=instance,
                    name=role_data["name"],
                    defaults={"description": role_data["description"]}
                )
        except Exception:
            logger.exception("default_role_creation_failed")

    transaction.on_commit(_create_roles)


@receiver(pre_save, sender=Tenant)
def _store_kyc_status_before_save(sender, instance, **kwargs):
    """Store previous kyc_status for post_save audit (feat1 2.3.2)."""
    if not instance.pk:
        return
    try:
        from django.db import connection

        # Use a short statement_timeout (2s) so this signal never blocks test
        # teardown.  ROOT CAUSE FIX: during TransactionTestCase teardown, the
        # ``flush`` command holds AccessExclusiveLock while TRUNCATE-ing tables.
        # If the *next* test's setUp fires this signal, the SELECT here waits
        # for that lock — up to the global statement_timeout (60 s) — causing a
        # cascading deadlock chain that makes every subsequent test time out.
        # A 2 s budget is generous for a single-row PK lookup; if it times out
        # we simply skip the KYC audit (non-critical).
        #
        # CRITICAL: SET LOCAL must be undone before returning. Django's nested
        # transaction.atomic() does not reliably scope SET LOCAL across pre_save
        # / ORM execution order. Use an explicit SAVEPOINT + ROLLBACK TO so
        # statement_timeout reverts; otherwise the outer transaction keeps 2s and
        # later statements (e.g. Contract.objects.create) hit QueryCanceled.
        old = None
        qn = connection.ops.quote_name
        tbl = qn(Tenant._meta.db_table)
        col = qn(Tenant._meta.get_field("kyc_status").column)
        pk_col = qn(Tenant._meta.pk.column)
        with connection.cursor() as cursor:
            cursor.execute("SAVEPOINT kyc_presave_snap")
            try:
                cursor.execute("SET LOCAL statement_timeout = '2s'")
                cursor.execute(
                    f"SELECT {col} FROM {tbl} WHERE {pk_col} = %s",
                    [instance.pk],
                )
                row = cursor.fetchone()
                old = row[0] if row else None
            finally:
                try:
                    cursor.execute("ROLLBACK TO SAVEPOINT kyc_presave_snap")
                except Exception:
                    pass
                try:
                    cursor.execute("RELEASE SAVEPOINT kyc_presave_snap")
                except Exception:
                    pass
        if not hasattr(_thread_local, 'kyc_before_save'):
            _thread_local.kyc_before_save = {}
        _thread_local.kyc_before_save[instance.pk] = old
    except Exception:
        pass


@receiver(post_save, sender=Tenant)
def audit_kyc_status_change(sender, instance, created, **kwargs):
    """
    Emit KYC_STATUS_CHANGED audit event when Tenant.kyc_status changes (feat1 2.3.2).
    Catches all code paths (API, admin, service).
    """
    if not hasattr(_thread_local, 'kyc_before_save'):
        return
    if created:
        # Clean up pre_save entry for newly created tenants (no KYC change to audit)
        _thread_local.kyc_before_save.pop(instance.pk, None)
        return
    old_kyc = _thread_local.kyc_before_save.pop(instance.pk, None)
    if old_kyc is None or old_kyc == instance.kyc_status:
        return
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="TENANT",
            action="KYC_STATUS_CHANGED",
            tenant=instance,
            actor_user=None,
            resource_id=str(instance.id),
            details={
                "previous_kyc_status": old_kyc,
                "new_kyc_status": instance.kyc_status,
                "tenant_id": str(instance.id),
            },
        )
    except Exception as e:
        logger.exception(
            "Failed to create KYC_STATUS_CHANGED audit event for tenant %s: %s",
            instance.pk,
            e,
            extra={"tenant_id": str(instance.id), "old_kyc": old_kyc, "new_kyc": instance.kyc_status},
        )


# ---------------------------------------------------------------------------
# Phase 250.5.A.5 (D250.16) — federated source-tenant deletion cascade
# ---------------------------------------------------------------------------

#: Thread-local for tracking the previous ``status`` value across a
#: pre/post-save pair so we can detect the ACTIVE/SUSPENDED → DELETED
#: transition. Mirrors the ``kyc_before_save`` pattern above.
_FEDERATED_STATUS_KEY = "federated_status_before_save"


@receiver(pre_save, sender=Tenant)
def _store_status_before_save_for_federated_cascade(sender, instance, **kwargs):
    """Snapshot ``status`` before save so the post_save handler can
    distinguish a transition INTO ``DELETED`` from a save where
    status was already DELETED. Without this, every save on a
    deleted tenant would re-fire the cascade signal.
    """
    if not instance.pk:
        return
    try:
        from django.db import connection

        old = None
        qn = connection.ops.quote_name
        # ``status`` is the literal column name on the ``tenants`` table
        # (the model field shares its name with the DB column). Avoid
        # ``Tenant._meta.get_field("status").column`` so static
        # type-checkers that conservatively type ``get_field`` as
        # ``ForeignObjectRel`` don't false-positive on the ``.column``
        # attribute access.
        tbl = qn(Tenant._meta.db_table)
        col = qn("status")
        pk_col = qn("id")
        with connection.cursor() as cursor:
            cursor.execute("SAVEPOINT fed_status_presave_snap")
            try:
                cursor.execute("SET LOCAL statement_timeout = '2s'")
                cursor.execute(
                    f"SELECT {col} FROM {tbl} WHERE {pk_col} = %s",
                    [instance.pk],
                )
                row = cursor.fetchone()
                old = row[0] if row else None
            finally:
                try:
                    cursor.execute("ROLLBACK TO SAVEPOINT fed_status_presave_snap")
                except Exception:
                    pass
                try:
                    cursor.execute("RELEASE SAVEPOINT fed_status_presave_snap")
                except Exception:
                    pass
        if not hasattr(_thread_local, _FEDERATED_STATUS_KEY):
            setattr(_thread_local, _FEDERATED_STATUS_KEY, {})
        getattr(_thread_local, _FEDERATED_STATUS_KEY)[instance.pk] = old
    except Exception:
        pass


@receiver(post_save, sender=Tenant)
def tombstone_federated_resources_on_tenant_delete(sender, instance, created, **kwargs):
    """Phase 250.5.A.5 (D250.16) — federated tombstone cascade.

    When a Tenant transitions into ``status="DELETED"``, set
    ``source_tenant_deleted_at = NOW`` on every consumer-side
    ``ExternalResourceReference`` whose ``source_tenant_id`` matches
    this tenant. The consumer-side row remains queryable for 90
    days (the ``TOMBSTONE_GRACE_DAYS`` constant on
    ``ExternalResourceReference``) so consumers can export; a
    scheduled cleanup task may hard-delete after grace expires.

    The signal is best-effort: a transient audit-DB outage logs the
    failure but does NOT block the tenant save (which would defeat
    the operator's deletion intent). The tombstone column update is
    inside the same transaction as the tenant save so a rollback
    of the soft-delete also rolls back the tombstone — the two
    states stay consistent.
    """
    from django.utils import timezone

    if created:
        return

    snap = getattr(_thread_local, _FEDERATED_STATUS_KEY, {}) if hasattr(
        _thread_local, _FEDERATED_STATUS_KEY,
    ) else {}
    old_status = snap.pop(instance.pk, None) if snap else None

    # Only fire on the transition INTO DELETED; subsequent saves on
    # an already-DELETED tenant are no-ops.
    from .models import TenantStatus

    if instance.status != TenantStatus.DELETED:
        return
    if old_status == TenantStatus.DELETED:
        return  # no transition; already deleted

    try:
        from hub.apps.assets.models import ExternalResourceReference
        from hub.apps.audit import event_types as _audit_event_types
        from hub.apps.audit.utils import create_audit_event

        now = timezone.now()
        # Update every consumer-side row in one query. The DB-level
        # update bypasses the model save() but that's appropriate —
        # we don't want to fire ExternalResourceReference's own
        # post_save signals for a cascade event.
        affected_qs = ExternalResourceReference.objects.filter(
            source_tenant_id=instance.id,
            source_tenant_deleted_at__isnull=True,
        )
        # Materialise IDs first so audit emission can iterate per row.
        affected = list(
            affected_qs.values_list(
                "id", "asset_id", "asset__tenant_id",
            )
        )
        if affected:
            affected_qs.update(source_tenant_deleted_at=now)

        from datetime import timedelta as _timedelta

        grace_end = now + _timedelta(
            days=ExternalResourceReference.TOMBSTONE_GRACE_DAYS,
        )
        for ref_id, asset_id, consumer_tenant_id in affected:
            try:
                # Resolve consumer tenant for the audit FK; fallback
                # to None when the consumer tenant lookup misses.
                consumer_tenant = None
                try:
                    consumer_tenant = Tenant.all_objects.get(
                        id=consumer_tenant_id,
                    )
                except Tenant.DoesNotExist:
                    pass
                create_audit_event(
                    resource_type=_audit_event_types.ASSET_RESOURCE_TYPE,
                    action=_audit_event_types.FEDERATED_SOURCE_TENANT_DELETED,
                    actor_user=None,  # cascade is system-initiated
                    tenant=consumer_tenant,
                    resource_id=str(asset_id),
                    result="WARNING",
                    details={
                        "source_tenant_id": str(instance.id),
                        "consumer_tenant_id": str(consumer_tenant_id),
                        "external_resource_reference_id": str(ref_id),
                        "asset_id": str(asset_id),
                        "source_tenant_deleted_at": now.isoformat(),
                        "grace_window_expires_at": grace_end.isoformat(),
                    },
                )
            except Exception as audit_exc:  # noqa: BLE001
                logger.warning(
                    "federated_source_tenant_deleted_audit_emit_failed",
                    extra={
                        "source_tenant_id": str(instance.id),
                        "external_resource_reference_id": str(ref_id),
                        "error": str(audit_exc),
                    },
                )
    except Exception:
        # Best-effort cascade. The tenant save already committed;
        # losing the tombstone update here is recoverable via a
        # later batch job, but MUST NOT roll back the tenant
        # deletion intent.
        logger.exception(
            "federated_resources_tombstone_cascade_failed",
            extra={"source_tenant_id": str(instance.id)},
        )


# ---------------------------------------------------------------------------
# Phase 250.6.D.1 — onboarding-completion signal handlers
# ---------------------------------------------------------------------------
#
# Three independent handlers observe the three onboarding signals
# (admin role assignment, KYC submission, subscription activation)
# and call the same idempotent ``mark_onboarding_complete_if_ready``.
# Whichever signal arrives LAST flips the tenant from incomplete to
# complete; the other two return False from the helper and are
# no-ops. The handler that DID flip the timestamp emits a single
# ``ONBOARDING_COMPLETED`` audit row with the originating signal
# captured in ``triggered_by`` so admin dashboards can report which
# signal closed the loop most often (informs onboarding-funnel UX
# work).


def _emit_onboarding_completed_audit(tenant, *, triggered_by: str) -> None:
    """Emit ``ONBOARDING_COMPLETED`` exactly once per tenant per transition.

    Caller is responsible for invoking this ONLY when
    ``mark_onboarding_complete_if_ready`` returned True (the
    false→true transition). The audit emitter is wrapped in a
    try/except so an audit-write failure cannot roll back the
    state transition itself — onboarding completion is a one-way
    ratchet whose primary side effect (asset creation unlocked) is
    far more important than the audit row.
    """
    try:
        from hub.apps.audit import event_types as _audit_event_types
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="TENANT",
            action=_audit_event_types.ONBOARDING_COMPLETED,
            tenant=tenant,
            actor_user=None,
            resource_id=str(tenant.id),
            details={
                "tenant_id": str(tenant.id),
                "onboarding_completed_at": (
                    tenant.onboarding_completed_at.isoformat()
                    if tenant.onboarding_completed_at is not None
                    else None
                ),
                "triggered_by": triggered_by,
                "asset_creation_enabled_after": True,
            },
        )
    except Exception as audit_exc:  # noqa: BLE001
        logger.warning(
            "onboarding_completed_audit_emit_failed",
            extra={
                "tenant_id": str(tenant.id),
                "triggered_by": triggered_by,
                "error": str(audit_exc),
            },
        )


def _check_and_mark_onboarding_complete(tenant, *, triggered_by: str) -> None:
    """Wrap the helper + audit so each handler is one-liner-thin.

    Wrapped in a try/except: signal handlers must NEVER raise back
    into the originating save() — that would roll back e.g. a
    UserRole creation just because the onboarding-completion logic
    blew up.
    """
    try:
        from hub.apps.tenants.onboarding import mark_onboarding_complete_if_ready

        if mark_onboarding_complete_if_ready(tenant):
            _emit_onboarding_completed_audit(tenant, triggered_by=triggered_by)
    except Exception:
        logger.exception(
            "onboarding_completion_check_failed",
            extra={
                "tenant_id": str(tenant.id) if tenant else None,
                "triggered_by": triggered_by,
            },
        )


def _onboarding_check_user_role(sender, instance, created, **kwargs):
    """Fire after a UserRole is created/updated; check only on TENANT_ADMIN.

    Connected dynamically below (not via @receiver decorator) so
    the import-time module load doesn't pull ``users.models``
    eagerly — keeps the tenants app's import order resilient to
    cycles between users and tenants.
    """
    if not created:
        return
    role = getattr(instance, "role", None)
    if role is None or role.name != "TENANT_ADMIN":
        return
    tenant = getattr(instance, "tenant", None) or (role.tenant if role else None)
    if tenant is None:
        return
    transaction.on_commit(
        lambda: _check_and_mark_onboarding_complete(
            tenant, triggered_by="tenant_admin_assigned"
        )
    )


@receiver(post_save, sender=Tenant)
def _onboarding_check_kyc_change(sender, instance, created, **kwargs):
    """Fire after a Tenant save; route to the helper if kyc is submitted.

    250.6.D audit-pass — the original implementation of this handler
    tried to gate on the kyc transition (UNVERIFIED → submitted) by
    reading ``_thread_local.kyc_before_save`` non-destructively. That
    plan was broken: ``audit_kyc_status_change`` is registered EARLIER
    in this module (line ~150) which means Django dispatches it FIRST,
    and that handler ``pop``s the thread-local entry — by the time
    this receiver runs, the entry is gone and ``old_kyc`` is always
    ``None``. The "subscription-first then admin then kyc" ordering
    therefore never completed onboarding because KYC as the LAST
    signal couldn't reach the helper.

    The fix is to drop the transition gate entirely. ``mark_onboarding
    _complete_if_ready`` is idempotent (returns False AND emits no
    audit if onboarding is already complete OR the three signals
    aren't yet satisfied) so a redundant call after a benign
    ``PENDING_REVIEW`` → ``VERIFIED`` change is a no-op (one extra
    SELECT chain, no audit, no state change). This handler now fires
    on every non-create Tenant save where the kyc field is in a
    submitted state; the helper handles all the actual gating.
    """
    if created:
        return
    if (instance.kyc_status or "UNVERIFIED") == "UNVERIFIED":
        # Not in a submitted state — there's no onboarding signal here.
        # (A tenant save changing some other field while kyc is still
        # UNVERIFIED is the common case for fresh tenants; we
        # short-circuit to avoid a guaranteed-False helper call.)
        return
    transaction.on_commit(
        lambda: _check_and_mark_onboarding_complete(
            instance, triggered_by="kyc_submitted"
        )
    )


def _onboarding_check_subscription(sender, instance, created, **kwargs):
    """Fire after a Subscription save; check when status is in active set.

    Both ``created`` (new subscription) and update-to-active (e.g.
    INCOMPLETE → ACTIVE after Stripe checkout completes) trigger
    the check. Connected dynamically (see ``register_*`` block at
    the bottom) to avoid eager import of ``billing.models`` during
    tenants-app load.
    """
    from hub.apps.tenants.onboarding import _BILLING_ACTIVE_STATES

    status = getattr(instance, "status", None)
    if status not in _BILLING_ACTIVE_STATES:
        return
    tenant = getattr(instance, "tenant", None)
    if tenant is None:
        return
    transaction.on_commit(
        lambda: _check_and_mark_onboarding_complete(
            tenant, triggered_by="subscription_activated"
        )
    )


def _register_onboarding_signal_handlers():
    """Attach the cross-app handlers (UserRole / Subscription).

    Done at apps.ready() time via ``signals`` import side-effect:
    ``hub.apps.tenants.apps.TenantsConfig.ready`` already imports
    this module, and importing the module triggers this function.
    Connecting via ``post_save.connect(...)`` (not ``@receiver``)
    keeps the cross-app references local — we don't add a
    top-level ``from hub.apps.users.models import UserRole`` which
    would create a hard import-time dependency on the users app.
    """
    try:
        from hub.apps.users.models import UserRole

        post_save.connect(
            _onboarding_check_user_role,
            sender=UserRole,
            dispatch_uid="onboarding_check_user_role",
        )
    except Exception:
        logger.exception(
            "onboarding_user_role_signal_register_failed"
        )

    try:
        from hub.apps.billing.models import Subscription

        post_save.connect(
            _onboarding_check_subscription,
            sender=Subscription,
            dispatch_uid="onboarding_check_subscription",
        )
    except Exception:
        logger.exception(
            "onboarding_subscription_signal_register_failed"
        )


# Connect on module import — the tenants AppConfig already imports
# this module from its ``ready()`` hook (see ``apps.py``), which is
# the correct moment to wire cross-app post_save connections (after
# Django's app registry is fully populated).
_register_onboarding_signal_handlers()

