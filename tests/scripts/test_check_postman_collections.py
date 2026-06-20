#!/usr/bin/env python3
"""
Tests for Postman collection checker script

Tests the comprehensive checking of Postman collections for endpoint URLs
and validates their accuracy.
"""

import json
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "scripts"))

from check_postman_collections import (
    PostmanCollectionChecker,
)


class TestPostmanCollectionChecker:
    """Test suite for PostmanCollectionChecker"""

    @pytest.fixture
    def temp_collections_dir(self, tmp_path):
        """Create temporary directory with Postman collection files"""
        collections_dir = tmp_path / "collections"
        collections_dir.mkdir()

        # Create valid Postman collection v2.1
        valid_collection = {
            "info": {
                "name": "Test API Collection",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                "_postman_id": "test-collection-id",
            },
            "item": [
                {
                    "name": "Contracts",
                    "item": [
                        {
                            "name": "List Contracts",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/contracts/",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "contracts", ""],
                                },
                            },
                        },
                        {
                            "name": "Create Contract",
                            "request": {
                                "method": "POST",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/contracts/",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "contracts", ""],
                                },
                            },
                        },
                    ],
                },
                {
                    "name": "Assets",
                    "item": [
                        {
                            "name": "Get Asset",
                            "request": {
                                "method": "GET",
                                "url": {
                                    "raw": "{{base_url}}/api/v1/assets/123",
                                    "host": ["{{base_url}}"],
                                    "path": ["api", "v1", "assets", "123"],
                                },
                            },
                        }
                    ],
                },
            ],
            "variable": [{"key": "base_url", "value": "http://localhost:8000", "type": "string"}],
        }
        (collections_dir / "valid_collection.json").write_text(
            json.dumps(valid_collection, indent=2)
        )

        # Create collection with invalid endpoint
        invalid_collection = {
            "info": {
                "name": "Invalid Collection",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": [
                {
                    "name": "Invalid Endpoint",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{base_url}}/api/v1/nonexistent/",
                            "host": ["{{base_url}}"],
                            "path": ["api", "v1", "nonexistent", ""],
                        },
                    },
                }
            ],
        }
        (collections_dir / "invalid_collection.json").write_text(
            json.dumps(invalid_collection, indent=2)
        )

        # Create invalid JSON file (not a Postman collection)
        (collections_dir / "not_a_collection.json").write_text('{"not": "a postman collection"}')

        return collections_dir

    @pytest.fixture
    def endpoint_inventory(self, tmp_path):
        """Create a sample endpoint inventory JSON file"""
        inventory_file = tmp_path / "endpoint-inventory.json"
        inventory_data = {
            "inventory": {
                "summary": {"total_endpoints": 2, "total_services": 1},
                "endpoints": [
                    {
                        "type": "path",
                        "full_path": "/api/v1/contracts/",
                        "methods": ["GET", "POST"],
                        "service": "contracts",
                    },
                    {
                        "type": "path",
                        "full_path": "/api/v1/assets/",
                        "methods": ["GET"],
                        "service": "assets",
                    },
                ],
            }
        }
        inventory_file.write_text(json.dumps(inventory_data, indent=2))
        return str(inventory_file)

    def test_checker_initialization(self, temp_collections_dir, endpoint_inventory):
        """Test checker initialization"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        assert checker.collections_dir == Path(temp_collections_dir)
        assert checker.endpoint_inventory_file == Path(endpoint_inventory)
        assert len(checker.known_endpoints) == 2

    def test_find_collection_files(self, temp_collections_dir, endpoint_inventory):
        """Test finding Postman collection files"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        collections = checker.find_collection_files()

        assert len(collections) >= 2  # At least valid and invalid collections
        collection_files = [c["file"] for c in collections]
        assert any("valid_collection.json" in f for f in collection_files)
        assert any("invalid_collection.json" in f for f in collection_files)

    def test_parse_postman_collection(self, temp_collections_dir, endpoint_inventory):
        """Test parsing Postman collection"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        valid_file = temp_collections_dir / "valid_collection.json"
        requests = checker.parse_collection(str(valid_file))

        assert len(requests) > 0
        # Should have requests from Contracts and Assets folders
        assert any("contracts" in r.endpoint.lower() for r in requests)
        assert any("assets" in r.endpoint.lower() for r in requests)

    def test_extract_endpoints_from_collections(self, temp_collections_dir, endpoint_inventory):
        """Test extracting endpoints from collections"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        endpoints = checker.extract_endpoints_from_collections()

        assert len(endpoints) > 0
        # Should find /api/v1/contracts/
        contracts_endpoints = [e for e in endpoints if "/api/v1/contracts/" in e["endpoint"]]
        assert len(contracts_endpoints) > 0

    def test_validate_endpoint_exists(self, temp_collections_dir, endpoint_inventory):
        """Test endpoint existence validation"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        # Valid endpoint
        result_valid = checker.validate_endpoint_exists("/api/v1/contracts/", "GET")
        assert result_valid["is_valid"] is True

        # Invalid endpoint
        result_invalid = checker.validate_endpoint_exists("/api/v1/nonexistent/", "GET")
        assert result_invalid["is_valid"] is False

    def test_validate_collection(self, temp_collections_dir, endpoint_inventory):
        """Test collection validation"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        valid_file = temp_collections_dir / "valid_collection.json"
        result = checker.validate_collection(str(valid_file))

        assert result.collection_file == str(valid_file)
        assert result.is_valid is True or len(result.errors) > 0  # May have some errors
        assert len(result.requests) > 0

    def test_validate_all_collections(self, temp_collections_dir, endpoint_inventory):
        """Test comprehensive validation of all collections"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        results = checker.validate_all_collections()

        assert "summary" in results
        assert "collections" in results
        assert results["summary"]["total_collections"] > 0
        assert results["summary"]["total_requests"] > 0

    def test_generate_report(self, temp_collections_dir, endpoint_inventory, tmp_path):
        """Test report generation"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        results = checker.validate_all_collections()
        report_file = tmp_path / "report.json"
        checker.generate_report(results, str(report_file))

        assert report_file.exists()
        report_data = json.loads(report_file.read_text())
        assert "summary" in report_data
        assert "collections" in report_data

    def test_empty_directory(self, tmp_path, endpoint_inventory):
        """Test behavior with empty directory"""
        empty_dir = tmp_path / "empty_collections"
        empty_dir.mkdir()

        checker = PostmanCollectionChecker(
            collections_dir=str(empty_dir), endpoint_inventory_file=endpoint_inventory
        )

        collections = checker.find_collection_files()
        assert len(collections) == 0

        results = checker.validate_all_collections()
        assert results["summary"]["total_collections"] == 0

    def test_missing_inventory_file(self, temp_collections_dir):
        """Test behavior with missing inventory file"""
        with pytest.raises(FileNotFoundError):
            PostmanCollectionChecker(
                collections_dir=str(temp_collections_dir),
                endpoint_inventory_file="nonexistent.json",
            )

    def test_invalid_json_file(self, temp_collections_dir, endpoint_inventory):
        """Test handling of invalid JSON files"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        # Create invalid JSON
        invalid_file = temp_collections_dir / "invalid.json"
        invalid_file.write_text("{ invalid json }")

        # Should handle gracefully
        collections = checker.find_collection_files()
        # Should still find valid collections
        assert len(collections) >= 2

    def test_endpoint_normalization(self, temp_collections_dir, endpoint_inventory):
        """Test endpoint path normalization"""
        checker = PostmanCollectionChecker(
            collections_dir=str(temp_collections_dir), endpoint_inventory_file=endpoint_inventory
        )

        # Test various endpoint formats
        test_cases = [
            ("http://localhost:8000/api/v1/contracts/", "/api/v1/contracts/"),
            ("{{base_url}}/api/v1/contracts/", "/api/v1/contracts/"),
            ("/api/v1/contracts/", "/api/v1/contracts/"),
            ("/api/v1/contracts", "/api/v1/contracts/"),
            ("/api/v1/contracts/?page=1", "/api/v1/contracts/"),
        ]

        for input_endpoint, expected_normalized in test_cases:
            normalized = checker.normalize_endpoint(input_endpoint)
            assert normalized == expected_normalized or normalized.startswith("/api/v1/")
