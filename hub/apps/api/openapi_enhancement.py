"""
OpenAPI Specification Enhancement

Enhances the auto-generated OpenAPI spec with comprehensive documentation,
examples, and metadata for all endpoints.
"""

from typing import Any, Dict

import structlog

logger = structlog.get_logger(__name__)


class OpenAPISpecEnhancer:
    """
    Enhances OpenAPI specifications with additional documentation.
    """

    @staticmethod
    def enhance_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance OpenAPI specification with comprehensive documentation.

        Args:
            spec: OpenAPI specification dictionary from drf-spectacular

        Returns:
            Enhanced specification
        """
        # Enhance info section
        spec = OpenAPISpecEnhancer._enhance_info(spec)

        # Enhance paths with examples
        spec = OpenAPISpecEnhancer._enhance_paths(spec)

        # Enhance components
        spec = OpenAPISpecEnhancer._enhance_components(spec)

        # Add tags with descriptions
        spec = OpenAPISpecEnhancer._enhance_tags(spec)

        return spec

    @staticmethod
    def _enhance_info(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance info section with comprehensive metadata."""
        if "info" not in spec:
            spec["info"] = {}

        info = spec["info"]

        # Set comprehensive title and description
        info["title"] = info.get("title", "Data Interoperability Hub API")
        info[
            "description"
        ] = """
# Data Interoperability Hub API

Complete REST API for managing data contracts, assets, datasets, compliance, data quality, and marketplace operations.

## Features

- **Contract Management**: Create, update, and manage data contracts with ODCS support
- **Multi-Level Lineage**: Track data dependencies at contract, model, and field levels
- **Data Quality**: Define and enforce data quality rules
- **Compliance**: Track privacy and compliance requirements
- **Search**: Full-text search across contracts and assets
- **Observability**: Monitor data freshness, volume, and pipeline health

## Authentication

All API requests require authentication using Bearer tokens. See the Authentication section for details.

## Rate Limiting

API requests are rate-limited per tenant. See response headers for rate limit information.

## Versioning

The API uses URL-based versioning. Current version: v1

## Support

For API support, contact: support@datahub.example.com
"""

        # Add contact information
        if "contact" not in info:
            info["contact"] = {
                "name": "API Support",
                "email": "support@datahub.example.com",
                "url": "https://docs.datahub.example.com",
            }

        # Add license
        if "license" not in info:
            info["license"] = {"name": "Proprietary", "url": "https://datahub.example.com/license"}

        # Add terms of service
        if "termsOfService" not in info:
            info["termsOfService"] = "https://datahub.example.com/terms"

        return spec

    @staticmethod
    def _enhance_paths(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance paths with examples and better descriptions."""
        if "paths" not in spec:
            return spec

        paths = spec["paths"]

        # Enhance contract endpoints
        contract_paths = [
            "/api/v1/contracts/",
            "/api/v1/contracts/{id}/",
        ]

        for path_key, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Enhance each operation
            for method, operation in path_item.items():
                if not isinstance(operation, dict) or method not in [
                    "get",
                    "post",
                    "patch",
                    "put",
                    "delete",
                ]:
                    continue

                # Add request body examples for POST/PATCH
                if method in ["post", "patch", "put"]:
                    operation = OpenAPISpecEnhancer._add_request_examples(
                        operation, path_key, method
                    )

                # Add response examples
                operation = OpenAPISpecEnhancer._add_response_examples(operation, path_key, method)

                # Add standard error responses
                operation = OpenAPISpecEnhancer._add_error_responses(operation)

                # Add idempotency headers for state-changing methods
                if method in ["post", "patch", "put"]:
                    operation = OpenAPISpecEnhancer._add_idempotency_headers(operation)

                # Enhance descriptions
                operation = OpenAPISpecEnhancer._enhance_operation_description(
                    operation, path_key, method
                )

                path_item[method] = operation

        return spec

    @staticmethod
    def _add_request_examples(operation: Dict[str, Any], path: str, method: str) -> Dict[str, Any]:
        """Add comprehensive request body examples for all endpoints."""
        if "requestBody" not in operation:
            return operation

        request_body = operation["requestBody"]
        if "content" not in request_body:
            return operation

        json_content = request_body["content"].get("application/json", {})
        if not json_content:
            return operation

        # Authentication endpoints
        if "/auth/login/" in path and method == "post":
            json_content["example"] = {
                "email": "user@example.com",
                "password": "securepassword123",
            }
        elif "/auth/refresh/" in path and method == "post":
            json_content["example"] = {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            }
        elif "/auth/register/" in path and method == "post":
            json_content["example"] = {
                "email": "newuser@example.com",
                "password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
                "tenant_name": "Example Tenant",
            }
        # Contract endpoints
        elif "/contracts/" in path and method == "post":
            json_content["example"] = {
                "original_raw": '{"apiVersion":"odcs/v3","kind":"DataContract","id":"customer-contract","name":"Customer Data Contract","schema":{"fields":[{"name":"customer_id","type":"string"},{"name":"email","type":"string"},{"name":"created_at","type":"timestamp"}]},"terms":{"usage":{"purpose":"Analytics and reporting","restrictions":["No PII sharing"]}}}',
                "original_format": "JSON",
            }
        elif "/contracts/" in path and method in ["patch", "put"]:
            json_content["example"] = {
                "original_raw": '{"apiVersion":"odcs/v3","kind":"DataContract","id":"customer-contract","name":"Updated Customer Contract","schema":{"fields":[{"name":"customer_id","type":"string"},{"name":"email","type":"string"},{"name":"created_at","type":"timestamp"},{"name":"updated_at","type":"timestamp"}]}}',
                "original_format": "JSON",
            }
        # Asset endpoints
        elif "/assets/" in path and method == "post":
            json_content["example"] = {
                "name": "Customer Analytics Dataset",
                "description": "Customer data for analytics and reporting",
                "asset_type": "DATASET",
                "domain": "analytics",
                "visibility": "INTERNAL",
            }
        elif "/assets/" in path and method in ["patch", "put"]:
            json_content["example"] = {
                "name": "Updated Customer Analytics Dataset",
                "description": "Updated description",
                "domain": "analytics",
            }
        # Dataset endpoints
        elif "/datasets/" in path and method == "post":
            json_content["example"] = {
                "name": "Customer Dataset v1",
                "description": "Customer dataset for analytics",
                "file_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        # Tenant endpoints
        elif "/tenants/" in path and method == "post":
            json_content["example"] = {
                "name": "Example Tenant",
                "domain": "example.com",
            }
        elif "/tenants/" in path and method in ["patch", "put"]:
            json_content["example"] = {
                "name": "Updated Tenant Name",
                "domain": "updated-example.com",
            }
        # User endpoints
        elif "/users/" in path and method == "post":
            json_content["example"] = {
                "email": "newuser@example.com",
                "first_name": "Jane",
                "last_name": "Smith",
                "role": "DATA_PROVIDER",
            }
        # Job endpoints
        elif "/jobs/" in path and method == "post":
            json_content["example"] = {
                "job_type": "DQ_RUN",
                "target_resource_type": "DATASET",
                "target_resource_id": "550e8400-e29b-41d4-a716-446655440000",
                "parameters": {"profile": "intake_basic_gx"},
            }
        # Data Quality endpoints
        elif "/dq/runs/" in path and method == "post":
            json_content["example"] = {
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
                "profile": "intake_basic_gx",
                "rules": [],
            }
        # Compliance endpoints
        elif "/compliance/scans/" in path and method == "post":
            json_content["example"] = {
                "asset_id": "550e8400-e29b-41d4-a716-446655440000",
                "regimes": ["GDPR", "HIPAA"],
            }
        # Marketplace endpoints
        elif "/marketplace/listings/" in path and method == "post":
            json_content["example"] = {
                "asset_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Customer Analytics Dataset",
                "description": "High-quality customer data for analytics",
                "pricing_model": "FIXED",
                "price": 1000.00,
            }
        elif "/marketplace/orders/" in path and method == "post":
            json_content["example"] = {
                "listing_id": "550e8400-e29b-41d4-a716-446655440000",
                "purpose": "Analytics and reporting",
            }
        # Scheduled Ingestion endpoints
        elif "/scheduled-ingestion/" in path and method == "post":
            json_content["example"] = {
                "name": "Daily Customer Data Ingestion",
                "source_type": "S3",
                "source_config": {
                    "bucket": "data-bucket",
                    "prefix": "customers/",
                },
                "schedule": "0 2 * * *",  # Daily at 2 AM
                "dataset_id": "550e8400-e29b-41d4-a716-446655440000",
            }

        return operation

    @staticmethod
    def _add_response_examples(operation: Dict[str, Any], path: str, method: str) -> Dict[str, Any]:
        """Add comprehensive response examples for all endpoints."""
        if "responses" not in operation:
            return operation

        responses = operation["responses"]

        # Add success response examples
        if "200" in responses or "201" in responses:
            status_code = "201" if "201" in responses else "200"
            response = responses[status_code]

            if "content" in response and "application/json" in response["content"]:
                json_content = response["content"]["application/json"]

                # Authentication responses
                if "/auth/login/" in path and method == "post":
                    json_content["example"] = {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }
                elif "/auth/refresh/" in path and method == "post":
                    json_content["example"] = {
                        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                    }
                # Contract responses
                elif "/contracts/" in path:
                    if method == "get" and "{id}" in path:
                        json_content["example"] = {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "hub_contract_json": {
                                "hub_contract_version": "1.0.0",
                                "id": "customer-contract",
                                "info": {"name": "Customer Data Contract", "version": "1.0.0"},
                                "schema": {
                                    "fields": [
                                        {"name": "customer_id", "type": "string"},
                                        {"name": "email", "type": "string"},
                                        {"name": "created_at", "type": "timestamp"},
                                    ]
                                },
                            },
                            "status": "ACTIVE",
                            "normalization_status": "NORMALIZED_OK",
                            "created_at": "2025-01-15T10:30:00Z",
                            "updated_at": "2025-01-15T10:30:00Z",
                        }
                    elif method == "get":
                        json_content["example"] = {
                            "count": 100,
                            "page": 1,
                            "page_size": 50,
                            "total_pages": 2,
                            "has_next": True,
                            "has_previous": False,
                            "results": [
                                {
                                    "id": "550e8400-e29b-41d4-a716-446655440000",
                                    "hub_contract_json": {
                                        "id": "contract-1",
                                        "info": {"name": "Contract 1"},
                                    },
                                    "status": "ACTIVE",
                                    "normalization_status": "NORMALIZED_OK",
                                }
                            ],
                        }
                # Asset responses
                elif "/assets/" in path:
                    if method == "get" and "{id}" in path:
                        json_content["example"] = {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "Customer Analytics Dataset",
                            "description": "Customer data for analytics",
                            "asset_type": "DATASET",
                            "domain": "analytics",
                            "visibility": "INTERNAL",
                            "status": "ACTIVE",
                            "created_at": "2025-01-15T10:30:00Z",
                        }
                    elif method == "get":
                        json_content["example"] = {
                            "count": 50,
                            "page": 1,
                            "page_size": 20,
                            "results": [
                                {
                                    "id": "550e8400-e29b-41d4-a716-446655440000",
                                    "name": "Customer Analytics Dataset",
                                    "asset_type": "DATASET",
                                    "status": "ACTIVE",
                                }
                            ],
                        }
                # Dataset responses
                elif "/datasets/" in path:
                    if method == "get" and "{id}" in path:
                        json_content["example"] = {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "Customer Dataset v1",
                            "description": "Customer dataset",
                            "file_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2025-01-15T10:30:00Z",
                        }
                # Job responses
                elif "/jobs/" in path:
                    if method == "get" and "{id}" in path:
                        json_content["example"] = {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "job_type": "DQ_RUN",
                            "status": "COMPLETED",
                            "target_resource_type": "DATASET",
                            "target_resource_id": "660e8400-e29b-41d4-a716-446655440001",
                            "created_at": "2025-01-15T10:30:00Z",
                            "completed_at": "2025-01-15T10:35:00Z",
                        }

        return operation

    @staticmethod
    def _add_error_responses(operation: Dict[str, Any]) -> Dict[str, Any]:
        """Add standard error responses to operation if not already present."""
        if "responses" not in operation:
            operation["responses"] = {}

        responses = operation["responses"]

        # Standard error responses to add
        standard_errors = {
            "400": {
                "description": "Bad Request - Validation error or invalid request data",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string", "example": "VALIDATION_ERROR"},
                                        "message": {
                                            "type": "string",
                                            "example": "Invalid request data",
                                        },
                                        "http_status": {"type": "integer", "example": 400},
                                        "request_id": {
                                            "type": "string",
                                            "example": "550e8400-e29b-41d4-a716-446655440000",
                                        },
                                        "timestamp": {
                                            "type": "string",
                                            "format": "date-time",
                                            "example": "2025-01-15T10:30:00Z",
                                        },
                                        "details": {
                                            "type": "object",
                                            "description": "Additional error details",
                                        },
                                    },
                                    "required": [
                                        "code",
                                        "message",
                                        "http_status",
                                        "request_id",
                                        "timestamp",
                                    ],
                                }
                            },
                            "required": ["error"],
                        },
                        "example": {
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Invalid request data",
                                "http_status": 400,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                                "details": {
                                    "field_errors": [
                                        {
                                            "field": "field_name",
                                            "message": "Field-specific error message",
                                            "code": "REQUIRED",
                                        }
                                    ]
                                },
                            }
                        },
                    }
                },
            },
            "401": {
                "description": "Unauthorized - Authentication required",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string", "example": "AUTH_UNAUTHORIZED"},
                                        "message": {
                                            "type": "string",
                                            "example": "Authentication required",
                                        },
                                        "http_status": {"type": "integer", "example": 401},
                                        "request_id": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                    },
                                }
                            },
                        },
                        "example": {
                            "error": {
                                "code": "AUTH_UNAUTHORIZED",
                                "message": "Authentication required",
                                "http_status": 401,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                            }
                        },
                    }
                },
            },
            "403": {
                "description": "Forbidden - Insufficient permissions",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string", "example": "AUTH_FORBIDDEN"},
                                        "message": {
                                            "type": "string",
                                            "example": "Permission denied",
                                        },
                                        "http_status": {"type": "integer", "example": 403},
                                        "request_id": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                    },
                                }
                            },
                        },
                        "example": {
                            "error": {
                                "code": "AUTH_FORBIDDEN",
                                "message": "Permission denied",
                                "http_status": 403,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                            }
                        },
                    }
                },
            },
            "404": {
                "description": "Not Found - Resource not found",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string", "example": "NOT_FOUND"},
                                        "message": {
                                            "type": "string",
                                            "example": "Resource not found",
                                        },
                                        "http_status": {"type": "integer", "example": 404},
                                        "request_id": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                    },
                                }
                            },
                        },
                        "example": {
                            "error": {
                                "code": "NOT_FOUND",
                                "message": "Resource not found",
                                "http_status": 404,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                            }
                        },
                    }
                },
            },
            "429": {
                "description": "Too Many Requests - Rate limit exceeded",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {
                                            "type": "string",
                                            "example": "RATE_LIMIT_EXCEEDED",
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Rate limit exceeded",
                                        },
                                        "http_status": {"type": "integer", "example": 429},
                                        "request_id": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                        "details": {
                                            "type": "object",
                                            "properties": {
                                                "retry_after": {"type": "integer", "example": 60}
                                            },
                                        },
                                    },
                                }
                            },
                        },
                        "example": {
                            "error": {
                                "code": "RATE_LIMIT_EXCEEDED",
                                "message": "Rate limit exceeded",
                                "http_status": 429,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                                "details": {"retry_after": 60},
                            }
                        },
                    }
                },
            },
            "500": {
                "description": "Internal Server Error",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "error": {
                                    "type": "object",
                                    "properties": {
                                        "code": {"type": "string", "example": "INTERNAL_ERROR"},
                                        "message": {
                                            "type": "string",
                                            "example": "Internal server error",
                                        },
                                        "http_status": {"type": "integer", "example": 500},
                                        "request_id": {"type": "string"},
                                        "timestamp": {"type": "string", "format": "date-time"},
                                    },
                                }
                            },
                        },
                        "example": {
                            "error": {
                                "code": "INTERNAL_ERROR",
                                "message": "Internal server error",
                                "http_status": 500,
                                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                                "timestamp": "2025-01-15T10:30:00Z",
                            }
                        },
                    }
                },
            },
        }

        # Add error responses if not already present
        for status_code, error_response in standard_errors.items():
            if status_code not in responses:
                responses[status_code] = error_response
            elif "content" not in responses[status_code]:
                # Merge content if description exists but no content
                responses[status_code].update(error_response)

        return operation

    @staticmethod
    def _enhance_operation_description(
        operation: Dict[str, Any], path: str, method: str
    ) -> Dict[str, Any]:
        """Enhance operation descriptions."""
        # Descriptions are already set via extend_schema decorators
        # This method can add additional context if needed
        return operation

    @staticmethod
    def _add_idempotency_headers(operation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add idempotency response headers to operation.

        Adds Idempotency-Key and Idempotency-Replayed headers to all responses
        for POST, PUT, and PATCH operations.

        Args:
            operation: OpenAPI operation dictionary

        Returns:
            Enhanced operation with idempotency headers
        """
        if "responses" not in operation:
            operation["responses"] = {}

        responses = operation["responses"]

        # Idempotency headers definition
        idempotency_headers = {
            "Idempotency-Key": {
                "description": (
                    "Echoes back the idempotency key provided in the request header. "
                    "Present when an Idempotency-Key header was included in the request."
                ),
                "schema": {
                    "type": "string",
                    "example": "550e8400-e29b-41d4-a716-446655440000"
                }
            },
            "Idempotency-Replayed": {
                "description": (
                    "Indicates whether the response was replayed from cache. "
                    "Set to 'true' when a cached response is returned for a duplicate request. "
                    "Not present for new requests."
                ),
                "schema": {
                    "type": "string",
                    "enum": ["true"],
                    "example": "true"
                }
            }
        }

        # Add headers to all success responses (2xx)
        for status_code in ["200", "201", "202", "204"]:
            if status_code in responses:
                response = responses[status_code]
                if "headers" not in response:
                    response["headers"] = {}

                # Add idempotency headers
                response["headers"].update(idempotency_headers)

        # Add Idempotency-Key header to error responses (but not Idempotency-Replayed)
        for status_code in ["400", "409"]:
            if status_code in responses:
                response = responses[status_code]
                if "headers" not in response:
                    response["headers"] = {}

                # Only add Idempotency-Key header (not Idempotency-Replayed for errors)
                if "Idempotency-Key" not in response["headers"]:
                    response["headers"]["Idempotency-Key"] = idempotency_headers["Idempotency-Key"]

        # Add parameters section for Idempotency-Key request header if not present
        if "parameters" not in operation:
            operation["parameters"] = []

        # Check if Idempotency-Key parameter already exists
        has_idempotency_param = any(
            param.get("name") == "Idempotency-Key"
            for param in operation["parameters"]
        )

        if not has_idempotency_param:
            operation["parameters"].append({
                "name": "Idempotency-Key",
                "in": "header",
                "description": (
                    "Idempotency key for ensuring request idempotency. "
                    "Provide a unique key (UUID or 8-256 alphanumeric characters) "
                    "to prevent duplicate processing of the same request. "
                    "The same key with the same request body will return the cached response. "
                    "Required for POST, PUT, and PATCH operations."
                ),
                "required": False,  # Optional but recommended
                "schema": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9\\-_/]{8,256}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                    "example": "550e8400-e29b-41d4-a716-446655440000"
                }
            })

        return operation

    @staticmethod
    def _enhance_components(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance components section."""
        if "components" not in spec:
            spec["components"] = {}

        components = spec["components"]

        # Ensure security schemes
        if "securitySchemes" not in components:
            components["securitySchemes"] = {}

        security_schemes = components["securitySchemes"]

        # Add Bearer authentication
        if "BearerAuth" not in security_schemes:
            security_schemes["BearerAuth"] = {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": 'JWT Bearer token authentication. Include token in Authorization header: "Bearer {token}"',
            }

        # Add API Key authentication
        if "ApiKeyAuth" not in security_schemes:
            security_schemes["ApiKeyAuth"] = {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": 'API key authentication. Include key in Authorization header: "ApiKey {key}"',
            }

        return spec

    @staticmethod
    def _enhance_tags(spec: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance tags with descriptions."""
        if "tags" not in spec:
            spec["tags"] = []

        tags = spec["tags"]
        tag_map = {
            "Contracts": {
                "name": "Contracts",
                "description": "Contract management endpoints for creating, updating, and managing data contracts.",
            },
            "Lineage": {
                "name": "Lineage",
                "description": "Multi-level lineage endpoints for tracking data dependencies.",
            },
            "Assets": {"name": "Assets", "description": "Data asset management endpoints."},
            "Datasets": {"name": "Datasets", "description": "Dataset management endpoints."},
            "Search": {
                "name": "Search",
                "description": "Search endpoints for finding contracts and assets.",
            },
            "Observability": {
                "name": "Observability",
                "description": "Data observability and monitoring endpoints.",
            },
            "API": {"name": "API", "description": "API information and documentation endpoints."},
        }

        # Add or update tags
        existing_tag_names = {tag.get("name") for tag in tags if isinstance(tag, dict)}

        for tag_name, tag_info in tag_map.items():
            if tag_name not in existing_tag_names:
                tags.append(tag_info)
            else:
                # Update existing tag
                for i, tag in enumerate(tags):
                    if isinstance(tag, dict) and tag.get("name") == tag_name:
                        tags[i] = tag_info
                        break

        return spec
