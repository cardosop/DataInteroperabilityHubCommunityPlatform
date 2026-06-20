#!/usr/bin/env python3
"""
Postman Collection Generator

Generates a Postman collection from the OpenAPI specification.
This script fetches the OpenAPI spec from a running API server and converts it to Postman Collection v2.1 format.
"""

import argparse
import json
import sys
from typing import Any

import requests
import yaml


class PostmanCollectionGenerator:
    """Generates Postman collections from OpenAPI specifications."""

    def __init__(self, openapi_spec: dict[str, Any], base_url: str = "http://localhost:8000"):
        """
        Initialize generator with OpenAPI spec.

        Args:
            openapi_spec: OpenAPI specification dictionary
            base_url: Base URL for API requests
        """
        self.spec = openapi_spec
        self.base_url = base_url.rstrip("/")
        self.collection = {
            "info": {
                "name": self.spec.get("info", {}).get("title", "API Collection"),
                "description": self.spec.get("info", {}).get("description", ""),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                "_postman_id": "550e8400-e29b-41d4-a716-446655440000",
            },
            "item": [],
            "variable": [
                {"key": "base_url", "value": self.base_url, "type": "string"},
                {"key": "api_version", "value": "v1", "type": "string"},
            ],
        }

    def generate(self) -> dict[str, Any]:
        """Generate Postman collection from OpenAPI spec."""
        # Group endpoints by tags
        endpoints_by_tag: dict[str, list[dict[str, Any]]] = {}

        paths = self.spec.get("paths", {})
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method not in ["get", "post", "put", "patch", "delete"]:
                    continue

                if not isinstance(operation, dict):
                    continue

                # Get tags (default to "API" if no tags)
                tags = operation.get("tags", ["API"])
                tag = tags[0] if tags else "API"

                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []

                # Create Postman request
                request = self._create_request(path, method, operation)
                endpoints_by_tag[tag].append(request)

        # Create collection items grouped by tags
        for tag, requests in sorted(endpoints_by_tag.items()):
            folder = {
                "name": tag,
                "item": requests,
                "description": self._get_tag_description(tag),
            }
            self.collection["item"].append(folder)

        # Add authentication helpers
        self._add_auth_helpers()

        return self.collection

    def _create_request(self, path: str, method: str, operation: dict[str, Any]) -> dict[str, Any]:
        """Create a Postman request from OpenAPI operation."""
        # Build full URL
        full_path = path
        if not full_path.startswith("/"):
            full_path = f"/{full_path}"

        # Replace path parameters with Postman variables
        path_with_vars = full_path.replace("{", "{{").replace("}", "}}")
        url = f"{{{{base_url}}}}/api/{{{{api_version}}}}{path_with_vars}"

        # Create request
        request: dict[str, Any] = {
            "name": operation.get(
                "summary", operation.get("operationId", f"{method.upper()} {path}")
            ),
            "request": {
                "method": method.upper(),
                "header": [],
                "url": {
                    "raw": url,
                    "host": ["{{base_url}}"],
                    "path": ["api", "{{api_version}}"] + full_path.split("/")[1:],
                },
                "description": operation.get("description", ""),
            },
            "response": [],
        }

        # Add query parameters
        parameters = operation.get("parameters", [])
        query_params = []
        path_params = []
        header_params = []

        for param in parameters:
            param_in = param.get("in", "query")
            param_schema = param.get("schema", {})
            param_example = param.get("example", param_schema.get("default", ""))

            param_obj = {
                "key": param.get("name", ""),
                "value": str(param_example) if param_example else "",
                "description": param.get("description", ""),
            }

            if param_in == "query":
                query_params.append(param_obj)
            elif param_in == "path":
                path_params.append(param_obj)
            elif param_in == "header":
                header_params.append(param_obj)

        if query_params:
            request["request"]["url"]["query"] = query_params

        # Add path variables
        if path_params:
            request["request"]["url"]["variable"] = [
                {"key": p["key"], "value": p["value"], "description": p.get("description", "")}
                for p in path_params
            ]

        # Add headers
        if header_params:
            request["request"]["header"] = [
                {"key": p["key"], "value": p["value"], "description": p.get("description", "")}
                for p in header_params
            ]

        # Add authentication header
        request["request"]["header"].append(
            {
                "key": "Authorization",
                "value": "Bearer {{access_token}}",
                "type": "text",
                "description": "JWT Bearer token",
            }
        )

        # Add request body
        request_body = operation.get("requestBody", {})
        if request_body:
            content = request_body.get("content", {})
            json_content = content.get("application/json", {})
            if json_content:
                schema = json_content.get("schema", {})
                example = json_content.get("example")

                if example:
                    request["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(example, indent=2),
                        "options": {"raw": {"language": "json"}},
                    }
                elif schema:
                    # Generate example from schema
                    example = self._generate_example_from_schema(schema)
                    request["request"]["body"] = {
                        "mode": "raw",
                        "raw": json.dumps(example, indent=2),
                        "options": {"raw": {"language": "json"}},
                    }

        # Add response examples
        responses = operation.get("responses", {})
        for status_code, response in responses.items():
            if status_code.startswith("2"):  # Success responses
                content = response.get("content", {})
                json_content = content.get("application/json", {})
                if json_content:
                    example = json_content.get("example")
                    if example:
                        request["response"].append(
                            {
                                "name": f"{status_code} {response.get('description', 'Success')}",
                                "originalRequest": request["request"].copy(),
                                "status": response.get("description", "OK"),
                                "code": int(status_code),
                                "_postman_previewlanguage": "json",
                                "header": [{"key": "Content-Type", "value": "application/json"}],
                                "body": json.dumps(example, indent=2),
                            }
                        )

        return request

    def _generate_example_from_schema(self, schema: dict[str, Any]) -> Any:
        """Generate example value from JSON schema."""
        schema_type = schema.get("type", "object")

        if schema_type == "object":
            example = {}
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if isinstance(prop_schema, dict):
                    example[prop_name] = self._generate_example_from_schema(prop_schema)
                else:
                    example[prop_name] = None
            return example
        elif schema_type == "array":
            items_schema = schema.get("items", {})
            return [self._generate_example_from_schema(items_schema)]
        elif schema_type == "string":
            return schema.get("example", "string")
        elif schema_type == "integer":
            return schema.get("example", 0)
        elif schema_type == "number":
            return schema.get("example", 0.0)
        elif schema_type == "boolean":
            return schema.get("example", True)
        else:
            return None

    def _get_tag_description(self, tag: str) -> str:
        """Get description for a tag from OpenAPI spec."""
        tags = self.spec.get("tags", [])
        for tag_obj in tags:
            if isinstance(tag_obj, dict) and tag_obj.get("name") == tag:
                return tag_obj.get("description", "")
        return ""

    def _add_auth_helpers(self):
        """Add authentication helper requests."""
        auth_folder = {
            "name": "Authentication",
            "item": [
                {
                    "name": "Login",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps(
                                {"email": "user@example.com", "password": "your-password"},
                                indent=2,
                            ),
                            "options": {"raw": {"language": "json"}},
                        },
                        "url": {
                            "raw": "{{base_url}}/api/{{api_version}}/auth/login/",
                            "host": ["{{base_url}}"],
                            "path": ["api", "{{api_version}}", "auth", "login"],
                        },
                    },
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "exec": [
                                    "if (pm.response.code === 200) {",
                                    "    var jsonData = pm.response.json();",
                                    "    pm.environment.set('access_token', jsonData.access_token);",
                                    "    if (jsonData.refresh_token) {",
                                    "        pm.environment.set('refresh_token', jsonData.refresh_token);",
                                    "    }",
                                    "}",
                                ],
                                "type": "text/javascript",
                            },
                        }
                    ],
                },
                {
                    "name": "Refresh Token",
                    "request": {
                        "method": "POST",
                        "header": [{"key": "Content-Type", "value": "application/json"}],
                        "body": {
                            "mode": "raw",
                            "raw": json.dumps({"refresh_token": "{{refresh_token}}"}, indent=2),
                            "options": {"raw": {"language": "json"}},
                        },
                        "url": {
                            "raw": "{{base_url}}/api/{{api_version}}/auth/refresh/",
                            "host": ["{{base_url}}"],
                            "path": ["api", "{{api_version}}", "auth", "refresh"],
                        },
                    },
                    "event": [
                        {
                            "listen": "test",
                            "script": {
                                "exec": [
                                    "if (pm.response.code === 200) {",
                                    "    var jsonData = pm.response.json();",
                                    "    pm.environment.set('access_token', jsonData.access_token);",
                                    "}",
                                ],
                                "type": "text/javascript",
                            },
                        }
                    ],
                },
            ],
        }

        # Insert auth folder at the beginning
        self.collection["item"].insert(0, auth_folder)


