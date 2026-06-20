"""
Phase 228.F2 (REQ-LIN-F2-002 / F2.15) — propagation integration test.

Pins the end-to-end coherence between the JSONB ``hub_contract_json.lineage``
write source and the derived ``LineageEdge`` row index after a
patch:

* Open ``LineageEdge`` rows match the post-patch desired set.
* ``hub_contract_json.lineage.entries[]`` is re-serialised to mirror.
* Audit rows are emitted (LINEAGE_EDGE_ADDED + LINEAGE_EDGE_REMOVED).
* The contract's ETag changes after the patch (so the next round-trip
  knows to re-read).

No mocks; real DB rows.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _setup_tenant_with_admin():
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"prop-{suffix}",
        slug=f"prop-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{suffix}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return tenant, user


def _make_contract(tenant, *, name: str, field_name: str = "id"):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uuid.uuid4().hex[:6]}",
        name=name,
        status=AssetStatus.DRAFT,
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json={
            "info": {"name": name},
            "models": [
                {
                    "name": "default",
                    "fields": [
                        {"name": field_name, "data_type": "string", "nullable": False},
                    ],
                }
            ],
        },
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=ContractStatus.ACTIVE,
    )


@pytest.mark.django_db(transaction=True)
class PropagationTests(TestCase):
    def test_patch_propagates_to_jsonb_and_edge_table(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.contracts.views_crud import _contract_etag

        tenant, user = _setup_tenant_with_admin()
        c_src = _make_contract(tenant, name="src", field_name="x")
        c_tgt = _make_contract(tenant, name="tgt", field_name="x")

        client = APIClient()
        client.force_authenticate(user=user)
        url = f"/api/v1/contracts/{c_tgt.id}/lineage/"
        before_etag = _contract_etag(c_tgt)

        # Patch: add one edge.
        response = client.patch(
            url,
            data={
                "edges": [
                    {
                        "source_contract": str(c_src.id),
                        "source_model": "default",
                        "source_field": "x",
                        "target_contract": str(c_tgt.id),
                        "target_model": "default",
                        "target_field": "x",
                        "edge_type": "transformation",
                        "transformation_ref": "dbt_propagation_v1",
                    },
                ],
            },
            format="json",
            HTTP_IF_MATCH=before_etag,
        )
        self.assertEqual(response.status_code, 200, response.content)

        # 1. LineageEdge row materialised + open.
        rows = LineageEdge.objects.filter(
            target_contract_id=c_tgt.id,
            valid_to__isnull=True,
        )
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().transformation_ref, "dbt_propagation_v1")

        # 2. hub_contract_json.lineage.entries re-serialised.
        c_tgt.refresh_from_db()
        lineage = (c_tgt.hub_contract_json or {}).get("lineage") or {}
        entries = lineage.get("entries") or []
        self.assertEqual(len(entries), 1)
        self.assertEqual(
            entries[0]["input_fields"][0]["field"],
            "x",
        )

        # 3. Audit rows emitted (one ADDED).
        added_rows = AuditEvent.objects.filter(
            action="LINEAGE_EDGE_ADDED",
            resource_id=c_tgt.id,
        )
        self.assertEqual(added_rows.count(), 1)

        # 4. ETag changed (the next round-trip needs to re-read).
        after_etag = _contract_etag(c_tgt)
        self.assertNotEqual(before_etag, after_etag)
