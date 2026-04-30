"""
Phase 227 Wave 1 (227.L8.1 + L8.3) — payload-size limit boundary tests.

Pins the 2 MB ceiling on ``original_raw`` at the serializer layer:

* 1.99 MB body → HTTP 200/201 (accepted) — proves the cap doesn't fire
  on legitimately-large but still-bounded payloads.
* 2.01 MB body → HTTP 413 (rejected) with structured error code
  ``PAYLOAD_TOO_LARGE`` — proves the cap does fire and surfaces a
  parseable code (not a free-form ``CharField`` validation error).

The 2 MB cap matches the Helm ingress ``proxy-body-size`` annotation;
without alignment, large bodies would 413 at the nginx layer with no
structured error envelope, which is unactionable for API consumers.

Tests use the existing ``ContractsAPITransactionTestBase`` so the
TENANT_ADMIN role + active subscription middleware prerequisites are
satisfied. No mocks of internal code paths.
"""
from __future__ import annotations

import json

from rest_framework import status

from hub.apps.contracts.tests.test_base import ContractsAPITransactionTestBase


def _build_padded_odcs(target_size_bytes: int) -> str:
    """Build a well-formed ODCS contract whose serialised JSON length
    equals (or just exceeds) ``target_size_bytes``.

    Padding lives in ``info.description`` — a free-text field the
    normaliser tolerates — so the contract still satisfies the
    structural-floor invariant (one model + one field).
    """
    base = {
        "kind": "DataContract",
        "apiVersion": "v3.0.2",
        "id": "size-test",
        "name": "size-test",
        "version": "1.0.0",
        "status": "active",
        "info": {"description": ""},
        "schema": [
            {"name": "rows", "fields": [{"name": "id", "type": "string"}]}
        ],
    }
    base_size = len(json.dumps(base))
    padding = max(0, target_size_bytes - base_size)
    base["info"]["description"] = "x" * padding
    return json.dumps(base)


_KIB = 1024
_MIB = 1024 * 1024


class PayloadSizeLimitCreateTest(ContractsAPITransactionTestBase):
    """``POST /api/v1/contracts/`` enforces the 2 MB cap."""

    def test_just_under_2mb_is_accepted(self):
        # 1.99 MB — should pass the serializer cap and (with a clean
        # contract body) reach normalisation successfully.
        raw = _build_padded_odcs(int(1.99 * _MIB))
        # Sanity — the JSON itself is under the cap.
        assert len(raw) < 2 * _MIB, len(raw)
        response = self.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": raw,
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
        )
        # Either 200 (existing contract) or 201 (new) — the point is
        # NOT 413. A 4xx other than 413 would mean the cap is
        # mis-sized; a 5xx would mean the engine choked.
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_201_CREATED),
            f"1.99 MB body should be accepted; got "
            f"{response.status_code}: {getattr(response, 'data', None)}",
        )

    def test_just_over_2mb_returns_413_with_structured_error(self):
        raw = _build_padded_odcs(int(2.01 * _MIB))
        assert len(raw) > 2 * _MIB, len(raw)
        response = self.client.post(
            "/api/v1/contracts/",
            data={
                "original_raw": raw,
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Over-2 MB body must return 413; got "
            f"{response.status_code}: {getattr(response, 'data', None)}",
        )
        # Structured envelope: the API consumer must be able to switch
        # on ``code`` programmatically, not parse a free-text message.
        body = response.data
        self.assertEqual(body.get("code"), "PAYLOAD_TOO_LARGE")
        details = body.get("details") or {}
        # Must report the limit + actual size so the client UI can render
        # an actionable "your payload is N KB; the limit is M KB" hint.
        self.assertEqual(details.get("limit_bytes"), 2_000_000)
        self.assertGreater(details.get("size_bytes"), 2_000_000)


class PayloadSizeLimitAlternateWritePathsTest(ContractsAPITransactionTestBase):
    """The 2 MB cap is enforced uniformly across every contract write
    surface — not just create/update. Pre-fix audit found three bypass
    routes: ``validate-draft``, ``products``, and the ODPS-link path.
    """

    def test_validate_draft_rejects_oversize(self):
        raw = _build_padded_odcs(int(2.01 * _MIB))
        response = self.client.post(
            "/api/v1/contracts/validate-draft/",
            data={"original_raw": raw, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"validate-draft must enforce the cap; got {response.status_code}",
        )
        self.assertEqual(response.data.get("code"), "PAYLOAD_TOO_LARGE")

    def test_products_endpoint_rejects_oversize(self):
        raw = _build_padded_odcs(int(2.01 * _MIB))
        response = self.client.post(
            "/api/v1/contracts/products/",
            data={"original_raw": raw, "original_format": "JSON"},
            format="json",
        )
        self.assertEqual(
            response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"products endpoint must enforce the cap; got {response.status_code}",
        )
        self.assertEqual(response.data.get("code"), "PAYLOAD_TOO_LARGE")


class PayloadSizeLimitUpdateTest(ContractsAPITransactionTestBase):
    """``PATCH /api/v1/contracts/{id}/`` enforces the same cap."""

    def _create_ok_contract(self):
        from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
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

    def test_update_just_over_2mb_returns_413(self):
        contract = self._create_ok_contract()
        raw = _build_padded_odcs(int(2.01 * _MIB))
        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/",
            data={
                "original_raw": raw,
                "original_format": "JSON",
                "original_spec_type": "ODCS",
            },
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Over-2 MB PATCH must return 413; got "
            f"{response.status_code}: {getattr(response, 'data', None)}",
        )
        self.assertEqual(response.data.get("code"), "PAYLOAD_TOO_LARGE")
