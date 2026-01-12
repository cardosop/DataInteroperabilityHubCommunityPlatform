#!/usr/bin/env python3
"""
Regenerate OpenAPI specification from Django REST Framework.

This script:
1. Generates OpenAPI spec using Django management command
2. Validates the generated spec
3. Saves to both JSON and YAML formats
4. Verifies endpoints are accessible
"""
import os
import sys
import json
import subprocess
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from django.test import Client
from drf_spectacular.generators import SchemaGenerator
from hub.apps.api.openapi_validation import OpenAPISpecValidator
from hub.apps.api.openapi_enhancement import OpenAPISpecEnhancer
import yaml


def generate_openapi_spec(output_dir: Path) -> dict:
    """Generate OpenAPI spec using SchemaGenerator."""
    print("Generating OpenAPI specification...")

    # Create a mock request
    from django.test import RequestFactory
    factory = RequestFactory()
    request = factory.get('/api/v1/')

    # Generate schema
    generator = SchemaGenerator(urlconf='hub.urls')
    schema = generator.get_schema(request=request, public=True)

    # Validate schema
    print("Validating OpenAPI specification...")
    is_valid, errors = OpenAPISpecValidator.validate_spec(schema)
    if not is_valid:
        print(f"⚠️  Validation warnings found: {len(errors)}")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more warnings")
    else:
        print("✅ OpenAPI specification is valid")

    # Enhance schema
    print("Enhancing OpenAPI specification...")
    schema = OpenAPISpecValidator.enhance_spec(schema)
    schema = OpenAPISpecEnhancer.enhance_spec(schema)

    # Save JSON format
    json_path = output_dir / 'openapi-schema.json'
    with open(json_path, 'w') as f:
        json.dump(schema, f, indent=2, sort_keys=False)
    print(f"✅ Saved JSON spec to: {json_path}")

    # Save YAML format
    yaml_path = output_dir / 'openapi-schema.yaml'
    yaml_content = yaml.dump(schema, default_flow_style=False, sort_keys=False, allow_unicode=True)
    with open(yaml_path, 'w') as f:
        f.write(yaml_content)
    print(f"✅ Saved YAML spec to: {yaml_path}")

    return schema


def verify_endpoints():
    """Verify that OpenAPI endpoints are accessible."""
    print("\nVerifying API documentation endpoints...")

    client = Client()

    endpoints = [
        ('/api-docs/openapi.json', 'application/json'),
        ('/api/v1/openapi.json', 'application/json'),
        ('/api/v1/openapi.yaml', 'application/x-yaml'),
        ('/api-docs/', 'text/html'),
        ('/api-docs/redoc/', 'text/html'),
    ]

    all_passed = True
    for endpoint, expected_content_type in endpoints:
        try:
            response = client.get(endpoint)
            if response.status_code == 200:
                content_type = response.get('Content-Type', '')
                if expected_content_type in content_type.lower() or 'openapi' in content_type.lower():
                    print(f"✅ {endpoint} - Status: {response.status_code}")
                else:
                    print(f"⚠️  {endpoint} - Unexpected content type: {content_type}")
                    all_passed = False
            else:
                print(f"❌ {endpoint} - Status: {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")
            all_passed = False

    return all_passed


def validate_spec_structure(schema: dict):
    """Validate OpenAPI spec structure and completeness."""
    print("\nValidating OpenAPI spec structure...")

    issues = []

    # Check required top-level fields
    required_fields = ['openapi', 'info', 'paths', 'components']
    for field in required_fields:
        if field not in schema:
            issues.append(f"Missing required field: {field}")

    # Check info section
    if 'info' in schema:
        info = schema['info']
        if 'title' not in info:
            issues.append("Missing 'title' in info section")
        if 'version' not in info:
            issues.append("Missing 'version' in info section")

    # Check paths
    if 'paths' in schema:
        paths = schema['paths']
        if not isinstance(paths, dict):
            issues.append("'paths' must be a dictionary")
        else:
            path_count = len(paths)
            print(f"  Found {path_count} paths")

            # Check for major endpoints
            expected_paths = [
                '/api/v1/auth/login/',
                '/api/v1/contracts/',
                '/api/v1/assets/',
                '/api/v1/datasets/',
            ]

            found_paths = []
            for expected in expected_paths:
                # Check variants (with/without trailing slash, with/without /api/v1 prefix)
                variants = [
                    expected,
                    expected.rstrip('/'),
                    expected.replace('/api/v1', ''),
                    expected.replace('/api/v1', '').rstrip('/'),
                ]
                if any(v in paths for v in variants):
                    found_paths.append(expected)

            if found_paths:
                print(f"  ✅ Found {len(found_paths)}/{len(expected_paths)} expected paths")
            else:
                print(f"  ⚠️  Expected paths not found (may be using different path format)")

    # Check components
    if 'components' in schema:
        components = schema['components']
        if 'schemas' in components:
            schema_count = len(components['schemas'])
            print(f"  Found {schema_count} component schemas")
        if 'securitySchemes' in components:
            security_count = len(components['securitySchemes'])
            print(f"  Found {security_count} security schemes")

    if issues:
        print("⚠️  Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ OpenAPI spec structure is valid")
        return True


def main():
    """Main execution function."""
    print("=" * 70)
    print("OpenAPI Specification Regeneration")
    print("=" * 70)

    # Create output directory
    output_dir = project_root / 'docs' / 'api-audit'
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate spec
        schema = generate_openapi_spec(output_dir)

        # Validate structure
        structure_valid = validate_spec_structure(schema)

        # Verify endpoints
        endpoints_valid = verify_endpoints()

        # Summary
        print("\n" + "=" * 70)
        print("Summary")
        print("=" * 70)
        print(f"OpenAPI Spec Generation: ✅ Complete")
        print(f"Spec Structure Validation: {'✅ Pass' if structure_valid else '⚠️  Warnings'}")
        print(f"Endpoints Verification: {'✅ Pass' if endpoints_valid else '❌ Failed'}")

        if structure_valid and endpoints_valid:
            print("\n✅ All checks passed!")
            return 0
        else:
            print("\n⚠️  Some checks had warnings or failures")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

