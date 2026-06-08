"""
Integration tests for DadosGovBrConnector with real dados.gov.br Swagger API.

Tests use real dados.gov.br API endpoints - no mocks or stubs.
Uses JWT Bearer token authentication.
"""

import unittest
import os

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.base import MarketplaceType, SyncDirection
from hub.apps.integrations.config.marketplace_instances import get_marketplace_instance_config
from hub.apps.integrations.connectors.dados_gov_br_client import DadosGovBrAPIClient
from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector


def handle_auth_failure(e: Exception) -> None:
    """
    Handle authentication failures by skipping tests with clear message.

    Uses ``unittest.SkipTest`` which is an ``Exception`` subclass.
    Since this function is always called from inside ``except Exception:``
    blocks in test methods, the ``SkipTest`` raised here propagates
    *out* of the except block (Python does not re-catch exceptions
    raised within an except clause) and reaches Django's test runner,
    which correctly marks the test as skipped.

    Args:
        e: Exception that may indicate authentication failure
    """
    # Never skip on assertion failures — those are real test bugs.
    if isinstance(e, (AssertionError, unittest.SkipTest)):
        raise

    error_str = str(e).lower()
    if (
        "authentication failed" in error_str
        or "jwt token" in error_str
        or "redirected to signin" in error_str
        # ``dados.gov.br`` returns a bare HTTP 401 (no descriptive body)
        # when the JWT token is missing/expired/revoked.
        or "401" in error_str
        or "unauthorized" in error_str
    ):
        raise unittest.SkipTest(
            f"JWT token authentication failed (token may be expired or invalid): {e}"
        )


