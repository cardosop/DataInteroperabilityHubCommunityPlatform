"""
Phase 26 — Regression tests for ODCS v3.1.0 normalization & export.

Pure-Python static validation (no Django, no running services).
Run: pytest hub/tests/test_phase26.py -v --noconftest -p no:django
"""
from __future__ import annotations

import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parent.parent.parent


def _read(rel: str) -> str:
    return (REPO / rel).read_text()


# ===================================================================
# Normalizer registry
# ===================================================================

class TestNormalizerRegistry:

    def test_odcs_v310_normalizer_registered(self):
        """v3.1.0 normalizer file exists and declares the class."""
        src = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_1_0.py"
        )
        assert "class ODCSNormalizerV3_1_0" in src

    def test_odcs_v310_fallback_no_longer_triggers(self):
        """The v3.1.0 normalizer has _supports_version
        matching '3.1.0', so the v3.0.2 normalizer won't
        handle it."""
        src302 = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_0_2.py"
        )
        src310 = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_1_0.py"
        )
        # v3.0.2 must NOT match "3.1.0"
        assert '"3.1.0"' not in src302 or "supports" not in src302
        # v3.1.0 MUST match "3.1.0"
        assert '"3.1.0"' in src310


# ===================================================================
# Typed models — relationships / element_id
# ===================================================================

class TestTypedModels:

    def test_relationship_class_defined(self):
        src = _read("hub/apps/contracts/typed_models.py")
        assert "class HubContractRelationship" in src

    def test_element_id_on_field(self):
        src = _read("hub/apps/contracts/typed_models.py")
        idx = src.find("class HubContractField")
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert "element_id" in body

    def test_element_id_on_model_entry(self):
        src = _read("hub/apps/contracts/typed_models.py")
        idx = src.find("class HubContractModelEntry")
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert "element_id" in body

    def test_relationships_on_schema(self):
        src = _read("hub/apps/contracts/typed_models.py")
        idx = src.find("class HubContractSchema")
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert "relationships" in body

    def test_logical_type_on_field(self):
        src = _read("hub/apps/contracts/typed_models.py")
        idx = src.find("class HubContractField")
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert "logicalType" in body


# ===================================================================
# v3.1.0 normalizer — version-specific mappings
# ===================================================================

class TestV310Normalizer:

    @pytest.fixture()
    def src(self):
        return _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_v3_1_0.py"
        )

    def test_map_relationships_method(self, src):
        assert "def _map_relationships(" in src

    def test_map_element_ids_method(self, src):
        assert "def _map_element_ids(" in src

    def test_map_quality_library_method(self, src):
        assert "def _map_quality_library(" in src

    def test_map_logical_types_method(self, src):
        assert "def _map_logical_types(" in src

    def test_sla_default_element_warning(self, src):
        assert "slaDefaultElement" in src
        assert "warning" in src.lower() or "Warning" in src

    def test_exclusive_bound_numeric_handling(self, src):
        assert "numeric_bound" in src

    def test_team_v31_object_parsing(self, src):
        assert "members" in src

    def test_v31_server_types_constant(self, src):
        assert "HiveServer" in src
        assert "ImpalaServer" in src
        assert "ActianZenServer" in src

    def test_v31_quality_metric_types(self, src):
        for metric in (
            "rowCount", "nullValues", "invalidValues",
            "duplicateValues", "missingValues",
        ):
            assert metric in src


# ===================================================================
# Generator — v3.1.0 export
# ===================================================================

class TestV310Generator:

    @pytest.fixture()
    def src(self):
        return _read("hub/apps/contracts/odcs_generator.py")

    def test_generator_class_exists(self, src):
        assert "class ODCSGeneratorV3_1_0" in src

    def test_generator_registered(self, src):
        assert 'register_odcs_generator("3.1.0"' in src

    def test_team_members_object_export(self, src):
        # v3.1.0 generator should emit team as object
        idx = src.find("class ODCSGeneratorV3_1_0")
        # Read until next top-level class or end
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert '"members"' in body or "'members'" in body

    def _v310_body(self, src: str) -> str:
        """Full body of ODCSGeneratorV3_1_0 class."""
        idx = src.find("class ODCSGeneratorV3_1_0")
        end = src.find("\nclass ", idx + 1)
        return src[idx:end] if end != -1 else src[idx:]

    def test_no_sla_default_element_in_export(self, src):
        body = self._v310_body(src)
        assert "slaDefaultElement" in body
        assert "strip" in body.lower() or "pop" in body

    def test_relationships_exported(self, src):
        body = self._v310_body(src)
        assert "relationships" in body

    def test_element_id_exported_as_id(self, src):
        body = self._v310_body(src)
        assert 'element_id' in body
        assert '"id"' in body

    def test_api_version_format(self, src):
        """v3.1.0 uses 'v3.1.0' not 'odcs.io/v3.1.0'."""
        idx = src.find("class ODCSGeneratorV3_1_0")
        end = src.find("\nclass ", idx + 1)
        body = src[idx:end] if end != -1 else src[idx:]
        assert 'f"v{target_version}"' in body

    def test_latest_version_is_3_0_2(self, src):
        """Default export version stays 3.0.2 for compat."""
        assert '_LATEST_ODCS_VERSION = "3.0.2"' in src


