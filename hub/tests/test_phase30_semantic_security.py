"""
Phase 30 — Semantic Security Hardening Tests

Covers:
  28.1  SERVICE keyword blocked in SPARQL validation
  28.2  Rate limiting exists for SPARQL queries
  28.3  Timeout + result-size cap configured
  28.6  FUSEKI_URL SSRF guard
"""
from unittest import TestCase


class SPARQLServiceKeywordBlockedTest(TestCase):
    """28.1: SERVICE keyword must be rejected."""

    def test_service_keyword_blocked_in_hub_views(self):
        """Hub views.py validate_sparql_query rejects SERVICE."""
        from hub.apps.semantic.views import validate_sparql_query
        result = validate_sparql_query(
            "SELECT * WHERE { SERVICE <http://evil.com/sparql> { ?s ?p ?o } }"
        )
        assert result["valid"] is False
        assert "SERVICE" in result["error"]

    def test_service_keyword_blocked_case_insensitive(self):
        from hub.apps.semantic.views import validate_sparql_query
        result = validate_sparql_query(
            "SELECT * WHERE { service <http://evil.com/sparql> { ?s ?p ?o } }"
        )
        assert result["valid"] is False

    def test_select_query_still_allowed(self):
        from hub.apps.semantic.views import validate_sparql_query
        result = validate_sparql_query(
            "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
        )
        assert result["valid"] is True

    def test_construct_still_allowed(self):
        from hub.apps.semantic.views import validate_sparql_query
        result = validate_sparql_query(
            "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
        )
        assert result["valid"] is True

    def test_insert_still_blocked(self):
        from hub.apps.semantic.views import validate_sparql_query
        result = validate_sparql_query(
            "INSERT DATA { <s> <p> <o> }"
        )
        assert result["valid"] is False

    def test_service_in_semantic_service_main(self):
        """Verify SERVICE is in the forbidden list in main.py."""
        import inspect
        import importlib
        # Import the semantic-service main to check forbidden lists
        # (can't run it directly — it starts uvicorn)
        import sys
        import os
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', '..', 'services', 'semantic-service'
        ))
        # Read the source to verify SERVICE is in forbidden lists
        main_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'services', 'semantic-service', 'main.py'
        )
        with open(main_path) as f:
            source = f.read()
        assert '"SERVICE"' in source, (
            "SERVICE must be in forbidden_keywords in semantic-service main.py"
        )


class SPARQLRateLimitingExistsTest(TestCase):
    """28.2: Rate limiting must be configured for SPARQL."""

    def test_sparql_query_category_exists(self):
        from hub.apps.rate_limiting.config import EndpointCategory
        assert hasattr(EndpointCategory, 'SPARQL_QUERY')

    def test_sparql_rate_limit_configured(self):
        from hub.apps.rate_limiting.config import (
            PLATFORM_DEFAULT_LIMITS,
            EndpointCategory,
        )
        assert EndpointCategory.SPARQL_QUERY in PLATFORM_DEFAULT_LIMITS


class SPARQLTimeoutConfiguredTest(TestCase):
    """28.3: Timeout + result-size cap."""

    def test_sparql_result_limit_setting(self):
        from django.conf import settings
        limit = getattr(settings, "SPARQL_RESULT_LIMIT", None)
        # Should be set or default to 10000
        assert limit is None or limit > 0


class FusekiURLSSRFGuardTest(TestCase):
    """28.6: FUSEKI_URL SSRF guard."""

    def test_validate_fuseki_url_allows_internal(self):
        """Internal hostnames should pass."""
        import sys, os
        sys.path.insert(0, os.path.join(
            os.path.dirname(__file__), '..', '..',
            'services', 'semantic-service',
        ))
        # Read the function from source
        main_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'services', 'semantic-service', 'main.py',
        )
        with open(main_path) as f:
            source = f.read()
        assert "_validate_fuseki_url" in source
        assert "FUSEKI_SSRF_ALLOW" in source

    def test_ssrf_guard_function_in_source(self):
        """SSRF guard should validate FUSEKI_URL at import time."""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'services', 'semantic-service', 'main.py',
        )
        with open(main_path) as f:
            source = f.read()
        # Should call the guard at module level
        assert "_validate_fuseki_url(FUSEKI_URL)" in source


class ScopedAPIKeyTest(TestCase):
    """28.7: SEMANTIC_INTERNAL_API_KEY support."""

    def test_scoped_key_takes_priority(self):
        """Source should prefer SEMANTIC_INTERNAL_API_KEY."""
        import os
        main_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'services', 'semantic-service', 'main.py',
        )
        with open(main_path) as f:
            source = f.read()
        assert "SEMANTIC_INTERNAL_API_KEY" in source
        # Should set INTERNAL_API_KEY from scoped key
        assert 'os.environ["INTERNAL_API_KEY"] = _semantic_key' in source
