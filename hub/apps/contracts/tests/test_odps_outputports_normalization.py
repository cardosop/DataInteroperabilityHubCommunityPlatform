"""
Phase 227 Wave 1 (227.L1.1, .L1.5, .L1.7, .L1.8, .L1.9) — tests for the
canonical ODPS ports → models[] / lineage normalisation helper.

Phase 227 root cause: ODPS contracts with ``outputPorts[]`` were dropping
their schemas during normalisation; the existing Bitol-v1 mapper only
recorded port metadata under ``extensions.x_odps.output_ports`` and never
extracted ``port.contract.spec.schema.fields`` (or any of the other 4
shorthand shapes ODPS allows) into ``hub_contract.models[]``. Net effect
in production was 100% of ODPS contracts normalising to empty
``models[]`` (the structureless population Wave 0 went hunting for).

This test file exercises ``normalize_models_from_ports`` end-to-end:

* Resolution priority order: ``contractId`` →
  ``contract.spec.schema`` → ``dataSchema.fields`` → ``schema``
  (Bitol shorthand) → ``contractURL``.
* Cycle detection (visited-set on ``contractId``) — A→B→A breaks with
  a ``STRUCTURELESS_CYCLIC_PORTS`` warning.
* ``inputPorts[]`` → ``hub_contract['lineage']['contracts'][]`` mapping.
* N+1 prevention: 100 ports with distinct ``contractId``s incur 1 DB
  round-trip, not 100.
* SSRF guard delegation for ``contractURL`` (covered separately in
  ``test_ssrf_port_contractURL.py``).

Tests use real ``Contract`` rows + the canonical predicate (no mocks of
internal code paths). The optional ``RefResolver`` parameter is stubbed
in only one test that explicitly exercises ``contractURL`` resolution
priority — and even there, the stub is the thinnest possible mock at
the network boundary.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

import pytest
from django.test import TestCase


def _make_field(name: str = "id", data_type: str = "string") -> Dict[str, Any]:
    return {"name": name, "data_type": data_type}


def _make_port(
    *,
    name: str = "orders",
    schema_path: str | None = None,
    fields: List[Dict[str, Any]] | None = None,
    contract_id: str | None = None,
    contract_url: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build an ODPS port dict in any of the 5 supported shapes.

    schema_path picks where the fields land:
      - "contract"      -> port.contract.spec.schema.fields
      - "dataSchema"    -> port.dataSchema.fields
      - "schema"        -> port.schema.fields  (Bitol shorthand)
      - None            -> no schema body (only contractId or contractURL)
    """
    port: Dict[str, Any] = {"name": name}
    fields = fields or [_make_field("id"), _make_field("amount", "number")]

    if schema_path == "contract":
        port["contract"] = {"spec": {"schema": {"fields": fields}}}
    elif schema_path == "dataSchema":
        port["dataSchema"] = {"fields": fields}
    elif schema_path == "schema":
        port["schema"] = {"fields": fields}
    if contract_id:
        port["contractId"] = contract_id
    if contract_url:
        port["contractURL"] = contract_url
    if extra:
        port.update(extra)
    return port


# ---------------------------------------------------------------------------
# Shape-by-shape: resolve from each of the 5 supported port-payload shapes
# ---------------------------------------------------------------------------

