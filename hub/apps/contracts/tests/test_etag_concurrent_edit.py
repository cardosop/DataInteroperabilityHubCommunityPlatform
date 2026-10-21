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
            "schema": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}],
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
                "models": [{"name": "m", "fields": [{"name": "id", "data_type": "string"}]}],
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
                "models": [{"name": "m", "fields": [{"name": "id", "data_type": "string"}]}],
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
            response.status_code,
            200,
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
            response.status_code,
            status.HTTP_412_PRECONDITION_FAILED,
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
            response.status_code,
            200,
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
            etag_before,
            etag_after,
            f"ETag must mutate after a write; before={etag_before!r} after={etag_after!r}",
        )

    def test_full_concurrent_edit_simulation(self):
        """Two-writer race: A reads, B reads, A PATCHes successfully,
        B PATCHes with stale ETag → 412. The whole point of L4.3 is to
        block B's overwrite."""
        contract = self._create_ok_contract()

        # Both writers GET the same fresh ETag.
        a_get = self.client.get(f"/api/v1/contracts/{contract.id}/")
        b_get = self.client.get(f"/api/v1/contracts/{contract.id}/")
        etag_a = a_get["ETag"]
        etag_b = b_get["ETag"]
        self.assertEqual(
            etag_a,
            etag_b,
            "Two reads of an unmodified row must yield the same ETag",
        )

        # A PATCHes successfully.
        a_patch = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
            HTTP_IF_MATCH=etag_a,
        )
        self.assertEqual(a_patch.status_code, 200)

        # B's PATCH with the now-stale ETag must 412.
        b_patch = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": _ok_odcs_payload(),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
            HTTP_IF_MATCH=etag_b,
        )
        self.assertEqual(
            b_patch.status_code,
            status.HTTP_412_PRECONDITION_FAILED,
            f"Stale writer must be rejected; got {b_patch.status_code}: {b_patch.data}",
        )
        # The 412 carries the server's CURRENT etag so B can recover
        # with one extra GET, not a full re-fetch loop.
        self.assertIn("ETag", b_patch)

    def test_etag_is_weak_validator_per_rfc7232(self):
        """RFC 7232 distinguishes strong (``"hex"``) from weak
        (``W/"hex"``) validators. Contracts use the weak form because
        the ETag is derived from ``updated_at`` which has microsecond
        granularity — two writes within the same microsecond would
        otherwise collide."""
        contract = self._create_ok_contract()
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")
        etag = response["ETag"]
        self.assertTrue(
            etag.startswith('W/"') and etag.endswith('"'),
            f"ETag must be RFC 7232 weak form; got {etag!r}",
        )

    def test_412_response_includes_current_server_etag(self):
        """The 412 body carries the current_etag so clients can show a
        useful conflict UI without an extra round-trip."""
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
        self.assertEqual(response.status_code, status.HTTP_412_PRECONDITION_FAILED)
        # Body carries the server's current ETag (not just the header).
        details = response.data.get("details") or {}
        self.assertIn("current_etag", details)
        self.assertEqual(details["current_etag"], response["ETag"])
        # Hint copy is non-empty so the frontend conflict-resolution
        # dialog has something to display.
        self.assertTrue(details.get("hint"), "412 must include a hint string")
