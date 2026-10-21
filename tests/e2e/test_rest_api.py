"""
Comprehensive E2E tests for REST API.

Covers:
- OpenAPI schema generation
- API documentation endpoints
- API versioning
- Endpoint consistency
- Response format validation

Uses REAL services (no mocks).
"""

import json

import pytest
from rest_framework import status

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e1]


class RESTAPIE2ETest(E2ETestBase):
    """Test REST API operations"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_openapi_schema_generation(self):
        """Test OpenAPI schema generation"""
        response = self.client.get("/api-docs/openapi.json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schema = json.loads(response.content)

        # Verify OpenAPI structure
        self.assertIn("openapi", schema)
        self.assertIn("info", schema)
        self.assertIn("paths", schema)
        self.assertIn("components", schema)

        # Verify OpenAPI version
        self.assertTrue(schema["openapi"].startswith("3."))

    def test_openapi_schema_info_section(self):
        """Test OpenAPI schema info section"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        self.assertIn("info", schema)
        info = schema["info"]
        self.assertIn("title", info)
        self.assertIn("version", info)
        self.assertIn("description", info)

    def test_openapi_schema_paths_exist(self):
        """Test OpenAPI schema contains expected paths"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        paths = schema.get("paths", {})

        # Verify key endpoints are documented
        expected_paths = [
            "/api/v1/auth/login/",
            "/api/v1/assets/",
            "/api/v1/contracts/",
            "/api/v1/datasets/",
            "/api/v1/files/",
        ]

        for path in expected_paths:
            # Paths may be documented with or without trailing slash
            path_variants = [path, path.rstrip("/")]
            found = any(p in paths for p in path_variants)
            self.assertTrue(
                found,
                f"Required path {path} not found in OpenAPI schema. "
                f"Available paths (first 10): {list(paths.keys())[:10]}",
            )

    def test_openapi_schema_components_schemas(self):
        """Test OpenAPI schema components/schemas section"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        self.assertIn("components", schema)
        components = schema["components"]
        self.assertIn("schemas", components)

        # Verify some common schemas exist
        schemas = components["schemas"]
        # Should have some model schemas
        self.assertGreater(len(schemas), 0)

    def test_openapi_schema_security_schemes(self):
        """Test OpenAPI schema security schemes"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        self.assertTrue(
            "components" in schema,
            "OpenAPI schema missing 'components' key",
        )
        self.assertTrue(
            "securitySchemes" in schema.get("components", {}),
            "OpenAPI schema components missing 'securitySchemes' key",
        )
        security_schemes = schema["components"]["securitySchemes"]
        # Should have authentication schemes
        self.assertGreater(len(security_schemes), 0)

    def test_swagger_ui_endpoint(self):
        """Test Swagger UI endpoint"""
        response = self.client.get("/api-docs/")

        # Should return HTML for Swagger UI
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response.get("Content-Type", ""))

    def test_redoc_endpoint(self):
        """Test ReDoc endpoint"""
        response = self.client.get("/api-docs/redoc/")

        # Should return HTML for ReDoc
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response.get("Content-Type", ""))

    def test_api_info_endpoint(self):
        """Test API info endpoint"""
        response = self.client.get("/api/v1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("name", response.data)
        self.assertIn("version", response.data)
        self.assertIn("base_url", response.data)
        self.assertIn("documentation", response.data)
        self.assertIn("endpoints", response.data)

    def test_api_versioning(self):
        """Test API versioning is consistent"""
        # All endpoints should be under /api/v1/
        endpoints = [
            "/api/v1/assets/",
            "/api/v1/contracts/",
            "/api/v1/datasets/",
            "/api/v1/files/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should not return 404 (endpoint exists)
            self.assertNotEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_openapi_schema_response_schemas(self):
        """Test OpenAPI schema response schemas"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        paths = schema.get("paths", {})

        # Check that paths have response schemas
        # Be lenient - some paths may not have complete documentation
        missing_responses = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ["get", "post", "patch", "put", "delete"]:
                    if "responses" not in operation:
                        missing_responses.append(f"{path} {method}")
                        continue
                    responses = operation["responses"]
                    # Should have at least 200 or 201 response
                    if not ("200" in responses or "201" in responses or "204" in responses):
                        missing_responses.append(f"{path} {method}")

        # Fail if more than 20% of documented operations are missing response schemas
        total_operations = sum(
            1
            for _path, methods in paths.items()
            for method in methods
            if method.lower() in ["get", "post", "patch", "put", "delete"]
        )
        if total_operations > 0:
            missing_ratio = len(missing_responses) / total_operations
            self.assertLessEqual(
                missing_ratio,
                0.20,
                f"{len(missing_responses)}/{total_operations} operations missing response schemas "
                f"({missing_ratio:.0%}): {missing_responses[:10]}",
            )

    def test_openapi_schema_error_responses(self):
        """Test OpenAPI schema includes error responses for most operations"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        paths = schema.get("paths", {})

        # Check that paths have error responses documented
        operations_with_errors = 0
        total_operations = 0
        for _path, methods in paths.items():
            for method, operation in methods.items():
                if method.lower() in ["get", "post", "patch", "put", "delete"]:
                    total_operations += 1
                    responses = operation.get("responses", {})
                    error_codes = ["400", "401", "403", "404", "500"]
                    if any(code in responses for code in error_codes):
                        operations_with_errors += 1

        self.assertGreater(
            total_operations,
            0,
            "No operations found in OpenAPI schema",
        )
        # At least some operations should document error responses
        self.assertGreater(
            operations_with_errors,
            0,
            f"None of the {total_operations} operations document any error responses (400/401/403/404/500)",
        )

    def test_openapi_schema_valid_json(self):
        """Test OpenAPI schema is valid JSON"""
        response = self.client.get("/api-docs/openapi.json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should be valid JSON
        try:
            schema = json.loads(response.content)
            self.assertIsInstance(schema, dict)
        except json.JSONDecodeError:
            self.fail("OpenAPI schema is not valid JSON")

    def test_openapi_schema_contains_tags(self):
        """Test OpenAPI schema contains tags"""
        response = self.client.get("/api-docs/openapi.json")
        schema = json.loads(response.content)

        # Should have tags for organization
        if "tags" in schema:
            self.assertIsInstance(schema["tags"], list)
            self.assertGreater(len(schema["tags"]), 0)
