"""
Test fixture helpers for the Phase 231.2 / 250 compliance gate.

``Asset.can_activate()`` and the activation view both consult
``compliance_threshold_activation_blocker`` /
``latest_compliance_run_for_asset_activation``.  Activation is only
allowed when the asset has at least one ``ComplianceRun`` with:

* ``status = SUCCEEDED``
* ``allowed_to_store = True``
* ``risk_level`` not exceeding the tenant's
  ``compliance_risk_threshold`` (default ``HIGH``)

Two helpers are exposed:

* :func:`seed_succeeded_compliance_run` — explicit, opt-in fixture
  builder.  Tests with one-off needs (e.g. seeding ``risk_level``,
  ``allowed_to_store=False``) call this directly.
* :func:`install_test_mode_asset_compliance_autoseed` — session-level
  ``post_save`` signal that auto-creates a SUCCEEDED ComplianceRun
  whenever an Asset is **created** in tests AND the asset's own
  ``compliance_status`` is in ``{PASS, WARN}`` (the happy-path
  shape).  Skipped when the field is FAIL/UNKNOWN/None — those
  shapes are deliberately exercising the activation gate's negative
  paths.  Gated on ``settings.ENVIRONMENT == "test"``; never fires
  in production.

Both build real Job + ComplianceRun rows (no mocks/stubs).
"""
from __future__ import annotations
import uuid
from typing import Optional

from django.utils import timezone


def seed_succeeded_compliance_run(
    *,
    asset,
    tenant=None,
    user=None,
    risk_level: str = "LOW",
    allowed_to_store: bool = True,
):
    """Create a SUCCEEDED ComplianceRun anchored on ``asset``.

    Args:
        asset: ``Asset`` instance the run is for. Required.
        tenant: ``Tenant`` instance. Defaults to ``asset.tenant``.
        user: ``User`` instance to record as the Job creator. Optional.
        risk_level: One of ``RiskLevel.choices``. Default ``LOW``
            (passes the default ``HIGH`` tenant threshold).
        allowed_to_store: Storage-allowance flag. Default ``True`` so
            the activation view's secondary check at
            ``views.py:2043-2055`` also passes.

    Returns:
        The created :class:`ComplianceRun`.
    """
    from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
    from hub.apps.jobs.models import Job, JobStatus, JobType

    effective_tenant = tenant if tenant is not None else asset.tenant
    job = Job.objects.create(
        tenant=effective_tenant,
        type=JobType.COMPLIANCE_RUN,
        status=JobStatus.COMPLETED,
        resource_type="COMPLIANCE_RUN",
        resource_id=uuid.uuid4(),
        created_by=user,
        details_json={"scan_mode": "internal"},
        timeout_seconds=300,
    )
    return ComplianceRun.objects.create(
        tenant=effective_tenant,
        asset=asset,
        job=job,
        status=ComplianceRunStatus.SUCCEEDED,
        risk_level=risk_level,
        allowed_to_store=allowed_to_store,
        completed_at=timezone.now(),
    )


# Use a sentinel attribute on the asset to disable the auto-seed for a
# specific test (e.g. tests that exercise the gate's negative paths
# need to assert the blocker fires when no run exists). Setting
# ``asset._skip_test_compliance_autoseed = True`` before save bypasses
# the signal.
_AUTOSEED_SKIP_ATTR = "_skip_test_compliance_autoseed"


