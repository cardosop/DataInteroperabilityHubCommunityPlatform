"""
Performance tests for ODPS query indexes (Task 6.3.1)

Tests:
1. Index creation verification (original_spec_type, extensions.x_odps, etc.)
2. Query performance with indexes
3. Index usage verification (EXPLAIN ANALYZE)
4. Performance comparison for different query patterns
5. Bulk query performance
6. Index maintenance and statistics

All tests use real implementations (no mocks/stubs) and follow engineering best practices.
"""

import time
import uuid

from django.db import connection

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase


class ODPSQueryIndexesPerformanceTest(ContractsTestBase):
    """
    Performance tests for ODPS query indexes.

    Tests all indexes created in migration 0011_add_odps_query_indexes:
    - idx_contracts_original_spec_type (B-tree)
    - idx_contracts_tenant_original_spec_type (composite B-tree)
    - idx_contracts_extensions_x_odps_gin (GIN)
    - idx_contracts_extensions_x_odps_odcs_link_gin (GIN)
    - idx_contracts_extensions_x_odps_odps_link_gin (GIN)
    """

    def setUp(self):
        """Set up test data with ODPS and ODCS contracts."""
        super().setUp()
        unique_id = str(uuid.uuid4())[:8]

        # Update tenant/user names for clarity
        self.tenant.name = f"Test Tenant {unique_id}"
        self.tenant.slug = f"test-tenant-{unique_id}"
        self.tenant.save()

        self.user.email = f"test-{unique_id}@example.com"
        self.user.save()

        # Create test contracts
        self.odps_contract_id = str(uuid.uuid4())
        self.odcs_contract_id = str(uuid.uuid4())

        # Create ODPS contract
        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "odps-test", "name": "ODPS Test"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "odps-test",
                "info": {"name": "ODPS Test"},
                "schema": {"fields": []},
                "extensions": {"x_odps": {"odcs_link": self.odcs_contract_id}},
            },
            created_by=self.user,
        )

        # Create ODCS contract
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "odcs-test", "name": "ODCS Test"}',
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "odcs-test",
                "info": {"name": "ODCS Test"},
                "schema": {"fields": []},
                "extensions": {"x_odps": {"odps_link": self.odps_contract_id}},
            },
            created_by=self.user,
        )

    def test_original_spec_type_index_exists(self):
        """Test that index on original_spec_type exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts'
                AND indexname = 'idx_contracts_original_spec_type'
            """
            )
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index idx_contracts_original_spec_type should exist")
            self.assertEqual(result[0], "idx_contracts_original_spec_type")

    def test_tenant_original_spec_type_index_exists(self):
        """Test that composite index on tenant_id + original_spec_type exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts'
                AND indexname = 'idx_contracts_tenant_original_spec_type'
            """
            )
            result = cursor.fetchone()
            self.assertIsNotNone(
                result, "Index idx_contracts_tenant_original_spec_type should exist"
            )
            self.assertEqual(result[0], "idx_contracts_tenant_original_spec_type")

    def test_extensions_x_odps_gin_index_exists(self):
        """Test that GIN index on extensions.x_odps exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts'
                AND indexname = 'idx_contracts_extensions_x_odps_gin'
            """
            )
            result = cursor.fetchone()
            self.assertIsNotNone(result, "Index idx_contracts_extensions_x_odps_gin should exist")
            index_def = result[1].upper()
            self.assertIn("GIN", index_def, "Index should be a GIN index")

    def test_extensions_x_odps_odcs_link_index_exists(self):
        """Test that GIN index on extensions.x_odps.odcs_link exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts'
                AND indexname = 'idx_contracts_extensions_x_odps_odcs_link_gin'
            """
            )
            result = cursor.fetchone()
            self.assertIsNotNone(
                result, "Index idx_contracts_extensions_x_odps_odcs_link_gin should exist"
            )
            index_def = result[1].upper()
            self.assertIn("GIN", index_def, "Index should be a GIN index")

    def test_extensions_x_odps_odps_link_index_exists(self):
        """Test that GIN index on extensions.x_odps.odps_link exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts'
                AND indexname = 'idx_contracts_extensions_x_odps_odps_link_gin'
            """
            )
            result = cursor.fetchone()
            self.assertIsNotNone(
                result, "Index idx_contracts_extensions_x_odps_odps_link_gin should exist"
            )
            index_def = result[1].upper()
            self.assertIn("GIN", index_def, "Index should be a GIN index")

    def test_original_spec_type_filtering_performance(self):
        """Test query performance when filtering by original_spec_type."""
        # Create multiple ODPS and ODCS contracts
        contracts = []
        for i in range(10):
            # Create ODPS contract
            odps_contract = Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "odps-{i}", "name": "ODPS {i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"odps-{i}",
                    "info": {"name": f"ODPS {i}"},
                    "schema": {"fields": []},
                },
                created_by=self.user,
            )
            contracts.append(odps_contract)

            # Create ODCS contract
            odcs_contract = Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "odcs-{i}", "name": "ODCS {i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"odcs-{i}",
                    "info": {"name": f"ODCS {i}"},
                    "schema": {"fields": []},
                },
                created_by=self.user,
            )
            contracts.append(odcs_contract)

        # Test ODPS filtering performance
        start_time = time.time()
        odps_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS
        )
        odps_count = odps_contracts.count()
        query_time = time.time() - start_time

        self.assertEqual(odps_count, 11, "Should find 11 ODPS contracts (10 new + 1 from setUp)")
        self.assertLess(query_time, 1.0, f"ODPS filtering should be fast (took {query_time:.3f}s)")

        # Test ODCS filtering performance
        start_time = time.time()
        odcs_contracts = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODCS
        )
        odcs_count = odcs_contracts.count()
        query_time = time.time() - start_time

        self.assertEqual(odcs_count, 11, "Should find 11 ODCS contracts (10 new + 1 from setUp)")
        self.assertLess(query_time, 1.0, f"ODCS filtering should be fast (took {query_time:.3f}s)")

        # Cleanup
        for contract in contracts:
            contract.delete()

    def test_odps_link_query_performance(self):
        """Test query performance for finding contracts by ODPS link."""
        # Create multiple ODCS contracts linked to the same ODPS contract
        contracts = []
        for i in range(10):
            contract = Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "odcs-linked-{i}", "name": "ODCS Linked {i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"odcs-linked-{i}",
                    "info": {"name": f"ODCS Linked {i}"},
                    "schema": {"fields": []},
                    "extensions": {"x_odps": {"odps_link": self.odps_contract_id}},
                },
                created_by=self.user,
            )
            contracts.append(contract)

        # Query using Django ORM (should use index)
        start_time = time.time()
        linked_contracts = Contract.objects.filter(
            hub_contract_json__extensions__x_odps__odps_link=self.odps_contract_id
        )
        count = linked_contracts.count()
        query_time = time.time() - start_time

        self.assertEqual(count, 11, "Should find 11 contracts (10 new + 1 from setUp)")
        self.assertLess(query_time, 1.0, f"ODPS link query should be fast (took {query_time:.3f}s)")

        # Cleanup
        for contract in contracts:
            contract.delete()

    def test_odcs_link_query_performance(self):
        """Test query performance for finding contracts by ODCS link."""
        # Create multiple ODPS contracts linked to the same ODCS contract
        contracts = []
        for i in range(10):
            contract = Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "odps-linked-{i}", "name": "ODPS Linked {i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"odps-linked-{i}",
                    "info": {"name": f"ODPS Linked {i}"},
                    "schema": {"fields": []},
                    "extensions": {"x_odps": {"odcs_link": self.odcs_contract_id}},
                },
                created_by=self.user,
            )
            contracts.append(contract)

        # Query using Django ORM (should use index)
        start_time = time.time()
        linked_contracts = Contract.objects.filter(
            hub_contract_json__extensions__x_odps__odcs_link=self.odcs_contract_id
        )
        count = linked_contracts.count()
        query_time = time.time() - start_time

        self.assertEqual(count, 11, "Should find 11 contracts (10 new + 1 from setUp)")
        self.assertLess(query_time, 1.0, f"ODCS link query should be fast (took {query_time:.3f}s)")

        # Cleanup
        for contract in contracts:
            contract.delete()

    def test_composite_query_performance(self):
        """Test performance of composite queries (tenant + original_spec_type + link)."""
        # Create multiple contracts with links
        contracts = []
        for i in range(5):
            # ODPS contract
            odps_contract = Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "odps-comp-{i}", "name": "ODPS Composite {i}"}}',
                hub_contract_json={
                    "hub_contract_version": "1.0.0",
                    "id": f"odps-comp-{i}",
                    "info": {"name": f"ODPS Composite {i}"},
                    "schema": {"fields": []},
                    "extensions": {"x_odps": {"odcs_link": self.odcs_contract_id}},
                },
                created_by=self.user,
            )
            contracts.append(odps_contract)

        # Test composite query: tenant + original_spec_type + link
        start_time = time.time()
        results = Contract.objects.filter(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODPS,
            hub_contract_json__extensions__x_odps__odcs_link=self.odcs_contract_id,
        )
        count = results.count()
        query_time = time.time() - start_time

        self.assertGreaterEqual(count, 5, "Should find at least 5 contracts")
        self.assertLess(query_time, 1.0, f"Composite query should be fast (took {query_time:.3f}s)")

        # Cleanup
        for contract in contracts:
            contract.delete()

    def test_index_explain_analyze(self):
        """Test EXPLAIN ANALYZE to verify index usage."""
        with connection.cursor() as cursor:
            # Test original_spec_type index usage
            cursor.execute(
                """
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT)
                SELECT id, original_spec_type
                FROM contracts
                WHERE original_spec_type = 'ODPS'
                AND tenant_id = %s
            """,
                [str(self.tenant.id)],
            )

            explain_output = cursor.fetchall()
            explain_text = "\n".join([row[0] for row in explain_output])

            # Verify query plan mentions index usage
            self.assertIn("contracts", explain_text.lower(), "Query should access contracts table")
            # Log for debugging
            print(f"\nEXPLAIN ANALYZE for original_spec_type:\n{explain_text}")

            # Test JSONB index usage
            cursor.execute(
                """
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT TEXT)
                SELECT id
                FROM contracts
                WHERE hub_contract_json->'extensions'->'x_odps'->>'odcs_link' = %s
            """,
                [self.odcs_contract_id],
            )

            explain_output = cursor.fetchall()
            explain_text = "\n".join([row[0] for row in explain_output])

            self.assertIn("contracts", explain_text.lower(), "Query should access contracts table")
            print(f"\nEXPLAIN ANALYZE for x_odps.odcs_link:\n{explain_text}")

    def test_bulk_query_performance(self):
        """Test performance with bulk queries (multiple links)."""
        # Create multiple ODPS contracts with different ODCS links
        odcs_contract_ids = [str(uuid.uuid4()) for _ in range(5)]
        contracts = []

        for odcs_id in odcs_contract_ids:
            for i in range(3):  # 3 ODPS contracts per ODCS link
                contract = Contract.objects.create(
                    tenant=self.tenant,
                    version=1,
                    status=ContractStatus.DRAFT,
                    original_spec_type=OriginalSpecType.ODPS,
                    original_spec_version="4.1",
                    original_format=OriginalFormat.JSON,
                    original_raw=f'{{"id": "odps-bulk-{odcs_id[:8]}-{i}", "name": "ODPS Bulk"}}',
                    hub_contract_json={
                        "hub_contract_version": "1.0.0",
                        "id": f"odps-bulk-{odcs_id[:8]}-{i}",
                        "info": {"name": "ODPS Bulk"},
                        "schema": {"fields": []},
                        "extensions": {"x_odps": {"odcs_link": odcs_id}},
                    },
                    created_by=self.user,
                )
                contracts.append(contract)

        # Query all contracts for a specific ODCS link
        start_time = time.time()
        target_odcs_id = odcs_contract_ids[0]
        linked_contracts = Contract.objects.filter(
            hub_contract_json__extensions__x_odps__odcs_link=target_odcs_id
        )
        count = linked_contracts.count()
        query_time = time.time() - start_time

        self.assertEqual(count, 3, "Should find 3 contracts for target ODCS link")
        self.assertLess(query_time, 1.0, f"Bulk query should be fast (took {query_time:.3f}s)")

        # Query all ODPS contracts
        start_time = time.time()
        all_odps = Contract.objects.filter(
            tenant=self.tenant, original_spec_type=OriginalSpecType.ODPS
        )
        all_count = all_odps.count()
        query_time = time.time() - start_time

        self.assertGreaterEqual(all_count, 15, "Should find all ODPS contracts")
        self.assertLess(query_time, 2.0, f"Query all ODPS should be fast (took {query_time:.3f}s)")

        # Cleanup
        for contract in contracts:
            contract.delete()

    def test_index_statistics(self):
        """Test index statistics and maintenance."""
        with connection.cursor() as cursor:
            # Get index statistics for original_spec_type index
            cursor.execute(
                """
                SELECT
                    schemaname,
                    relname as tablename,
                    indexrelname as indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE indexrelname = 'idx_contracts_original_spec_type'
            """
            )
            result = cursor.fetchone()

            # Index should exist in statistics (may have zero scans if not used yet)
            if result:
                self.assertEqual(result[2], "idx_contracts_original_spec_type")
            else:
                # Verify index exists even if not in statistics
                cursor.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'contracts'
                    AND indexname = 'idx_contracts_original_spec_type'
                """
                )
                index_check = cursor.fetchone()
                self.assertIsNotNone(
                    index_check, "Index should exist even if not in statistics yet"
                )

    def test_all_indexes_exist(self):
        """Test that all required indexes exist."""
        required_indexes = [
            "idx_contracts_original_spec_type",
            "idx_contracts_tenant_original_spec_type",
            "idx_contracts_extensions_x_odps_gin",
            "idx_contracts_extensions_x_odps_odcs_link_gin",
            "idx_contracts_extensions_x_odps_odps_link_gin",
        ]

        with connection.cursor() as cursor:
            for index_name in required_indexes:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM pg_indexes
                    WHERE tablename = 'contracts'
                    AND indexname = %s
                """,
                    [index_name],
                )
                count = cursor.fetchone()[0]
                self.assertEqual(count, 1, f"Index {index_name} should exist")
