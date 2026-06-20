"""
Tests for Django API URL Builder utility.

Tests ensure URL construction follows naming standards and prevents duplication.
"""

from django.test import TestCase

from hub.apps.api.utils.api_url_builder import APIURLBuilder, build_api_url, build_full_api_url


class APIURLBuilderTest(TestCase):
    """Test API URL Builder functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.builder = APIURLBuilder()

    def test_build_simple_resource_url(self):
        """Test building a simple resource URL"""
        url = self.builder.build("contracts")
        self.assertEqual(url, "/api/v1/contracts/")

    def test_build_resource_with_id(self):
        """Test building a resource URL with ID"""
        url = self.builder.build("contracts", resource_id="123")
        self.assertEqual(url, "/api/v1/contracts/123/")

    def test_build_resource_with_action(self):
        """Test building a resource URL with action"""
        url = self.builder.build("contracts", resource_id="123", action="lineage-visualization")
        self.assertEqual(url, "/api/v1/contracts/123/lineage-visualization/")

    def test_build_resource_with_query_params(self):
        """Test building a resource URL with query parameters"""
        url = self.builder.build(
            "contracts", query_params={"format": "json", "include": "metadata"}
        )
        self.assertIn("format=json", url)
        self.assertIn("include=metadata", url)
        self.assertTrue(url.startswith("/api/v1/contracts/"))

    def test_build_kebab_case_validation(self):
        """Test that kebab-case validation works"""
        # Valid kebab-case
        url = self.builder.build("data-assets")
        self.assertEqual(url, "/api/v1/data-assets/")

        # Invalid snake_case should raise ValueError
        with self.assertRaises(ValueError) as cm:
            self.builder.build("data_assets")
        self.assertIn("kebab-case", str(cm.exception))

        # Invalid camelCase should raise ValueError
        with self.assertRaises(ValueError) as cm:
            self.builder.build("dataAssets")
        self.assertIn("kebab-case", str(cm.exception))

    def test_build_action_kebab_case_validation(self):
        """Test that action names must be kebab-case"""
        # Valid kebab-case action
        url = self.builder.build("contracts", resource_id="123", action="lineage-visualization")
        self.assertEqual(url, "/api/v1/contracts/123/lineage-visualization/")

        # Invalid camelCase action should raise ValueError
        with self.assertRaises(ValueError) as cm:
            self.builder.build("contracts", resource_id="123", action="lineageVisualization")
        self.assertIn("kebab-case", str(cm.exception))

    def test_build_full_url(self):
        """Test building a full URL with base URL"""
        url = self.builder.build_full_url(
            "contracts", resource_id="123", base_url="http://example.com"
        )
        self.assertEqual(url, "http://example.com/api/v1/contracts/123/")

    def test_build_full_url_default_base(self):
        """Test building full URL with default base URL"""
        url = self.builder.build_full_url("contracts")
        self.assertTrue(url.startswith("http://"))
        self.assertIn("/api/v1/contracts/", url)

    def test_validate_url_valid(self):
        """Test URL validation with valid URLs"""
        is_valid, error = self.builder.validate_url("/api/v1/contracts/")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = self.builder.validate_url("/api/v1/contracts/123/")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        is_valid, error = self.builder.validate_url("/api/v1/data-assets/")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_url_invalid_base(self):
        """Test URL validation with invalid base path"""
        is_valid, error = self.builder.validate_url("/api/v2/contracts/")
        self.assertFalse(is_valid)
        self.assertIn("must start with", error)

    def test_validate_url_duplicate_segments(self):
        """Test URL validation detects duplicate segments"""
        is_valid, error = self.builder.validate_url("/api/v1/contracts/contracts/")
        self.assertFalse(is_valid)
        self.assertIn("Duplicate segment", error)

    def test_validate_url_invalid_kebab_case(self):
        """Test URL validation detects invalid kebab-case"""
        is_valid, error = self.builder.validate_url("/api/v1/data_assets/")
        self.assertFalse(is_valid)
        self.assertIn("kebab-case", error)

    def test_validate_url_uuid_allowed(self):
        """Test that UUIDs are allowed in URLs"""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        is_valid, error = self.builder.validate_url(f"/api/v1/contracts/{uuid}/")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_convenience_function_build_api_url(self):
        """Test convenience function build_api_url"""
        url = build_api_url("contracts", resource_id="123")
        self.assertEqual(url, "/api/v1/contracts/123/")

    def test_convenience_function_build_full_api_url(self):
        """Test convenience function build_full_api_url"""
        url = build_full_api_url("contracts", resource_id="123", base_url="http://test.com")
        self.assertEqual(url, "http://test.com/api/v1/contracts/123/")

    def test_build_with_plural_resources(self):
        """Test building URLs with plural resource names"""
        url = self.builder.build("contracts")
        self.assertEqual(url, "/api/v1/contracts/")

        url = self.builder.build("data-assets")
        self.assertEqual(url, "/api/v1/data-assets/")

        url = self.builder.build("scheduled-ingestions")
        self.assertEqual(url, "/api/v1/scheduled-ingestions/")

    def test_build_normalizes_slashes(self):
        """Test that URL builder normalizes multiple slashes"""
        # Should handle base_path with trailing slash
        builder = APIURLBuilder(base_path="/api/v1/")
        url = builder.build("contracts")
        self.assertEqual(url, "/api/v1/contracts/")

        # Should normalize multiple slashes
        builder = APIURLBuilder(base_path="//api//v1//")
        url = builder.build("contracts")
        self.assertEqual(url, "/api/v1/contracts/")

    def test_build_with_complex_action(self):
        """Test building URL with complex action name"""
        url = self.builder.build(
            "contracts", resource_id="123", action="lineage-visualization-custom"
        )
        self.assertEqual(url, "/api/v1/contracts/123/lineage-visualization-custom/")

    def test_build_with_numeric_id(self):
        """Test building URL with numeric ID"""
        url = self.builder.build("contracts", resource_id="12345")
        self.assertEqual(url, "/api/v1/contracts/12345/")

    def test_is_kebab_case_helper(self):
        """Test kebab-case validation helper"""
        # Valid cases
        self.assertTrue(APIURLBuilder._is_kebab_case("contracts"))
        self.assertTrue(APIURLBuilder._is_kebab_case("data-assets"))
        self.assertTrue(APIURLBuilder._is_kebab_case("scheduled-ingestions"))
        self.assertTrue(APIURLBuilder._is_kebab_case("lineage-visualization"))

        # Invalid cases
        self.assertFalse(APIURLBuilder._is_kebab_case("dataAssets"))
        self.assertFalse(APIURLBuilder._is_kebab_case("data_assets"))
        self.assertFalse(APIURLBuilder._is_kebab_case("DataAssets"))
        self.assertFalse(APIURLBuilder._is_kebab_case("-contracts"))
        self.assertFalse(APIURLBuilder._is_kebab_case("contracts-"))
        self.assertFalse(APIURLBuilder._is_kebab_case("contracts--assets"))
        self.assertFalse(APIURLBuilder._is_kebab_case(""))
        self.assertFalse(APIURLBuilder._is_kebab_case("contracts assets"))