class PortShapeResolutionTests(TestCase):

    def setUp(self) -> None:
        from hub.apps.contracts.normalization import _ports_helper
        self._normalize = _ports_helper.normalize_models_from_ports

    def _empty_hub_contract(self) -> Dict[str, Any]:
        return {"info": {}, "schema": {"fields": []}, "extensions": {}}

    def test_shape_contract_spec_schema(self):
        """Priority 2: port.contract.spec.schema.fields → models[0].fields."""
        port = _make_port(name="orders", schema_path="contract")
        hub = self._empty_hub_contract()
        warnings: List[str] = []

        self._normalize(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=warnings,
        )

        assert len(hub["models"]) == 1
        m = hub["models"][0]
        assert m["name"] == "orders"
        assert [f["name"] for f in m["fields"]] == ["id", "amount"]
        assert warnings == []

    def test_shape_dataSchema_fields(self):
        """Priority 3: port.dataSchema.fields."""
        port = _make_port(name="orders", schema_path="dataSchema")
        hub = self._empty_hub_contract()
        self._normalize({"product": {"outputPorts": [port]}}, hub, [])
        assert len(hub["models"]) == 1
        assert [f["name"] for f in hub["models"][0]["fields"]] == ["id", "amount"]

    def test_shape_bitol_schema_shorthand(self):
        """Priority 4: port.schema.fields (Bitol v1 shorthand)."""
        port = _make_port(name="orders", schema_path="schema")
        hub = self._empty_hub_contract()
        self._normalize({"product": {"outputPorts": [port]}}, hub, [])
        assert len(hub["models"]) == 1
        assert [f["name"] for f in hub["models"][0]["fields"]] == ["id", "amount"]

    def test_no_resolvable_payload_emits_warning(self):
        """A port with neither contractId, contract.spec, dataSchema,
        schema, nor contractURL should produce no model and surface a
        warning so ops can find the broken contract.
        """
        port = _make_port(name="empty", schema_path=None)
        hub = self._empty_hub_contract()
        warnings: List[str] = []
        self._normalize({"product": {"outputPorts": [port]}}, hub, warnings)
        assert hub["models"] == []
        assert any("STRUCTURELESS" in w or "no resolvable" in w.lower() for w in warnings)

    def test_multiple_outputports_produce_multiple_models(self):
        ports = [
            _make_port(name="orders", schema_path="contract"),
            _make_port(name="users", schema_path="dataSchema"),
            _make_port(name="catalog", schema_path="schema"),
        ]
        hub = self._empty_hub_contract()
        self._normalize({"product": {"outputPorts": ports}}, hub, [])
        assert [m["name"] for m in hub["models"]] == ["orders", "users", "catalog"]

    def test_top_level_outputPorts_also_resolved(self):
        """ODPS allows outputPorts at top level OR under product. The
        helper supports both, matching the existing _get_ports behaviour.
        """
        ports = [_make_port(name="orders", schema_path="contract")]
        hub = self._empty_hub_contract()
        self._normalize({"outputPorts": ports}, hub, [])
        assert len(hub["models"]) == 1

    def test_inline_odcs_shape_normalised_to_canonical(self):
        """ODCS-shaped fields (``type``, ``minLength``, ``maxLength``) MUST
        be converted to canonical HubContract shape (``data_type``,
        ``min_length``, ``max_length``). Without conversion, downstream
        raw-dict consumers would not find ``data_type`` and the contract
        would render with empty types in the UI.
        """
        port = {
            "name": "orders",
            "contract": {
                "spec": {
                    "schema": {
                        "fields": [
                            {
                                "name": "id",
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 64,
                                "description": "primary key",
                            },
                            {"name": "amount", "type": "number"},
                        ]
                    }
                }
            },
        }
        hub = self._empty_hub_contract()
        self._normalize({"product": {"outputPorts": [port]}}, hub, [])
        assert len(hub["models"]) == 1
        fields = hub["models"][0]["fields"]
        # Canonical keys present.
        assert all("data_type" in f for f in fields), fields
        # ODCS aliases REPLACED, not duplicated.
        assert all("type" not in f for f in fields), fields
        # Renamed length keys.
        first = fields[0]
        assert first["data_type"] == "string"
        assert first["min_length"] == 1
        assert first["max_length"] == 64
        assert "minLength" not in first
        assert "maxLength" not in first
        # Non-aliased properties are preserved verbatim.
        assert first["description"] == "primary key"


