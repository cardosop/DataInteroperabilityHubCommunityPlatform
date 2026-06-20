"""
OpenAPI Spec Validation

Validation and enhancement of OpenAPI specifications.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
import yaml

logger = structlog.get_logger(__name__)


class OpenAPISpecValidator:
    """
    Validator for OpenAPI specifications.
    """

    @staticmethod
    def validate_spec(spec: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate OpenAPI 3.0 specification.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        required_fields = ["openapi", "info", "paths"]
        for field in required_fields:
            if field not in spec:
                errors.append(f"Missing required field: {field}")

        # Validate OpenAPI version
        if "openapi" in spec:
            version = spec["openapi"]
            if not version.startswith("3."):
                errors.append(f"Unsupported OpenAPI version: {version}. Expected 3.x")

        # Validate info section
        if "info" in spec:
            info = spec["info"]
            if "title" not in info:
                errors.append("Missing 'title' in info section")
            if "version" not in info:
                errors.append("Missing 'version' in info section")

        # Validate paths section
        if "paths" in spec:
            paths = spec["paths"]
            if not isinstance(paths, dict):
                errors.append("'paths' must be a dictionary")
            else:
                for path, path_item in paths.items():
                    if not path.startswith("/"):
                        errors.append(f"Path must start with '/': {path}")

                    # Validate path item
                    if isinstance(path_item, dict):
                        valid_methods = [
                            "get",
                            "post",
                            "put",
                            "patch",
                            "delete",
                            "head",
                            "options",
                            "trace",
                        ]
                        for method, operation in path_item.items():
                            if method.lower() in valid_methods:
                                if not isinstance(operation, dict):
                                    errors.append(
                                        f"Operation for {method} {path} must be a dictionary"
                                    )

        return len(errors) == 0, errors

    @staticmethod
    def enhance_spec(spec: dict[str, Any]) -> dict[str, Any]:
        """
        Enhance OpenAPI specification with additional metadata.

        Args:
            spec: OpenAPI specification dictionary

        Returns:
            Enhanced specification
        """
        # Ensure info section exists
        if "info" not in spec:
            spec["info"] = {}

        # Add contact information if not present
        if "contact" not in spec["info"]:
            spec["info"]["contact"] = {
                "name": "API Support",
                "email": "support@datahub.example.com",
            }

        # Add license information if not present
        if "license" not in spec["info"]:
            spec["info"]["license"] = {"name": "Proprietary"}

        # Add servers if not present
        if "servers" not in spec:
            spec["servers"] = [{"url": "/api/v1", "description": "API v1 Server"}]

        # Add security schemes if not present
        if "components" not in spec:
            spec["components"] = {}

        if "securitySchemes" not in spec["components"]:
            spec["components"]["securitySchemes"] = {
                "BearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
            }

        # Add global security requirement
        if "security" not in spec:
            spec["security"] = [{"BearerAuth": []}]

        return spec

    @staticmethod
    def export_spec(spec: dict[str, Any], format: str = "json") -> str:
        """
        Export OpenAPI specification to string format.

        Args:
            spec: OpenAPI specification dictionary
            format: 'json' or 'yaml'

        Returns:
            Specification as string
        """
        if format.lower() == "yaml":
            return yaml.dump(spec, default_flow_style=False, sort_keys=False)
        else:
            return json.dumps(spec, indent=2, sort_keys=False)
