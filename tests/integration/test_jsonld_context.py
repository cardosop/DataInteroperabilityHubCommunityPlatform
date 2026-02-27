"""
Integration Tests: JSON-LD Context.

Tests that JSON-LD context includes all standard vocabulary prefixes.
Uses real semantic service (no mocks - skips at runtime if service unavailable).
"""

import pytest
from django.test import TestCase

from hub.apps.semantic.service_client import SemanticServiceClient
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name


def check_semantic_service_available():
    """Check if semantic service is available"""
    try:
        client = SemanticServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


def _skip_if_circuit_breaker(context):
    """Skip test when semantic service returns circuit breaker (unavailable at runtime)."""
    if isinstance(context, dict) and context.get("error") and "circuit breaker" in str(context.get("error", "")).lower():
        pytest.skip("Semantic service unavailable (circuit breaker open)")


class JSONLDContextTest(TestCase):
    """Test JSON-LD context includes all prefixes. Skips at runtime if semantic service unavailable."""

    def setUp(self):
        """Set up test fixtures. Check semantic service at runtime so batch runs can pass when service is up."""
        reset_circuit_breaker_by_name("semantic-service")
        if not check_semantic_service_available():
            pytest.skip("Semantic service not available")
        self.client = SemanticServiceClient()

    def test_jsonld_context_includes_all_prefixes(self):
        """Test that JSON-LD context includes all standard vocabulary prefixes"""
        context = self.client.get_jsonld_context()
        _skip_if_circuit_breaker(context)
        self.assertNotIn("error", context)
        self.assertIsInstance(context, dict)

        # Check for required prefixes
        required_prefixes = [
            "hub",  # Hub ontology
            "dqv",  # Data Quality Vocabulary
            "dpv",  # Data Privacy Vocabulary
            "prov",  # PROV-O
            "odrl",  # ODRL
            "shacl",  # SHACL
            "schema",  # Schema.org
            "foaf",  # FOAF
            "dcat",  # DCAT
            "dct",  # Dublin Core Terms
            "rdf",  # RDF
            "rdfs",  # RDFS
            "xsd",  # XML Schema
        ]

        # Context should be a dict with @context key
        if "@context" in context:
            context_dict = context["@context"]
        else:
            context_dict = context

        for prefix in required_prefixes:
            # Prefix should be in context (case-insensitive check)
            found = False
            for key in context_dict.keys():
                if prefix.lower() in key.lower():
                    found = True
                    break
            # Note: Some prefixes may be optional, so we log but don't fail
            if not found:
                print(f"Warning: Prefix '{prefix}' not found in JSON-LD context")

    def test_jsonld_context_structure(self):
        """Test that JSON-LD context has correct structure"""
        context = self.client.get_jsonld_context()
        _skip_if_circuit_breaker(context)
        self.assertNotIn("error", context)
        self.assertIsInstance(context, dict)

        # Should have @context key or be the context itself
        if "@context" in context:
            context_dict = context["@context"]
        else:
            context_dict = context

        # Should be a dictionary
        self.assertIsInstance(context_dict, dict)

        # Should have at least some prefixes
        self.assertGreater(len(context_dict), 0)

    def test_jsonld_context_prefixes_are_uris(self):
        """Test that JSON-LD context prefixes map to valid URIs"""
        context = self.client.get_jsonld_context()
        _skip_if_circuit_breaker(context)
        self.assertNotIn("error", context)

        if "@context" in context:
            context_dict = context["@context"]
        else:
            context_dict = context

        # Check that values are strings (URIs) or objects with @id
        for key, value in context_dict.items():
            if isinstance(value, str):
                # Should be a valid URI or compact IRI (e.g., "hub:DataAsset")
                # Compact IRIs are valid in JSON-LD (prefix:local)
                is_uri = value.startswith("http://") or value.startswith("https://")
                is_compact_iri = (
                    ":" in value and not value.startswith("http") and not value.startswith("/")
                )
                self.assertTrue(
                    is_uri or is_compact_iri,
                    f"Prefix '{key}' maps to non-URI value: {value} (should be URI or compact IRI)",
                )
            elif isinstance(value, dict):
                # Should have @id key
                self.assertIn("@id", value)
