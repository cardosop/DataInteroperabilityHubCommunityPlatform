#!/usr/bin/env python3
"""
Verify Integration Test Coverage

This script:
1. Analyzes integration tests to identify which endpoints are tested
2. Compares against actual API endpoints
3. Generates a coverage report
4. Verifies coverage meets the >80% threshold
"""

import re
import sys
from pathlib import Path

# API endpoints from the codebase
COMPLIANCE_ENDPOINTS = {
    "GET /api/v1/compliance/runs/": "list",
    "POST /api/v1/compliance/runs/": "create",
    "GET /api/v1/compliance/runs/{id}/": "retrieve",
    "PUT /api/v1/compliance/runs/{id}/": "update",
    "PATCH /api/v1/compliance/runs/{id}/": "partial_update",
    "DELETE /api/v1/compliance/runs/{id}/": "destroy",
    "GET /api/v1/compliance/runs/{id}/results/": "results",
}

DQ_ENDPOINTS = {
    "GET /api/v1/dq/runs/": "list",
    "POST /api/v1/dq/runs/": "create",
    "GET /api/v1/dq/runs/{id}/": "retrieve",
    "PUT /api/v1/dq/runs/{id}/": "update",
    "PATCH /api/v1/dq/runs/{id}/": "partial_update",
    "DELETE /api/v1/dq/runs/{id}/": "destroy",
    "GET /api/v1/dq/runs/{id}/results/": "results",
}


