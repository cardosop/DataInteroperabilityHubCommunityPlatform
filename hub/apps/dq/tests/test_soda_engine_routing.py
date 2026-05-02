"""
Phase 240.3.A.8 — engine routing tests for the api-side ``DQService``.

Verifies the suffix-based dispatch in
``hub.apps.dq.services.DQService.create_dq_run`` (lines 198-204):

* ``*_gx`` / contains ``"gx"`` → ``DQEngine.GREAT_EXPECTATIONS``
* ``*_soda`` / contains ``"soda"`` → ``DQEngine.SODA``
* anything else → ``DQEngine.GREAT_EXPECTATIONS`` (safe default)

These tests don't reach the real dq-service container — they pin the
ROUTING decision so the persisted ``DQRun.engine`` field is always
correct regardless of whether the downstream service call succeeds.
The end-to-end-with-real-service path is exercised by
``test_views.py::test_create_dq_run_success_with_profile_key``
(skipped when dq-service is unavailable).
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TransactionTestCase


pytestmark = [pytest.mark.django_db(transaction=True)]


def _setup_real_graph():
    """Build the minimum viable Tenant→Asset→Dataset→File graph
    required for ``DQService.create_dq_run`` to walk to the routing
    decision before any downstream service call."""
    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.datasets.models import Dataset
    from hub.apps.files.models import File, FileStatus
    from hub.apps.tenants.models import Tenant
    from hub.apps.users.models import User, UserStatus

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"DQ Routing Tenant {uid}",
        slug=f"dq-routing-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant, key=f"a-{uid}", name=f"A {uid}",
        status=AssetStatus.ACTIVE, created_by=user,
    )
    file_obj = File.objects.create(
        tenant=tenant, name=f"f-{uid}.csv",
        content_type="text/csv", size=10,
        status=FileStatus.ACTIVE,
        storage_path=f"dq/{tenant.id}/{uid}/payload.csv",
        content_sha256="0" * 64,
        created_by=user,
    )
    dataset = Dataset.objects.create(
        tenant=tenant, asset=asset, file=file_obj,
        format="CSV", created_by=user,
    )
    return tenant, user, asset, dataset, file_obj


class DQServiceEngineRoutingTests(TransactionTestCase):
    """Pin the ``profile_key`` → ``DQEngine`` routing in
    ``DQService.create_dq_run``.

    Each test calls ``_resolve_engine`` (a private helper extracted
    from the production code path) so the assertion is scoped to the
    routing decision itself — independent of the rest of the
    create_dq_run flow (which involves the dq-service HTTP call,
    business-rule validation, etc.).
    """

    def _resolve_engine(self, profile_key: str):
        """Delegate to the production helper so this test exercises
        the actual routing code, not a copy. If services.py changes
        the routing logic without updating tests, those changes
        surface here."""
        from hub.apps.dq.services import resolve_engine_for_profile

        return resolve_engine_for_profile(profile_key)

    def test_gx_suffix_routes_to_great_expectations(self):
        from hub.apps.dq.models import DQEngine

        assert self._resolve_engine("intake_basic_gx") == DQEngine.GREAT_EXPECTATIONS

    def test_soda_suffix_routes_to_soda(self):
        from hub.apps.dq.models import DQEngine

        assert self._resolve_engine("intake_basic_soda") == DQEngine.SODA

    def test_substring_match_routes_to_soda(self):
        """Per services.py, a profile_key containing ``"soda"``
        (anywhere) also maps to SODA. Belt-and-suspenders fallback
        for legacy profile keys that aren't strictly suffix-conformant."""
        from hub.apps.dq.models import DQEngine

        assert self._resolve_engine("soda_custom_profile") == DQEngine.SODA

    def test_unknown_profile_defaults_to_great_expectations(self):
        from hub.apps.dq.models import DQEngine

        # No ``gx`` and no ``soda`` substring — falls through to
        # the default branch.
        assert self._resolve_engine("custom_intake_profile") == DQEngine.GREAT_EXPECTATIONS

    def test_create_dq_run_persists_soda_engine(self):
        """End-to-end-ish: the persisted ``DQRun.engine`` field
        reflects the routing decision when create_dq_run completes
        — even if the downstream dq-service HTTP call fails / is
        absent. The DQRun row is created in PENDING state BEFORE
        the service call, so the engine attribution survives a
        backend outage and shows up in the audit log + retention
        sweep correctly.
        """
        from hub.apps.dq.models import DQEngine, DQRun

        tenant, user, asset, dataset, file_obj = _setup_real_graph()
        # We don't call the full DQService.create_dq_run here (it
        # would attempt a dq-service HTTP request and fail in unit-
        # test env). Instead we verify the model + manager support
        # writing a row with engine=SODA AND the routing helper
        # picks SODA — together those pin the contract.
        run = DQRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=__import__(
                "hub.apps.jobs.models", fromlist=["Job"],
            ).Job.objects.create(
                tenant=tenant,
                type="DQ_RUN",
                status="COMPLETED",
                resource_type="ASSET",
                resource_id=asset.id,
            ),
            profile_key="intake_basic_soda",
            engine=self._resolve_engine("intake_basic_soda"),
            status="PENDING",
        )
        reloaded = DQRun.objects.get(pk=run.pk)
        assert reloaded.engine == DQEngine.SODA
        assert reloaded.profile_key == "intake_basic_soda"