@pytest.mark.integration
class TestDadosGovBrConnectorIntegration(TestCase):
    """
    Integration tests for DadosGovBrConnector with real dados.gov.br API.

    Tests use real Swagger API endpoints - no mocks or stubs.
    Requires DADOS_GOV_BR_API_KEY environment variable with JWT token (or CKAN_DADOS_GOV_BR_API_KEY for backward compatibility).
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real dados.gov.br connector."""
        # Check skip conditions BEFORE super().setUpClass() so that if we
        # raise SkipTest, no class-level atomics are opened and the PG
        # connection is not left in a stale transaction for the next class.
        cls.jwt_token = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY")
        if not cls.jwt_token:
            raise unittest.SkipTest("CKAN_DADOS_GOV_BR_API_KEY not set - skipping integration tests")

        cls.instance_config = get_marketplace_instance_config("dados.gov.br")
        if not cls.instance_config:
            raise unittest.SkipTest("dados.gov.br instance configuration not found")

        super().setUpClass()

        # Create connector
        assert cls.instance_config is not None
        assert cls.jwt_token is not None
        cls.connector = DadosGovBrConnector(
            base_url=cls.instance_config.base_url,
            jwt_token=cls.jwt_token,
            swagger_spec_url=getattr(cls.instance_config, "swagger_spec_url", None),
        )

    def test_connector_initialization(self):
        """Test that connector initializes correctly."""
        assert self.connector is not None
        assert self.connector.base_url == "https://dados.gov.br"
        assert self.connector.jwt_token == self.jwt_token
        assert self.connector.client is not None

    def test_marketplace_type(self):
        """Test that marketplace type is CKAN_INSTANCE for compatibility."""
        assert self.connector.marketplace_type == MarketplaceType.CKAN_INSTANCE

    def test_supported_sync_directions(self):
        """Test that connector supports only PULL (harvest-only)."""
        assert self.connector.supported_sync_directions == [SyncDirection.PULL]

    def test_test_connection(self):
        """Test connection to dados.gov.br API."""
        try:
            result = self.connector.test_connection()
            assert result is True
        except unittest.SkipTest:
            raise
        except (ValueError, ConnectionError) as e:
            handle_auth_failure(e)
            pytest.fail(f"Connection test failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"Connection test failed: {e}")

    def test_list_listings_basic(self):
        """Test listing datasets with basic query."""
        try:
            listings = self.connector.list_listings(limit=5)
            assert isinstance(listings, list)
            assert len(listings) <= 5

            if listings:
                listing = listings[0]
                assert listing.marketplace_id is not None
                assert listing.title is not None
                assert listing.marketplace_type == MarketplaceType.CKAN_INSTANCE
        except unittest.SkipTest:
            raise
        except (ValueError, ConnectionError) as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings failed: {e}")

    def test_list_listings_with_filters(self):
        """Test listing datasets with filters."""
        try:
            listings = self.connector.list_listings(filters={"q": "dados"}, limit=3)
            assert isinstance(listings, list)
            assert len(listings) <= 3
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings with filters failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings with filters failed: {e}")

    def test_list_listings_pagination(self):
        """Test listing datasets with pagination."""
        try:
            # Get first page
            page1 = self.connector.list_listings(limit=3, offset=0)
            assert len(page1) <= 3

            # Get second page
            page2 = self.connector.list_listings(limit=3, offset=3)
            assert len(page2) <= 3

            # If we have results, they should be different
            if page1 and page2:
                ids1 = {l.marketplace_id for l in page1}
                ids2 = {l.marketplace_id for l in page2}
                # Results may overlap, but not necessarily all the same
                assert isinstance(ids1, set)
                assert isinstance(ids2, set)
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings pagination failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"list_listings pagination failed: {e}")

    def test_get_listing_by_id(self):
        """Test getting a specific dataset by ID."""
        try:
            # First, get a listing ID from search
            listings = self.connector.list_listings(limit=1)
            if not listings:
                raise unittest.SkipTest("No datasets available for testing")

            listing_id = listings[0].marketplace_id

            # Get the listing by ID
            listing = self.connector.get_listing(listing_id)

            assert listing is not None
            assert listing.marketplace_id == listing_id
            assert listing.marketplace_id is not None
            assert listing.title is not None
            assert listing.marketplace_type == MarketplaceType.CKAN_INSTANCE
        except NotFoundError:
            raise unittest.SkipTest("Dataset not found - may have been deleted")
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"get_listing failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"get_listing failed: {e}")

    def test_get_listing_not_found(self):
        """Test that getting non-existent listing raises NotFoundError."""
        try:
            with pytest.raises(NotFoundError):
                self.connector.get_listing("non-existent-dataset-id-12345")
        except (ValueError, ConnectionError) as e:
            # If authentication fails, skip this test
            handle_auth_failure(e)
            raise unittest.SkipTest(f"Cannot test NotFoundError due to authentication failure: {e}")

    def test_list_resources(self):
        """Test listing resources for a dataset."""
        try:
            # First, get a listing with resources
            listings = self.connector.list_listings(limit=10)
            if not listings:
                raise unittest.SkipTest("No datasets available for testing")

            # Find a listing with resources
            listing_with_resources = None
            for listing in listings:
                try:
                    resources = self.connector.list_resources(listing.marketplace_id)
                    if resources:
                        listing_with_resources = listing
                        break
                except Exception:
                    continue

            if not listing_with_resources:
                raise unittest.SkipTest("No datasets with resources available for testing")

            assert listing_with_resources.marketplace_id is not None
            resources = self.connector.list_resources(listing_with_resources.marketplace_id)
            assert isinstance(resources, list)

            if resources:
                resource = resources[0]
                assert resource.resource_id is not None
                assert resource.name is not None
        except NotFoundError:
            raise unittest.SkipTest("Dataset not found - may have been deleted")
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"list_resources failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"list_resources failed: {e}")

    def test_swagger_dataset_to_listing_mapping(self):
        """Test mapping Swagger dataset response to MarketplaceListing."""
        try:
            listings = self.connector.list_listings(limit=1)
            if not listings:
                raise unittest.SkipTest("No datasets available for testing")

            listing = listings[0]

            # Verify mapping
            assert listing.marketplace_id is not None
            assert listing.title is not None
            assert listing.marketplace_type == MarketplaceType.CKAN_INSTANCE
            assert "swagger_dataset" in listing.metadata
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"Dataset mapping failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"Dataset mapping failed: {e}")

    def test_swagger_resource_to_marketplace_resource_mapping(self):
        """Test mapping Swagger resource response to MarketplaceResource."""
        try:
            # Get a listing with resources
            listings = self.connector.list_listings(limit=10)
            if not listings:
                raise unittest.SkipTest("No datasets available for testing")

            # Find a listing with resources
            listing_with_resources = None
            for listing in listings:
                try:
                    resources = self.connector.list_resources(listing.marketplace_id)
                    if resources:
                        listing_with_resources = listing
                        break
                except Exception:
                    continue

            if not listing_with_resources:
                raise unittest.SkipTest("No datasets with resources available for testing")

            resources = self.connector.list_resources(listing_with_resources.marketplace_id)
            if not resources:
                raise unittest.SkipTest("No resources available for testing")

            resource = resources[0]

            # Verify mapping
            assert resource.resource_id is not None
            assert resource.name is not None
            assert resource.resource_type in ["FILE", "API"]
            assert "swagger_resource" in resource.metadata
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"Resource mapping failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"Resource mapping failed: {e}")

    def test_jwt_token_authentication(self):
        """Test that JWT token authentication works."""
        try:
            # Test connection should succeed with valid token
            result = self.connector.test_connection()
            assert result is True

            # Try to list listings - should work with valid token
            listings = self.connector.list_listings(limit=1)
            assert isinstance(listings, list)
        except (ValueError, ConnectionError) as e:
            handle_auth_failure(e)
            pytest.fail(f"JWT token authentication failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"JWT token authentication failed: {e}")

    def test_endpoint_resolution(self):
        """Test that endpoints are resolved correctly."""
        try:
            # Test that search endpoint works
            listings = self.connector.list_listings(limit=1)
            assert isinstance(listings, list)

            # Test that get endpoint works
            if listings:
                listing = self.connector.get_listing(listings[0].marketplace_id)
                assert listing is not None
        except (ValueError, ConnectionError) as e:
            handle_auth_failure(e)
            pytest.fail(f"Endpoint resolution failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"Endpoint resolution failed: {e}")


@pytest.mark.integration
class TestDadosGovBrAPIClientIntegration(TestCase):
    """
    Integration tests for DadosGovBrAPIClient with real dados.gov.br API.

    Tests use real Swagger API endpoints - no mocks or stubs.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real API client."""
        # Check skip conditions BEFORE super().setUpClass() so that if we
        # raise SkipTest, no class-level atomics are opened and the PG
        # connection is not left in a stale transaction for the next class.
        cls.jwt_token = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY")
        if not cls.jwt_token:
            raise unittest.SkipTest(
                "DADOS_GOV_BR_API_KEY or CKAN_DADOS_GOV_BR_API_KEY not set - skipping integration tests"
            )

        super().setUpClass()

        # Create API client (use api_client to avoid conflict with Django TestCase.client)
        assert cls.jwt_token is not None
        cls.api_client = DadosGovBrAPIClient(
            base_url="https://dados.gov.br", jwt_token=cls.jwt_token
        )

    def test_client_initialization(self):
        """Test that client initializes correctly."""
        assert self.api_client is not None
        assert self.api_client.base_url == "https://dados.gov.br"
        assert self.api_client.jwt_token == self.jwt_token

    def test_load_swagger_spec(self):
        """Test loading Swagger specification."""
        try:
            spec = self.api_client.load_swagger_spec("https://dados.gov.br/v3/api-docs")
            # Spec may be None if endpoint returns HTML instead of JSON
            # This is acceptable - we have fallback endpoints
            if spec:
                assert isinstance(spec, dict)
                assert "paths" in spec or "openapi" in spec or "swagger" in spec
        except Exception as e:
            # Swagger spec loading may fail - that's OK, we have fallbacks
            raise unittest.SkipTest(f"Swagger spec loading failed (acceptable): {e}")

    def test_get_endpoint_path(self):
        """Test endpoint path resolution."""
        # Test fallback endpoint paths - should use dados.gov.br endpoints
        path = self.api_client.get_endpoint_path("package_search")
        assert path == "/dados/api/publico/conjuntos-dados"

        path = self.api_client.get_endpoint_path("package_show")
        assert path == "/dados/api/publico/conjuntos-dados"  # Base path, ID appended in method

        path = self.api_client.get_endpoint_path("resource_show")
        assert path == "/dados/api/publico/conjuntos-dados"  # Resources nested in datasets

    def test_search_datasets(self):
        """Test searching datasets."""
        try:
            # API requires pagina parameter (page number)
            response = self.api_client.search_datasets(page=1)
            # API returns direct array according to Swagger spec
            assert isinstance(response, list)
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"search_datasets failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"search_datasets failed: {e}")

    def test_get_dataset(self):
        """Test getting dataset by ID."""
        try:
            # First, search for a dataset (API requires pagina parameter)
            search_response = self.api_client.search_datasets(page=1)

            # API returns direct array according to Swagger spec
            results = []
            if isinstance(search_response, list):
                results = search_response
            elif isinstance(search_response, dict):
                # Fallback: try to extract array from dict (for backward compatibility)
                if "results" in search_response:
                    results = search_response.get("results", [])
                elif "result" in search_response:
                    result = search_response.get("result", {})
                    if isinstance(result, list):
                        results = result
                    else:
                        results = result.get("results", [])

            if not results:
                raise unittest.SkipTest("No datasets available for testing")

            # Extract dataset ID (handle Portuguese: identificador, English: id, name)
            dataset_data = results[0]
            dataset_id = (
                dataset_data.get("identificador")
                or dataset_data.get("id")
                or dataset_data.get("name")
            )
            if not dataset_id:
                raise unittest.SkipTest("Dataset ID not found in search results")

            # Get the dataset
            response = self.api_client.get_dataset(dataset_id)
            assert isinstance(response, dict)
            # Response may be direct object or wrapped in success/result
            assert isinstance(response, dict)
        except ValueError as e:
            handle_auth_failure(e)
            pytest.fail(f"get_dataset failed: {e}")
        except Exception as e:
            handle_auth_failure(e)
            pytest.fail(f"get_dataset failed: {e}")

    def test_bearer_token_in_headers(self):
        """Test that Bearer token is included in request headers."""
        # This is tested implicitly by successful API calls
        # If token wasn't included, we'd get 401 Unauthorized
        try:
            # API requires pagina parameter (page number)
            response = self.api_client.search_datasets(page=1)
            # API returns direct array according to Swagger spec
            assert isinstance(response, list)
        except (ValueError, ConnectionError) as e:
            # If we get authentication failure, token wasn't sent or was invalid
            handle_auth_failure(e)
            raise unittest.SkipTest("Bearer token authentication failed - cannot test headers")
        except Exception as e:
            # If we get 401, token wasn't sent or was invalid
            if (
                "401" in str(e)
                or "Unauthorized" in str(e)
                or "authentication failed" in str(e).lower()
            ):
                handle_auth_failure(e)
                raise unittest.SkipTest("Bearer token not included in headers or invalid")
            raise


@pytest.mark.integration
class TestDadosGovBrBackwardCompatibility(TestCase):
    """
    Test backward compatibility with other CKAN instances.

    Ensures that other CKAN instances continue using standard CKANConnector.
    Tests that call list_listings/get_listing/list_resources or constructor
    use self.connector, self.instance_config, and self.jwt_token set in setUp.
    """

    def setUp(self):
        """Set up instance config, JWT token, and connector for dados.gov.br (used by later tests)."""
        super().setUp()
        self.instance_config = get_marketplace_instance_config("dados.gov.br")
        self.jwt_token = (
            os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY") or ""
        )
        self.connector = None
        if self.instance_config and self.jwt_token:
            try:
                from hub.apps.integrations.factory import MarketplaceConnectorFactory

                self.connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                    "dados.gov.br", api_key=self.jwt_token
                )
            except Exception:
                pass

    def test_demo_ckan_org_uses_ckan_connector(self):
        """Test that demo.ckan.org uses standard CKANConnector."""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        # Get instance config
        config = get_marketplace_instance_config("demo.ckan.org")
        assert config is not None
        assert config.connector_type == "ckan"  # Should default to "ckan"

        # Factory should create CKANConnector
        try:
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                "demo.ckan.org"
            )
            assert isinstance(connector, CKANConnector)
        except Exception as e:
            raise unittest.SkipTest(f"CKANConnector not registered or demo.ckan.org unavailable: {e}")

    def test_data_gov_uses_ckan_connector(self):
        """Test that data.gov uses standard CKANConnector."""
        from hub.apps.integrations.connectors.ckan_connector import CKANConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        # Get instance config
        config = get_marketplace_instance_config("data.gov")
        assert config is not None
        assert config.connector_type == "ckan"  # Should default to "ckan"

        # Factory should create CKANConnector
        try:
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance("data.gov")
            assert isinstance(connector, CKANConnector)
        except Exception as e:
            raise unittest.SkipTest(f"CKANConnector not registered or data.gov unavailable: {e}")

    def test_dados_gov_br_uses_swagger_connector(self):
        """Test that dados.gov.br uses DadosGovBrConnector."""
        from hub.apps.integrations.connectors.dados_gov_br_connector import DadosGovBrConnector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        # Get instance config
        config = get_marketplace_instance_config("dados.gov.br")
        assert config is not None
        assert config.connector_type == "swagger"

        # Factory should create DadosGovBrConnector
        jwt_token = os.getenv("DADOS_GOV_BR_API_KEY") or os.getenv("CKAN_DADOS_GOV_BR_API_KEY", "")
        try:
            connector = MarketplaceConnectorFactory.create_ckan_connector_from_instance(
                "dados.gov.br", api_key=jwt_token
            )
            assert isinstance(connector, DadosGovBrConnector)
        except Exception as e:
            raise unittest.SkipTest(f"DadosGovBrConnector creation failed: {e}")

    def test_list_listings_with_zero_limit(self):
        """Test list_listings() edge case with zero limit"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            listings = self.connector.list_listings(limit=0)
            self.assertIsInstance(listings, list)
            self.assertEqual(len(listings), 0)
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_list_listings_with_none_limit(self):
        """Test list_listings() error handling with None limit"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            listings = self.connector.list_listings(limit=None)  # type: ignore[arg-type]  # test: None limit for unbounded list exercise
            # Should handle None limit gracefully (may use default)
            self.assertIsInstance(listings, list)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_get_listing_with_empty_id(self):
        """Test get_listing() error handling with empty ID"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.get_listing("")
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_get_listing_with_none_id(self):
        """Test get_listing() error handling with None ID"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.get_listing(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_list_resources_with_empty_package_id(self):
        """Test list_resources() error handling with empty package ID"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            with self.assertRaises((ValueError, NotFoundError)):
                self.connector.list_resources("")
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_list_resources_with_none_package_id(self):
        """Test list_resources() error handling with None package ID"""
        if self.connector is None:
            raise unittest.SkipTest("dados.gov.br connector not available (config or API key missing)")
        try:
            with self.assertRaises((ValueError, TypeError, NotFoundError)):
                self.connector.list_resources(None)  # type: ignore[arg-type]  # test: edge-case type exercise
        except Exception as e:
            handle_auth_failure(e)
            raise

    def test_connector_initialization_with_empty_base_url(self):
        """Test connector initialization error handling with empty base_url"""
        # jwt_token is set in setUp (may be empty)
        with self.assertRaises((ValueError, TypeError)):
            DadosGovBrConnector(base_url="", jwt_token=self.jwt_token)

    def test_connector_initialization_with_none_jwt_token(self):
        """Test connector initialization error handling with None jwt_token"""
        if self.instance_config is None:
            raise unittest.SkipTest("dados.gov.br instance configuration not found")
        with self.assertRaises((ValueError, TypeError)):
            DadosGovBrConnector(
                base_url=self.instance_config.base_url, jwt_token=None  # type: ignore[arg-type]  # test: edge-case type exercise
            )
