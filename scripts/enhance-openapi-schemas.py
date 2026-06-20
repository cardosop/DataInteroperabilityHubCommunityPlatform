#!/usr/bin/env python3
"""
Comprehensive OpenAPI Schema Enhancement Script

Enhances all OpenAPI 3.0 specifications with:
- Complete validation rules (required fields, types, formats, enums, min/max, patterns)
- Default values where appropriate
- Comprehensive examples
- Better documentation

This script processes all OpenAPI spec files in docs/api-contracts/missing/
"""

import sys
from pathlib import Path
from typing import Any

import yaml

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class SchemaEnhancer:
    """Comprehensive OpenAPI schema enhancer."""

    def __init__(self):
        self.enhancements_applied = 0
        self.files_processed = 0

    def enhance_all_specs(self, directory: Path) -> None:
        """Enhance all OpenAPI spec files in directory."""
        spec_files = list(directory.rglob("*.yaml")) + list(directory.rglob("*.yml"))

        for spec_file in spec_files:
            if spec_file.name == "README.md":
                continue

            print(f"Processing: {spec_file.relative_to(PROJECT_ROOT)}")
            try:
                self.enhance_spec_file(spec_file)
                self.files_processed += 1
            except Exception as e:
                print(f"  ❌ Error: {e}")
                raise

        print(
            f"\n✅ Enhanced {self.files_processed} files with {self.enhancements_applied} total enhancements"
        )

    def enhance_spec_file(self, file_path: Path) -> None:
        """Enhance a single OpenAPI spec file."""
        # Read spec
        with open(file_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        if not spec or "openapi" not in spec:
            print("  ⚠️  Skipping: Not a valid OpenAPI spec")
            return

        # Enhance schemas
        if "components" in spec and "schemas" in spec["components"]:
            schemas = spec["components"]["schemas"]
            for schema_name, schema in schemas.items():
                if isinstance(schema, dict):
                    enhanced = self.enhance_schema(schema, schema_name)
                    if enhanced:
                        schemas[schema_name] = enhanced
                        self.enhancements_applied += 1

        # Enhance request bodies
        if "paths" in spec:
            for path, path_item in spec["paths"].items():
                if isinstance(path_item, dict):
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "patch", "delete"] and isinstance(
                            operation, dict
                        ):
                            # Enhance request body
                            if "requestBody" in operation:
                                operation["requestBody"] = self.enhance_request_body(
                                    operation["requestBody"], path, method
                                )

                            # Enhance responses
                            if "responses" in operation:
                                operation["responses"] = self.enhance_responses(
                                    operation["responses"], path, method
                                )

        # Write enhanced spec
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(
                spec,
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
                width=120,
                indent=2,
            )

        print("  ✅ Enhanced")

    def enhance_schema(self, schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Enhance a single schema with validation rules, defaults, and examples."""
        if schema.get("type") != "object":
            return schema

        enhanced = schema.copy()
        properties = enhanced.get("properties", {})

        # Apply enhancements based on schema name patterns
        if "Request" in schema_name:
            enhanced = self._enhance_request_schema(enhanced, schema_name)
        elif "Response" in schema_name:
            enhanced = self._enhance_response_schema(enhanced, schema_name)
        elif "Error" in schema_name:
            enhanced = self._enhance_error_schema(enhanced)

        # Enhance all properties
        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                properties[prop_name] = self._enhance_property(prop_schema, prop_name, schema_name)

        enhanced["properties"] = properties
        return enhanced

    def _enhance_request_schema(self, schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Enhance request schema with validation rules."""
        properties = schema.get("properties", {})

        # Common request field enhancements
        field_enhancements = {
            "email": {
                "format": "email",
                "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "maxLength": 255,
                "example": "user@example.com",
            },
            "password": {
                "format": "password",
                "minLength": 8,
                "maxLength": 128,
                "pattern": r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$",
                "description": "Password (min 8 chars, must contain uppercase, lowercase, and number)",
                "example": "SecurePass123",
            },
            "name": {
                "minLength": 1,
                "maxLength": 255,
                "pattern": r"^[a-zA-Z0-9\s\-_\.]+$",
                "example": "John Doe",
            },
            "tenant_id": {"format": "uuid", "example": "550e8400-e29b-41d4-a716-446655440000"},
            "asset_id": {"format": "uuid", "example": "550e8400-e29b-41d4-a716-446655440000"},
            "rating": {"type": "integer", "minimum": 1, "maximum": 5, "example": 5},
            "query": {
                "minLength": 3,
                "maxLength": 500,
                "example": "Find all customer data assets from last month",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 10,
                "example": 20,
            },
            "offset": {"type": "integer", "minimum": 0, "default": 0, "example": 0},
        }

        for prop_name, prop_schema in properties.items():
            if prop_name.lower() in field_enhancements:
                enhancements = field_enhancements[prop_name.lower()]
                for key, value in enhancements.items():
                    if key not in prop_schema:
                        prop_schema[key] = value

        return schema

    def _enhance_response_schema(self, schema: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Enhance response schema with examples."""
        properties = schema.get("properties", {})

        # Common response field enhancements
        field_enhancements = {
            "id": {"format": "uuid", "example": "550e8400-e29b-41d4-a716-446655440000"},
            "created_at": {"format": "date-time", "example": "2025-01-15T10:30:00Z"},
            "updated_at": {"format": "date-time", "example": "2025-01-15T10:30:00Z"},
            "timestamp": {"format": "date-time", "example": "2025-01-15T10:30:00Z"},
        }

        for prop_name, prop_schema in properties.items():
            if prop_name.lower() in field_enhancements:
                enhancements = field_enhancements[prop_name.lower()]
                for key, value in enhancements.items():
                    if key not in prop_schema:
                        prop_schema[key] = value

        return schema

    def _enhance_error_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Enhance error schema with standard error format."""
        # Ensure error schema follows standard format
        if "properties" in schema and "error" in schema["properties"]:
            error_props = schema["properties"]["error"].get("properties", {})

            # Ensure required error fields
            required_fields = ["code", "message", "http_status", "request_id", "timestamp"]
            if "required" not in schema["properties"]["error"]:
                schema["properties"]["error"]["required"] = required_fields

            # Enhance error properties
            if "code" in error_props and "example" not in error_props["code"]:
                error_props["code"]["example"] = "ERROR_CODE"
            if "message" in error_props and "example" not in error_props["message"]:
                error_props["message"]["example"] = "Error message"
            if "http_status" in error_props and "example" not in error_props["http_status"]:
                error_props["http_status"]["example"] = 400
            if "request_id" in error_props and "example" not in error_props["request_id"]:
                error_props["request_id"]["format"] = "uuid"
                error_props["request_id"]["example"] = "550e8400-e29b-41d4-a716-446655440000"
            if "timestamp" in error_props and "example" not in error_props["timestamp"]:
                error_props["timestamp"]["format"] = "date-time"
                error_props["timestamp"]["example"] = "2025-01-15T10:30:00Z"

        return schema

    def _enhance_property(
        self, prop_schema: dict[str, Any], prop_name: str, parent_schema_name: str
    ) -> dict[str, Any]:
        """Enhance a single property with validation rules and defaults."""
        enhanced = prop_schema.copy()
        prop_type = enhanced.get("type")

        # Add validation rules based on type
        if prop_type == "string":
            # Add string validations
            if "format" not in enhanced:
                # Infer format from property name
                if "email" in prop_name.lower():
                    enhanced["format"] = "email"
                    enhanced["pattern"] = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                    enhanced["maxLength"] = 255
                elif "url" in prop_name.lower():
                    enhanced["format"] = "uri"
                elif "date" in prop_name.lower() or "time" in prop_name.lower():
                    enhanced["format"] = "date-time"
                elif "id" in prop_name.lower() and prop_name.endswith("_id"):
                    enhanced["format"] = "uuid"

            # Add length constraints if not present
            if "minLength" not in enhanced and "format" not in enhanced:
                enhanced["minLength"] = 1
            if "maxLength" not in enhanced and "format" not in enhanced:
                enhanced["maxLength"] = 255

        elif prop_type == "integer":
            # Add integer validations
            if "minimum" not in enhanced:
                enhanced["minimum"] = 0
            if "maximum" not in enhanced:
                # Set reasonable maximum based on context
                if "limit" in prop_name.lower() or "page_size" in prop_name.lower():
                    enhanced["maximum"] = 100
                    enhanced["default"] = 10
                elif "page" in prop_name.lower() or "offset" in prop_name.lower():
                    enhanced["maximum"] = 10000
                    enhanced["default"] = 0

        elif prop_type == "number":
            # Add number validations
            if "minimum" not in enhanced:
                enhanced["minimum"] = 0

        elif prop_type == "array":
            # Add array validations
            if "minItems" not in enhanced:
                enhanced["minItems"] = 0
            if "maxItems" not in enhanced:
                enhanced["maxItems"] = 1000
            if "items" in enhanced and isinstance(enhanced["items"], dict):
                enhanced["items"] = self._enhance_property(
                    enhanced["items"], "item", parent_schema_name
                )

        elif prop_type == "object":
            # Recursively enhance nested objects
            if "properties" in enhanced:
                for nested_prop_name, nested_prop_schema in enhanced["properties"].items():
                    if isinstance(nested_prop_schema, dict):
                        enhanced["properties"][nested_prop_name] = self._enhance_property(
                            nested_prop_schema, nested_prop_name, parent_schema_name
                        )

        # Add example if not present
        if "example" not in enhanced:
            enhanced["example"] = self._generate_example(enhanced, prop_name)

        # Add description if not present
        if "description" not in enhanced:
            enhanced["description"] = self._generate_description(enhanced, prop_name)

        return enhanced

    def _generate_example(self, prop_schema: dict[str, Any], prop_name: str) -> Any:
        """Generate example value for property."""
        prop_type = prop_schema.get("type")
        format_type = prop_schema.get("format")
        enum_values = prop_schema.get("enum")

        if enum_values:
            return enum_values[0]

        if format_type == "uuid":
            return "550e8400-e29b-41d4-a716-446655440000"
        elif format_type == "email":
            return "user@example.com"
        elif format_type == "date-time":
            return "2025-01-15T10:30:00Z"
        elif format_type == "date":
            return "2025-01-15"
        elif format_type == "uri":
            return "https://example.com"

        if prop_type == "string":
            if "id" in prop_name.lower():
                return f"{prop_name}_example"
            return f"example_{prop_name}"
        elif prop_type == "integer":
            return prop_schema.get("minimum", 0) or 1
        elif prop_type == "number":
            return 0.0
        elif prop_type == "boolean":
            return False
        elif prop_type == "array":
            return []
        elif prop_type == "object":
            return {}

        return None

    def _generate_description(self, prop_schema: dict[str, Any], prop_name: str) -> str:
        """Generate description for property."""
        prop_type = prop_schema.get("type")
        format_type = prop_schema.get("format")

        # Convert snake_case to Title Case
        words = prop_name.replace("_", " ").title()

        if format_type:
            return f"{words} ({format_type})"
        elif prop_type:
            return f"{words} ({prop_type})"
        else:
            return words

    def enhance_request_body(
        self, request_body: dict[str, Any], path: str, method: str
    ) -> dict[str, Any]:
        """Enhance request body with validation and examples."""
        if "content" not in request_body:
            return request_body

        for content_type, content_schema in request_body["content"].items():
            if content_type == "application/json" and "schema" in content_schema:
                schema_ref = content_schema["schema"]

                # If schema is a reference, we can't enhance it here
                # But we can ensure examples are present
                if "$ref" not in schema_ref and "examples" not in content_schema:
                    # Try to add example based on path/method
                    example = self._generate_request_example(path, method)
                    if example:
                        content_schema["examples"] = {
                            "default": {"summary": "Example request", "value": example}
                        }

        return request_body

    def enhance_responses(
        self, responses: dict[str, Any], path: str, method: str
    ) -> dict[str, Any]:
        """Enhance responses with examples."""
        for status_code, response in responses.items():
            if isinstance(response, dict) and "content" in response:
                for content_type, content_schema in response["content"].items():
                    if content_type == "application/json":
                        # Ensure examples are present
                        if "examples" not in content_schema and "example" not in content_schema:
                            example = self._generate_response_example(path, method, status_code)
                            if example:
                                content_schema["example"] = example

        return responses

    def _generate_request_example(self, path: str, method: str) -> dict[str, Any] | None:
        """Generate request example based on path and method."""
        # Examples are already in the specs, so return None to preserve them
        return None

    def _generate_response_example(
        self, path: str, method: str, status_code: str
    ) -> dict[str, Any] | None:
        """Generate response example based on path, method, and status code."""
        # Examples are already in the specs, so return None to preserve them
        return None


def main():
    """Main entry point."""
    contracts_dir = PROJECT_ROOT / "docs" / "api-contracts" / "missing"

    if not contracts_dir.exists():
        print(f"❌ Directory not found: {contracts_dir}")
        sys.exit(1)

    print(f"Enhancing OpenAPI schemas in: {contracts_dir.relative_to(PROJECT_ROOT)}")
    print("=" * 80)

    enhancer = SchemaEnhancer()
    enhancer.enhance_all_specs(contracts_dir)

    print("\n" + "=" * 80)
    print("✅ Schema enhancement complete!")


if __name__ == "__main__":
    main()
