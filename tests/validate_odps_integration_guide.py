#!/usr/bin/env python3
"""
Test script to validate ODPS Integration Guide implementation.

This script validates that all endpoints, workflows, and features documented
in docs/ODPS_INTEGRATION_GUIDE.md work as described.

Tests use REAL services (no mocks/stubs) and follow development best practices.
"""

import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Test configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
API_KEY = (
    os.environ.get("API_KEY") or
    os.environ.get("DATAHUB_API_KEY") or
    os.environ.get("TEST_API_KEY")
)
TEST_TIMEOUT = 30


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class ODPSIntegrationGuideValidator:
    """Validates ODPS Integration Guide implementation"""

    def __init__(self, api_base_url: str, api_key: Optional[str] = None):
        self.api_base_url = api_base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set headers
        if self.api_key:
            # API keys use "ApiKey" prefix, not "Bearer"
            self.session.headers.update({
                "Authorization": f"ApiKey {self.api_key}",
                "Content-Type": "application/json"
            })

        self.test_results = {
            "passed": [],
            "failed": [],
            "skipped": [],
            "errors": []
        }

    def log(self, message: str, color: str = Colors.RESET):
        """Log message with color"""
        print(f"{color}{message}{Colors.RESET}")

    def test_pass(self, test_name: str):
        """Record test pass"""
        self.test_results["passed"].append(test_name)
        self.log(f"✓ PASS: {test_name}", Colors.GREEN)

    def test_fail(self, test_name: str, reason: str):
        """Record test failure"""
        self.test_results["failed"].append((test_name, reason))
        self.log(f"✗ FAIL: {test_name}", Colors.RED)
        self.log(f"  Reason: {reason}", Colors.RED)

    def test_skip(self, test_name: str, reason: str):
        """Record test skip"""
        self.test_results["skipped"].append((test_name, reason))
        self.log(f"⊘ SKIP: {test_name}", Colors.YELLOW)
        self.log(f"  Reason: {reason}", Colors.YELLOW)

    def test_error(self, test_name: str, error: Exception):
        """Record test error"""
        self.test_results["errors"].append((test_name, str(error)))
        self.log(f"✗ ERROR: {test_name}", Colors.RED)
        self.log(f"  Error: {str(error)}", Colors.RED)

    def check_api_available(self) -> bool:
        """Check if API is available"""
        try:
            response = self.session.get(
                f"{self.api_base_url}/",
                timeout=5
            )
            return response.status_code in [200, 401, 403]
        except Exception as e:
            self.log(f"API not available: {str(e)}", Colors.RED)
            return False

    def create_test_tenant_and_user(self) -> tuple[Optional[str], Optional[str]]:
        """Create test tenant and user for testing"""
        # This would require admin access or a test setup script
        # For now, we'll use existing credentials or skip
        return None, None

    def test_odps_ingestion_product_first_flow(self):
        """Test ODPS ingestion via Product-First flow (REST API)"""
        test_name = "ODPS Ingestion - Product-First Flow (REST API)"

        try:
            # Create sample ODPS document with embedded ODCS
            odps_document = {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product for Integration Guide",
                            "description": "Test product created to validate integration guide"
                        }
                    },
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs.io/v3.0.2",
                            "kind": "DataContract",
                            "id": f"test-contract-{uuid.uuid4().hex[:8]}",
                            "name": "Test ODCS Contract",
                            "version": "1.0.0",
                            "schema": {
                                "fields": [
                                    {"name": "id", "type": "string", "description": "Unique identifier"},
                                    {"name": "name", "type": "string", "description": "Name field"}
                                ]
                            }
                        }
                    },
                    "marketplace": {
                        "pricingPlans": [
                            {
                                "planID": "basic",
                                "name": "Basic Plan",
                                "price": 9.99,
                                "currency": "USD",
                                "billingPeriod": "monthly"
                            }
                        ]
                    }
                }
            }

            # POST to /api/v1/contracts/products/
            response = self.session.post(
                f"{self.api_base_url}/contracts/products/",
                json={
                    "original_raw": json.dumps(odps_document),
                    "original_format": "JSON",
                    "resolve_external_refs": True
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 201:
                data = response.json()
                if "odps_contract" in data and "odcs_contract" in data:
                    self.test_pass(test_name)
                    return data["odps_contract"]["id"], data["odcs_contract"]["id"]
                else:
                    self.test_fail(test_name, f"Response missing required fields: {data}")
                    return None, None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None, None
            else:
                # Try to get more detailed error information
                error_details = response.text
                try:
                    error_json = response.json()
                    if "details" in error_json and "error" in error_json["details"]:
                        error_details = error_json["details"]["error"]
                    elif "error" in error_json:
                        error_details = error_json["error"]
                except:
                    pass
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {error_details}")
                return None, None

        except Exception as e:
            self.test_error(test_name, e)
            return None, None

    def test_odps_ingestion_link_flow(self, odcs_contract_id: Optional[str] = None):
        """Test ODPS ingestion via Link flow (REST API)"""
        test_name = "ODPS Ingestion - Link Flow (REST API)"

        try:
            # Create ODPS document without embedded contract
            odps_document = {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-linked-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Linked Product",
                            "description": "Test product for link flow validation"
                        }
                    },
                    "marketplace": {
                        "pricingPlans": [
                            {
                                "planID": "basic",
                                "name": "Basic Plan",
                                "price": 9.99,
                                "currency": "USD",
                                "billingPeriod": "monthly"
                            }
                        ]
                    }
                }
            }

            # If no ODCS contract provided, skip this test
            if not odcs_contract_id:
                self.test_skip(test_name, "ODCS contract ID required (run Product-First flow first)")
                return None

            # POST to /api/v1/contracts/ with link_odcs_id
            response = self.session.post(
                f"{self.api_base_url}/contracts/",
                json={
                    "original_raw": json.dumps(odps_document),
                    "original_format": "JSON",
                    "original_spec_type": "ODPS",
                    "link_odcs_id": odcs_contract_id
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 201:
                data = response.json()
                if "id" in data:
                    self.test_pass(test_name)
                    return data["id"]
                else:
                    self.test_fail(test_name, f"Response missing id field: {data}")
                    return None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None
            else:
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            self.test_error(test_name, e)
            return None

    def test_odps_export_json(self, odps_contract_id: Optional[str] = None):
        """Test ODPS export as JSON"""
        test_name = "ODPS Export - JSON Format"

        if not odps_contract_id:
            self.test_skip(test_name, "ODPS contract ID required")
            return None

        try:
            # GET /api/v1/contracts/{id}/export/?format=odps&output_format=json
            response = self.session.get(
                f"{self.api_base_url}/contracts/{odps_contract_id}/export/",
                params={
                    "format": "odps",
                    "output_format": "json",
                    "version": "4.1"
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 200:
                # Export endpoint may return JSON as string (formatted) or as dict
                # Try to parse as JSON first
                try:
                    data = response.json()
                    # If it's a dict, verify it's a valid ODPS document
                    if isinstance(data, dict) and "schema" in data and "product" in data:
                        if "opendataproducts.org" in str(data.get("schema", "")):
                            self.test_pass(test_name)
                            return data
                        else:
                            self.test_fail(test_name, "Response is not a valid ODPS document (missing schema)")
                            return None
                    else:
                        # If it's a string, try to parse it
                        if isinstance(data, str):
                            parsed = json.loads(data)
                            if isinstance(parsed, dict) and "schema" in parsed and "product" in parsed:
                                if "opendataproducts.org" in str(parsed.get("schema", "")):
                                    self.test_pass(test_name)
                                    return parsed
                except json.JSONDecodeError:
                    # Response might be a JSON string, try parsing the text
                    try:
                        data = json.loads(response.text)
                        if isinstance(data, dict) and "schema" in data and "product" in data:
                            if "opendataproducts.org" in str(data.get("schema", "")):
                                self.test_pass(test_name)
                                return data
                    except json.JSONDecodeError:
                        pass

                # If we get here, validation failed
                self.test_fail(test_name, f"Response is not a valid ODPS JSON document. Content type: {type(response.text).__name__}")
                return None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None
            elif response.status_code == 404:
                self.test_fail(test_name, "Contract not found")
                return None
            else:
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            self.test_error(test_name, e)
            return None

    def test_odps_export_yaml(self, odps_contract_id: Optional[str] = None):
        """Test ODPS export as YAML"""
        test_name = "ODPS Export - YAML Format"

        if not odps_contract_id:
            self.test_skip(test_name, "ODPS contract ID required")
            return None

        try:
            # GET /api/v1/contracts/{id}/export/?format=odps&output_format=yaml
            response = self.session.get(
                f"{self.api_base_url}/contracts/{odps_contract_id}/export/",
                params={
                    "format": "odps",
                    "output_format": "yaml"
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 200:
                # Export endpoint returns YAML as string directly
                content = response.text
                # Verify it's valid YAML by checking for ODPS schema
                if "opendataproducts.org" in content and "product:" in content:
                    self.test_pass(test_name)
                    return content
                else:
                    self.test_fail(test_name, "Response is not a valid ODPS YAML document")
                    return None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None
            elif response.status_code == 404:
                self.test_fail(test_name, "Contract not found")
                return None
            else:
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            self.test_error(test_name, e)
            return None

    def test_odps_download_json(self, odps_contract_id: Optional[str] = None):
        """Test ODPS download as JSON file"""
        test_name = "ODPS Download - JSON File"

        if not odps_contract_id:
            self.test_skip(test_name, "ODPS contract ID required")
            return None

        try:
            # GET /api/v1/contracts/{id}/download/?format=odps&output_format=json
            response = self.session.get(
                f"{self.api_base_url}/contracts/{odps_contract_id}/download/",
                params={
                    "format": "odps",
                    "output_format": "json"
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 200:
                # Check Content-Type
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type or "json" in content_type:
                    # Check Content-Disposition
                    content_disposition = response.headers.get("Content-Disposition", "")
                    if "attachment" in content_disposition or "filename" in content_disposition:
                        # Verify content is valid JSON
                        try:
                            json.loads(response.content)
                            self.test_pass(test_name)
                            return response.content
                        except json.JSONDecodeError:
                            self.test_fail(test_name, "Downloaded content is not valid JSON")
                            return None
                    else:
                        self.test_fail(test_name, "Missing Content-Disposition header")
                        return None
                else:
                    self.test_fail(test_name, f"Invalid Content-Type: {content_type}")
                    return None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None
            elif response.status_code == 404:
                self.test_fail(test_name, "Contract not found")
                return None
            else:
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            self.test_error(test_name, e)
            return None

    def test_odps_download_yaml(self, odps_contract_id: Optional[str] = None):
        """Test ODPS download as YAML file"""
        test_name = "ODPS Download - YAML File"

        if not odps_contract_id:
            self.test_skip(test_name, "ODPS contract ID required")
            return None

        try:
            # GET /api/v1/contracts/{id}/download/?format=odps&output_format=yaml
            response = self.session.get(
                f"{self.api_base_url}/contracts/{odps_contract_id}/download/",
                params={
                    "format": "odps",
                    "output_format": "yaml"
                },
                timeout=TEST_TIMEOUT
            )

            if response.status_code == 200:
                # Check Content-Type
                content_type = response.headers.get("Content-Type", "")
                if "yaml" in content_type.lower() or "application/x-yaml" in content_type:
                    # Check Content-Disposition
                    content_disposition = response.headers.get("Content-Disposition", "")
                    if "attachment" in content_disposition or "filename" in content_disposition:
                        self.test_pass(test_name)
                        return response.content
                    else:
                        self.test_fail(test_name, "Missing Content-Disposition header")
                        return None
                else:
                    self.test_fail(test_name, f"Invalid Content-Type: {content_type}")
                    return None
            elif response.status_code == 401:
                self.test_skip(test_name, "Authentication required (API key not set)")
                return None
            elif response.status_code == 404:
                self.test_fail(test_name, "Contract not found")
                return None
            else:
                self.test_fail(test_name, f"Unexpected status code: {response.status_code}, Response: {response.text}")
                return None

        except Exception as e:
            self.test_error(test_name, e)
            return None

    def run_all_tests(self):
        """Run all validation tests"""
        self.log("\n" + "="*80, Colors.BOLD)
        self.log("ODPS Integration Guide Validation", Colors.BOLD + Colors.BLUE)
        self.log("="*80 + "\n", Colors.BOLD)

        # Check API availability
        if not self.check_api_available():
            self.log("API is not available. Please ensure Docker Compose services are running.", Colors.RED)
            self.log("Run: docker compose ps", Colors.YELLOW)
            return False

        self.log(f"API Base URL: {self.api_base_url}", Colors.BLUE)
        if self.api_key:
            self.log("API Key: Set", Colors.BLUE)
        else:
            self.log("API Key: Not set (some tests may be skipped)", Colors.YELLOW)
        self.log("")

        # Test 1: Product-First Flow
        odps_contract_id, odcs_contract_id = self.test_odps_ingestion_product_first_flow()

        # Test 2: Link Flow (requires ODCS contract from Test 1)
        linked_odps_contract_id = self.test_odps_ingestion_link_flow(odcs_contract_id)

        # Test 3: Export as JSON
        exported_json = self.test_odps_export_json(odps_contract_id)

        # Test 4: Export as YAML
        exported_yaml = self.test_odps_export_yaml(odps_contract_id)

        # Test 5: Download as JSON
        downloaded_json = self.test_odps_download_json(odps_contract_id)

        # Test 6: Download as YAML
        downloaded_yaml = self.test_odps_download_yaml(odps_contract_id)

        # Print summary
        self.print_summary()

        # Return success if no failures or errors
        return len(self.test_results["failed"]) == 0 and len(self.test_results["errors"]) == 0

    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*80, Colors.BOLD)
        self.log("Test Summary", Colors.BOLD + Colors.BLUE)
        self.log("="*80, Colors.BOLD)

        total = (
            len(self.test_results["passed"]) +
            len(self.test_results["failed"]) +
            len(self.test_results["skipped"]) +
            len(self.test_results["errors"])
        )

        self.log(f"\nTotal Tests: {total}", Colors.BOLD)
        self.log(f"  {Colors.GREEN}Passed: {len(self.test_results['passed'])}{Colors.RESET}")
        self.log(f"  {Colors.RED}Failed: {len(self.test_results['failed'])}{Colors.RESET}")
        self.log(f"  {Colors.YELLOW}Skipped: {len(self.test_results['skipped'])}{Colors.RESET}")
        self.log(f"  {Colors.RED}Errors: {len(self.test_results['errors'])}{Colors.RESET}")

        if self.test_results["failed"]:
            self.log("\nFailed Tests:", Colors.RED + Colors.BOLD)
            for test_name, reason in self.test_results["failed"]:
                self.log(f"  - {test_name}: {reason}", Colors.RED)

        if self.test_results["errors"]:
            self.log("\nErrors:", Colors.RED + Colors.BOLD)
            for test_name, error in self.test_results["errors"]:
                self.log(f"  - {test_name}: {error}", Colors.RED)

        if self.test_results["skipped"]:
            self.log("\nSkipped Tests:", Colors.YELLOW + Colors.BOLD)
            for test_name, reason in self.test_results["skipped"]:
                self.log(f"  - {test_name}: {reason}", Colors.YELLOW)

        self.log("")


def main():
    """Main entry point"""
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")
    api_key = (
        os.environ.get("API_KEY") or
        os.environ.get("DATAHUB_API_KEY") or
        os.environ.get("TEST_API_KEY")
    )

    validator = ODPSIntegrationGuideValidator(api_base_url, api_key)
    success = validator.run_all_tests()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