def fetch_openapi_spec(url: str) -> dict[str, Any]:
    """Fetch OpenAPI spec from URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "yaml" in content_type or url.endswith(".yaml") or url.endswith(".yml"):
            return yaml.safe_load(response.text)
        else:
            return response.json()
    except requests.RequestException as e:
        print(f"Error fetching OpenAPI spec: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate Postman collection from OpenAPI spec")
    parser.add_argument(
        "--spec-url",
        default="http://localhost:8000/api-docs/openapi.json",
        help="URL to OpenAPI specification (default: http://localhost:8000/api-docs/openapi.json)",
    )
    parser.add_argument(
        "--spec-file",
        help="Path to OpenAPI specification file (JSON or YAML)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for API requests (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--output",
        default="postman_collection.json",
        help="Output file path (default: postman_collection.json)",
    )

    args = parser.parse_args()

    # Load OpenAPI spec
    if args.spec_file:
        with open(args.spec_file, encoding="utf-8") as f:
            if args.spec_file.endswith((".yaml", ".yml")):
                spec = yaml.safe_load(f)
            else:
                spec = json.load(f)
    else:
        spec = fetch_openapi_spec(args.spec_url)

    # Generate Postman collection
    generator = PostmanCollectionGenerator(spec, base_url=args.base_url)
    collection = generator.generate()

    # Write collection to file
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)

    print(f"Postman collection generated: {args.output}")
    print(f"Collection contains {len(collection['item'])} folders")


if __name__ == "__main__":
    main()
