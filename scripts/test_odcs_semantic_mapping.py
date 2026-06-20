#!/usr/bin/env python
"""
Test ODCS Semantic Mapping

This script tests that ODCS contracts are properly mapped to RDF/JSON-LD
by the semantic service. It verifies that semantic mapping works correctly
after DCS removal.

Usage:
    python scripts/test_odcs_semantic_mapping.py

Requirements:
    - Semantic service must be running
    - Fuseki must be running
    - Test database must be set up
"""

import os
import sys
from pathlib import Path
from typing import Any

import django
import requests

# Setup Django
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Configuration
SEMANTIC_SERVICE_URL = os.getenv("SEMANTIC_SERVICE_URL", "http://localhost:8082")
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://localhost:3030")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "hub")


def create_test_odcs_contract() -> dict[str, Any]:
    """Create a test ODCS contract for semantic mapping"""
    return {
        "apiVersion": "odcs.io/v3.0.2",
        "kind": "DataContract",
        "id": "test-semantic-mapping",
        "name": "Test Contract for Semantic Mapping",
        "version": "1.0.0",
        "description": "Test contract to verify ODCS semantic mapping",
        "schema": {
            "fields": [
                {
                    "name": "id",
                    "type": "string",
                    "nullable": False,
                    "description": "Unique identifier",
                },
                {
                    "name": "email",
                    "type": "string",
                    "nullable": True,
                    "description": "Email address",
                    "format": "email",
                },
            ]
        },
        "info": {
            "owners": [{"name": "Test Owner", "email": "owner@example.com"}],
            "tags": ["test", "semantic"],
        },
    }


def test_semantic_service_health() -> bool:
    """Test that semantic service is running"""
    try:
        response = requests.get(f"{SEMANTIC_SERVICE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Semantic service is healthy")
            return True
        else:
            print(f"✗ Semantic service health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Semantic service not reachable: {e}")
        return False


def test_jsonld_context_endpoint() -> bool:
    """Test that JSON-LD context endpoint works"""
    try:
        response = requests.get(f"{SEMANTIC_SERVICE_URL}/context.jsonld", timeout=5)
        if response.status_code == 200:
            context = response.json()
            if "@context" in context:
                print("✓ JSON-LD context endpoint works")
                # Verify context contains ODCS-related mappings
                ctx = context["@context"]
                if "DataContract" in ctx and "hub:DataContract" in ctx["DataContract"]:
                    print("  ✓ Context contains DataContract mapping")
                    return True
                else:
                    print("  ✗ Context missing DataContract mapping")
                    return False
            else:
                print("✗ Invalid JSON-LD context format")
                return False
        else:
            print(f"✗ JSON-LD context endpoint failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ JSON-LD context endpoint error: {e}")
        return False


def test_contract_mapping(contract_data: dict[str, Any], contract_uuid: str) -> bool:
    """Test that a contract can be mapped to RDF"""
    try:
        # Map contract to RDF
        response = requests.post(
            f"{SEMANTIC_SERVICE_URL}/map/contract",
            json={"hub_contract": contract_data, "contract_uuid": contract_uuid},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            if "contract_uri" in result and "triples_count" in result:
                print("✓ Contract mapped successfully")
                print(f"  Contract URI: {result['contract_uri']}")
                print(f"  Triples count: {result['triples_count']}")

                # Verify contract URI is resolvable
                if test_contract_uri_resolution(result["contract_uri"]):
                    return True
                else:
                    return False
            else:
                print("✗ Invalid mapping response format")
                return False
        else:
            print(f"✗ Contract mapping failed: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Contract mapping error: {e}")
        return False


def test_contract_uri_resolution(contract_uri: str) -> bool:
    """Test that contract URI can be resolved to JSON-LD"""
    try:
        # Extract resource path from URI
        # URI format: https://hub.example.com/id/contract/{uuid}
        if "/id/contract/" in contract_uri:
            resource_path = contract_uri.split("/id/contract/")[-1]
            response = requests.get(
                f"{SEMANTIC_SERVICE_URL}/id/contract/{resource_path}", timeout=5
            )

            if response.status_code == 200:
                jsonld = response.json()
                if "@context" in jsonld and "@id" in jsonld:
                    print("  ✓ Contract URI resolved to JSON-LD")
                    return True
                else:
                    print("  ✗ Invalid JSON-LD format")
                    return False
            else:
                print(f"  ✗ URI resolution failed: {response.status_code}")
                return False
        else:
            print(f"  ✗ Invalid contract URI format: {contract_uri}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"  ✗ URI resolution error: {e}")
        return False


def test_sparql_query() -> bool:
    """Test that SPARQL queries work for ODCS contracts"""
    try:
        # Query for all DataContract instances
        query = """
        PREFIX hub: <https://hub.example.com/ontology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        
        SELECT ?contract ?specType WHERE {
            ?contract a hub:DataContract .
            ?contract hub:contractSpecType ?specType .
        } LIMIT 10
        """

        response = requests.post(
            f"{SEMANTIC_SERVICE_URL}/sparql", json={"query": query}, timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if "results" in result or "bindings" in result:
                print("✓ SPARQL queries work")
                return True
            else:
                print("✗ Invalid SPARQL response format")
                return False
        else:
            print(f"✗ SPARQL query failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ SPARQL query error: {e}")
        return False


def main():
    """Run all semantic mapping tests"""
    print("=" * 80)
    print("ODCS Semantic Mapping Tests")
    print("=" * 80)
    print("")

    tests_passed = 0
    tests_failed = 0

    # Test 1: Semantic service health
    print("Test 1: Semantic Service Health Check")
    print("-" * 80)
    if test_semantic_service_health():
        tests_passed += 1
    else:
        tests_failed += 1
        print("\n⚠️  Semantic service is not running. Some tests will be skipped.")
        print("   Start semantic service with: docker-compose up semantic-service")
        print("")

    # Test 2: JSON-LD context endpoint
    print("\nTest 2: JSON-LD Context Endpoint")
    print("-" * 80)
    if test_jsonld_context_endpoint():
        tests_passed += 1
    else:
        tests_failed += 1

    # Test 3: Contract mapping (only if service is available)
    if tests_failed == 0:
        print("\nTest 3: Contract to RDF Mapping")
        print("-" * 80)
        contract_data = create_test_odcs_contract()
        contract_uuid = "test-uuid-123"

        if test_contract_mapping(contract_data, contract_uuid):
            tests_passed += 1
        else:
            tests_failed += 1

        # Test 4: SPARQL queries
        print("\nTest 4: SPARQL Query")
        print("-" * 80)
        if test_sparql_query():
            tests_passed += 1
        else:
            tests_failed += 1
    else:
        print("\n⚠️  Skipping contract mapping and SPARQL tests (service not available)")
        tests_failed += 1

    # Summary
    print("")
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print("")

    if tests_failed == 0:
        print("✓ All semantic mapping tests passed!")
        return 0
    else:
        print("✗ Some tests failed or services not available")
        print("")
        print("Note: These tests require the semantic service to be running.")
        print("Start services with: docker-compose up semantic-service fuseki")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
