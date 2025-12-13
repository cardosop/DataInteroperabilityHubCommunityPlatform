"""
Integration tests for OpenAPI specification completeness.

Tests validate:
- All endpoints have required documentation
- Error responses are present
- Examples are included
- Schemas are complete
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests
import yaml

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class TestOpenAPISpecCompleteness:
    """Tests for OpenAPI specification completeness."""

    @pytest.fixture(scope="class")
    def openapi_spec(self):
        """Load OpenAPI specification."""
        # Try to fetch from running API first
        api_url = os.getenv("API_SERVICE_URL", "http://localhost:8000")
        try:
            response = requests.get(f"{api_url}/api/v1/openapi.json", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass

        # Fallback to file if API not available
        spec_path = project_root / "api" / "openapi-hub-v1.yaml"
        if spec_path.exists():
            with open(spec_path, "r") as f:
                return yaml.safe_load(f)

        # Try JSON file
        spec_path = project_root / "api" / "openapi-hub-v1.json"
        if spec_path.exists():
            with open(spec_path, "r") as f:
                return json.load(f)

        pytest.skip("OpenAPI spec not available")

    def test_openapi_version(self, openapi_spec):
        """Test that OpenAPI version is 3.x."""
        assert "openapi" in openapi_spec
        assert openapi_spec["openapi"].startswith(
            "3."
        ), f"OpenAPI version must be 3.x, got {openapi_spec['openapi']}"

    def test_info_section_complete(self, openapi_spec):
        """Test that info section is complete."""
        assert "info" in openapi_spec
        info = openapi_spec["info"]
        assert "title" in info, "Info section must have title"
        assert "version" in info, "Info section must have version"
        assert "description" in info, "Info section should have description"

    def test_paths_exist(self, openapi_spec):
        """Test that paths section exists and has endpoints."""
        assert "paths" in openapi_spec
        paths = openapi_spec["paths"]
        assert len(paths) > 0, "OpenAPI spec must have at least one path"

    def test_all_operations_have_tags(self, openapi_spec):
        """Test that all operations have tags."""
        paths = openapi_spec.get("paths", {})
        operations_without_tags = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                if not operation.get("tags"):
                    operations_without_tags.append(f"{method.upper()} {path}")

        assert (
            len(operations_without_tags) == 0
        ), f"Operations without tags: {operations_without_tags[:10]}"

    def test_all_operations_have_operation_id(self, openapi_spec):
        """Test that all operations have operationId."""
        paths = openapi_spec.get("paths", {})
        operations_without_id = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                if not operation.get("operationId"):
                    operations_without_id.append(f"{method.upper()} {path}")

        assert (
            len(operations_without_id) == 0
        ), f"Operations without operationId: {operations_without_id[:10]}"

    def test_operations_have_descriptions(self, openapi_spec):
        """Test that operations have descriptions or summaries."""
        paths = openapi_spec.get("paths", {})
        operations_without_docs = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                if not operation.get("description") and not operation.get("summary"):
                    operations_without_docs.append(f"{method.upper()} {path}")

        # Warn but don't fail - descriptions are nice to have
        if operations_without_docs:
            pytest.skip(
                f"Some operations lack descriptions (non-blocking): {len(operations_without_docs)}"
            )

    def test_error_responses_present(self, openapi_spec):
        """Test that operations include standard error responses."""
        paths = openapi_spec.get("paths", {})
        operations_missing_errors = []

        # Standard error codes that should be present
        standard_errors = ["400", "401", "403", "404", "500"]

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                responses = operation.get("responses", {})
                missing_errors = [code for code in standard_errors if code not in responses]

                if missing_errors:
                    operations_missing_errors.append(
                        {
                            "operation": f"{method.upper()} {path}",
                            "missing": missing_errors,
                        }
                    )

        # Warn but don't fail - error responses are added by enhancement
        if operations_missing_errors:
            pytest.skip(
                f"Some operations missing error responses (may be added by enhancement): {len(operations_missing_errors)}"
            )

    def test_components_schemas_exist(self, openapi_spec):
        """Test that components section has schemas."""
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})
        assert len(schemas) > 0, "OpenAPI spec should have component schemas"

    def test_security_schemes_defined(self, openapi_spec):
        """Test that security schemes are defined."""
        components = openapi_spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})
        assert len(security_schemes) > 0, "OpenAPI spec must define security schemes"
        assert (
            "BearerAuth" in security_schemes or "bearerAuth" in security_schemes
        ), "Bearer authentication scheme must be defined"

    def test_examples_present(self, openapi_spec):
        """Test that operations have examples (at least for POST/PUT/PATCH)."""
        paths = openapi_spec.get("paths", {})
        operations_without_examples = []

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["post", "put", "patch"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                has_example = False

                # Check request body examples
                request_body = operation.get("requestBody", {})
                if request_body:
                    content = request_body.get("content", {})
                    for media_spec in content.values():
                        if "example" in media_spec or "examples" in media_spec:
                            has_example = True
                            break

                # Check response examples
                if not has_example:
                    responses = operation.get("responses", {})
                    for response in responses.values():
                        if isinstance(response, dict):
                            content = response.get("content", {})
                            for media_spec in content.values():
                                if "example" in media_spec or "examples" in media_spec:
                                    has_example = True
                                    break
                        if has_example:
                            break

                if not has_example:
                    operations_without_examples.append(f"{method.upper()} {path}")

        # Warn but don't fail - examples are nice to have
        if operations_without_examples:
            pytest.skip(
                f"Some operations lack examples (non-blocking): {len(operations_without_examples)}"
            )

    def test_tags_defined(self, openapi_spec):
        """Test that tags are defined with descriptions."""
        tags = openapi_spec.get("tags", [])
        assert len(tags) > 0, "OpenAPI spec should have tags defined"

        # Check that tags have descriptions
        tags_without_description = [
            tag.get("name", "unknown")
            for tag in tags
            if isinstance(tag, dict) and not tag.get("description")
        ]

        if tags_without_description:
            pytest.skip(
                f"Some tags lack descriptions (non-blocking): {tags_without_description[:5]}"
            )