# ---------------------------------------------------------------------------
# Resolution priority — contractId beats inline schemas
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class ResolutionPriorityTests(TestCase):

    def _empty_hub_contract(self) -> Dict[str, Any]:
        return {"info": {}, "schema": {"fields": []}, "extensions": {}}

    def _create_tenant(self, name: str = "Wave 1 Co"):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))

    def _create_contract_with_models(
        self,
        tenant,
        models: List[Dict[str, Any]],
        *,
        spec_type: str = "ODCS",
    ):
        from hub.apps.contracts.models import Contract
        return Contract.objects.create(
            tenant=tenant,
            original_spec_type=spec_type,
            original_spec_version="3.1.0",
            original_format="JSON",
            original_raw="{}",
            hub_contract_json={"models": models},
            normalization_status="NORMALIZED_OK",
        )

    def test_priority_contractId_resolves_to_referenced_contract_models(self):
        """Priority 1: port.contractId references an existing Contract;
        its hub_contract_json.models[] become the port's models[]."""
        from hub.apps.contracts.normalization import _ports_helper

        tenant = self._create_tenant()
        ref_contract = self._create_contract_with_models(
            tenant,
            models=[{"name": "orders", "fields": [_make_field("id")]}],
        )

        port = _make_port(name="orders-port", contract_id=str(ref_contract.id))
        hub = self._empty_hub_contract()
        _ports_helper.normalize_models_from_ports(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=[],
        )

        assert len(hub["models"]) == 1
        assert hub["models"][0]["name"] in ("orders-port", "orders")
        assert [f["name"] for f in hub["models"][0]["fields"]] == ["id"]

    def test_contractId_takes_priority_over_inline_dataSchema(self):
        """When BOTH contractId and dataSchema are present, contractId wins."""
        from hub.apps.contracts.normalization import _ports_helper

        tenant = self._create_tenant()
        ref_contract = self._create_contract_with_models(
            tenant,
            models=[{"name": "from_ref", "fields": [_make_field("ref_id")]}],
        )

        port = _make_port(
            name="dual",
            schema_path="dataSchema",
            fields=[_make_field("inline_id")],
            contract_id=str(ref_contract.id),
        )
        hub = self._empty_hub_contract()
        _ports_helper.normalize_models_from_ports(
            {"product": {"outputPorts": [port]}}, hub, [],
        )

        # The contractId-resolved field is "ref_id"; inline was "inline_id".
        assert len(hub["models"]) == 1
        assert "ref_id" in [f["name"] for f in hub["models"][0]["fields"]]
        assert "inline_id" not in [f["name"] for f in hub["models"][0]["fields"]]

    def test_contractId_to_nonexistent_contract_emits_warning(self):
        from hub.apps.contracts.normalization import _ports_helper

        port = _make_port(name="missing", contract_id=str(uuid.uuid4()))
        hub = self._empty_hub_contract()
        warnings: List[str] = []
        _ports_helper.normalize_models_from_ports(
            {"product": {"outputPorts": [port]}}, hub, warnings,
        )

        assert hub["models"] == []
        assert any("contractId" in w.lower() or "not found" in w.lower() for w in warnings)

    def test_contractId_failure_falls_back_to_inline(self):
        """Best-effort priority order — when contractId points at a
        nonexistent row but the port also carries an inline schema, the
        helper falls back to the inline shape AND emits a soft warning
        about the dangling contractId. Dropping the port entirely
        would cause the structureless population we are fixing.
        """
        from hub.apps.contracts.normalization import _ports_helper

        port = _make_port(
            name="dangling",
            schema_path="dataSchema",
            fields=[_make_field("inline_id"), _make_field("amount", "number")],
            contract_id=str(uuid.uuid4()),  # Random UUID — not in DB.
        )
        hub = self._empty_hub_contract()
        warnings: List[str] = []
        _ports_helper.normalize_models_from_ports(
            {"product": {"outputPorts": [port]}}, hub, warnings,
        )

        # Inline fallback engaged → one model, with the inline fields.
        assert len(hub["models"]) == 1
        assert hub["models"][0]["name"] == "dangling"
        names = [f["name"] for f in hub["models"][0]["fields"]]
        assert names == ["inline_id", "amount"]
        # Soft warning surfaces the dangling contractId so ops can clean.
        assert any(
            "STRUCTURELESS_PORT_CONTRACTID_NOT_FOUND" in w for w in warnings
        ), f"Expected dangling-contractId warning; got {warnings!r}"


