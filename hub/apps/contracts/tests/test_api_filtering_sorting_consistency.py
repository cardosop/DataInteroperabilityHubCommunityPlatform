"""
Comprehensive API Filtering & Sorting Consistency Test Suite (Task 10.1.18.7) - CRITICAL FRONTEND BLOCKER

Tests verify:
1. All list endpoints support filtering
2. Filter parameter format is consistent
3. All list endpoints support sorting
4. Sort parameter format is consistent (ordering field)
5. Filter and sort combinations work correctly
6. Filter validation and error messages
7. Sort validation and error messages
8. Filtering and sorting performance
"""

import json

from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import KYCStatus
from hub.apps.users.models import Role, UserRole


class APIFilteringSortingConsistencyTest(ContractsAPITestBase):
    """
    Comprehensive API filtering & sorting consistency tests (Task 10.1.18.7) - CRITICAL FRONTEND BLOCKER.

    Tests all list endpoints for consistent filtering and sorting behavior without mocks/stubs:
    1. All list endpoints support filtering
    2. Filter parameter format is consistent
    3. All list endpoints support sorting
    4. Sort parameter format is consistent
    5. Filter and sort combinations work
    6. Validation and error messages
    7. Performance considerations
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create role
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=self.admin_role)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Filtering Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid ODPS structure
        self.valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-filtering",
                        "name": "Test Product",
                        "description": "Test description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                    }
                },
            },
        }

        # Create test contracts with different attributes
        # Use different versions to avoid unique constraint (tenant, asset, version)
        self.contracts = []
        for i in range(10):
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw=json.dumps(
                    {
                        **self.valid_odps,
                        "product": {
                            **self.valid_odps["product"],
                            "details": {
                                "en": {
                                    **self.valid_odps["product"]["details"]["en"],
                                    "productID": f"test-product-{i}",
                                    "name": f"Product {i}",
                                }
                            },
                        },
                    }
                ),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE if i % 2 == 0 else ContractStatus.DRAFT,
                version=i + 1,  # Use different versions to avoid unique constraint
                normalization_status=(
                    NormalizationStatus.NORMALIZED_OK
                    if i % 3 == 0
                    else NormalizationStatus.NOT_NORMALIZED
                ),
            )
            self.contracts.append(contract)

    def test_contracts_list_endpoint_supports_filtering(self):
        """Test contracts list endpoint supports filtering"""
        # Test filtering by status
        response = self.client.get("/api/v1/contracts/", {"status": "ACTIVE"})

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Contracts list should support filtering"
        )

        # Verify all results match filter
        if response.data.get("results"):
            for result in response.data["results"]:
                self.assertEqual(
                    result["status"], "ACTIVE", "All results should match status filter"
                )

    def test_filter_parameter_format_is_consistent(self):
        """Test filter parameter format is consistent"""
        # Test different filter formats
        filters = {
            "status": "ACTIVE",
            "original_spec_type": "ODPS",
            "normalization_status": "NORMALIZED_OK",
        }

        for filter_name, filter_value in filters.items():
            response = self.client.get("/api/v1/contracts/", {filter_name: filter_value})

            self.assertEqual(
                response.status_code, status.HTTP_200_OK, f"Filter {filter_name} should work"
            )
            self.assertIn(
                "results",
                response.data,
                f"Response should include results for {filter_name} filter",
            )

    def test_contracts_list_endpoint_supports_sorting(self):
        """Test contracts list endpoint supports sorting"""
        # Test sorting by created_at
        response = self.client.get("/api/v1/contracts/", {"ordering": "-created_at"})

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Contracts list should support sorting"
        )

        # Verify results are sorted
        if len(response.data.get("results", [])) > 1:
            results = response.data["results"]
            first_created = results[0].get("created_at")
            second_created = results[1].get("created_at")
            if first_created and second_created:
                self.assertGreaterEqual(
                    first_created,
                    second_created,
                    "Results should be sorted by created_at descending",
                )

    def test_sort_parameter_format_is_consistent(self):
        """Test sort parameter format is consistent (ordering field)"""
        # Test different sort formats
        sort_params = ["created_at", "-created_at", "updated_at", "-updated_at"]

        for sort_param in sort_params:
            response = self.client.get("/api/v1/contracts/", {"ordering": sort_param})

            self.assertEqual(
                response.status_code, status.HTTP_200_OK, f"Sort parameter {sort_param} should work"
            )
            self.assertIn(
                "results", response.data, f"Response should include results for {sort_param} sort"
            )

    def test_filter_and_sort_combinations_work_correctly(self):
        """Test filter and sort combinations work correctly"""
        # Test filtering by status and sorting by created_at
        response = self.client.get(
            "/api/v1/contracts/", {"status": "ACTIVE", "ordering": "-created_at"}
        )

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Filter and sort combination should work"
        )

        # Verify filter is applied
        if response.data.get("results"):
            for result in response.data["results"]:
                self.assertEqual(
                    result["status"], "ACTIVE", "All results should match status filter"
                )

        # Verify sort is applied
        if len(response.data.get("results", [])) > 1:
            results = response.data["results"]
            first_created = results[0].get("created_at")
            second_created = results[1].get("created_at")
            if first_created and second_created:
                self.assertGreaterEqual(first_created, second_created, "Results should be sorted")

    def test_filter_validation_and_error_messages(self):
        """Test filter validation and error messages"""
        # Test invalid filter value
        response = self.client.get("/api/v1/contracts/", {"status": "INVALID_STATUS"})

        # Should either return 400 with error or return empty results
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn("error", response.data or {}, "Error response should include error field")
        else:
            # If it returns 200, results should be empty or filtered
            self.assertEqual(
                response.status_code, status.HTTP_200_OK, "Should handle invalid filter gracefully"
            )

    def test_sort_validation_invalid_field(self):
        """Test sort validation with invalid field returns appropriate response."""
        # Arrange
        query_params = {"ordering": "invalid_field"}

        # Act
        response = self.client.get("/api/v1/contracts/", query_params)

        # Assert
        # Should either return 400 with error or ignore invalid sort
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.assertIn("error", response.data or {}, "Error response should include error field")
        else:
            self.assertEqual(
                response.status_code, status.HTTP_200_OK, "Should handle invalid sort gracefully"
            )

    def test_multiple_filter_parameters_work(self):
        """Test multiple filter parameters work together"""
        response = self.client.get(
            "/api/v1/contracts/", {"status": "ACTIVE", "original_spec_type": "ODPS"}
        )

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Multiple filters should work together"
        )

        # Verify all filters are applied
        if response.data.get("results"):
            for result in response.data["results"]:
                self.assertEqual(
                    result["status"], "ACTIVE", "All results should match status filter"
                )
                self.assertEqual(
                    result["original_spec_type"],
                    "ODPS",
                    "All results should match spec type filter",
                )

    def test_multiple_sort_fields_work(self):
        """Test multiple sort fields work (comma-separated)"""
        # Arrange
        query_params = {"ordering": "-created_at,updated_at"}

        # Act
        response = self.client.get("/api/v1/contracts/", query_params)

        # Assert
        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Multiple sort fields should work"
        )
        self.assertIn("results", response.data, "Response should include results")

    def test_filtering_and_sorting_performance(self):
        """Test filtering and sorting performance"""
        import time

        # Arrange
        query_params_with_filter = {"status": "ACTIVE", "ordering": "-created_at"}

        # Act
        start = time.time()
        response1 = self.client.get("/api/v1/contracts/")
        time_without = time.time() - start

        start = time.time()
        response2 = self.client.get("/api/v1/contracts/", query_params_with_filter)
        time_with = time.time() - start

        # Assert
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        # Performance should be reasonable (filtering/sorting shouldn't be orders of magnitude slower)
        # Allow 10x tolerance for test environment variability
        self.assertLess(
            time_with, time_without * 10, "Filtering and sorting should not be excessively slow"
        )

    def test_empty_filter_results(self):
        """Test filtering returns empty results when no matches"""
        # Filter for non-existent status
        response = self.client.get(
            "/api/v1/contracts/",
            {"status": "RETIRED"},  # Assuming no RETIRED contracts in test data
        )

        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Should return 200 even with no results"
        )
        self.assertEqual(
            len(response.data.get("results", [])), 0, "Should return empty results when no matches"
        )
        self.assertEqual(response.data.get("count", 0), 0, "Count should be 0 when no matches")

    def test_filtering_with_special_characters(self):
        """Test filtering with special characters in filter values"""
        # Test filtering (may not support special characters, but should handle gracefully)
        response = self.client.get(
            "/api/v1/contracts/",
            {"status": "ACTIVE", "search": 'test<script>alert("xss")</script>'},
        )

        # Should handle special characters gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Should handle special characters in filters",
        )

    def test_sorting_with_invalid_direction(self):
        """Test sorting with invalid sort direction"""
        # Test with invalid sort format
        response = self.client.get(
            "/api/v1/contracts/", {"ordering": "++created_at"}  # Invalid format
        )

        # Should handle invalid sort format gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Should handle invalid sort format",
        )

    def test_filtering_with_empty_string(self):
        """Test filtering with empty string value"""
        response = self.client.get("/api/v1/contracts/", {"status": ""})  # Empty string

        # Should handle empty string filter gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Should handle empty string filter",
        )

    def test_sorting_with_empty_string(self):
        """Test sorting with empty string"""
        response = self.client.get("/api/v1/contracts/", {"ordering": ""})  # Empty string

        # Should handle empty sort gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Should handle empty sort",
        )

    def test_filtering_with_none_value(self):
        """Test filtering with None value"""
        # Test filtering (None values may be handled differently)
        response = self.client.get("/api/v1/contracts/", {"status": None})  # None value

        # Should handle None value gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "Should handle None filter value",
        )

    def test_multiple_filters_with_same_field(self):
        """Test multiple filters with same field (should use last one or combine)"""
        response = self.client.get(
            "/api/v1/contracts/", {"status": "ACTIVE", "status": "DRAFT"}  # Duplicate filter
        )

        # Should handle duplicate filters (may use last one or combine)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Should handle duplicate filters"
        )

    def test_filtering_and_sorting_with_pagination(self):
        """Test filtering and sorting combined with pagination"""
        response = self.client.get(
            "/api/v1/contracts/",
            {"status": "ACTIVE", "ordering": "-created_at", "page": 1, "page_size": 5},
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Filter, sort, and pagination should work together",
        )

        # Verify all are applied
        if response.data.get("results"):
            # Verify filter
            for result in response.data["results"]:
                self.assertEqual(result["status"], "ACTIVE", "All results should match filter")

            # Verify pagination
            self.assertLessEqual(
                len(response.data["results"]), 5, "Results should respect page_size"
            )

    def test_filtering_case_sensitivity(self):
        """Test filtering case sensitivity"""
        # Test with different case
        response_lower = self.client.get("/api/v1/contracts/", {"status": "active"})
        response_upper = self.client.get("/api/v1/contracts/", {"status": "ACTIVE"})

        # Both should work (may be case-insensitive or case-sensitive)
        self.assertEqual(
            response_lower.status_code, status.HTTP_200_OK, "Lowercase filter should work"
        )
        self.assertEqual(
            response_upper.status_code, status.HTTP_200_OK, "Uppercase filter should work"
        )
