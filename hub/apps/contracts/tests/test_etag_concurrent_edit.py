"""
Phase 227 Wave 1 (227.L4.3, L4.4) — ETag / If-Match optimistic concurrency.

Two writers can race on the same contract: A reads, B reads, A PATCHes
(saves), B PATCHes (overwrites A's changes). Wave 1 introduces a weak
ETag derived from ``Contract.updated_at``; clients send ``If-Match`` and
the server returns HTTP 412 on mismatch.

Uses :class:`ContractsAPITransactionTestBase` so the middleware
prerequisites (TENANT_ADMIN role, active subscription, etc.) are
already satisfied by the existing test scaffold.
"""
from __future__ import annotations

import json

from rest_framework import status

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsAPITransactionTestBase


def _ok_odcs_payload() -> str:
    """Well-formed ODCS body for PATCH that won't trigger the
    structural-floor (so we test ETag in isolation)."""
    return json.dumps(
        {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "ok",
            "name": "ok",
            "version": "1.0.1",
            "status": "active",
            "schema": [
                {"name": "m", "fields": [{"name": "id", "type": "string"}]}
            ],
        }
    )


class ETagOnRetrieveTest(ContractsAPITransactionTestBase):
    """The GET response carries a weak ``ETag`` header."""

    def _create_ok_contract(self) -> Contract:
        return Contract.objects.create(
            tenant=self.tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={
                "models": [
                    {"name": "m", "fields": [{"name": "id", "data_type": "string"}]}
                ],
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.DRAFT,
        )

    def test_retrieve_emits_etag_header(self):
        contract = self._create_ok_contract()

        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("ETag", response, "GET response must carry ETag header")
        # Weak validator format `W/"<hex>"`.
        etag = response["ETag"]
        self.assertTrue(
            etag.startswith('W/"'),
            f"Expected weak ETag; got {etag!r}",
        )


class IfMatchOnUpdateTest(ContractsAPITransactionTestBase):
    """PATCH validates ``If-Match`` and returns 412 on conflict."""

    def _create_ok_contract(self) -> Contract:
        return Contract.objects.create(
            tenant=self.tenant,
            version=1,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.1.0",
            original_format=OriginalFormat.JSON,
            original_raw="{}",
            hub_contract_json={
                "models": [
                    {"name": "m", "fields": [{"name": "id", "data_type": "string"}]}
                ],
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status=ContractStatus.DRAFT,
        )

    def test_patch_with_correct_etag_succeeds(self):
        contract = self._create_ok_contract()
        get_response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        etag = get_response["ETag"]

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
            HTTP_IF_MATCH=etag,
        )
        self.assertEqual(
            response.status_code, 200,
            f"Fresh ETag should succeed; got {response.status_code}: {response.data}",
        )
        self.assertIn("ETag", response, "PATCH success must carry fresh ETag")

    def test_patch_with_stale_etag_returns_412(self):
        contract = self._create_ok_contract()
        stale_etag = 'W/"deadbeefcafebabe"'

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
            HTTP_IF_MATCH=stale_etag,
        )
        self.assertEqual(
            response.status_code, status.HTTP_412_PRECONDITION_FAILED,
            f"Stale If-Match must return 412; got {response.status_code}: {response.data}",
        )
        self.assertEqual(response.data["code"], "PRECONDITION_FAILED")
        # The 412 response must carry the SERVER's current ETag so the
        # client can reconcile without an extra GET.
        self.assertIn("ETag", response)

    def test_patch_without_if_match_keeps_last_write_wins(self):
        """Backward compatibility — clients that omit ``If-Match`` keep
        the pre-Wave-1 last-write-wins semantics. Don't break them."""
        contract = self._create_ok_contract()

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code, 200,
            f"PATCH without If-Match must still succeed; got {response.data}",
        )

    def test_etag_changes_after_successful_patch(self):
        """The ETag MUST mutate after a successful write so subsequent
        PATCH attempts with the OLD ETag are rejected — the whole point
        of optimistic concurrency."""
        contract = self._create_ok_contract()
        first = self.client.get(f"/api/v1/contracts/{contract.id}/")
        etag_before = first["ETag"]

        self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
            HTTP_IF_MATCH=etag_before,
        )

        second = self.client.get(f"/api/v1/contracts/{contract.id}/")
        etag_after = second["ETag"]
        self.assertNotEqual(
            etag_before, etag_after,
            f"ETag must mutate after a write; before={etag_before!r} "
            f"after={etag_after!r}",
        )