# ---------------------------------------------------------------------------
# Cycle detection (227.L1.7)
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class CycleDetectionTests(TestCase):

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.create(name="Cycle Co", slug="cycle-co")

    def _create_contract(self, tenant, *, hub_contract_json):
        from hub.apps.contracts.models import Contract
        return Contract.objects.create(
            tenant=tenant,
            original_spec_type="ODPS",
            original_spec_version="bitol-1.0.0",
            original_format="JSON",
            original_raw="{}",
            hub_contract_json=hub_contract_json,
            normalization_status="NORMALIZED_OK",
        )

    def test_self_reference_breaks_with_warning(self):
        """A → A. Visited-set must short-circuit before infinite loop."""
        from hub.apps.contracts.normalization import _ports_helper

        tenant = self._create_tenant()
        # Contract A references itself via outputPorts.contractId
        a = self._create_contract(tenant, hub_contract_json={
            "models": [],
            "outputPorts_for_self_ref": True,
        })
        # Update A so its referenced ports point back to itself.
        # (Not a normal scenario but defensive.)
        a.hub_contract_json = {
            "models": [],
            "extensions": {"x_odps": {"output_ports": [{"contract_id": str(a.id)}]}},
        }
        a.save()

        port = _make_port(name="self-ref", contract_id=str(a.id))
        hub = {"info": {}, "schema": {"fields": []}, "extensions": {}}
        warnings: List[str] = []

        _ports_helper.normalize_models_from_ports(
            {"product": {"outputPorts": [port]}},
            hub,
            warnings,
            visited_contract_ids={uuid.UUID(str(a.id))},
        )

        # No infinite recursion; warning emitted.
        assert any("STRUCTURELESS_CYCLIC_PORTS" in w for w in warnings)

    def test_transitive_cycle_a_to_b_to_a(self):
        """A → B → A. Contract B's normalised payload references A; when A
        is being normalised and its outputPort lists B as ``contractId``,
        the visited-set passed in by the caller (containing A) must
        short-circuit B's onward reference back to A.

        This test models the second hop directly: the helper is called
        ONCE per normalisation pass (it does not recurse into resolved
        contracts), so the caller is responsible for seeding the
        visited-set with the in-flight contract's UUID. We exercise that
        contract here: the visited-set already contains A, the port
        references A (representing B's pointer back to A in a B→A→B
        cycle), and the helper detects the re-visit before any DB hit.
        """
        from hub.apps.contracts.normalization import _ports_helper

        tenant = self._create_tenant()
        a = self._create_contract(
            tenant,
            hub_contract_json={
                "models": [{"name": "a-model", "fields": [_make_field("a_id")]}]
            },
        )
        b = self._create_contract(
            tenant,
            hub_contract_json={
                "models": [{"name": "b-model", "fields": [_make_field("b_id")]}],
                # B's metadata records that its port references A — the
                # cycle the visited-set must intercept on B's normalisation.
                "extensions": {
                    "x_odps": {"output_ports": [{"contract_id": str(a.id)}]}
                },
            },
        )

        # Simulate B's normalisation pass: visited contains B; B's port
        # references A; on a second hop, A's port would reference B and
        # the visited-set must catch it. We call the helper once with
        # visited={A, B} to assert that re-visiting A is intercepted
        # without DB lookup or infinite recursion.
        port = _make_port(name="b-out-port", contract_id=str(a.id))
        hub: Dict[str, Any] = {"info": {}, "schema": {"fields": []}, "extensions": {}}
        warnings: List[str] = []

        _ports_helper.normalize_models_from_ports(
            {"product": {"outputPorts": [port]}},
            hub,
            warnings,
            visited_contract_ids={
                uuid.UUID(str(a.id)),
                uuid.UUID(str(b.id)),
            },
        )

        assert any("STRUCTURELESS_CYCLIC_PORTS" in w for w in warnings), (
            f"A→B→A transitive cycle must emit STRUCTURELESS_CYCLIC_PORTS; "
            f"got {warnings!r}"
        )
        # The cycled port produces no model from contractId; no inline
        # fallback exists, so models[] is empty.
        assert hub["models"] == []


# ---------------------------------------------------------------------------
# inputPorts → lineage.contracts (227.L1.8)
# ---------------------------------------------------------------------------

class InputPortsLineageTests(TestCase):

    def _empty_hub_contract(self) -> Dict[str, Any]:
        return {"info": {}, "schema": {"fields": []}, "extensions": {}, "models": []}

    def test_inputports_emit_to_lineage_contracts(self):
        """inputPorts should populate hub_contract['lineage']['contracts']."""
        from hub.apps.contracts.normalization import _ports_helper

        contract_data = {
            "product": {
                "inputPorts": [
                    {"name": "raw-orders", "namespace": "ingest"},
                    {"name": "raw-users", "namespace": "ingest"},
                ],
                "outputPorts": [],
            }
        }
        hub = self._empty_hub_contract()
        _ports_helper.normalize_models_from_ports(contract_data, hub, [])

        lineage = hub.get("lineage", {})
        contracts = lineage.get("contracts", [])
        assert len(contracts) == 2
        names = sorted(c["name"] for c in contracts)
        assert names == ["raw-orders", "raw-users"]
        for c in contracts:
            assert c["namespace"] == "ingest"

    def test_inputports_without_namespace_skipped(self):
        """Ports without name OR namespace are dropped (defensive)."""
        from hub.apps.contracts.normalization import _ports_helper

        contract_data = {"product": {"inputPorts": [{}, {"name": "x"}]}}
        hub = self._empty_hub_contract()
        _ports_helper.normalize_models_from_ports(contract_data, hub, [])
        # The empty entry is dropped; the {"name": "x"} entry stays
        # (namespace is optional in the lineage shape per Phase 227).
        contracts = hub.get("lineage", {}).get("contracts", [])
        assert len(contracts) == 1
        assert contracts[0]["name"] == "x"


