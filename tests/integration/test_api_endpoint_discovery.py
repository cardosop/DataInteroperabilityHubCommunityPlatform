"""
Comprehensive integration tests for API endpoint discovery.

Tests verify:
- API info endpoint (/api/v1/) structure and accuracy
- OpenAPI spec generation (JSON and YAML)
- Swagger UI availability (221.4.2: requires auth)
- ReDoc availability (221.4.2: requires auth)
- Endpoint listing accuracy (comparing API info with OpenAPI spec)

Uses REAL services (no mocks/stubs) - always fixing root causes and following
development best practices.
"""
import uuid

import pytest
import json
import yaml
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.urls import get_resolver, URLPattern, URLResolver
from django.conf import settings

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class APIEndpointDiscoveryTest(TestCase):
    """Comprehensive tests for API endpoint discovery"""

    def setUp(self):
        """Set up test fixtures — authenticated client (221.4.2)."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"T {uid}", slug=f"t-disc-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"disc-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_api_info_endpoint_structure(self):
        """Test that /api/v1/ info endpoint returns correct structure"""
        response = self.client.get("/api/v1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify top-level structure
        self.assertIn("name", data)
        self.assertIn("version", data)
        self.assertIn("base_url", data)
        self.assertIn("documentation", data)
        self.assertIn("endpoints", data)

        # Verify name
        self.assertEqual(data["name"], "Interoperable Data Hub API")

        # Verify base_url
        self.assertEqual(data["base_url"], "/api/v1")

        # Verify version is a string
        self.assertIsInstance(data["version"], str)
        self.assertGreater(len(data["version"]), 0)

    def test_api_info_documentation_links(self):
        """Test that API info endpoint includes correct documentation links"""
        response = self.client.get("/api/v1/")
        data = response.json()

        documentation = data.get("documentation", {})
        self.assertIsInstance(documentation, dict)

        # Verify all documentation links are present
        self.assertIn("openapi", documentation)
        self.assertIn("openapi_yaml", documentation)
        self.assertIn("swagger", documentation)
        self.assertIn("redoc", documentation)

        # Verify documentation URLs are correct
        self.assertEqual(documentation["openapi"], "/api-docs/openapi.json")
        self.assertEqual(documentation["openapi_yaml"], "/api/v1/openapi.yaml")
        self.assertEqual(documentation["swagger"], "/api-docs/")
        self.assertEqual(documentation["redoc"], "/api-docs/redoc/")

    def test_api_info_endpoints_list(self):
        """Test that API info endpoint lists all major endpoints"""
        response = self.client.get("/api/v1/")
        data = response.json()

        endpoints = data.get("endpoints", {})
        self.assertIsInstance(endpoints, dict)
        self.assertGreater(len(endpoints), 0)

        # Verify major endpoints are listed
        required_endpoints = [
            "auth",
            "tenants",
            "users",
            "files",
            "datasets",
            "assets",
            "contracts",
            "jobs",
            "dq",
            "compliance",
        ]

        for endpoint_name in required_endpoints:
            self.assertIn(
                endpoint_name,
                endpoints,
                f"Endpoint {endpoint_name} not found in API info endpoints list",
            )

    def test_api_info_endpoint_urls_format(self):
        """Test that endpoint URLs follow consistent format"""
        response = self.client.get("/api/v1/")
        data = response.json()

        endpoints = data.get("endpoints", {})

        # All endpoints should start with /api/v1/
        for endpoint_name, endpoint_url in endpoints.items():
            self.assertTrue(
                endpoint_url.startswith("/api/v1/"),
                f"Endpoint {endpoint_name} URL {endpoint_url} does not start with /api/v1/",
            )
            # Endpoints should end with /
            self.assertTrue(
                endpoint_url.endswith("/"),
                f"Endpoint {endpoint_name} URL {endpoint_url} should end with /",
            )

    def test_openapi_spec_json_available(self):
        """Test that OpenAPI spec in JSON format is available"""
        response = self.client.get("/api/v1/openapi.json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("application/json", response["content-type"].lower())

        spec = response.json()

        # Verify OpenAPI 3.0 structure
        self.assertIn("openapi", spec)
        self.assertIn("info", spec)
        self.assertIn("paths", spec)
        self.assertIn("components", spec)

        # Verify OpenAPI version
        self.assertTrue(
            spec["openapi"].startswith("3."),
            f"Expected OpenAPI 3.x, got {spec['openapi']}",
        )

    def test_openapi_spec_json_structure(self):
        """Test that OpenAPI spec JSON has correct structure"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        # Verify info structure
        info = spec.get("info", {})
        self.assertIn("title", info)
        self.assertIn("version", info)
        self.assertEqual(info["title"], "Interoperable Data Hub API")

        # Verify paths structure
        paths = spec.get("paths", {})
        self.assertIsInstance(paths, dict)
        self.assertGreater(len(paths), 0)

        # Verify components structure
        components = spec.get("components", {})
        self.assertIsInstance(components, dict)

    def test_openapi_spec_yaml_available(self):
        """Test that OpenAPI spec in YAML format is available"""
        response = self.client.get("/api/v1/openapi.yaml")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("yaml", response["content-type"].lower())

        # Verify YAML content is parseable (decode bytes first)
        content = response.content.decode("utf-8")
        spec = yaml.safe_load(content)
        self.assertIn("openapi", spec)
        self.assertIn("info", spec)
        self.assertIn("paths", spec)

    def test_openapi_spec_yaml_structure(self):
        """Test that OpenAPI spec YAML has correct structure"""
        response = self.client.get("/api/v1/openapi.yaml")

        # DRF may parse YAML response as string in response.data, or we need to use response.content
        # Try both approaches
        if hasattr(response, 'data') and isinstance(response.data, str):
            content = response.data
        elif hasattr(response, 'data') and isinstance(response.data, bytes):
            content = response.data.decode("utf-8")
        else:
            # Fallback to response.content
            content = response.content.decode("utf-8") if isinstance(response.content, bytes) else str(response.content)

        spec = yaml.safe_load(content)
        self.assertIsInstance(spec, dict, f"YAML spec should be dict, got {type(spec)}")

        # Verify info structure
        info = spec.get("info", {})
        self.assertIn("title", info)
        self.assertIn("version", info)
        self.assertEqual(info["title"], "Interoperable Data Hub API")

        # Verify paths structure
        paths = spec.get("paths", {})
        self.assertIsInstance(paths, dict)
        self.assertGreater(len(paths), 0)

    def test_openapi_spec_json_yaml_consistency(self):
        """Test that OpenAPI spec JSON and YAML contain same data"""
        json_response = self.client.get("/api/v1/openapi.json")
        yaml_response = self.client.get("/api/v1/openapi.yaml")

        json_spec = json_response.json()

        # DRF may parse YAML response as string in response.data, or we need to use response.content
        # Try both approaches
        if hasattr(yaml_response, 'data') and isinstance(yaml_response.data, str):
            yaml_content = yaml_response.data
        elif hasattr(yaml_response, 'data') and isinstance(yaml_response.data, bytes):
            yaml_content = yaml_response.data.decode("utf-8")
        else:
            # Fallback to response.content
            yaml_content = yaml_response.content.decode("utf-8") if isinstance(yaml_response.content, bytes) else str(yaml_response.content)

        yaml_spec = yaml.safe_load(yaml_content)
        self.assertIsInstance(yaml_spec, dict, f"YAML spec should be dict, got {type(yaml_spec)}")

        # Compare key fields
        self.assertEqual(json_spec["openapi"], yaml_spec["openapi"])
        self.assertEqual(json_spec["info"]["title"], yaml_spec["info"]["title"])
        self.assertEqual(json_spec["info"]["version"], yaml_spec["info"]["version"])

        # Compare paths count (should be same)
        self.assertEqual(len(json_spec["paths"]), len(yaml_spec["paths"]))

    def test_openapi_spec_includes_major_endpoints(self):
        """Test that OpenAPI spec includes all major endpoints"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        paths = spec.get("paths", {})

        # Verify major endpoint categories exist in paths
        required_path_patterns = [
            "/api/v1/auth",
            "/api/v1/assets",
            "/api/v1/contracts",
            "/api/v1/datasets",
            "/api/v1/jobs",
        ]

        path_keys = list(paths.keys())
        for pattern in required_path_patterns:
            # Check if any path contains the pattern
            found = any(pattern in key for key in path_keys)
            self.assertTrue(
                found,
                f"Required path pattern {pattern} not found in OpenAPI spec. "
                f"Available paths (first 10): {path_keys[:10]}",
            )

    def test_openapi_spec_has_request_schemas(self):
        """Test that OpenAPI spec includes request schemas for POST/PUT endpoints"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        paths = spec.get("paths", {})

        # Check that POST endpoints have request bodies
        post_endpoints_with_body = 0
        for path, methods in paths.items():
            if "post" in methods:
                post_method = methods["post"]
                if "requestBody" in post_method:
                    post_endpoints_with_body += 1

        self.assertGreater(
            post_endpoints_with_body,
            0,
            "No POST endpoints with requestBody found in OpenAPI spec",
        )

    def test_openapi_spec_has_response_schemas(self):
        """Test that OpenAPI spec includes response schemas"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        paths = spec.get("paths", {})

        # Check endpoints have responses
        endpoints_with_responses = 0
        for path, methods in paths.items():
            for method_name, method_spec in methods.items():
                if isinstance(method_spec, dict) and "responses" in method_spec:
                    endpoints_with_responses += 1

        self.assertGreater(
            endpoints_with_responses,
            0,
            "No endpoints with responses found in OpenAPI spec",
        )

    def test_swagger_ui_available(self):
        """Test that Swagger UI is available"""
        response = self.client.get("/api-docs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["content-type"].lower())

        # Verify Swagger UI content
        content = response.content.decode("utf-8")
        # Swagger UI typically contains "swagger" or "swagger-ui" in the HTML
        self.assertTrue(
            "swagger" in content.lower() or "swagger-ui" in content.lower(),
            "Swagger UI content not found in response",
        )

    def test_swagger_ui_loads_openapi_spec(self):
        """Test that Swagger UI references OpenAPI spec"""
        response = self.client.get("/api-docs/")
        content = response.content.decode("utf-8")

        # Swagger UI should reference the OpenAPI spec URL
        # Check for common patterns: openapi.json, openapi-schema, etc.
        self.assertTrue(
            "openapi" in content.lower() or "swagger" in content.lower(),
            "Swagger UI does not appear to reference OpenAPI spec",
        )

    def test_redoc_available(self):
        """Test that ReDoc is available"""
        response = self.client.get("/api-docs/redoc/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["content-type"].lower())

        # Verify ReDoc content
        content = response.content.decode("utf-8")
        # ReDoc typically contains "redoc" in the HTML
        self.assertTrue(
            "redoc" in content.lower(),
            "ReDoc content not found in response",
        )

    def test_redoc_loads_openapi_spec(self):
        """Test that ReDoc references OpenAPI spec"""
        response = self.client.get("/api-docs/redoc/")
        content = response.content.decode("utf-8")

        # ReDoc should reference the OpenAPI spec URL
        self.assertTrue(
            "openapi" in content.lower() or "redoc" in content.lower(),
            "ReDoc does not appear to reference OpenAPI spec",
        )

    def test_endpoint_listing_accuracy(self):
        """Test that API info endpoint accurately lists endpoints from OpenAPI spec"""
        # Get API info endpoint
        info_response = self.client.get("/api/v1/")
        info_data = info_response.json()
        info_endpoints = info_data.get("endpoints", {})

        # Get OpenAPI spec
        spec_response = self.client.get("/api/v1/openapi.json")
        spec = spec_response.json()
        spec_paths = spec.get("paths", {})

        # Extract base paths from OpenAPI spec (e.g., /api/v1/assets/ from /api/v1/assets/{id}/)
        spec_base_paths = set()
        for path in spec_paths.keys():
            # Extract base path (remove {id} patterns and trailing slashes)
            base_path = path.split("{")[0].rstrip("/")
            if base_path.startswith("/api/v1/"):
                spec_base_paths.add(base_path)

        # Verify that major endpoints from API info exist in OpenAPI spec
        for endpoint_name, endpoint_url in info_endpoints.items():
            # Remove trailing slash for comparison
            endpoint_path = endpoint_url.rstrip("/")
            # Check if this path or a sub-path exists in OpenAPI spec
            found = any(
                endpoint_path in spec_path or spec_path.startswith(endpoint_path)
                for spec_path in spec_base_paths
            )
            self.assertTrue(
                found,
                f"Endpoint {endpoint_name} ({endpoint_url}) from API info not found in OpenAPI spec. "
                f"Available paths (first 10): {list(spec_base_paths)[:10]}",
            )

    def test_api_info_endpoint_accuracy_comprehensive(self):
        """Comprehensive test of API info endpoint accuracy"""
        response = self.client.get("/api/v1/")
        data = response.json()

        endpoints = data.get("endpoints", {})

        # Verify endpoints are non-empty
        self.assertGreater(len(endpoints), 0, "Endpoints list is empty")

        # Verify all endpoint URLs are valid format
        for endpoint_name, endpoint_url in endpoints.items():
            # Should start with /api/v1/
            self.assertTrue(
                endpoint_url.startswith("/api/v1/"),
                f"Endpoint {endpoint_name} URL {endpoint_url} does not start with /api/v1/",
            )
            # Should end with /
            self.assertTrue(
                endpoint_url.endswith("/"),
                f"Endpoint {endpoint_name} URL {endpoint_url} should end with /",
            )
            # Should not contain double slashes (except after /api/v1/)
            if "//" in endpoint_url.replace("/api/v1/", ""):
                self.fail(
                    f"Endpoint {endpoint_name} URL {endpoint_url} contains double slashes"
                )

    def test_openapi_spec_completeness(self):
        """Test that OpenAPI spec is complete and includes all necessary components"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        # Verify required top-level fields
        required_fields = ["openapi", "info", "paths", "components"]
        for field in required_fields:
            self.assertIn(
                field, spec, f"Required field {field} missing from OpenAPI spec"
            )

        # Verify info has required fields
        info = spec.get("info", {})
        self.assertIn("title", info, "Info.title missing from OpenAPI spec")
        self.assertIn("version", info, "Info.version missing from OpenAPI spec")

        # Verify paths is non-empty
        paths = spec.get("paths", {})
        self.assertGreater(
            len(paths), 0, "OpenAPI spec paths section is empty"
        )

        # Verify components has schemas
        components = spec.get("components", {})
        self.assertIn(
            "schemas", components, "Components.schemas missing from OpenAPI spec"
        )

    def test_openapi_spec_has_security_schemes(self):
        """Test that OpenAPI spec includes security schemes"""
        response = self.client.get("/api/v1/openapi.json")
        spec = response.json()

        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        # Should have at least one security scheme (e.g., ApiKeyAuth, BearerAuth)
        self.assertGreater(
            len(security_schemes),
            0,
            "No security schemes found in OpenAPI spec",
        )

    def test_api_info_endpoint_no_auth_required(self):
        """Test that API info endpoint is accessible without authentication"""
        # Use unauthenticated client
        client = APIClient()
        response = client.get("/api/v1/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "API info endpoint should be accessible without authentication",
        )

    def test_openapi_spec_no_auth_required(self):
        """Test that OpenAPI spec is accessible without authentication"""
        # Use unauthenticated client
        client = APIClient()
        response = client.get("/api/v1/openapi.json")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "OpenAPI spec should be accessible without authentication",
        )

    def test_swagger_ui_requires_auth(self):
        """Swagger UI must reject unauthenticated access (221.4.2)."""
        client = APIClient()
        response = client.get("/api-docs/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            "Swagger UI must reject unauthenticated requests",
        )

    def test_redoc_requires_auth(self):
        """ReDoc must reject unauthenticated access (221.4.2)."""
        client = APIClient()
        response = client.get("/api-docs/redoc/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
            "ReDoc must reject unauthenticated requests",
        )