def normalize_url(url: str) -> str:
    """Normalize URL to standard format"""
    # Remove trailing slash
    url = url.rstrip("/")

    # Replace UUIDs and variables with {id}
    url = re.sub(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", "{id}", url)
    url = re.sub(r"\{[^}]+\}", "{id}", url)  # Replace any {variable} with {id}
    url = re.sub(r"[^/]+-id", "{id}", url)
    url = re.sub(r"[^/]+\.id", "{id}", url)
    url = re.sub(r"[^/]+_id", "{id}", url)

    # Remove query parameters
    if "?" in url:
        url = url.split("?")[0]

    # Ensure trailing slash for consistency
    if not url.endswith("/"):
        url += "/"

    return url


def extract_endpoints_from_tests(test_file: Path) -> set[str]:
    """Extract API endpoints tested from test file"""
    endpoints = set()

    try:
        content = test_file.read_text()
        lines = content.split("\n")

        # Pattern: Look for HTTP method calls with URLs
        for i, line in enumerate(lines):
            # Find HTTP method calls
            method_match = re.search(r"self\.client\.(get|post|put|patch|delete)\(", line)
            if not method_match:
                continue

            method = method_match.group(1).upper()

            # Find URL in the same line or next few lines
            url_match = re.search(r"['\"](/api/v1/[^'\"]+)['\"]", line)
            if not url_match:
                # Check next few lines
                for j in range(i + 1, min(len(lines), i + 5)):
                    url_match = re.search(r"['\"](/api/v1/[^'\"]+)['\"]", lines[j])
                    if url_match:
                        break

            if url_match:
                url = normalize_url(url_match.group(1))
                endpoints.add(f"{method} {url}")

        # Also check test method names for coverage
        test_methods = re.findall(r"def test_([^\(]+)", content)
        is_compliance = "compliance" in test_file.name.lower()
        is_dq = "dq" in test_file.name.lower()

        for method in test_methods:
            method_lower = method.lower()
            if "create" in method_lower:
                if is_compliance:
                    endpoints.add("POST /api/v1/compliance/runs/")
                if is_dq:
                    endpoints.add("POST /api/v1/dq/runs/")
            elif "retrieve" in method_lower or (
                "get" in method_lower and "list" not in method_lower
            ):
                if is_compliance:
                    endpoints.add("GET /api/v1/compliance/runs/{id}/")
                if is_dq:
                    endpoints.add("GET /api/v1/dq/runs/{id}/")
            elif "update" in method_lower:
                if is_compliance:
                    endpoints.add("PATCH /api/v1/compliance/runs/{id}/")
                    endpoints.add("PUT /api/v1/compliance/runs/{id}/")
                if is_dq:
                    endpoints.add("PATCH /api/v1/dq/runs/{id}/")
                    endpoints.add("PUT /api/v1/dq/runs/{id}/")
            elif "delete" in method_lower:
                if is_compliance:
                    endpoints.add("DELETE /api/v1/compliance/runs/{id}/")
                if is_dq:
                    endpoints.add("DELETE /api/v1/dq/runs/{id}/")
            elif "list" in method_lower:
                if is_compliance:
                    endpoints.add("GET /api/v1/compliance/runs/")
                if is_dq:
                    endpoints.add("GET /api/v1/dq/runs/")
            elif "results" in method_lower:
                if is_compliance:
                    endpoints.add("GET /api/v1/compliance/runs/{id}/results/")
                if is_dq:
                    endpoints.add("GET /api/v1/dq/runs/{id}/results/")

    except Exception as e:
        print(f"Error reading {test_file}: {e}", file=sys.stderr)

    return endpoints


def analyze_test_coverage():
    """Analyze integration test coverage"""
    project_root = Path(__file__).parent.parent
    test_files = [
        project_root / "tests" / "integration" / "test_compliance_apis_comprehensive.py",
        project_root / "tests" / "integration" / "test_dq_apis_comprehensive.py",
    ]

    tested_endpoints = set()
    for test_file in test_files:
        if test_file.exists():
            endpoints = extract_endpoints_from_tests(test_file)
            tested_endpoints.update(endpoints)

    # Calculate coverage
    all_endpoints = set(COMPLIANCE_ENDPOINTS.keys()) | set(DQ_ENDPOINTS.keys())

    compliance_tested = set()
    dq_tested = set()

    for endpoint in tested_endpoints:
        if "/compliance/" in endpoint:
            compliance_tested.add(endpoint)
        elif "/dq/" in endpoint:
            dq_tested.add(endpoint)

    compliance_coverage = len(compliance_tested) / len(COMPLIANCE_ENDPOINTS) * 100
    dq_coverage = len(dq_tested) / len(DQ_ENDPOINTS) * 100
    overall_coverage = len(tested_endpoints) / len(all_endpoints) * 100

    return {
        "compliance": {
            "total": len(COMPLIANCE_ENDPOINTS),
            "tested": len(compliance_tested),
            "coverage": compliance_coverage,
            "endpoints": {
                "tested": sorted(compliance_tested),
                "missing": sorted(set(COMPLIANCE_ENDPOINTS.keys()) - compliance_tested),
            },
        },
        "dq": {
            "total": len(DQ_ENDPOINTS),
            "tested": len(dq_tested),
            "coverage": dq_coverage,
            "endpoints": {
                "tested": sorted(dq_tested),
                "missing": sorted(set(DQ_ENDPOINTS.keys()) - dq_tested),
            },
        },
        "overall": {
            "total": len(all_endpoints),
            "tested": len(tested_endpoints),
            "coverage": overall_coverage,
        },
    }


def main():
    """Main function"""
    print("=" * 80)
    print("Integration Test Coverage Analysis")
    print("=" * 80)
    print()

    coverage_data = analyze_test_coverage()

    # Print compliance coverage
    print("COMPLIANCE API ENDPOINTS")
    print("-" * 80)
    print(f"Total Endpoints: {coverage_data['compliance']['total']}")
    print(f"Tested Endpoints: {coverage_data['compliance']['tested']}")
    print(f"Coverage: {coverage_data['compliance']['coverage']:.1f}%")
    print()
    print("Tested Endpoints:")
    for endpoint in coverage_data["compliance"]["endpoints"]["tested"]:
        print(f"  ✓ {endpoint}")
    print()
    if coverage_data["compliance"]["endpoints"]["missing"]:
        print("Missing Endpoints:")
        for endpoint in coverage_data["compliance"]["endpoints"]["missing"]:
            print(f"  ✗ {endpoint}")
    print()

    # Print DQ coverage
    print("DQ API ENDPOINTS")
    print("-" * 80)
    print(f"Total Endpoints: {coverage_data['dq']['total']}")
    print(f"Tested Endpoints: {coverage_data['dq']['tested']}")
    print(f"Coverage: {coverage_data['dq']['coverage']:.1f}%")
    print()
    print("Tested Endpoints:")
    for endpoint in coverage_data["dq"]["endpoints"]["tested"]:
        print(f"  ✓ {endpoint}")
    print()
    if coverage_data["dq"]["endpoints"]["missing"]:
        print("Missing Endpoints:")
        for endpoint in coverage_data["dq"]["endpoints"]["missing"]:
            print(f"  ✗ {endpoint}")
    print()

    # Overall coverage
    print("OVERALL COVERAGE")
    print("-" * 80)
    print(f"Total Endpoints: {coverage_data['overall']['total']}")
    print(f"Tested Endpoints: {coverage_data['overall']['tested']}")
    print(f"Coverage: {coverage_data['overall']['coverage']:.1f}%")
    print()

    # Check threshold
    threshold = 80.0
    if coverage_data["overall"]["coverage"] >= threshold:
        print(
            f"✅ Coverage {coverage_data['overall']['coverage']:.1f}% meets threshold of {threshold}%"
        )
        return 0
    else:
        print(
            f"❌ Coverage {coverage_data['overall']['coverage']:.1f}% is below threshold of {threshold}%"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
