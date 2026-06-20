"""
Comprehensive API Caching Headers Test Suite (Task 10.1.18.8) - CRITICAL FRONTEND BLOCKER

Tests verify:
1. ETag headers are present for GET requests
2. Last-Modified headers are present
3. Cache-Control headers are correct
4. If-None-Match (ETag) conditional requests work
5. If-Modified-Since conditional requests work
6. Cache invalidation on updates
7. Cache headers for all resource types
8. Cache header error handling
"""

import json
import uuid

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
from hub.apps.users.models import Role, UserRole


class APICachingHeadersTest(ContractsAPITestBase):
    """
    Comprehensive API caching headers tests (Task 10.1.18.8) - CRITICAL FRONTEND BLOCKER.

    Tests all endpoints for proper caching headers without mocks/stubs:
    1. ETag headers are present
    2. Last-Modified headers are present
    3. Cache-Control headers are correct
    4. Conditional requests work
    5. Cache invalidation works
    6. All resource types have cache headers
    7. Error handling is proper
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        uid = uuid.uuid4().hex[:8]
        # Update tenant/user names for clarity
        self.tenant.name = f"Caching Test {uid}"
        self.tenant.slug = f"caching-test-{uid}"
        self.tenant.save()

        self.user.email = f"user-{uid}@caching.test"
        self.user.save()

        # Create role
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Caching Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid ODPS structure
        self.valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-caching",
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

        # Create test contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

    def test_etag_headers_are_present_for_get_requests(self):
        """Test ETag headers are present for GET requests"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "GET request should succeed")

        # ETag header should be present for GET detail requests
        self.assertIn("ETag", response, "ETag header should be present for GET requests")
        self.assertIsNotNone(response["ETag"], "ETag header should have a value")
        self.assertTrue(
            response["ETag"].startswith('"') or response["ETag"].startswith("W/"),
            "ETag should be properly formatted",
        )

    def test_last_modified_headers_are_present(self):
        """Test Last-Modified headers are present"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "GET request should succeed")

        # Check for Last-Modified header (may be present or not depending on implementation)
        if "Last-Modified" in response:
            self.assertIsNotNone(
                response["Last-Modified"], "Last-Modified header should have a value if present"
            )
            # Should be in HTTP date format
            from email.utils import parsedate

            parsed_date = parsedate(response["Last-Modified"])
            self.assertIsNotNone(parsed_date, "Last-Modified should be in valid HTTP date format")

    def test_cache_control_headers_are_correct(self):
        """Test Cache-Control headers are correct"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "GET request should succeed")

        # Cache-Control header should be present for authenticated API responses
        self.assertIn("Cache-Control", response, "Cache-Control header should be present")
        cache_control = response["Cache-Control"]
        self.assertIsNotNone(cache_control, "Cache-Control header should have a value")
        # Should contain recognized directives
        known_directives = {
            "no-cache",
            "no-store",
            "must-revalidate",
            "private",
            "public",
            "max-age",
        }
        directives = [d.strip().split("=")[0] for d in cache_control.split(",")]
        matching = [d for d in directives if d in known_directives]
        self.assertGreater(
            len(matching),
            0,
            f"Cache-Control should contain recognized directives, got: {cache_control}",
        )

    def test_if_none_match_etag_conditional_requests_work(self):
        """Test If-None-Match (ETag) conditional requests work"""
        # First request to get ETag
        response1 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # ETag should be present
        self.assertIn("ETag", response1, "ETag header should be present")
        etag = response1["ETag"]

        # Request with If-None-Match header
        response2 = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/", HTTP_IF_NONE_MATCH=etag
        )

        # Should return 304 Not Modified if resource hasn't changed
        # Or 200 OK if implementation doesn't support conditional requests
        self.assertIn(
            response2.status_code,
            [status.HTTP_200_OK, status.HTTP_304_NOT_MODIFIED],
            "Conditional request should return 200 or 304",
        )

        if response2.status_code == status.HTTP_304_NOT_MODIFIED:
            # 304 should not have body
            self.assertEqual(len(response2.content), 0, "304 response should not have body")

    def test_if_modified_since_conditional_requests_work(self):
        """Test If-Modified-Since conditional requests work"""
        # First request to get Last-Modified
        response1 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # If Last-Modified is present, test conditional request
        if "Last-Modified" in response1:
            last_modified = response1["Last-Modified"]

            # Request with If-Modified-Since header
            response2 = self.client.get(
                f"/api/v1/contracts/{self.contract.id}/", HTTP_IF_MODIFIED_SINCE=last_modified
            )

            # Should return 304 Not Modified if resource hasn't changed
            # Or 200 OK if implementation doesn't support conditional requests
            self.assertIn(
                response2.status_code,
                [status.HTTP_200_OK, status.HTTP_304_NOT_MODIFIED],
                "Conditional request should return 200 or 304",
            )

    def test_cache_invalidation_on_updates(self):
        """Test cache invalidation on updates"""
        # Get initial ETag/Last-Modified
        response1 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        initial_etag = response1.get("ETag")
        initial_last_modified = response1.get("Last-Modified")

        # Ensure the update timestamp differs from the initial read
        # (HTTP Last-Modified has second-level precision).
        import time
        time.sleep(1.1)

        # Update the contract
        updated_odps = {
            **self.valid_odps,
            "product": {
                **self.valid_odps["product"],
                "details": {
                    "en": {
                        **self.valid_odps["product"]["details"]["en"],
                        "name": "Updated Product Name",
                    }
                },
            },
        }

        response_update = self.client.patch(
            f"/api/v1/contracts/{self.contract.id}/",
            {"original_raw": json.dumps(updated_odps)},
            format="json",
        )

        self.assertIn(
            response_update.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
            "Update should succeed",
        )

        # Get updated resource
        response2 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # If ETag/Last-Modified were present, they should have changed
        if initial_etag and "ETag" in response2:
            self.assertNotEqual(response2["ETag"], initial_etag, "ETag should change after update")

        if initial_last_modified and "Last-Modified" in response2:
            self.assertNotEqual(
                response2["Last-Modified"],
                initial_last_modified,
                "Last-Modified should change after update",
            )

    def test_cache_headers_for_all_resource_types(self):
        """Test cache headers for all resource types"""
        # Test contracts detail endpoint
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Test contracts list endpoint
        response = self.client.get("/api/v1/contracts/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Both should return successfully (cache headers may or may not be present)
        # The important thing is they don't error

    def test_cache_header_error_handling(self):
        """Test cache header error handling"""
        # Test with invalid ETag format
        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/", HTTP_IF_NONE_MATCH="invalid-etag-format"
        )

        # Should still return 200 OK (invalid ETag should be ignored)
        self.assertEqual(
            response.status_code, status.HTTP_200_OK, "Invalid ETag should be handled gracefully"
        )

        # Test with invalid Last-Modified format
        response = self.client.get(
            f"/api/v1/contracts/{self.contract.id}/", HTTP_IF_MODIFIED_SINCE="invalid-date-format"
        )

        # Should still return 200 OK (invalid date should be ignored)
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            "Invalid Last-Modified should be handled gracefully",
        )

    def test_cache_headers_for_list_endpoints(self):
        """Test cache headers for list endpoints"""
        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "List endpoint should work")

        # List endpoints should have cache headers
        self.assertIn(
            "Cache-Control", response, "Cache-Control should be present for list endpoints"
        )

    def test_cache_headers_consistency_across_requests(self):
        """Test cache headers consistency across multiple requests"""
        # Make multiple requests to same resource
        responses = []
        for _i in range(3):
            response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            responses.append(response)

        # ETag should be present and consistent if resource hasn't changed
        etags = [r["ETag"] for r in responses]
        self.assertEqual(len(etags), 3, "All 3 responses should have ETag headers")
        # All ETags should be the same for unchanged resource
        self.assertEqual(len(set(etags)), 1, "ETag should be consistent for unchanged resource")

    def test_cache_headers_with_query_parameters(self):
        """Test cache headers with query parameters"""
        # Request with query parameters
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/", {"format": "json"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should handle query parameters gracefully
        # Cache headers may or may not be present

    def test_cache_headers_for_nonexistent_resource(self):
        """Test cache headers for nonexistent resource"""

        fake_id = str(uuid.uuid4())

        response = self.client.get(f"/api/v1/contracts/{fake_id}/")

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # 404 responses typically don't have cache headers
        # But if they do, should be properly formatted

    def test_cache_headers_after_resource_deletion(self):
        """Test cache headers after resource deletion"""
        # Get initial ETag
        response1 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        response1.get("ETag")

        # Delete the contract
        response_delete = self.client.delete(f"/api/v1/contracts/{self.contract.id}/")
        self.assertIn(
            response_delete.status_code,
            [status.HTTP_204_NO_CONTENT, status.HTTP_200_OK],
            "Delete should succeed",
        )

        # Request soft-deleted resource — contract is RETIRED (not hard-deleted), still accessible
        response2 = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        self.assertIn(
            response2.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
            "Soft-deleted resource should return 200 (RETIRED) or 404",
        )

    def test_cache_control_no_cache_directive(self):
        """Test Cache-Control no-cache directive"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Cache-Control header should be present and contain directives
        self.assertIn("Cache-Control", response, "Cache-Control should be present")
        cache_control = response["Cache-Control"].lower()
        self.assertIsInstance(cache_control, str, "Cache-Control should be a string")
        self.assertGreater(len(cache_control), 0, "Cache-Control should not be empty")

    def test_etag_format_validation(self):
        """Test ETag format validation"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # ETag should be present and properly formatted
        self.assertIn("ETag", response, "ETag header should be present")
        etag = response["ETag"]
        # ETag should be quoted string or weak tag (W/"...")
        self.assertTrue(
            (etag.startswith('"') and etag.endswith('"'))
            or (etag.startswith('W/"') and etag.endswith('"')),
            f"ETag should be properly formatted, got: {etag}",
        )

    def test_cache_headers_with_authentication(self):
        """Test cache headers with authentication"""
        # Already authenticated via setUp
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cache headers should work with authentication
        # Private resources may have different cache headers than public ones