def _asset_post_save_autoseed(sender, instance, created, raw, **_kwargs):
    # Fire on both create AND update so a test that builds the asset
    # via ``client.post`` (default ``compliance_status=UNKNOWN``) and
    # later flips it to ``PASS`` via ``asset.save()`` triggers the
    # auto-seed at that point.  The ``ComplianceRun.objects.filter
    # (asset_id=...).exists()`` guard below prevents duplicates.
    _ = created  # signal-contract kw, kept for clarity
    if raw:
        return
    from django.conf import settings as _settings

    if getattr(_settings, "ENVIRONMENT", "").lower() != "test":
        return
    if getattr(instance, _AUTOSEED_SKIP_ATTR, False):
        return
    # Only auto-seed for assets whose ``compliance_status`` carries
    # an explicit happy-path value (``PASS`` / ``WARN``).  ``UNKNOWN``
    # is the model default and is also the natural state for tests
    # that build their OWN ComplianceRun later (e.g. one with
    # ``allowed_to_store=False`` exercising the denial path); auto-
    # seeding for UNKNOWN would race the test's run for "latest" and
    # yield false 200s where the test expects 403.  Tests that want
    # the auto-seed pass ``compliance_status=ComplianceStatus.PASS``
    # in their fixture explicitly.  Fire on both create and update
    # because tests sometimes create the asset via ``client.post``
    # (default UNKNOWN) then later flip ``compliance_status=PASS``
    # via ``asset.save()`` to indicate the happy-path intent.
    happy_states = {"PASS", "WARN"}
    if str(getattr(instance, "compliance_status", "")) not in happy_states:
        return
    if getattr(instance, "tenant_id", None) is None:
        return
    # Avoid recursion / re-creation if a run already exists.
    from hub.apps.compliance.models import ComplianceRun

    if ComplianceRun.objects.filter(asset_id=instance.pk).exists():
        return
    try:
        seed_succeeded_compliance_run(asset=instance)
    except Exception:
        # Auto-seed is a test convenience — a failure (e.g. missing
        # Job FK metadata) must not block the asset save itself.  The
        # explicit ``seed_succeeded_compliance_run`` helper still
        # surfaces real errors when called directly.
        pass


def _contract_post_save_autoseed(sender, instance, created, raw, **_kwargs):
    """Auto-seed a ComplianceRun for the asset of a freshly-created
    ACTIVE+VALID+NORMALIZED_OK Contract.  The combination signals a
    happy-path "ready-to-activate" fixture even when the asset still
    carries the default ``compliance_status=UNKNOWN`` (typical when
    the asset was created via ``client.post('/api/v1/assets/')``).
    Tests that exercise the gate's denial path either skip the
    contract attach OR build their own ComplianceRun before calling
    activate; the existing-run guard below prevents duplicates.
    """
    # Fire on both create AND update so a test that creates an
    # INVALID contract and later flips ``validation_status=VALID``
    # via ``contract.save()`` triggers the auto-seed at that point.
    # The existing-run guard prevents duplicates.
    _ = created  # signal-contract kw
    if raw:
        return
    from django.conf import settings as _settings

    if getattr(_settings, "ENVIRONMENT", "").lower() != "test":
        return
    if getattr(instance, "asset_id", None) is None:
        return
    if str(getattr(instance, "status", "")) != "ACTIVE":
        return
    if str(getattr(instance, "validation_status", "")) not in ("VALID", "WARNING_ONLY"):
        return
    if str(getattr(instance, "normalization_status", "")) not in ("NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"):
        return
    from hub.apps.assets.models import Asset
    from hub.apps.compliance.models import ComplianceRun

    if ComplianceRun.objects.filter(asset_id=instance.asset_id).exists():
        return
    try:
        asset = Asset.objects.get(pk=instance.asset_id)
    except Asset.DoesNotExist:
        return
    if getattr(asset, _AUTOSEED_SKIP_ATTR, False):
        return
    try:
        seed_succeeded_compliance_run(asset=asset)
    except Exception:
        pass


def install_test_mode_asset_compliance_autoseed() -> None:
    """Idempotently connect the auto-seed signals."""
    from django.db.models.signals import post_save
    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract

    post_save.connect(
        _asset_post_save_autoseed,
        sender=Asset,
        dispatch_uid="testing_asset_compliance_autoseed",
    )
    post_save.connect(
        _contract_post_save_autoseed,
        sender=Contract,
        dispatch_uid="testing_contract_compliance_autoseed",
    )