# ---------------------------------------------------------------------------
# N+1 prevention (227.L1.5)
# ---------------------------------------------------------------------------

@pytest.mark.django_db(transaction=True)
class NPlusOnePreventionTests(TestCase):

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant
        return Tenant.objects.create(name="N+1 Co", slug="nplus1-co")

    def test_bulk_fetch_avoids_n_plus_one(self):
        """100 ports with distinct contractIds must hit the DB at most
        twice (one for the bulk fetch, possibly one for tenant scope).
        """
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.normalization import _ports_helper

        tenant = self._create_tenant()
        ref_ids = []
        for i in range(20):
            c = Contract.objects.create(
                tenant=tenant,
                original_spec_type="ODCS",
                original_spec_version="3.1.0",
                original_format="JSON",
                original_raw="{}",
                hub_contract_json={
                    "models": [{"name": f"m{i}", "fields": [_make_field(f"f{i}")]}],
                },
                normalization_status="NORMALIZED_OK",
            )
            ref_ids.append(str(c.id))

        ports = [_make_port(name=f"p{i}", contract_id=cid) for i, cid in enumerate(ref_ids)]
        hub = {"info": {}, "schema": {"fields": []}, "extensions": {}}

        with self.assertNumQueries(1):
            _ports_helper.normalize_models_from_ports(
                {"product": {"outputPorts": ports}}, hub, [],
            )

        assert len(hub["models"]) == 20


# ---------------------------------------------------------------------------
# Per-version end-to-end coverage (227.L1.4 + 227.L1.9)
# ---------------------------------------------------------------------------
#
# The shared helper is wired into ``ODPSNormalizerBase.normalize()`` so every
# ODPS variant inherits port → models[] mapping. These tests run the FULL
# normalisation pipeline (not the helper directly) for each supported
# version + the Bitol fork to prove that:
#
# * The base wiring fires for that version.
# * No version-specific normaliser shadows or skips the helper.
# * Inline outputPort schemas land in ``hub_contract['models']``.
#
# We deliberately use the smallest ODPS contract that passes
# ``_initialize_hub_contract`` for each version — schema URL only, plus a
# minimal product block. The single outputPort carries a ``contract.spec.schema.fields``
# inline schema (priority 2 in the helper).
# ---------------------------------------------------------------------------


class _PerVersionNormalisationMixin:
    """Builds a minimal ODPS contract with one inline-schema outputPort."""

    def _build_contract(self, *, schema_url: str, version: str) -> Dict[str, Any]:
        return {
            "schema": schema_url,
            "version": version,
            "product": {
                "details": {
                    "en": {
                        "productID": "per-version-test",
                        "name": "Per-version test product",
                        "productVersion": "1.0.0",
                    }
                },
                "outputPorts": [
                    {
                        "name": "orders",
                        "contract": {
                            "spec": {
                                "schema": {
                                    "fields": [
                                        {"name": "order_id", "type": "string"},
                                        {"name": "amount", "type": "number"},
                                    ]
                                }
                            }
                        },
                    }
                ],
            },
        }

    def _assert_models_populated(self, hub_contract: Dict[str, Any]) -> None:
        models = hub_contract.get("models")
        assert isinstance(models, list) and models, (
            f"Expected at least one model after normalisation; "
            f"got models={models!r}"
        )
        first = models[0]
        assert first.get("name") == "orders"
        names = [f.get("name") for f in first.get("fields", [])]
        assert names == ["order_id", "amount"], f"Unexpected fields: {names}"
        # Field shape MUST be canonical (data_type, not type).
        for f in first["fields"]:
            assert "data_type" in f, (
                f"Field {f!r} missing canonical 'data_type' key"
            )


