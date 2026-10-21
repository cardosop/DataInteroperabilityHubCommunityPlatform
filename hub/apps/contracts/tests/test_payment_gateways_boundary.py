"""
Phase 313.H.3 — payment-gateways endpoint boundary.

The contracts ``payment-gateways`` endpoint lists the payment gateways
configured in an ODPS contract through the commercial hook
``list_payment_gateways_for_contract`` (marketplace registers the
provider from its ``AppConfig.ready()``). Core-only mode has no
provider → an empty gateway list (no payment layer exists).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
endpoint, real marketplace service in full mode.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.core import commercial_hooks
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class PaymentGatewaysBoundaryTests(TestCase):
    """Payment-gateway listing — full-mode marketplace vs core-only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T-{uid}", slug=f"t-{uid}", status="ACTIVE")
        self.user = User.objects.create_user(
            email=f"u-{uid}@meshant.test", password="testpass", tenant=self.tenant
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="ODPS Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={
                "marketplace": {
                    "x_odps": {
                        "payment_gateways": {
                            "gw-stripe": {"type": "stripe", "enabled": True},
                        },
                    },
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _url(self):
        return f"/api/v1/contracts/{self.contract.id}/payment-gateways/"

    def test_full_mode_lists_configured_gateways(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            # The paid provider is absent in core-only — the core contract
            # is pinned by test_core_only_returns_empty_gateway_list below.
            self.skipTest("full-mode contract — billing provider absent in core-only")
        resp = self.client.get(self._url())
        assert resp.status_code == 200
        assert resp.json()["payment_gateways"]["gw-stripe"]["type"] == "stripe"

    def test_core_only_returns_empty_gateway_list(self):
        """Core-only: no payment layer → empty gateway dict (the full-mode
        shape for a contract without configured gateways), not an error."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resp = self.client.get(self._url())
        assert resp.status_code == 200
        assert resp.json() == {"payment_gateways": {}}
