"""Optional scalability check: ``build_ropa_payload`` over many assets (opt-in).

Export ``ROPA_BENCHMARK_10K=1`` to enable. Uses ``bulk_create`` (no per-row signals).
"""

from __future__ import annotations
import pytest
import pytest

import os
import time
import uuid

from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.ropa.services.generator import build_ropa_payload
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription


@pytest.mark.django_db(transaction=True)
@pytest.mark.slow
class RopaBenchmarkTests(TestCase):
    @pytest.mark.integration
    def test_build_ropa_payload_10k_assets_under_thirty_seconds(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"ropa-bench-{uid}",
            slug=f"ropa-bench-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_ropa_enabled=True,
        )
        ensure_tenant_has_active_subscription(tenant)

        rows = [
            Asset(tenant=tenant, key=f"b{i}", name=f"Bulk {i}", status=AssetStatus.ACTIVE)
            for i in range(10_000)
        ]
        Asset.objects.bulk_create(rows, batch_size=1000)

        t0 = time.monotonic()
        payload = build_ropa_payload(tenant_id=str(tenant.id), regulation="GDPR")
        elapsed = time.monotonic() - t0

        self.assertEqual((payload.get("meta") or {}).get("asset_count"), 10_000)
        self.assertLess(elapsed, 30.0, f"build_ropa_payload took {elapsed:.2f}s, expected < 30s")
