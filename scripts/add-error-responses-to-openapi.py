#!/usr/bin/env python3
"""
Add Comprehensive Error Responses to OpenAPI Specifications

This script adds complete error response documentation to all OpenAPI 3.0 specs,
including standard error schemas, examples, and comprehensive error codes.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class ErrorResponse:
    """Error response definition"""

    status_code: int
    description: str
    error_code: str
    error_message: str
    example_details: dict | None = None
    headers: dict | None = None


class OpenAPIErrorResponseEnhancer:
    """Enhances OpenAPI specs with comprehensive error responses"""

    def __init__(self):
        # Standard error responses for all endpoints
        self.standard_errors = {
            400: ErrorResponse(
                status_code=400,
                description="Bad Request - Validation error or invalid request data",
                error_code="VALIDATION_ERROR",
                error_message="Invalid request data",
                example_details={
                    "field_errors": [
                        {
                            "field": "email",
                            "message": "Invalid email format",
                            "code": "VALIDATION_ERROR",
                        }
                    ]
                },
            ),
            401: ErrorResponse(
                status_code=401,
                description="Unauthorized - Authentication required",
                error_code="AUTH_UNAUTHORIZED",
                error_message="Authentication required",
            ),
            403: ErrorResponse(
                status_code=403,
                description="Forbidden - Insufficient permissions",
                error_code="AUTH_FORBIDDEN",
                error_message="Permission denied",
            ),
            404: ErrorResponse(
                status_code=404,
                description="Not Found - Resource not found",
                error_code="NOT_FOUND",
                error_message="Resource not found",
            ),
            409: ErrorResponse(
                status_code=409,
                description="Conflict - Resource conflict",
                error_code="CONFLICT_ERROR",
                error_message="Resource conflict",
            ),
            429: ErrorResponse(
                status_code=429,
                description="Too Many Requests - Rate limit exceeded",
                error_code="RATE_LIMIT_EXCEEDED",
                error_message="Rate limit exceeded. Please retry after the specified time.",
                headers={
                    "Retry-After": {
                        "description": "Number of seconds to wait before retrying",
                        "schema": {"type": "integer", "example": 60},
                    },
                    "X-RateLimit-Limit": {
                        "description": "Request limit per time window",
                        "schema": {"type": "integer", "example": 1000},
                    },
                    "X-RateLimit-Remaining": {
                        "description": "Remaining requests in current window",
                        "schema": {"type": "integer", "example": 0},
                    },
                    "X-RateLimit-Reset": {
                        "description": "Unix timestamp when rate limit resets",
                        "schema": {"type": "integer", "example": 1642248000},
                    },
                },
            ),
            500: ErrorResponse(
                status_code=500,
                description="Internal Server Error - Unexpected server error",
                error_code="INTERNAL_ERROR",
                error_message="An internal server error occurred",
            ),
            502: ErrorResponse(
                status_code=502,
                description="Bad Gateway - Upstream service error",
                error_code="SERVICE_UNAVAILABLE",
                error_message="Service temporarily unavailable",
            ),
            503: ErrorResponse(
                status_code=503,
                description="Service Unavailable - Service temporarily unavailable",
                error_code="SERVICE_UNAVAILABLE",
                error_message="Service temporarily unavailable. Please try again later.",
            ),
            504: ErrorResponse(
                status_code=504,
                description="Gateway Timeout - Request timeout",
                error_code="GATEWAY_TIMEOUT",
                error_message="Request timeout",
            ),
        }

        # Endpoint-specific error codes
        self.endpoint_specific_errors = {
            "register": {
                400: [
                    ("EMAIL_ALREADY_EXISTS", "Email address is already registered"),
                    ("WEAK_PASSWORD", "Password does not meet strength requirements"),
                ]
            },
            "login": {
                401: [
                    ("INVALID_CREDENTIALS", "Invalid email or password"),
                    ("ACCOUNT_LOCKED", "Account is locked due to too many failed attempts"),
                ]
            },
            "credentials": {
                400: [
                    ("INVALID_CREDENTIALS", "Invalid credential format"),
                    ("CONNECTION_FAILED", "Failed to connect with provided credentials"),
                ],
                404: [
                    ("CREDENTIALS_NOT_FOUND", "Credentials not found for this scheduled ingestion"),
                ],
            },
            "natural-language-search": {
                400: [
                    ("INVALID_QUERY", "Invalid natural language query"),
                    ("QUERY_TOO_COMPLEX", "Query is too complex to process"),
                ],
                503: [
                    ("LLM_SERVICE_UNAVAILABLE", "AI service is temporarily unavailable"),
                ],
            },
            "schema-matching": {
                400: [
                    ("INVALID_SCHEMAS", "Invalid source or target schema"),
                    ("SCHEMA_MATCHING_FAILED", "Failed to match schemas"),
                ],
                503: [
                    ("AI_SERVICE_UNAVAILABLE", "AI service is temporarily unavailable"),
                ],
            },
            "ratings": {
                400: [
                    ("INVALID_RATING", "Rating must be between 1 and 5"),
                    ("ALREADY_RATED", "You have already rated this asset"),
                ]
            },
            "reviews": {
                400: [
                    ("INVALID_REVIEW", "Review text is required"),
                    ("REVIEW_TOO_LONG", "Review exceeds maximum length"),
                ]
            },
            "preview": {
                403: [
                    ("PREVIEW_NOT_ALLOWED", "Preview not available for this listing"),
                ],
                404: [
                    ("LISTING_NOT_FOUND", "Marketplace listing not found"),
                ],
            },
        }

    def get_error_response_schema(self) -> dict:
        """Get reusable ErrorResponse schema component"""
        return {
            "ErrorResponse": {
                "type": "object",
                "required": ["error"],
                "properties": {
                    "error": {
                        "type": "object",
                        "required": ["code", "message", "http_status", "request_id", "timestamp"],
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Machine-readable error code",
                                "example": "VALIDATION_ERROR",
                            },
                            "message": {
                                "type": "string",
                                "description": "Human-readable error message",
                                "example": "Invalid request data",
                            },
                            "http_status": {
                                "type": "integer",
                                "description": "HTTP status code",
                                "example": 400,
                            },
                            "request_id": {
                                "type": "string",
                                "format": "uuid",
                                "description": "Unique request identifier for support",
                                "example": "550e8400-e29b-41d4-a716-446655440000",
                            },
                            "timestamp": {
                                "type": "string",
                                "format": "date-time",
                                "description": "ISO 8601 timestamp of error",
                                "example": "2025-01-15T10:30:00Z",
                            },
                            "details": {
                                "type": "object",
                                "description": "Additional error details",
                                "additionalProperties": True,
                                "nullable": True,
                                "properties": {
                                    "field_errors": {
                                        "type": "array",
                                        "description": "Field-level validation errors",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "field": {
                                                    "type": "string",
                                                    "description": "Field name",
                                                    "example": "email",
                                                },
                                                "message": {
                                                    "type": "string",
                                                    "description": "Field-specific error message",
                                                    "example": "Invalid email format",
                                                },
                                                "code": {
                                                    "type": "string",
                                                    "description": "Error code",
                                                    "example": "VALIDATION_ERROR",
                                                },
                                            },
                                            "required": ["field", "message", "code"],
                                        },
                                    }
                                },
                            },
                        },
                    }
                },
            }
        }

    def get_error_example(self, error: ErrorResponse, endpoint_name: str | None = None) -> dict:
        """Generate error response example"""
        example = {
            "error": {
                "code": error.error_code,
                "message": error.error_message,
                "http_status": error.status_code,
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-01-15T10:30:00Z",
            }
        }

        if error.example_details:
            example["error"]["details"] = error.example_details

        # Add endpoint-specific errors
        if endpoint_name and endpoint_name in self.endpoint_specific_errors:
            specific_errors = self.endpoint_specific_errors[endpoint_name].get(
                error.status_code, []
            )
            if specific_errors:
                # Use first specific error as example
                code, message = specific_errors[0]
                example["error"]["code"] = code
                example["error"]["message"] = message

        return example

    def determine_required_errors(
        self, method: str, path: str, requires_auth: bool = True
    ) -> list[int]:
        """Determine which error responses are required for an endpoint"""
        required = []

        # All endpoints can return these
        required.extend([400, 500, 503])

        # Authentication endpoints
        if requires_auth:
            required.extend([401, 403])

        # Resource endpoints (with ID)
        if "{id}" in path or "{pk}" in path:
            required.append(404)

        # POST/PUT endpoints can have conflicts
        if method in ["POST", "PUT", "PATCH"]:
            required.append(409)

        # Rate limiting (especially for auth endpoints)
        if "auth" in path or "register" in path or "login" in path:
            required.append(429)

        return sorted(set(required))

    def add_error_responses_to_spec(self, spec_path: Path) -> bool:
        """Add error responses to an OpenAPI spec"""
        try:
            with open(spec_path, encoding="utf-8") as f:
                spec = yaml.safe_load(f)

            if not spec or "paths" not in spec:
                print(f"Warning: Invalid OpenAPI spec: {spec_path}")
                return False

            # Ensure components/schemas exists
            if "components" not in spec:
                spec["components"] = {}
            if "schemas" not in spec["components"]:
                spec["components"]["schemas"] = {}

            # Add ErrorResponse schema if not present
            if "ErrorResponse" not in spec["components"]["schemas"]:
                spec["components"]["schemas"].update(self.get_error_response_schema())

            modified = False

            # Process each path
            for path, path_item in spec["paths"].items():
                # Extract endpoint name for specific errors
                endpoint_name = self._extract_endpoint_name(path)

                # Process each method
                for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                    if method not in path_item:
                        continue

                    operation = path_item[method]

                    # Determine if auth is required
                    requires_auth = self._requires_auth(operation, spec)

                    # Determine required error codes
                    required_errors = self.determine_required_errors(
                        method.upper(), path, requires_auth
                    )

                    # Ensure responses section exists
                    if "responses" not in operation:
                        operation["responses"] = {}

                    # Add/update error responses
                    for status_code in required_errors:
                        status_str = str(status_code)

                        if status_str not in operation["responses"]:
                            error = self.standard_errors[status_code]

                            response_def = {
                                "description": error.description,
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/ErrorResponse"},
                                        "examples": {},
                                    }
                                },
                            }

                            # Add headers for rate limiting
                            if status_code == 429 and error.headers:
                                response_def["headers"] = error.headers

                            # Add default example
                            default_example = self.get_error_example(error, endpoint_name)
                            response_def["content"]["application/json"]["examples"]["default"] = {
                                "summary": f"{error.error_code} example",
                                "value": default_example,
                            }

                            # Add endpoint-specific examples
                            if endpoint_name and endpoint_name in self.endpoint_specific_errors:
                                specific_errors = self.endpoint_specific_errors[endpoint_name].get(
                                    status_code, []
                                )
                                for idx, (code, message) in enumerate(specific_errors):
                                    specific_example = default_example.copy()
                                    specific_example["error"]["code"] = code
                                    specific_example["error"]["message"] = message
                                    response_def["content"]["application/json"]["examples"][
                                        f"example_{idx + 1}"
                                    ] = {"summary": f"{code} example", "value": specific_example}

                            operation["responses"][status_str] = response_def
                            modified = True
                        else:
                            # Update existing error response
                            existing = operation["responses"][status_str]
                            error = self.standard_errors[status_code]

                            # Ensure schema reference
                            if "content" in existing and "application/json" in existing["content"]:
                                if "schema" not in existing["content"]["application/json"]:
                                    existing["content"]["application/json"]["schema"] = {
                                        "$ref": "#/components/schemas/ErrorResponse"
                                    }

                                # Add examples if missing
                                if "examples" not in existing["content"]["application/json"]:
                                    existing["content"]["application/json"]["examples"] = {}

                                if (
                                    "default"
                                    not in existing["content"]["application/json"]["examples"]
                                ):
                                    default_example = self.get_error_example(error, endpoint_name)
                                    existing["content"]["application/json"]["examples"][
                                        "default"
                                    ] = {
                                        "summary": f"{error.error_code} example",
                                        "value": default_example,
                                    }
                                    modified = True

                            # Add headers for 429
                            if status_code == 429 and "headers" not in existing and error.headers:
                                existing["headers"] = error.headers
                                modified = True

            if modified:
                # Write back
                with open(spec_path, "w", encoding="utf-8") as f:
                    yaml.dump(
                        spec, f, default_flow_style=False, sort_keys=False, allow_unicode=True
                    )
                return True

            return False

        except Exception as e:
            print(f"Error processing {spec_path}: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _extract_endpoint_name(self, path: str) -> str | None:
        """Extract endpoint name from path for specific error mapping"""
        # Remove /api/v1/ prefix
        path = re.sub(r"^/api/v1/", "", path)
        # Remove trailing slash
        path = path.rstrip("/")
        # Extract last segment
        segments = path.split("/")
        if segments:
            last = segments[-1]
            # Remove {id} or {pk} placeholders
            last = re.sub(r"\{[^}]+\}", "", last)
            return last if last else None
        return None

    def _requires_auth(self, operation: dict, spec: dict) -> bool:
        """Determine if operation requires authentication"""
        # Check security in operation
        if "security" in operation:
            if operation["security"] == []:
                return False
            return True

        # Check global security
        if "security" in spec:
            if spec["security"] == []:
                return False
            return True

        # Default to requiring auth
        return True

    def process_all_specs(self, contracts_dir: Path) -> dict[str, bool]:
        """Process all OpenAPI specs in directory"""
        results = {}

        # Find all YAML files
        yaml_files = list(contracts_dir.rglob("*.yaml")) + list(contracts_dir.rglob("*.yml"))

        for spec_file in yaml_files:
            if spec_file.name == "README.md":
                continue

            print(f"Processing: {spec_file.relative_to(contracts_dir.parent)}")
            success = self.add_error_responses_to_spec(spec_file)
            results[str(spec_file)] = success

        return results


def main():
    """Main execution"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    contracts_dir = repo_root / "docs" / "api-contracts" / "missing"

    if not contracts_dir.exists():
        print(f"Error: Contracts directory not found at {contracts_dir}")
        return 1

    enhancer = OpenAPIErrorResponseEnhancer()
    results = enhancer.process_all_specs(contracts_dir)

    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    print(f"\n✅ Processed {total_count} OpenAPI specs")
    print(f"   - Modified: {success_count}")
    print(f"   - Unchanged: {total_count - success_count}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
