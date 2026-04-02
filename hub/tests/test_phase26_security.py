"""
Phase 26 Security Tests — Expanded Attack Surface

Covers:
  26.14.1  SSRF guard on relationship target_contract URLs
  26.14.2  Input length validation on relationship type/name
  26.14.3  element_id safe pattern validation
  26.14.4  Bitol ODPS unexpected schema URL audit
"""
from unittest import TestCase

from pydantic import ValidationError


# ======================================================================
# 26.14.1 — SSRF guard on relationship target_contract
# ======================================================================

class RelationshipSSRFGuardTest(TestCase):
    """Confirm resolve_relationship_target_refs uses SSRF guard."""

    def test_resolve_external_called_for_url_targets(self):
        """URL targets go through resolve_external which has SSRF guard."""
        from hub.apps.contracts.ref_resolver import RefResolver
        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [{
                "name": "orders",
                "fields": [],
                "relationships": [{
                    "type": "foreignKey",
                    "source": ["id"],
                    "target_contract": "http://169.254.169.254/latest/meta-data/",
                    "target_properties": ["id"],
                }],
            }],
            "schema": {"fields": []},
        }
        _, warnings = resolver.resolve_relationship_target_refs(hub)
        # The SSRF guard should block this (via resolve_external →
        # _validate_external_url → _ssrf_host_is_private).
        # The method catches the exception and produces a warning.
        assert len(warnings) >= 1
        assert "169.254.169.254" in warnings[0]

    def test_private_ip_target_blocked(self):
        """10.x.x.x private IP should be blocked."""
        from hub.apps.contracts.ref_resolver import RefResolver
        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [{
                "name": "m",
                "fields": [],
                "relationships": [{
                    "type": "fk",
                    "source": ["id"],
                    "target_contract": "http://10.0.0.1/contract.json",
                    "target_properties": ["id"],
                }],
            }],
            "schema": {"fields": []},
        }
        _, warnings = resolver.resolve_relationship_target_refs(hub)
        assert len(warnings) >= 1

    def test_localhost_target_blocked(self):
        """http://localhost should be blocked."""
        from hub.apps.contracts.ref_resolver import RefResolver
        resolver = RefResolver(tenant_id="test", user_id="test")
        hub = {
            "models": [{
                "name": "m",
                "fields": [],
                "relationships": [{
                    "type": "fk",
                    "source": ["id"],
                    "target_contract": "http://127.0.0.1/contract.json",
                    "target_properties": ["id"],
                }],
            }],
            "schema": {"fields": []},
        }
        _, warnings = resolver.resolve_relationship_target_refs(hub)
        assert len(warnings) >= 1

    def test_config_comment_documents_relationship_urls(self):
        """odps_refs.yaml should document that relationship URLs are covered."""
        import os
        config_path = os.path.join(
            os.path.dirname(__file__), "..",
            "apps", "contracts", "config", "odps_refs.yaml",
        )
        with open(config_path) as f:
            content = f.read()
        assert "relationships" in content.lower()
        assert "target_contract" in content


# ======================================================================
# 26.14.2 — Input length validation
# ======================================================================

class RelationshipLengthValidationTest(TestCase):
    """Test max_length on relationship type and name."""

    def test_type_max_length_100(self):
        from hub.apps.contracts.typed_models import HubContractRelationship
        # Exactly 100 chars — should pass
        rel = HubContractRelationship(type="x" * 100)
        assert len(rel.type) == 100

    def test_type_exceeds_max_length(self):
        from hub.apps.contracts.typed_models import HubContractRelationship
        with self.assertRaises(ValidationError) as ctx:
            HubContractRelationship(type="x" * 101)
        errors = ctx.exception.errors()
        assert any("type" in str(e.get("loc", "")) for e in errors)

    def test_name_max_length_255(self):
        from hub.apps.contracts.typed_models import HubContractRelationship
        rel = HubContractRelationship(name="y" * 255)
        assert len(rel.name) == 255

    def test_name_exceeds_max_length(self):
        from hub.apps.contracts.typed_models import HubContractRelationship
        with self.assertRaises(ValidationError) as ctx:
            HubContractRelationship(name="y" * 256)
        errors = ctx.exception.errors()
        assert any("name" in str(e.get("loc", "")) for e in errors)

    def test_none_values_pass(self):
        from hub.apps.contracts.typed_models import HubContractRelationship
        rel = HubContractRelationship(type=None, name=None)
        assert rel.type is None
        assert rel.name is None


