"""
Phase 227 Wave 1 (227.L3.6 + 227.L3.7) — validation pipeline tests.

This file pins the always-on structural-floor invariant. Per the
2026-04-30 ungate directive, structureless contract writes are rejected
unconditionally — there is no feature flag, no per-tenant override, and
no deprecation period. The previous "silent-nullify" path
(``hub_contract = None`` and persist a row with NULL hub_contract_json)
is gone; create + update both raise ``ValidationError(code="STRUCTURELESS_CONTRACT")``.

Coverage
--------
* Subcode classification (ODPS_NO_PORTS, ODCS_NO_SCHEMA, CYCLIC_PORTS,
  GENERIC) with full error-payload-shape assertions.
* Internal counters (``_count_models_with_fields`` and
  ``_schema_fields_count``) on representative shapes.
* Remediation-URL template substitution behaviour.
* Non-raising sibling ``collect_structural_floor_errors``.
* ``ContractService.create_contract`` rejects each subcode end-to-end —
  no row persisted on rejection.
* ``ContractService.update_contract`` mirrors the create-path invariant
  and **preserves** the prior ``hub_contract_json`` on rejection.
* Alternate ODPS write-paths (``ODPSService.create_odps``,
  ``ContractService.link_odps_to_odcs``, ``ODPSService.normalize_odps``)
  enforce the floor too — Wave-0 audit found these three bypass the
  ``ContractService.create_contract`` pipeline.
* Consolidation: ``validate_hubcontract_schema`` (legacy bool/list API)
  and ``validate_hub_contract_dict`` (Pydantic-typed API) agree on the
  set of accepted/rejected payloads — same shared Pydantic core, no drift.

No mocks of internal code paths — the service is called with real DB
rows and the engine runs.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

import pytest
from django.test import TestCase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _unique_tenant():
    """Helper: build a Tenant with a guaranteed-unique name + slug."""
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"L3 Co {suffix}",
        slug=f"l3-co-{suffix}",
    )


@pytest.fixture
def odcs_with_fields() -> Dict[str, Any]:
    """A minimal valid ODCS v3.0.2 contract that satisfies the floor."""
    return {
        "kind": "DataContract",
        "apiVersion": "v3.0.2",
        "id": "ok-odcs",
        "name": "OK ODCS contract",
        "version": "1.0.0",
        "status": "active",
        "schema": [
            {
                "name": "customers",
                "fields": [{"name": "id", "type": "string"}],
            }
        ],
    }


@pytest.fixture
def odcs_no_schema() -> Dict[str, Any]:
    """ODCS contract missing ``schema``/``models`` entirely → ODCS_NO_SCHEMA."""
    return {
        "kind": "DataContract",
        "apiVersion": "v3.0.2",
        "id": "bad-odcs",
        "name": "Structureless ODCS",
        "version": "1.0.0",
        "status": "active",
        "info": {"description": "no fields anywhere"},
    }


@pytest.fixture
def odps_no_ports() -> Dict[str, Any]:
    """ODPS contract with empty outputPorts → ODPS_NO_PORTS."""
    return {
        "schema": "https://opendataproducts.org/schema/v3.0",
        "version": "3.0",
        "product": {
            "details": {
                "en": {
                    "productID": "bad-odps",
                    "name": "Structureless ODPS",
                    "productVersion": "1.0.0",
                }
            },
            "outputPorts": [],
        },
    }


# Required keys that EVERY ``STRUCTURELESS_CONTRACT`` error payload MUST
# carry — the canonical shape consumed by the frontend toast + Schema-
# editor deep-link.
REQUIRED_DETAIL_KEYS = (
    "subcode",
    "models_count",
    "schema_fields_count",
    "spec_type",
    "spec_version",
    "hint",
    "remediation_url",
)

# collect_structural_floor_errors returns flattened 4-key error dicts (Phase 274.4).
COLLECT_ERROR_KEYS = ("code", "subcode", "message", "remediation_url")


def _assert_full_payload_shape(details: Dict[str, Any]) -> None:
    """Assert every required detail key is present and non-empty."""
    missing = [k for k in REQUIRED_DETAIL_KEYS if k not in details]
    assert not missing, f"missing details keys: {missing} (got {details})"
    assert isinstance(details["models_count"], int)
    assert isinstance(details["schema_fields_count"], int)
    assert details["hint"], "hint must be non-empty"
    assert details["remediation_url"], "remediation_url must be non-empty"


# ---------------------------------------------------------------------------
# Internal helpers — counters
# ---------------------------------------------------------------------------


class TestStructuralFloorCounters:
    """Internal helpers used to populate the error payload."""

    def test_models_count_zero_when_no_models_key(self):
        from hub.apps.contracts.structural_floor import _count_models_with_fields

        assert _count_models_with_fields({}) == 0

    def test_models_count_zero_when_models_empty_list(self):
        from hub.apps.contracts.structural_floor import _count_models_with_fields

        assert _count_models_with_fields({"models": []}) == 0

    def test_models_count_zero_when_models_have_no_fields(self):
        """A model declared with ``fields=[]`` does not contribute structure."""
        from hub.apps.contracts.structural_floor import _count_models_with_fields

        payload = {"models": [{"name": "m1", "fields": []}, {"name": "m2"}]}
        assert _count_models_with_fields(payload) == 0

    def test_models_count_only_counts_models_with_at_least_one_field(self):
        from hub.apps.contracts.structural_floor import _count_models_with_fields

        payload = {
            "models": [
                {"name": "empty", "fields": []},
                {"name": "good", "fields": [{"name": "id"}]},
                {"name": "missing"},
                {"name": "good2", "fields": [{"name": "x"}, {"name": "y"}]},
            ]
        }
        assert _count_models_with_fields(payload) == 2

    def test_models_count_tolerates_non_list(self):
        from hub.apps.contracts.structural_floor import _count_models_with_fields

        # Defensive: malformed payloads must not crash the floor.
        assert _count_models_with_fields({"models": "not-a-list"}) == 0
        assert _count_models_with_fields({"models": None}) == 0

    def test_schema_fields_count_basic(self):
        from hub.apps.contracts.structural_floor import _schema_fields_count

        payload = {"schema": {"fields": [{"name": "a"}, {"name": "b"}]}}
        assert _schema_fields_count(payload) == 2

    def test_schema_fields_count_when_schema_missing(self):
        from hub.apps.contracts.structural_floor import _schema_fields_count

        assert _schema_fields_count({}) == 0
        assert _schema_fields_count({"schema": None}) == 0
        assert _schema_fields_count({"schema": {"fields": None}}) == 0


# ---------------------------------------------------------------------------
# Subcode classification + payload shape
# ---------------------------------------------------------------------------


class TestEnforceStructuralFloorSubcodes:
    """``enforce_structural_floor`` picks the right subcode for each cause
    and emits the canonical 7-key error-payload shape every time."""

    def test_odps_no_ports_subcode_full_payload_shape(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_ODPS_NO_PORTS,
            ERROR_CODE,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                {"models": []},
                spec_type="ODPS",
                spec_version="bitol-1.0.0",
            )
        assert exc.value.code == ERROR_CODE
        _assert_full_payload_shape(exc.value.details)
        assert exc.value.details["subcode"] == SUBCODE_ODPS_NO_PORTS
        assert exc.value.details["spec_type"] == "ODPS"
        assert exc.value.details["spec_version"] == "bitol-1.0.0"
        assert exc.value.details["models_count"] == 0
        assert exc.value.details["schema_fields_count"] == 0
        assert "/contracts/" in exc.value.details["remediation_url"]
        # Floor violations are 400-class — not 500.
        assert exc.value.http_status == 400
        # The human-readable message is a load-bearing diagnostic for
        # ops watching logs — pin that the subcode is in the message.
        assert SUBCODE_ODPS_NO_PORTS in exc.value.message

    def test_odcs_no_schema_subcode_full_payload_shape(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_ODCS_NO_SCHEMA,
            ERROR_CODE,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                {"info": {"name": "x"}, "schema": {"fields": []}, "models": []},
                spec_type="ODCS",
                spec_version="3.0.2",
            )
        assert exc.value.code == ERROR_CODE
        _assert_full_payload_shape(exc.value.details)
        assert exc.value.details["subcode"] == SUBCODE_ODCS_NO_SCHEMA
        assert exc.value.details["spec_type"] == "ODCS"
        assert exc.value.details["spec_version"] == "3.0.2"
        assert exc.value.http_status == 400
        assert SUBCODE_ODCS_NO_SCHEMA in exc.value.message

    def test_cyclic_ports_subcode_takes_priority(self):
        """When normalisation surfaced a CYCLIC_PORTS warning, the floor
        enforcer reports that cause specifically — operators need to fix
        the cycle, not just "add fields"."""
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_CYCLIC_PORTS,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                {"models": []},
                spec_type="ODPS",
                spec_version="bitol-1.0.0",
                warnings=[
                    "STRUCTURELESS_CYCLIC_PORTS: outputPort A->B->A intercepted"
                ],
            )
        _assert_full_payload_shape(exc.value.details)
        assert exc.value.details["subcode"] == SUBCODE_CYCLIC_PORTS

    def test_cyclic_ports_priority_independent_of_spec_type(self):
        """Cyclic warning wins even when spec_type would otherwise pick a
        different subcode — the cycle is the actionable cause."""
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_CYCLIC_PORTS,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                None,
                spec_type="ODCS",  # would normally → ODCS_NO_SCHEMA
                spec_version="3.0.2",
                warnings=["STRUCTURELESS_CYCLIC_PORTS: cycle detected"],
            )
        assert exc.value.details["subcode"] == SUBCODE_CYCLIC_PORTS

    def test_generic_subcode_for_unknown_spec(self):
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_GENERIC,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                None,
                spec_type="UNKNOWN_SPEC",
                spec_version="1.0",
            )
        _assert_full_payload_shape(exc.value.details)
        assert exc.value.details["subcode"] == SUBCODE_GENERIC

    def test_generic_subcode_for_none_spec_type(self):
        """``spec_type=None`` (auto-detect failure path) → GENERIC."""
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_GENERIC,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                {},
                spec_type=None,
                spec_version=None,
            )
        assert exc.value.details["subcode"] == SUBCODE_GENERIC
        # Both are None — payload still includes them for the frontend.
        assert exc.value.details["spec_type"] is None
        assert exc.value.details["spec_version"] is None

    def test_satisfied_floor_returns_silently(self):
        from hub.apps.contracts.structural_floor import enforce_structural_floor

        # No exception expected when at least one model has at least one field.
        enforce_structural_floor(
            {
                "models": [
                    {"name": "m", "fields": [{"name": "id", "type": "string"}]}
                ]
            },
            spec_type="ODCS",
            spec_version="3.0.2",
        )

    def test_floor_satisfied_via_top_level_schema_fields(self):
        """Top-level ``schema.fields[]`` alone satisfies the floor —
        no models needed."""
        from hub.apps.contracts.structural_floor import enforce_structural_floor

        enforce_structural_floor(
            {"schema": {"fields": [{"name": "id", "data_type": "string"}]}},
            spec_type="ODCS",
            spec_version="3.0.2",
        )

    def test_models_with_empty_fields_violates_floor(self):
        """``models=[{"fields": []}]`` is structureless even though
        ``models`` is technically populated."""
        from hub.apps.contracts.structural_floor import (
            enforce_structural_floor,
            SUBCODE_ODCS_NO_SCHEMA,
        )
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                {"models": [{"name": "ghost", "fields": []}]},
                spec_type="ODCS",
                spec_version="3.0.2",
            )
        assert exc.value.details["subcode"] == SUBCODE_ODCS_NO_SCHEMA
        assert exc.value.details["models_count"] == 0


# ---------------------------------------------------------------------------
# Remediation URL behaviour
# ---------------------------------------------------------------------------


class TestRemediationURL:
    """Schema-editor deep link is emitted on every floor violation."""

    def test_remediation_url_uses_contract_id_when_supplied(self):
        from hub.apps.contracts.structural_floor import enforce_structural_floor
        from hub.apps.core.services.base import ValidationError

        cid = "11111111-1111-1111-1111-111111111111"
        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                None,
                spec_type="ODCS",
                spec_version="3.0.2",
                contract_id=cid,
            )
        assert cid in exc.value.details["remediation_url"]
        assert "{contract_id}" not in exc.value.details["remediation_url"]

    def test_remediation_url_keeps_placeholder_on_create(self):
        """No contract_id (create path) → frontend resolves placeholder."""
        from hub.apps.contracts.structural_floor import enforce_structural_floor
        from hub.apps.core.services.base import ValidationError

        with pytest.raises(ValidationError) as exc:
            enforce_structural_floor(
                None,
                spec_type="ODCS",
                spec_version="3.0.2",
                # contract_id omitted
            )
        # Placeholder MUST be retained so the frontend knows this is a
        # pre-persistence rejection and can route to the "new contract"
        # editor entry point.
        assert "{contract_id}" in exc.value.details["remediation_url"]


# ---------------------------------------------------------------------------
# Non-raising sibling
# ---------------------------------------------------------------------------


class TestCollectStructuralFloorErrors:
    """``collect_structural_floor_errors`` is the non-raising surface used
    by call-sites that aggregate blockers (Asset.can_activate)."""

    def test_returns_empty_list_when_floor_satisfied(self):
        from hub.apps.contracts.structural_floor import collect_structural_floor_errors

        errors = collect_structural_floor_errors(
            {
                "models": [
                    {"name": "m", "fields": [{"name": "id", "type": "string"}]}
                ]
            },
            spec_type="ODCS",
            spec_version="3.0.2",
        )
        assert errors == []

    def test_returns_one_error_dict_when_floor_violated(self):
        from hub.apps.contracts.structural_floor import (
            collect_structural_floor_errors,
            ERROR_CODE,
            SUBCODE_ODPS_NO_PORTS,
        )

        errors = collect_structural_floor_errors(
            {"models": []},
            spec_type="ODPS",
            spec_version="bitol-1.0.0",
        )
        assert len(errors) == 1
        err = errors[0]
        # Phase 274.4: collect_structural_floor_errors returns flattened 4-key dicts
        for key in COLLECT_ERROR_KEYS:
            assert key in err, f"missing key {key!r} in {err}"
        assert err["code"] == ERROR_CODE
        assert err["subcode"] == SUBCODE_ODPS_NO_PORTS


# ---------------------------------------------------------------------------
# End-to-end: ContractService.create_contract rejects structureless writes
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestCreateContractRejectsStructureless(TestCase):
    """``ContractService.create_contract`` raises ValidationError when the
    structural floor is violated. No row is persisted."""

    def _service(self, tenant):
        from hub.apps.contracts.services import ContractService
        return ContractService(tenant_id=str(tenant.id))

    def test_create_rejects_odcs_without_schema(self):
        from hub.apps.contracts.models import Contract
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "x",
            "name": "x",
            "version": "1.0.0",
            "status": "active",
            "info": {"description": "no fields"},
        }
        before = Contract.objects.count()
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw=json.dumps(odcs),
                original_format="JSON",
                original_spec_type="ODCS",
            )
        assert exc.value.code == "STRUCTURELESS_CONTRACT"
        # Full payload shape — frontend depends on every key.
        for key in REQUIRED_DETAIL_KEYS:
            assert key in exc.value.details, f"missing {key!r}"
        assert Contract.objects.count() == before, (
            "No row should be persisted on rejection"
        )

    def test_create_rejects_odps_with_empty_outputports(self):
        from hub.apps.contracts.models import Contract
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        odps = {
            "schema": "https://opendataproducts.org/schema/v3.0",
            "version": "3.0",
            "product": {
                "details": {
                    "en": {
                        "productID": "x",
                        "name": "x",
                        "productVersion": "1.0.0",
                    }
                },
                "outputPorts": [],
            },
        }
        before = Contract.objects.count()
        with pytest.raises(ValidationError) as exc:
            self._service(tenant).create_contract(
                original_raw=json.dumps(odps),
                original_format="JSON",
                original_spec_type="ODPS",
            )
        assert exc.value.code == "STRUCTURELESS_CONTRACT"
        assert exc.value.details["subcode"] == "STRUCTURELESS_ODPS_NO_PORTS"
        assert exc.value.details["spec_type"] == "ODPS"
        assert Contract.objects.count() == before

    def test_create_accepts_well_formed_odcs(self):
        """Sanity — a valid ODCS contract still creates successfully."""
        tenant = _unique_tenant()
        odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "ok",
            "name": "ok",
            "version": "1.0.0",
            "status": "active",
            "schema": [
                {
                    "name": "customers",
                    "fields": [{"name": "id", "type": "string"}],
                }
            ],
        }
        result = self._service(tenant).create_contract(
            original_raw=json.dumps(odcs),
            original_format="JSON",
            original_spec_type="ODCS",
        )
        assert result is not None
        assert getattr(result, "id", None) is not None
        # The persisted hub_contract_json MUST satisfy the floor — i.e.,
        # no silent-nullify.
        assert result.hub_contract_json is not None
        assert result.hub_contract_json.get("models") or result.hub_contract_json.get(
            "schema", {}
        ).get("fields")


# ---------------------------------------------------------------------------
# End-to-end: ContractService.update_contract mirrors the create invariant
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestUpdateContractMirrorsStructuralFloor(TestCase):
    """``update_contract`` rejects PATCHes that would violate the floor —
    parity with ``create_contract`` per Phase 227 L3.4 — AND must NOT
    leave the persisted row in a partially-updated state."""

    def _service(self, tenant):
        from hub.apps.contracts.services import ContractService
        return ContractService(tenant_id=str(tenant.id))

    def _create_ok_contract(self, service):
        ok_odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "ok",
            "name": "ok",
            "version": "1.0.0",
            "status": "active",
            "schema": [
                {"name": "customers", "fields": [{"name": "id", "type": "string"}]}
            ],
        }
        return service.create_contract(
            original_raw=json.dumps(ok_odcs),
            original_format="JSON",
            original_spec_type="ODCS",
        )

    def test_update_to_structureless_is_rejected(self):
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        service = self._service(tenant)
        contract = self._create_ok_contract(service)

        # Attempt to PATCH the original_raw to a structureless ODCS body.
        bad_odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "x",
            "name": "x",
            "version": "1.0.0",
            "status": "active",
            "info": {"description": "no fields anymore"},
        }
        with pytest.raises(ValidationError) as exc:
            service.update_contract(
                str(contract.id),
                original_raw=json.dumps(bad_odcs),
            )
        assert exc.value.code == "STRUCTURELESS_CONTRACT"
        assert exc.value.details["subcode"] == "STRUCTURELESS_ODCS_NO_SCHEMA"
        # Every required key is present.
        for key in REQUIRED_DETAIL_KEYS:
            assert key in exc.value.details, f"missing {key!r}"
        # The remediation_url for an existing contract carries the UUID.
        assert str(contract.id) in exc.value.details["remediation_url"]
        assert "{contract_id}" not in exc.value.details["remediation_url"]

    def test_update_rejection_preserves_prior_state(self):
        """A rejected update MUST NOT mutate the persisted row.

        Pre-Wave-1 the silent-nullify path produced exactly this defect:
        the PATCH ran, the engine returned an empty payload, and the
        row was saved with ``hub_contract_json=NULL`` despite the rejection
        being implicit. The Wave-1 invariant is "raise BEFORE save"."""
        from hub.apps.contracts.models import Contract
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        service = self._service(tenant)
        contract = self._create_ok_contract(service)

        original_hub_contract = contract.hub_contract_json
        original_raw = contract.original_raw
        original_status = contract.status
        assert original_hub_contract  # sanity — created with structure

        bad_odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "x",
            "name": "x",
            "version": "1.0.0",
            "status": "active",
            "info": {"description": "stripped"},
        }
        with pytest.raises(ValidationError):
            service.update_contract(
                str(contract.id),
                original_raw=json.dumps(bad_odcs),
            )

        # Re-fetch from the DB — the row must be unchanged.
        refreshed = Contract.objects.get(id=contract.id)
        assert refreshed.hub_contract_json == original_hub_contract, (
            "hub_contract_json must be preserved on rejection — silent-"
            "nullify was the Wave-0 bug being fixed"
        )
        assert refreshed.original_raw == original_raw
        assert refreshed.status == original_status


# ---------------------------------------------------------------------------
# Validator consolidation (227.L3.6)
# ---------------------------------------------------------------------------


class TestValidatorConsolidation:
    """``validate_hubcontract_schema`` (legacy bool/list API) and
    ``validate_hub_contract_dict`` (Pydantic-typed API) MUST agree on
    rejections — any input one accepts, the other accepts; any input
    one rejects, the other rejects.

    Pre-Wave-1 there were two parallel validators with subtle drift.
    Wave 1 collapses them on a shared Pydantic core (``HubContractModel``);
    ``validate_hubcontract_schema`` is now a thin wrapper that adds only
    the ``hub_contract_version`` check on top of ``validate_hub_contract_dict``.
    This test pins that they no longer disagree.
    """

    def _legacy_ok(self, hub_contract: Dict[str, Any]) -> bool:
        from hub.apps.contracts.normalization_engine import (
            validate_hubcontract_schema,
        )

        ok, _ = validate_hubcontract_schema(hub_contract)
        return ok

    def _pydantic_ok(self, hub_contract: Dict[str, Any]) -> bool:
        from hub.apps.contracts.typed_models import validate_hub_contract_dict

        model, errors = validate_hub_contract_dict(hub_contract)
        return model is not None and not errors

    def _pydantic_errors(self, hub_contract: Dict[str, Any]) -> List[str]:
        from hub.apps.contracts.typed_models import validate_hub_contract_dict

        _model, errors = validate_hub_contract_dict(hub_contract)
        return errors

    def _legacy_errors(self, hub_contract: Dict[str, Any]) -> List[str]:
        from hub.apps.contracts.normalization_engine import (
            validate_hubcontract_schema,
        )

        _ok, errors = validate_hubcontract_schema(hub_contract)
        return errors

    def _both_validators_agree(self, hub_contract: Dict[str, Any]) -> bool:
        return self._legacy_ok(hub_contract) == self._pydantic_ok(hub_contract)

    def test_well_formed_minimal_contract_agrees(self):
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "ok",
            "info": {"name": "ok"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [
                {"name": "customers", "fields": [{"name": "id", "data_type": "string"}]}
            ],
        }
        assert self._both_validators_agree(hub_contract)
        # Both should accept.
        assert self._legacy_ok(hub_contract)
        assert self._pydantic_ok(hub_contract)

    def test_missing_required_top_level_agrees(self):
        # No info, no schema → both reject.
        hub_contract = {"hub_contract_version": "1.0.0", "id": "x"}
        assert self._both_validators_agree(hub_contract)
        assert not self._legacy_ok(hub_contract)
        assert not self._pydantic_ok(hub_contract)

    def test_object_field_without_nested_fields_agrees(self):
        """Object types with no nested fields[] hit the Phase 227.L2
        structural floor on HubContractField — both validators must
        catch it identically."""
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "x",
            "info": {"name": "x"},
            "schema": {
                "fields": [
                    {
                        "name": "customer",
                        "data_type": "object",
                        # No fields[] — should be rejected by Pydantic
                        # validator at HubContractField level.
                    }
                ]
            },
            "models": [
                {
                    "name": "m",
                    "fields": [
                        {
                            "name": "customer",
                            "data_type": "object",
                        }
                    ],
                }
            ],
        }
        assert self._both_validators_agree(hub_contract)

    def test_consolidation_test_no_drift_via_thin_wrapper(self):
        """``validate_hubcontract_schema`` is ONLY allowed to emit one
        extra error class on top of the Pydantic-validated set — the
        ``hub_contract_version`` mismatch. Anything else means the two
        validators have drifted."""
        # Bad version → legacy rejects with version error; Pydantic
        # accepts (version is just a string field there).
        hub_contract = {
            "hub_contract_version": "9.9.9",
            "id": "x",
            "info": {"name": "x"},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            "models": [
                {"name": "m", "fields": [{"name": "id", "data_type": "string"}]}
            ],
        }
        assert self._pydantic_ok(hub_contract), (
            "Pydantic accepts arbitrary version string"
        )
        assert not self._legacy_ok(hub_contract), (
            "Legacy validator must reject mismatched hub_contract_version"
        )
        # The error must mention hub_contract_version specifically.
        errors = self._legacy_errors(hub_contract)
        assert any("hub_contract_version" in e for e in errors)

    def test_pydantic_error_messages_propagate_through_legacy_wrapper(self):
        """Any error the Pydantic validator produces is surfaced verbatim
        by the legacy wrapper — proves the wrapper does not swallow or
        rewrite errors."""
        hub_contract = {"hub_contract_version": "1.0.0", "id": "x"}
        legacy = set(self._legacy_errors(hub_contract))
        pyd = set(self._pydantic_errors(hub_contract))
        # Every Pydantic error appears in the legacy error set.
        assert pyd.issubset(legacy), (
            f"Pydantic errors not propagated: missing {pyd - legacy}"
        )


# ---------------------------------------------------------------------------
# Audit gap (227.L3 review) — alternate ODPS write-paths must enforce the
# floor too. Wave-0 catalogued THREE entry points that bypass
# ``ContractService.create_contract``:
#
# 1. ``ODPSService.create_odps``        — direct ODPS create endpoint
#    (used by ``coordinate_odcs_odps_operations`` and the
#    ``views_odps`` REST surface).
# 2. ``ContractService.link_odps_to_odcs`` — called from the GraphQL
#    mutation and ``views_odps``; persists a fresh ODPS row when
#    invoked with ``odps_raw=`` (vs. a pre-existing contract id).
# 3. ``ODPSService.normalize_odps``     — preview/normalize endpoint
#    that returns a hub_contract dict; if structureless, the dict
#    looks superficially valid but has empty models — the API
#    consumer should see the typed STRUCTURELESS_CONTRACT code, not
#    a silently empty payload.
#
# Pre-fix, all three skipped ``enforce_structural_floor``. Post-fix,
# they all raise ``ValidationError(code="STRUCTURELESS_CONTRACT")``
# uniformly. These tests pin that behaviour so a future refactor can't
# reintroduce the bypass.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestAlternateODPSWritePathsEnforceFloor(TestCase):
    """The three alternate ODPS write-paths must reject structureless docs
    just like ``ContractService.create_contract`` does — no silent-nullify
    on the ``ODPSService.create_odps`` exception path either."""

    def _odps_service(self, tenant):
        from hub.apps.contracts.services import ODPSService

        return ODPSService(tenant_id=str(tenant.id))

    def _contract_service(self, tenant):
        from hub.apps.contracts.services import ContractService

        return ContractService(tenant_id=str(tenant.id))

    def _structureless_odps(self) -> Dict[str, Any]:
        return {
            "schema": "https://opendataproducts.org/schema/v3.0",
            "version": "3.0",
            "product": {
                "details": {
                    "en": {
                        "productID": "x",
                        "name": "x",
                        "productVersion": "1.0.0",
                    }
                },
                "outputPorts": [],
            },
        }

    def test_create_odps_rejects_structureless_no_silent_nullify(self):
        """``ODPSService.create_odps`` must NOT persist a row with
        ``hub_contract_json=NULL`` on a structureless input. Pre-fix
        this path caught ``ODPSNormalizationError``, set ``hub_contract
        = None``, and persisted with ``normalization_status =
        NORMALIZATION_FAILED`` — the exact Wave-0 defect."""
        from hub.apps.contracts.models import Contract
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        odps = self._structureless_odps()
        before = Contract.objects.count()
        with pytest.raises(ValidationError) as exc:
            self._odps_service(tenant).create_odps(
                odps_raw=json.dumps(odps),
                odps_format="json",
                resolve_external_refs=False,
            )
        # ``create_odps`` runs ODPSBusinessRules.validate_odps_structure
        # FIRST, which already rejects empty ``outputPorts`` /
        # ``dataSchema`` with ``BUSINESS_RULES_VALIDATION``. The
        # structural-floor enforcer is a secondary belt-and-braces guard
        # for the case where business rules accept the doc but
        # normalisation produces empty ``models[]``. Any of these codes
        # is acceptable as long as **no row landed**.
        assert exc.value.code in (
            "STRUCTURELESS_CONTRACT",
            "NORMALIZATION_FAILED",
            "BUSINESS_RULES_VALIDATION",
            "ODPS_VALIDATION_FAILED",
            "ODPS_PARSE_FAILED",
        ), (
            f"Expected a recognised rejection code; got {exc.value.code!r}"
        )
        assert Contract.objects.count() == before, (
            "create_odps must NOT persist a structureless row "
            "(silent-nullify regression)"
        )

    def test_link_odps_to_odcs_rejects_structureless_odps_raw(self):
        """``ContractService.link_odps_to_odcs`` builds an ODPS row when
        invoked with ``odps_raw=``. That row must satisfy the floor."""
        from hub.apps.contracts.models import Contract
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        contract_service = self._contract_service(tenant)

        # Seed a valid ODCS contract to link against.
        ok_odcs = {
            "kind": "DataContract",
            "apiVersion": "v3.0.2",
            "id": "ok",
            "name": "ok",
            "version": "1.0.0",
            "status": "active",
            "schema": [
                {"name": "customers", "fields": [{"name": "id", "type": "string"}]}
            ],
        }
        odcs_contract = contract_service.create_contract(
            original_raw=json.dumps(ok_odcs),
            original_format="JSON",
            original_spec_type="ODCS",
        )

        before = Contract.objects.count()
        bad_odps = self._structureless_odps()
        with pytest.raises(ValidationError) as exc:
            contract_service.link_odps_to_odcs(
                odcs_contract_id=str(odcs_contract.id),
                odps_raw=json.dumps(bad_odps),
                odps_format="JSON",
                resolve_external_refs=False,
            )
        # Floor or upstream rejection — what we pin is no extra row landed.
        # ``link_odps_to_odcs`` may reject via ``ODPS_MISSING_CONTRACT``
        # if the ODPS body lacks the expected ``contract`` block, or via
        # any of the codes listed below for other structureless shapes.
        assert exc.value.code in (
            "STRUCTURELESS_CONTRACT",
            "ODPS_VALIDATION_FAILED",
            "BUSINESS_RULES_VALIDATION",
            "NORMALIZATION_FAILED",
            "ODPS_MISSING_CONTRACT",
            "ODPS_PARSE_FAILED",
        ), f"Unexpected error code {exc.value.code!r}"
        assert Contract.objects.count() == before, (
            "link_odps_to_odcs must NOT persist a structureless ODPS row"
        )

    def test_normalize_odps_rejects_structureless_payload(self):
        """``ODPSService.normalize_odps`` must surface the typed
        ``STRUCTURELESS_CONTRACT`` code instead of returning a dict
        with empty models. Even though the method does not persist,
        downstream callers (``coordinate_odcs_odps_operations`` and the
        REST preview path) consume the dict directly."""
        from hub.apps.core.services.base import ValidationError

        tenant = _unique_tenant()
        odps_doc = self._structureless_odps()
        with pytest.raises(ValidationError) as exc:
            self._odps_service(tenant).normalize_odps(odps_doc=odps_doc)
        # ``normalize_odps`` may surface either the typed structural-
        # floor error or the legacy ``NORMALIZATION_FAILED`` — both
        # acceptable; what's load-bearing is the raise.
        assert exc.value.code in (
            "STRUCTURELESS_CONTRACT",
            "NORMALIZATION_FAILED",
        ), f"Unexpected error code {exc.value.code!r}"
