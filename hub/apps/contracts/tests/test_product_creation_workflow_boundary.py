"""P.2c — product-creation workflow boundary (mirrors
``test_payment_gateways_boundary.py``).

``POST /api/v1/contracts/products/`` (Product-First flow) resolves the
execution engine through the commercial hook
``get_product_creation_workflow`` — marketplace registers
``ProductCreationWorkflow`` from its ``AppConfig.ready()``. Before this
module, the hook's full-mode path had NO behavioral test: the
marketplace workflow tests call the workflow class DIRECTLY, which proves
nothing about the registered hook the endpoint actually uses.

Full mode: the endpoint drives the REAL paid workflow (synchronous in
the test environment) and returns the created ODPS + ODCS contract pair.
Core-only (simulated by ``hooks_snapshot`` + ``reset_hooks`` — the exact
runtime shape of a core-only process): the endpoint returns the
structured FEATURE_NOT_AVAILABLE response, not an import error.

NO MOCKS at contract boundaries: real Postgres, real ORM, real endpoint,
real marketplace workflow in full mode. The ODPS fixture reuses the
canonical ``create_odps_contract`` helper from the backward-compat E2E
suite (a real ODPS 4.1 document with an embedded ODCS 3.0.2 contract).
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.tests.test_backward_compatibility_e2e_comprehensive import (
    create_odps_contract,
)
from hub.apps.core import commercial_hooks
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ProductCreationWorkflowBoundaryTests(TestCase):
    """Product-first creation — full-mode marketplace workflow vs core-only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T-{uid}", slug=f"t-{uid}", status="ACTIVE")
        self.user = User.objects.create_user(
            email=f"u-{uid}@meshant.test", password="testpass", tenant=self.tenant
        )
        # The subscription paywall (P.2c, now liveness-pinned) 403s writes
        # without an active subscription — same setup the compat E2E uses.
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _post_product(self):
        odps_doc = create_odps_contract("4.1")
        return self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(odps_doc),
                "original_format": "JSON",
            },
            format="json",
        )

    def test_full_mode_endpoint_drives_the_paid_workflow(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("full-mode contract — provider absent in core-only")
        resp = self._post_product()
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        body = resp.json()
        assert "odps_contract" in body, "the workflow result must carry the ODPS contract"
        assert "odcs_contract" in body, "the workflow result must carry the ODCS contract"

    def test_full_mode_hook_resolves_to_the_paid_workflow(self):
        from hub.apps.manifest import is_core_only

        if is_core_only():
            self.skipTest("full-mode contract — provider absent in core-only")
        workflow = commercial_hooks.get_product_creation_workflow()
        assert workflow is not None
        assert "marketplace" in workflow.__module__

    def test_core_only_returns_structured_feature_unavailable(self):
        """Core-only: no workflow → FEATURE_NOT_AVAILABLE, not an import error."""
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            resp = self._post_product()
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        body = resp.json()
        assert body.get("error_code") == "FEATURE_NOT_AVAILABLE"
        assert "SaaS feature" in body.get("detail", "")