# ======================================================================
# 26.14.3 — element_id safe pattern validation
# ======================================================================

class ElementIdPatternTest(TestCase):
    """Test element_id validates against safe pattern."""

    def test_valid_element_id(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(name="test", element_id="order-item_001")
        assert f.element_id == "order-item_001"

    def test_element_id_with_dots(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(name="test", element_id="com.example.field")
        assert f.element_id == "com.example.field"

    def test_element_id_rejects_uri_injection(self):
        """element_id with URI characters should be rejected."""
        from hub.apps.contracts.typed_models import HubContractField
        with self.assertRaises(ValidationError):
            HubContractField(
                name="test",
                element_id="http://evil.com/inject",
            )

    def test_element_id_rejects_spaces(self):
        from hub.apps.contracts.typed_models import HubContractField
        with self.assertRaises(ValidationError):
            HubContractField(name="test", element_id="has space")

    def test_element_id_rejects_angle_brackets(self):
        from hub.apps.contracts.typed_models import HubContractField
        with self.assertRaises(ValidationError):
            HubContractField(name="test", element_id="<script>")

    def test_element_id_max_128_chars(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(name="test", element_id="a" * 128)
        assert len(f.element_id) == 128

    def test_element_id_exceeds_128_rejected(self):
        from hub.apps.contracts.typed_models import HubContractField
        with self.assertRaises(ValidationError):
            HubContractField(name="test", element_id="a" * 129)

    def test_element_id_none_passes(self):
        from hub.apps.contracts.typed_models import HubContractField
        f = HubContractField(name="test", element_id=None)
        assert f.element_id is None

    def test_model_entry_element_id_same_pattern(self):
        from hub.apps.contracts.typed_models import HubContractModelEntry
        with self.assertRaises(ValidationError):
            HubContractModelEntry(
                name="test",
                element_id="http://evil.com",
                fields=[{"name": "id", "data_type": "string"}],
            )


# ======================================================================
# 26.14.4 — Bitol schema URL audit
# ======================================================================

class BitolSchemaURLAuditTest(TestCase):
    """Test that unexpected Bitol schema URL domain produces warning."""

    def test_expected_domain_no_warning(self):
        from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
            ODPSBitolNormalizerV1_0_0,
        )
        contract = {
            "schema": (
                "https://bitol-io.github.io/"
                "open-data-product-standard/v1.0.0/schema.json"
            ),
            "kind": "DataProduct",
            "apiVersion": "v1.0.0",
            "product": {
                "details": {
                    "en": {"productID": "dp-1", "name": "Test"},
                },
            },
        }
        n = ODPSBitolNormalizerV1_0_0()
        result = n.normalize(contract, spec_version="bitol-1.0.0")
        # No warning about unexpected domain
        domain_warnings = [
            w for w in result.warnings
            if "unexpected domain" in w.lower()
        ]
        assert len(domain_warnings) == 0

    def test_unexpected_domain_produces_warning(self):
        from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
            ODPSBitolNormalizerV1_0_0,
        )
        contract = {
            "schema": (
                "https://evil-site.example.com/"
                "open-data-product-standard/v1.0.0/schema.json"
            ),
            "kind": "DataProduct",
            "apiVersion": "v1.0.0",
            "product": {
                "details": {
                    "en": {"productID": "dp-1", "name": "Test"},
                },
            },
        }
        n = ODPSBitolNormalizerV1_0_0()
        result = n.normalize(contract, spec_version="bitol-1.0.0")
        domain_warnings = [
            w for w in result.warnings
            if "unexpected domain" in w.lower()
        ]
        assert len(domain_warnings) >= 1, (
            f"Expected unexpected-domain warning, got: {result.warnings}"
        )
        assert "evil-site.example.com" in domain_warnings[0]

    def test_no_schema_url_no_warning(self):
        from hub.apps.contracts.normalization.odps_normalizer_bitol_v1 import (
            ODPSBitolNormalizerV1_0_0,
        )
        contract = {
            "kind": "DataProduct",
            "apiVersion": "v1.0.0",
            "product": {
                "details": {
                    "en": {"productID": "dp-1", "name": "Test"},
                },
            },
        }
        n = ODPSBitolNormalizerV1_0_0()
        result = n.normalize(contract, spec_version="bitol-1.0.0")
        domain_warnings = [
            w for w in result.warnings
            if "unexpected domain" in w.lower()
        ]
        assert len(domain_warnings) == 0