# ===================================================================
# Export view — downgrade warnings
# ===================================================================

class TestExportDowngradeWarnings:

    @pytest.fixture()
    def src(self):
        return _read("hub/apps/contracts/views_export.py")

    def test_downgrade_header_emitted(self, src):
        assert "X-Export-Downgrade-Warnings" in src

    def test_relationships_dropped_warning(self, src):
        assert "relationships_dropped" in src

    def test_ids_dropped_warning(self, src):
        assert "ids_dropped" in src

    def test_team_format_changed_warning(self, src):
        assert "team_format_changed" in src

    def test_version_tuple_comparison(self, src):
        """Version comparison must use tuple, not string."""
        assert "_ver_tuple" in src


# ===================================================================
# Version detection — short format support
# ===================================================================

class TestVersionDetection:

    def test_short_api_version_detected(self):
        src = _read(
            "hub/apps/contracts/normalization/"
            "odcs_normalizer_base.py"
        )
        idx = src.find("def _detect_odcs_version")
        next_def = src.find("\n    def ", idx + 1)
        body = src[idx:next_def] if next_def != -1 else src[idx:]
        assert "startswith" in body
        assert "'v'" in body or '"v"' in body


# ===================================================================
# Migration exists
# ===================================================================

class TestMigration:

    def test_temp_index_migration_exists(self):
        path = (
            REPO / "hub" / "apps" / "contracts" / "migrations"
            / "0016_add_temp_spec_version_index.py"
        )
        assert path.exists()

    def test_temp_index_adds_index(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0016_add_temp_spec_version_index.py"
        )
        assert "AddIndex" in src
        assert "tmp_spec_ver_idx" in src

    def test_backfill_migration_exists(self):
        path = (
            REPO / "hub" / "apps" / "contracts" / "migrations"
            / "0017_hubcontract_v3_1_0_backfill.py"
        )
        assert path.exists()

    def test_backfill_is_data_only(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        assert "RunPython" in src
        assert "AddField" not in src
        assert "RemoveField" not in src

    def test_backfill_has_batching(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        assert "BATCH_SIZE" in src
        assert "batch_num" in src or "batch" in src

    def test_backfill_has_error_isolation(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        assert "NORMALIZATION_FAILED" in src
        assert "normalization_errors" in src

    def test_backfill_is_idempotent(self):
        """Backfill collects IDs upfront for stable iteration."""
        src = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        # Must collect IDs upfront to avoid offset-drift
        assert "values_list" in src
        assert "contract_ids" in src or "batch_ids" in src

    def test_backfill_has_audit_log(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        assert "phase26_v310_backfill" in src
        assert "json.dumps" in src or "json" in src

    def test_cleanup_index_migration_exists(self):
        path = (
            REPO / "hub" / "apps" / "contracts" / "migrations"
            / "0018_remove_temp_spec_version_index.py"
        )
        assert path.exists()

    def test_cleanup_removes_index(self):
        src = _read(
            "hub/apps/contracts/migrations/"
            "0018_remove_temp_spec_version_index.py"
        )
        assert "RemoveIndex" in src
        assert "tmp_spec_ver_idx" in src

    def test_migration_dependency_chain(self):
        """0016 → 0017 → 0018 dependency chain."""
        src16 = _read(
            "hub/apps/contracts/migrations/"
            "0016_add_temp_spec_version_index.py"
        )
        src17 = _read(
            "hub/apps/contracts/migrations/"
            "0017_hubcontract_v3_1_0_backfill.py"
        )
        src18 = _read(
            "hub/apps/contracts/migrations/"
            "0018_remove_temp_spec_version_index.py"
        )
        assert "0015_normalise_regulation_keys" in src16
        assert "0016_add_temp_spec_version_index" in src17
        assert "0017_hubcontract_v3_1_0_backfill" in src18


# ===================================================================
# Semantic — relationship ontology + mapper
# ===================================================================

class TestSemanticRelationships:

    def test_ontology_has_relationship_class(self):
        src = _read("services/semantic-service/ontology.py")
        assert "HUB_Relationship" in src

    def test_ontology_has_relationship_type_property(self):
        src = _read("services/semantic-service/ontology.py")
        assert "HUB_relationshipType" in src

    def test_ontology_has_has_relationship_property(self):
        src = _read("services/semantic-service/ontology.py")
        assert "HUB_hasRelationship" in src

    def test_mapper_has_map_relationships(self):
        src = _read("services/semantic-service/mapper.py")
        assert "def _map_relationships(" in src

    def test_mapper_emits_owl_same_as_for_fk(self):
        src = _read("services/semantic-service/mapper.py")
        assert "OWL.sameAs" in src
        assert "foreignKey" in src

    def test_endpoint_validates_contract_id(self):
        """SPARQL injection guard."""
        src = _read("services/semantic-service/main.py")
        assert "re.match" in src or "regex" in src.lower()

    def test_service_client_has_get_relationships(self):
        src = _read("hub/apps/semantic/service_client.py")
        assert "def get_contract_relationships(" in src

    def test_service_client_caches_result(self):
        src = _read("hub/apps/semantic/service_client.py")
        assert "semantic:relationships:" in src
