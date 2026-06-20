#!/usr/bin/env python3
"""
Add Comprehensive Security Requirements to OpenAPI Specifications

Enhances all OpenAPI 3.0 specifications with:
- Detailed authentication method documentation
- Authorization rules (roles, permissions, scopes)
- Rate limiting requirements
- Input validation requirements
- Security scheme enhancements
"""

import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# Security requirements by endpoint
SECURITY_REQUIREMENTS = {
    "/auth/register/": {
        "auth_required": False,
        "auth_methods": [],
        "roles": [],
        "scopes": [],
        "rate_limit": {
            "burst": 10,
            "sustained": 10,
            "daily": 100,
            "window": 60,
            "unit": "per IP address",
        },
    },
    "/auth/me/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": [],
        "rate_limit": {
            "burst": 100,
            "sustained": 600,
            "daily": 100000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/scheduled-ingestions/{id}/credentials/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["DATA_PROVIDER", "TENANT_ADMIN"],
        "scopes": ["scheduled_ingestion:read"],
        "rate_limit": {
            "burst": 100,
            "sustained": 600,
            "daily": 100000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/scheduled-ingestions/{id}/credentials/test/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["DATA_PROVIDER", "TENANT_ADMIN"],
        "scopes": ["scheduled_ingestion:write"],
        "rate_limit": {
            "burst": 10,
            "sustained": 30,
            "daily": 1000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/ai/natural-language-search/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["search:execute"],
        "rate_limit": {
            "burst": 10,
            "sustained": 20,
            "daily": 5000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/ai/schema-matching/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["DATA_PROVIDER", "TENANT_ADMIN"],
        "scopes": ["ai:schema_matching"],
        "rate_limit": {
            "burst": 5,
            "sustained": 10,
            "daily": 2000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/social/ratings/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["social:rate"],
        "rate_limit": {
            "burst": 10,
            "sustained": 10,
            "daily": 1000,
            "window": 3600,
            "unit": "per user per asset (10 per hour)",
        },
    },
    "/social/reviews/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["social:review"],
        "rate_limit": {"burst": 5, "sustained": 20, "daily": 100, "window": 60, "unit": "per user"},
    },
    "/social/comments/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["social:comment"],
        "rate_limit": {
            "burst": 20,
            "sustained": 100,
            "daily": 5000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/social/communities/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["social:community"],
        "rate_limit": {"burst": 5, "sustained": 10, "daily": 100, "window": 60, "unit": "per user"},
    },
    "/marketplace/listings/{id}/preview/": {
        "auth_required": True,
        "auth_methods": ["JWT", "API Key"],
        "roles": ["Any authenticated"],
        "scopes": ["marketplace:preview"],
        "rate_limit": {
            "burst": 20,
            "sustained": 50,
            "daily": 2000,
            "window": 60,
            "unit": "per user",
        },
    },
    "/developer/plugins/": {
        "auth_required": False,
        "auth_methods": ["JWT (optional)", "API Key (optional)"],
        "roles": [],
        "scopes": [],
        "rate_limit": {
            "burst": 100,
            "sustained": 600,
            "daily": 100000,
            "window": 60,
            "unit": "per IP address",
        },
    },
    "/developer/sdk/": {
        "auth_required": False,
        "auth_methods": ["JWT (optional)", "API Key (optional)"],
        "roles": [],
        "scopes": [],
        "rate_limit": {
            "burst": 100,
            "sustained": 600,
            "daily": 100000,
            "window": 60,
            "unit": "per IP address",
        },
    },
}


def enhance_openapi_spec(file_path: Path) -> bool:
    """Enhance a single OpenAPI spec file with security requirements."""
    print(f"\nProcessing: {file_path.relative_to(PROJECT_ROOT)}")

    try:
        # Read spec
        with open(file_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)

        if not spec or "openapi" not in spec:
            print("  ⚠️  Skipping: Not a valid OpenAPI spec")
            return False

        enhanced = False

        # Enhance paths
        if "paths" in spec:
            for path, path_item in spec["paths"].items():
                if isinstance(path_item, dict):
                    for method, operation in path_item.items():
                        if method in ["get", "post", "put", "patch", "delete"] and isinstance(
                            operation, dict
                        ):
                            # Find matching security requirements
                            path_key = path
                            if path_key in SECURITY_REQUIREMENTS:
                                reqs = SECURITY_REQUIREMENTS[path_key]
                                enhanced |= enhance_operation(
                                    operation, path_key, method, reqs, spec
                                )

        # Enhance security schemes
        if "components" not in spec:
            spec["components"] = {}
        if "securitySchemes" not in spec["components"]:
            spec["components"]["securitySchemes"] = {}

        enhanced |= enhance_security_schemes(spec["components"]["securitySchemes"])

        # Write enhanced spec
        if enhanced:
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
            print("  ✅ Enhanced with security requirements")
            return True
        else:
            print("  ℹ️  No enhancements needed")
            return False

    except Exception as e:
        print(f"  ❌ Error: {e}")
        raise


def enhance_operation(
    operation: dict[str, Any], path: str, method: str, reqs: dict[str, Any], spec: dict[str, Any]
) -> bool:
    """Enhance a single operation with security requirements."""
    enhanced = False

    # Enhance description with security requirements
    description = operation.get("description", "")

    # Add authentication section
    auth_section = "\n\n**Authentication**: "
    if reqs["auth_required"]:
        auth_section += f"Required ({', '.join(reqs['auth_methods'])})"
    else:
        auth_section += "Not required (public endpoint)"

    if auth_section not in description:
        operation["description"] = description + auth_section
        enhanced = True

    # Add authorization section
    if reqs["roles"] or reqs["scopes"]:
        authz_section = "\n\n**Authorization**: "
        parts = []
        if reqs["roles"]:
            roles_str = (
                ", ".join(reqs["roles"]) if isinstance(reqs["roles"], list) else reqs["roles"]
            )
            parts.append(f"Required role(s): {roles_str}")
        if reqs["scopes"]:
            scopes_str = (
                ", ".join(reqs["scopes"]) if isinstance(reqs["scopes"], list) else reqs["scopes"]
            )
            parts.append(f"Required scope(s): {scopes_str}")
        if parts:
            authz_section += "; ".join(parts)
            if authz_section not in operation.get("description", ""):
                operation["description"] = operation.get("description", "") + authz_section
                enhanced = True

    # Add rate limiting section
    rate_limit = reqs.get("rate_limit", {})
    if rate_limit:
        rate_section = f"\n\n**Rate Limiting**: {rate_limit['sustained']} requests per {rate_limit['window']} seconds {rate_limit.get('unit', 'per user')}"
        if rate_limit.get("burst"):
            rate_section += f" (burst: {rate_limit['burst']} per 10 seconds)"
        if rate_limit.get("daily"):
            rate_section += f" (daily: {rate_limit['daily']} per day)"

        if rate_section not in operation.get("description", ""):
            operation["description"] = operation.get("description", "") + rate_section
            enhanced = True

    # Add input validation section
    validation_section = "\n\n**Input Validation**: All request fields validated (types, formats, lengths, patterns, enums). See request schema for details."
    if validation_section not in operation.get("description", ""):
        operation["description"] = operation.get("description", "") + validation_section
        enhanced = True

    # Enhance security array
    if "security" not in operation:
        if reqs["auth_required"]:
            operation["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
            enhanced = True
        elif reqs.get("auth_methods") and "optional" in str(reqs["auth_methods"]).lower():
            # Optional authentication
            operation["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
            enhanced = True

    # Enhance 429 response with rate limit details
    if "responses" in operation and "429" in operation["responses"]:
        response_429 = operation["responses"]["429"]
        if "headers" not in response_429:
            response_429["headers"] = {}

        # Add rate limit headers
        headers = response_429["headers"]
        if "X-RateLimit-Limit" not in headers:
            headers["X-RateLimit-Limit"] = {
                "description": "Maximum number of requests allowed in the current window",
                "schema": {"type": "integer"},
                "example": rate_limit.get("sustained", 20),
            }
            enhanced = True

        if "X-RateLimit-Remaining" not in headers:
            headers["X-RateLimit-Remaining"] = {
                "description": "Number of requests remaining in the current window",
                "schema": {"type": "integer"},
                "example": 0,
            }
            enhanced = True

        if "X-RateLimit-Reset" not in headers:
            headers["X-RateLimit-Reset"] = {
                "description": "Unix timestamp when rate limit resets",
                "schema": {"type": "integer"},
                "example": 1736868000,
            }
            enhanced = True

        if "Retry-After" not in headers:
            headers["Retry-After"] = {
                "description": "Number of seconds to wait before retrying",
                "schema": {"type": "integer"},
                "example": 30,
            }
            enhanced = True

    return enhanced


def enhance_security_schemes(security_schemes: dict[str, Any]) -> bool:
    """Enhance security schemes with detailed documentation."""
    enhanced = False

    # Enhance BearerAuth
    if "BearerAuth" not in security_schemes:
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": 'JWT Bearer token authentication. Include token in Authorization header: "Bearer {token}". Tokens expire after 1 hour and can be refreshed using refresh tokens.',
        }
        enhanced = True
    elif (
        "description" not in security_schemes["BearerAuth"]
        or len(security_schemes["BearerAuth"].get("description", "")) < 50
    ):
        security_schemes["BearerAuth"]["description"] = (
            'JWT Bearer token authentication. Include token in Authorization header: "Bearer {token}". Tokens expire after 1 hour and can be refreshed using refresh tokens.'
        )
        enhanced = True

    # Enhance ApiKeyAuth
    if "ApiKeyAuth" not in security_schemes:
        security_schemes["ApiKeyAuth"] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": 'API key authentication. Include key in Authorization header: "ApiKey {key}" or in X-API-Key header. API keys can have scopes to limit access and can be expired or revoked.',
        }
        enhanced = True
    elif (
        "description" not in security_schemes["ApiKeyAuth"]
        or len(security_schemes["ApiKeyAuth"].get("description", "")) < 50
    ):
        security_schemes["ApiKeyAuth"]["description"] = (
            'API key authentication. Include key in Authorization header: "ApiKey {key}" or in X-API-Key header. API keys can have scopes to limit access and can be expired or revoked.'
        )
        enhanced = True

    return enhanced


def main():
    """Main entry point."""
    contracts_dir = PROJECT_ROOT / "docs" / "api-contracts" / "missing"

    if not contracts_dir.exists():
        print(f"❌ Directory not found: {contracts_dir}")
        sys.exit(1)

    print(
        f"Adding security requirements to OpenAPI specs in: {contracts_dir.relative_to(PROJECT_ROOT)}"
    )
    print("=" * 80)

    spec_files = list(contracts_dir.rglob("*.yaml")) + list(contracts_dir.rglob("*.yml"))
    enhanced_count = 0

    for spec_file in spec_files:
        if spec_file.name == "README.md":
            continue

        if enhance_openapi_spec(spec_file):
            enhanced_count += 1

    print("\n" + "=" * 80)
    print(f"✅ Enhanced {enhanced_count} OpenAPI spec files with security requirements!")


if __name__ == "__main__":
    main()