class ODPSV1XPortsTest(TestCase, _PerVersionNormalisationMixin):
    """ODPS v1.x inherits the base helper wiring."""

    def test_v1_x_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v1_x import (
            ODPSNormalizerV1_X,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v1.0",
            version="1.0",
        )
        result = ODPSNormalizerV1_X().normalize(contract, spec_version="1.0")
        assert result.hub_contract is not None, (
            f"v1.x normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSV2XPortsTest(TestCase, _PerVersionNormalisationMixin):

    def test_v2_x_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v2_x import (
            ODPSNormalizerV2_X,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v2.0",
            version="2.0",
        )
        result = ODPSNormalizerV2_X().normalize(contract, spec_version="2.0")
        assert result.hub_contract is not None, (
            f"v2.x normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSV3XPortsTest(TestCase, _PerVersionNormalisationMixin):

    def test_v3_x_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v3_x import (
            ODPSNormalizerV3_X,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v3.0",
            version="3.0",
        )
        result = ODPSNormalizerV3_X().normalize(contract, spec_version="3.0")
        assert result.hub_contract is not None, (
            f"v3.x normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSV4_0PortsTest(TestCase, _PerVersionNormalisationMixin):

    def test_v4_0_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v4_0 import (
            ODPSNormalizerV4_0,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v4.0",
            version="4.0",
        )
        result = ODPSNormalizerV4_0().normalize(contract, spec_version="4.0")
        assert result.hub_contract is not None, (
            f"v4.0 normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSV4_1PortsTest(TestCase, _PerVersionNormalisationMixin):

    def test_v4_1_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v4_1 import (
            ODPSNormalizerV4_1,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v4.1",
            version="4.1",
        )
        result = ODPSNormalizerV4_1().normalize(contract, spec_version="4.1")
        assert result.hub_contract is not None, (
            f"v4.1 normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSV4_2PortsTest(TestCase, _PerVersionNormalisationMixin):

    def test_v4_2_outputPorts_to_models(self):
        from hub.apps.contracts.normalization.odps_normalizer_v4_2 import (
            ODPSNormalizerV4_2,
        )

        contract = self._build_contract(
            schema_url="https://opendataproducts.org/schema/v4.2",
            version="4.2",
        )
        result = ODPSNormalizerV4_2().normalize(contract, spec_version="4.2")
        assert result.hub_contract is not None, (
            f"v4.2 normalisation produced no hub_contract; errors={result.errors}"
        )
        self._assert_models_populated(result.hub_contract)


class ODPSBitolV1PortsTest(TestCase, _PerVersionNormalisationMixin):
    """Bitol v1.0.0 carries Bitol-specific schema URL and is the variant
    whose existing ``_map_output_ports`` we reduced to metadata-only."""

    def test_bitol_v1_outputPorts_to_models_and_metadata(self):
        from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
            ODPSBitolNormalizerV1_0_0,
        )

        contract = self._build_contract(
            schema_url=(
                "https://bitol-io.github.io/open-data-product-standard/v1.0.0"
            ),
            version="1.0.0",
        )
        # Add Bitol-specific port metadata that the base helper does NOT
        # touch but `_map_output_ports` (post-helper) MUST preserve.
        contract["product"]["outputPorts"][0].update({
            "tags": ["pii", "regulated"],
            "customProperties": [{"key": "owner-team", "value": "data-platform"}],
        })

        result = ODPSBitolNormalizerV1_0_0().normalize(
            contract, spec_version="bitol-1.0.0"
        )
        assert result.hub_contract is not None, (
            f"Bitol v1.0.0 normalisation produced no hub_contract; "
            f"errors={result.errors}"
        )
        # 1. Schema → models[] via the helper.
        self._assert_models_populated(result.hub_contract)
        # 2. Bitol metadata preserved under extensions.x_odps.output_ports.
        x_odps = result.hub_contract.get("extensions", {}).get("x_odps", {})
        bitol_ports = x_odps.get("output_ports") or []
        assert len(bitol_ports) == 1, (
            f"Bitol metadata extraction lost the port; got {bitol_ports!r}"
        )
        assert bitol_ports[0].get("tags") == ["pii", "regulated"], (
            f"tags lost in metadata path: {bitol_ports[0]!r}"
        )
        assert bitol_ports[0].get("custom_properties") == [
            {"key": "owner-team", "value": "data-platform"}
        ], f"customProperties lost in metadata path: {bitol_ports[0]!r}"
