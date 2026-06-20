#!/usr/bin/env python3
"""
API Endpoint Testing Script

Comprehensively tests all existing API endpoints to verify functionality,
document working/broken/deprecated endpoints, and measure performance characteristics.

This script:
1. Tests all endpoints from the API inventory
2. Measures response times (performance)
3. Documents working/broken/deprecated endpoints
4. Updates the inventory file with test results
5. Generates a comprehensive test report

Usage:
    python scripts/test-api-endpoints.py [--base-url BASE_URL] [--username USERNAME] [--password PASSWORD]
"""

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@dataclass
class EndpointTestResult:
    """Result of testing a single endpoint."""

    endpoint: str
    method: str
    status: str  # working, broken, deprecated, skipped
    status_code: int | None = None
    response_time_ms: float | None = None
    error_message: str | None = None
    requires_auth: bool = False
    requires_data: bool = False
    tested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    notes: str = ""


@dataclass
class TestSummary:
    """Summary of all endpoint tests."""

    total_endpoints: int = 0
    tested: int = 0
    working: int = 0
    broken: int = 0
    deprecated: int = 0
    skipped: int = 0
    avg_response_time_ms: float = 0.0
    p50_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0


class APIEndpointTester:
    """Comprehensive API endpoint tester."""

    def __init__(self, base_url: str, username: str | None = None, password: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1"
        self.username = username
        self.password = password
        self.auth_token: str | None = None
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update(
            {"Content-Type": "application/json", "Accept": "application/json"}
        )

    def authenticate(self) -> bool:
        """Authenticate and get JWT token."""
        if not self.username or not self.password:
            print("⚠️  No credentials provided, testing without authentication")
            return False

        try:
            response = self.session.post(
                f"{self.api_base}/auth/login/",
                json={"email": self.username, "password": self.password},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                if self.auth_token:
                    self.session.headers["Authorization"] = f"Bearer {self.auth_token}"
                    print(f"✅ Authenticated as {self.username}")
                    return True
                else:
                    print("⚠️  Login successful but no token received")
                    return False
            else:
                print(f"⚠️  Authentication failed: {response.status_code} - {response.text[:100]}")
                return False
        except Exception as e:
            print(f"⚠️  Authentication error: {e!s}")
            return False

    def test_endpoint(
        self, endpoint: str, method: str, requires_auth: bool = True, requires_data: bool = False
    ) -> EndpointTestResult:
        """Test a single endpoint."""
        result = EndpointTestResult(
            endpoint=endpoint,
            method=method.upper(),
            status="skipped",
            requires_auth=requires_auth,
            requires_data=requires_data,
        )

        # Skip if requires auth but we don't have token
        if requires_auth and not self.auth_token:
            result.status = "skipped"
            result.notes = "Requires authentication but no token available"
            return result

        # Build full URL
        # Handle endpoints that are not under /api/v1/ (e.g., /health/, /metrics/)
        if endpoint.startswith("/health/") or endpoint.startswith("/metrics/"):
            # These are root-level endpoints, not under /api/v1/
            url = f"{self.base_url}{endpoint}"
        elif endpoint.startswith("/"):
            # Standard /api/v1/ endpoints
            url = f"{self.api_base}{endpoint}"
        elif endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.api_base}/{endpoint}"

        # Prepare request
        kwargs = {"timeout": 30, "allow_redirects": False}

        # Add request body for POST/PUT/PATCH if needed
        if method.upper() in ["POST", "PUT", "PATCH"]:
            if requires_data:
                # Try to provide minimal valid data
                kwargs["json"] = self._get_minimal_payload(endpoint, method)
            else:
                kwargs["json"] = {}

        # Make request and measure time
        try:
            start_time = time.time()
            response = self.session.request(method.upper(), url, **kwargs)
            response_time_ms = (time.time() - start_time) * 1000

            result.status_code = response.status_code
            result.response_time_ms = round(response_time_ms, 2)

            # Determine status
            if response.status_code in [200, 201, 204]:
                result.status = "working"
            elif response.status_code == 401:
                result.status = "broken"
                result.error_message = "Unauthorized - authentication required"
            elif response.status_code == 403:
                result.status = "broken"
                result.error_message = "Forbidden - insufficient permissions"
            elif response.status_code == 404:
                result.status = "broken"
                result.error_message = "Not found - endpoint may not exist"
            elif response.status_code == 405:
                # Method Not Allowed - endpoint exists but doesn't support this HTTP method
                result.status = "broken"
                result.error_message = (
                    f"Method {method.upper()} not allowed - endpoint may only support other methods"
                )
                result.notes = "Endpoint exists but doesn't support this HTTP method. Check inventory for correct method."
            elif response.status_code == 410:
                result.status = "deprecated"
                result.error_message = "Gone - endpoint is deprecated"
            elif response.status_code in [500, 502, 503, 504]:
                result.status = "broken"
                result.error_message = f"Server error: {response.status_code}"
            elif response.status_code == 429:
                result.status = "working"
                result.notes = "Rate limited (expected behavior)"
            elif response.status_code == 400:
                # Bad Request - endpoint exists but request is invalid
                # This is actually a good sign - endpoint exists and is processing the request
                result.status = "working"
                result.notes = (
                    "Endpoint exists (400 Bad Request indicates endpoint is processing request)"
                )
            else:
                result.status = "broken"
                result.error_message = f"Unexpected status: {response.status_code}"

        except requests.exceptions.Timeout:
            result.status = "broken"
            result.error_message = "Request timeout (>30s)"
        except requests.exceptions.ConnectionError:
            result.status = "broken"
            result.error_message = "Connection error - service may be down"
        except Exception as e:
            result.status = "broken"
            result.error_message = f"Error: {e!s}"

        return result

    def _get_minimal_payload(self, endpoint: str, method: str) -> dict:
        """Get minimal valid payload for an endpoint."""
        # Common payloads based on endpoint patterns
        if "asset" in endpoint.lower():
            return {"name": "test-asset", "description": "Test asset"}
        elif "contract" in endpoint.lower():
            return {
                "original_raw": '{"apiVersion":"odcs/v3","kind":"DataContract","id":"test"}',
                "original_format": "JSON",
            }
        elif "dataset" in endpoint.lower():
            return {"name": "test-dataset", "format": "CSV"}
        elif "auth" in endpoint.lower() and "register" in endpoint.lower():
            return {"email": "test@example.com", "password": "Test123!@#", "name": "Test User"}
        elif "auth" in endpoint.lower() and "password-reset" in endpoint.lower():
            return {"email": "test@example.com"}
        elif "search" in endpoint.lower():
            return {"q": "test"}
        else:
            return {}

    def parse_inventory(self, inventory_path: Path) -> list[tuple[str, str]]:
        """
        Parse API inventory file to extract endpoints.

        Supports multiple markdown formats:
        - Table format: | Method | Path | View | Action | Type |
        - Header format: #### METHOD /api/v1/path/
        - Standardized endpoint patterns from current-api-inventory.md
        """
        endpoints = []

        if not inventory_path.exists():
            print(f"⚠️  Inventory file not found: {inventory_path}")
            return endpoints

        content = inventory_path.read_text()
        lines = content.split("\n")

        # Track if we're in a table
        in_table = False

        for _i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip empty lines
            if not line_stripped:
                continue

            # Detect table start (look for header row with Method, Path, etc.)
            if "|" in line_stripped and ("Method" in line_stripped or "GET" in line_stripped):
                # Check if it's a header row (contains Method, Path, View, etc.)
                if any(
                    keyword in line_stripped
                    for keyword in ["Method", "Path", "View", "Action", "Type"]
                ):
                    in_table = True
                    continue
                # Check if it's a separator row (contains dashes)
                elif "---" in line_stripped or re.match(r"^\|[\s\-|:]+\|", line_stripped):
                    continue

            # Parse table rows
            if in_table and "|" in line_stripped:
                parts = [p.strip() for p in line_stripped.split("|")]
                # Remove empty first/last elements from split
                parts = [p for p in parts if p]

                if len(parts) >= 2:
                    # Try to find method and path
                    method = None
                    endpoint = None

                    # Method is usually first or second column
                    for part in parts[:3]:
                        part_upper = part.upper()
                        if part_upper in [
                            "GET",
                            "POST",
                            "PUT",
                            "PATCH",
                            "DELETE",
                            "HEAD",
                            "OPTIONS",
                        ]:
                            method = part_upper
                            break

                    # Path is usually second or third column (after method)
                    for part in parts[1:4]:
                        # Clean up path (remove backticks, whitespace)
                        cleaned = part.replace("`", "").strip()
                        # Check if it looks like a path
                        if cleaned.startswith("/api/v1/") or (
                            cleaned.startswith("/") and "api" in cleaned.lower()
                        ):
                            endpoint = cleaned
                            break

                    if method and endpoint:
                        endpoints.append((endpoint, method))
                        continue

            # Parse header format: #### METHOD /api/v1/path/
            if line_stripped.startswith("#### "):
                header_content = line_stripped.replace("#### ", "").strip()
                # Try to extract method and path
                parts = header_content.split()
                if len(parts) >= 2:
                    method = parts[0].upper()
                    endpoint = parts[1]
                    # Validate method
                    if method in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
                        # Validate endpoint format
                        if endpoint.startswith("/") or "api" in endpoint.lower():
                            endpoints.append((endpoint, method))
                            continue

            # Reset table state if we hit a new section
            if line_stripped.startswith("### ") or line_stripped.startswith("## "):
                in_table = False

        # Deduplicate and normalize
        seen = set()
        unique_endpoints = []
        for endpoint, method in endpoints:
            # Normalize endpoint (ensure trailing slash consistency)
            normalized_endpoint = endpoint.rstrip("/") + "/" if endpoint else endpoint

            # Normalize method
            normalized_method = method.upper()

            key = (normalized_endpoint, normalized_method)
            if key not in seen:
                seen.add(key)
                unique_endpoints.append((normalized_endpoint, normalized_method))

        return unique_endpoints

    def test_all_endpoints(self, endpoints: list[tuple[str, str]]) -> list[EndpointTestResult]:
        """Test all endpoints."""
        results = []
        total = len(endpoints)

        print(f"\n🧪 Testing {total} endpoints...\n")

        for i, (endpoint, method) in enumerate(endpoints, 1):
            print(f"[{i}/{total}] Testing {method} {endpoint}...", end=" ", flush=True)

            # Determine if endpoint requires auth
            requires_auth = not any(
                public in endpoint.lower()
                for public in ["login", "register", "password-reset", "health", "openapi"]
            )

            # Determine if endpoint requires data
            requires_data = method in ["POST", "PUT", "PATCH"] and any(
                create in endpoint.lower() for create in ["create", "new", "register"]
            )

            result = self.test_endpoint(endpoint, method, requires_auth, requires_data)
            results.append(result)

            # Print status
            if result.status == "working":
                print(f"✅ {result.status_code} ({result.response_time_ms}ms)")
            elif result.status == "broken":
                print(f"❌ {result.status} - {result.error_message}")
            elif result.status == "deprecated":
                print(f"⚠️  {result.status} - {result.error_message}")
            else:
                print(f"⏭️  {result.status} - {result.notes}")

        return results

    def generate_summary(self, results: list[EndpointTestResult]) -> TestSummary:
        """Generate test summary statistics."""
        summary = TestSummary()
        summary.total_endpoints = len(results)

        working_times = []

        for result in results:
            summary.tested += 1

            if result.status == "working":
                summary.working += 1
                if result.response_time_ms:
                    working_times.append(result.response_time_ms)
            elif result.status == "broken":
                summary.broken += 1
            elif result.status == "deprecated":
                summary.deprecated += 1
            else:
                summary.skipped += 1

        # Calculate percentiles
        if working_times:
            working_times.sort()
            summary.avg_response_time_ms = round(sum(working_times) / len(working_times), 2)
            summary.p50_response_time_ms = round(working_times[len(working_times) // 2], 2)
            summary.p95_response_time_ms = (
                round(working_times[int(len(working_times) * 0.95)], 2)
                if len(working_times) > 20
                else round(working_times[-1], 2)
            )
            summary.p99_response_time_ms = (
                round(working_times[int(len(working_times) * 0.99)], 2)
                if len(working_times) > 100
                else round(working_times[-1], 2)
            )

        return summary

    def generate_report(self, results: list[EndpointTestResult], summary: TestSummary) -> str:
        """Generate markdown test report."""
        lines = []

        lines.append("# API Endpoint Test Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now(UTC).isoformat()}")
        lines.append(f"**Base URL**: {self.base_url}")
        lines.append(f"**Tested By**: {self.username or 'Anonymous'}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Endpoints**: {summary.total_endpoints}")
        lines.append(f"- **Tested**: {summary.tested}")
        lines.append(f"- **Working**: {summary.working} ✅")
        lines.append(f"- **Broken**: {summary.broken} ❌")
        lines.append(f"- **Deprecated**: {summary.deprecated} ⚠️")
        lines.append(f"- **Skipped**: {summary.skipped} ⏭️")
        lines.append("")

        if summary.avg_response_time_ms > 0:
            lines.append("### Performance Metrics")
            lines.append("")
            lines.append(f"- **Average Response Time**: {summary.avg_response_time_ms}ms")
            lines.append(f"- **P50 (Median)**: {summary.p50_response_time_ms}ms")
            lines.append(f"- **P95**: {summary.p95_response_time_ms}ms")
            lines.append(f"- **P99**: {summary.p99_response_time_ms}ms")
            lines.append("")

        # Working endpoints
        working = [r for r in results if r.status == "working"]
        if working:
            lines.append("## Working Endpoints")
            lines.append("")
            lines.append("| Endpoint | Method | Status Code | Response Time (ms) |")
            lines.append("|----------|--------|-------------|-------------------|")
            for result in sorted(working, key=lambda x: x.response_time_ms or 0):
                lines.append(
                    f"| `{result.endpoint}` | {result.method} | {result.status_code} | {result.response_time_ms} |"
                )
            lines.append("")

        # Broken endpoints
        broken = [r for r in results if r.status == "broken"]
        if broken:
            lines.append("## Broken Endpoints")
            lines.append("")
            lines.append("| Endpoint | Method | Status Code | Error |")
            lines.append("|----------|--------|-------------|-------|")
            for result in broken:
                error = result.error_message or "Unknown error"
                lines.append(
                    f"| `{result.endpoint}` | {result.method} | {result.status_code or 'N/A'} | {error} |"
                )
            lines.append("")

        # Deprecated endpoints
        deprecated = [r for r in results if r.status == "deprecated"]
        if deprecated:
            lines.append("## Deprecated Endpoints")
            lines.append("")
            lines.append("| Endpoint | Method | Status Code | Notes |")
            lines.append("|----------|--------|-------------|-------|")
            for result in deprecated:
                lines.append(
                    f"| `{result.endpoint}` | {result.method} | {result.status_code} | {result.error_message} |"
                )
            lines.append("")

        # Skipped endpoints
        skipped = [r for r in results if r.status == "skipped"]
        if skipped:
            lines.append("## Skipped Endpoints")
            lines.append("")
            lines.append("| Endpoint | Method | Reason |")
            lines.append("|----------|--------|--------|")
            for result in skipped:
                lines.append(f"| `{result.endpoint}` | {result.method} | {result.notes} |")
            lines.append("")

        # Detailed results
        lines.append("## Detailed Results")
        lines.append("")
        for result in results:
            lines.append(f"### {result.method} {result.endpoint}")
            lines.append("")
            lines.append(f"- **Status**: {result.status}")
            if result.status_code:
                lines.append(f"- **Status Code**: {result.status_code}")
            if result.response_time_ms:
                lines.append(f"- **Response Time**: {result.response_time_ms}ms")
            if result.error_message:
                lines.append(f"- **Error**: {result.error_message}")
            if result.notes:
                lines.append(f"- **Notes**: {result.notes}")
            lines.append("")

        return "\n".join(lines)

    def update_inventory(self, inventory_path: Path, results: list[EndpointTestResult]):
        """Update inventory file with test results."""
        if not inventory_path.exists():
            print(f"⚠️  Inventory file not found: {inventory_path}")
            return

        content = inventory_path.read_text()

        # Create a mapping of endpoint+method to result
        results_map = {(r.endpoint, r.method): r for r in results}

        # Add test results section at the end
        lines = content.split("\n")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Endpoint Test Results")
        lines.append("")
        lines.append(f"**Last Tested**: {datetime.now(UTC).isoformat()}")
        lines.append("")
        lines.append("| Endpoint | Method | Status | Status Code | Response Time (ms) | Notes |")
        lines.append("|----------|--------|--------|-------------|-------------------|-------|")

        for endpoint, method in sorted(set((r.endpoint, r.method) for r in results)):
            result = results_map.get((endpoint, method))
            if result:
                status_icon = (
                    "✅"
                    if result.status == "working"
                    else "❌"
                    if result.status == "broken"
                    else "⚠️"
                    if result.status == "deprecated"
                    else "⏭️"
                )
                lines.append(
                    f"| `{endpoint}` | {method} | {status_icon} {result.status} | "
                    f"{result.status_code or 'N/A'} | {result.response_time_ms or 'N/A'} | {result.notes or ''} |"
                )

        inventory_path.write_text("\n".join(lines))
        print(f"\n✅ Updated inventory file: {inventory_path}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test all API endpoints")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument(
        "--inventory",
        default="docs/api-audit/current-api-inventory.md",
        help="Path to API inventory file",
    )
    parser.add_argument(
        "--output",
        default="docs/api-audit/endpoint-test-report.md",
        help="Path to output test report",
    )
    parser.add_argument(
        "--skip-auth", action="store_true", help="Skip authentication (test public endpoints only)"
    )

    args = parser.parse_args()

    # Initialize tester
    tester = APIEndpointTester(args.base_url, args.username, args.password)

    # Authenticate if credentials provided
    if not args.skip_auth and args.username and args.password:
        if not tester.authenticate():
            print("⚠️  Continuing without authentication (some endpoints may be skipped)")
    elif args.skip_auth:
        print("⏭️  Skipping authentication (testing public endpoints only)")

    # Parse inventory
    inventory_path = Path(args.inventory)
    endpoints = tester.parse_inventory(inventory_path)

    if not endpoints:
        print("❌ No endpoints found in inventory file")
        return 1

    print(f"📋 Found {len(endpoints)} endpoints in inventory")

    # Test all endpoints
    results = tester.test_all_endpoints(endpoints)

    # Generate summary
    summary = tester.generate_summary(results)

    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Endpoints: {summary.total_endpoints}")
    print(f"Tested: {summary.tested}")
    print(f"Working: {summary.working} ✅")
    print(f"Broken: {summary.broken} ❌")
    print(f"Deprecated: {summary.deprecated} ⚠️")
    print(f"Skipped: {summary.skipped} ⏭️")
    if summary.avg_response_time_ms > 0:
        print("\nPerformance:")
        print(f"  Average: {summary.avg_response_time_ms}ms")
        print(f"  P50: {summary.p50_response_time_ms}ms")
        print(f"  P95: {summary.p95_response_time_ms}ms")
        print(f"  P99: {summary.p99_response_time_ms}ms")
    print("=" * 60)

    # Generate report
    report = tester.generate_report(results, summary)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report)
    print(f"\n✅ Test report saved to: {output_path}")

    # Update inventory
    tester.update_inventory(inventory_path, results)

    # Save JSON results
    json_path = Path(args.output).with_suffix(".json")
    json_data = {
        "summary": asdict(summary),
        "results": [asdict(r) for r in results],
        "tested_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
    }
    json_path.write_text(json.dumps(json_data, indent=2))
    print(f"✅ JSON results saved to: {json_path}")

    return 0 if summary.broken == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
