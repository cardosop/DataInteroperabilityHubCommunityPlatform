"""
Migration tests for DataMeshDomain model.

Tests forward and backward migrations to ensure data integrity.
"""
import pytest
from django.test import TestCase
from django.core.management import call_command
from django.db import connection

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.mesh.models import DataMeshDomain, DomainStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DataMeshDomainMigrationTest(TestCase):
    """Test migration for DataMeshDomain model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

    def test_migration_forward_creates_table(self):
        """Test that forward migration creates the data_mesh_domains table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'data_mesh_domains'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "Table should exist after migration")

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating DataMeshDomain instances."""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain"
        )

        self.assertIsNotNone(domain.id)
        self.assertEqual(domain.tenant, self.tenant)
        self.assertEqual(domain.name, "Test Domain")
        self.assertEqual(domain.status, DomainStatus.ACTIVE)

    def test_migration_fields_exist(self):
        """Test that all required fields exist in the table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'data_mesh_domains'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            self.assertIn("id", columns)
            self.assertIn("tenant_id", columns)
            self.assertIn("name", columns)
            self.assertIn("description", columns)
            self.assertIn("owner_id", columns)
            self.assertIn("boundaries", columns)
            self.assertIn("capabilities", columns)
            self.assertIn("resource_quota", columns)
            self.assertIn("resource_usage", columns)
            self.assertIn("status", columns)
            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)

            # Check data types
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["name"][0], "character varying")
            self.assertEqual(columns["boundaries"][0], "jsonb")
            self.assertEqual(columns["capabilities"][0], "jsonb")
            self.assertEqual(columns["resource_quota"][0], "jsonb")
            self.assertEqual(columns["resource_usage"][0], "jsonb")

    def test_migration_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            # Check indexes by querying pg_indexes and joining with pg_attribute
            # to get the actual column names (using tenant_id, owner_id, etc.)
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as column_names
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = c.oid
                JOIN pg_class t ON t.oid = idx.indrelid AND t.relname = 'data_mesh_domains'
                JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'data_mesh_domains'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for required indexes by column names
            # Note: Foreign keys create indexes with _id suffix (tenant_id, owner_id)
            found_tenant = False
            found_owner = False
            found_status = False
            found_created_at = False

            for index_name, column_names in indexes.items():
                # Skip primary key and unique constraints
                if 'pkey' in index_name or 'unique' in index_name:
                    continue
                # Check column names (can be tenant_id or tenant, owner_id or owner, etc.)
                for col_name in column_names:
                    if 'tenant' in col_name.lower():
                        found_tenant = True
                    if 'owner' in col_name.lower():
                        found_owner = True
                    if col_name.lower() == 'status':
                        found_status = True
                    if col_name.lower() == 'created_at':
                        found_created_at = True

            self.assertTrue(found_tenant, f"Index on tenant column should exist. Found indexes: {indexes}")
            self.assertTrue(found_owner, f"Index on owner column should exist. Found indexes: {indexes}")
            self.assertTrue(found_status, f"Index on status column should exist. Found indexes: {indexes}")
            self.assertTrue(found_created_at, f"Index on created_at column should exist. Found indexes: {indexes}")

    def test_migration_constraints_exist(self):
        """Test that all required constraints exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_name = 'data_mesh_domains'
                ORDER BY constraint_name;
            """)
            constraints = {row[0]: row[1] for row in cursor.fetchall()}

            # Check for unique constraint
            unique_constraint_found = any(
                "unique_domain_name_per_tenant" in name.lower()
                for name in constraints.keys()
            )
            self.assertTrue(unique_constraint_found, "Unique constraint should exist")

    def test_migration_rollback_removes_table(self):
        """Test that migration rollback removes the table."""
        # First verify table exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'data_mesh_domains'
                );
            """)
            table_exists_before = cursor.fetchone()[0]
            self.assertTrue(table_exists_before, "Table should exist before rollback")

        # Rollback migration (rollback to zero)
        call_command('migrate', 'mesh', 'zero', verbosity=0, interactive=False)

        # Verify table is removed
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'data_mesh_domains'
                );
            """)
            table_exists_after = cursor.fetchone()[0]
            self.assertFalse(table_exists_after, "Table should not exist after rollback")

        # Re-apply migration for other tests
        call_command('migrate', 'mesh', verbosity=0, interactive=False)

    def test_migration_forward_creates_foreign_key_constraint(self):
        """Test that forward migration creates foreign key constraints."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    tc.constraint_name,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = 'data_mesh_domains';
            """)
            foreign_keys = cursor.fetchall()

            # Check for tenant foreign key
            tenant_fk_found = any(
                "tenant" in row[2].lower() and "tenants" in row[3].lower()
                for row in foreign_keys
            )
            self.assertTrue(tenant_fk_found, "Tenant foreign key should exist")

            # Check for owner foreign key (if user model is available)
            owner_fk_found = any(
                "owner" in row[2].lower()
                for row in foreign_keys
            )
            self.assertTrue(owner_fk_found, "Owner foreign key should exist")

    def test_migration_data_persistence(self):
        """Test that data persists through migration operations."""
        # Create domain
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Persistence Test Domain",
            description="Test description",
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 1000},
            resource_usage={"storage_gb": 500},
            status=DomainStatus.ACTIVE
        )
        domain_id = domain.id

        # Verify data exists
        self.assertTrue(DataMeshDomain.objects.filter(id=domain_id).exists())

        # Refresh from database
        domain.refresh_from_db()
        self.assertEqual(domain.name, "Persistence Test Domain")
        self.assertEqual(domain.description, "Test description")
        self.assertEqual(domain.boundaries, {"data_products": ["product1"]})
        self.assertEqual(domain.capabilities, {"apis": ["api1"]})
        self.assertEqual(domain.resource_quota, {"storage_gb": 1000})
        self.assertEqual(domain.resource_usage, {"storage_gb": 500})
        self.assertEqual(domain.status, DomainStatus.ACTIVE)


class PolicyApplicationComplianceReportMigrationTest(TestCase):
    """Test migration for PolicyApplication and ComplianceReport models"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user
        )
        from hub.apps.governance.models import AccessPolicy
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={},
            effect="ALLOW",
            created_by=self.user
        )
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user
        )

    def test_migration_forward_creates_policy_application_table(self):
        """Test that forward migration creates the policy_applications table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'policy_applications'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "Table should exist after migration")

    def test_migration_forward_creates_compliance_report_table(self):
        """Test that forward migration creates the mesh_compliance_reports table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'mesh_compliance_reports'
                );
            """)
            table_exists = cursor.fetchone()[0]
            self.assertTrue(table_exists, "Table should exist after migration")

    def test_migration_forward_creates_policy_application_model(self):
        """Test that forward migration allows creating PolicyApplication instances."""
        from hub.apps.mesh.models import PolicyApplication, PolicyApplicationStatus
        application = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.user,
            status=PolicyApplicationStatus.APPLIED
        )

        self.assertIsNotNone(application.id)
        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)

    def test_migration_forward_creates_compliance_report_model(self):
        """Test that forward migration allows creating ComplianceReport instances."""
        from hub.apps.mesh.models import ComplianceReport, MeshComplianceStatus
        report = ComplianceReport.objects.create(
            domain=self.domain,
            asset=self.asset,
            compliance_status=MeshComplianceStatus.COMPLIANT
        )

        self.assertIsNotNone(report.id)
        self.assertEqual(report.domain, self.domain)
        self.assertEqual(report.asset, self.asset)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.COMPLIANT)

    def test_migration_policy_application_fields_exist(self):
        """Test that all required fields exist in policy_applications table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'policy_applications'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            self.assertIn("id", columns)
            self.assertIn("domain_id", columns)
            self.assertIn("policy_id", columns)
            self.assertIn("applied_by_id", columns)
            self.assertIn("overrides", columns)
            self.assertIn("status", columns)
            self.assertIn("applied_at", columns)
            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)

            # Check data types
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["overrides"][0], "jsonb")

    def test_migration_compliance_report_fields_exist(self):
        """Test that all required fields exist in mesh_compliance_reports table."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'mesh_compliance_reports'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

            # Check required fields
            self.assertIn("id", columns)
            self.assertIn("domain_id", columns)
            self.assertIn("asset_id", columns)
            self.assertIn("compliance_status", columns)
            self.assertIn("violations", columns)
            self.assertIn("generated_at", columns)
            self.assertIn("created_at", columns)
            self.assertIn("updated_at", columns)

            # Check data types
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["violations"][0], "jsonb")

    def test_migration_policy_application_indexes_exist(self):
        """Test that all required indexes exist for policy_applications."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as column_names
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = c.oid
                JOIN pg_class t ON t.oid = idx.indrelid AND t.relname = 'policy_applications'
                JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'policy_applications'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            found_domain = False
            found_policy = False
            found_status = False

            for index_name, column_names in indexes.items():
                if 'pkey' in index_name or 'unique' in index_name:
                    continue
                for col_name in column_names:
                    if 'domain' in col_name.lower():
                        found_domain = True
                    if 'policy' in col_name.lower():
                        found_policy = True
                    if col_name.lower() == 'status':
                        found_status = True

            self.assertTrue(found_domain, f"Index on domain column should exist. Found indexes: {indexes}")
            self.assertTrue(found_policy, f"Index on policy column should exist. Found indexes: {indexes}")
            self.assertTrue(found_status, f"Index on status column should exist. Found indexes: {indexes}")

    def test_migration_compliance_report_indexes_exist(self):
        """Test that all required indexes exist for mesh_compliance_reports."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(a.attname ORDER BY array_position(idx.indkey, a.attnum)) as column_names
                FROM pg_indexes i
                JOIN pg_class c ON c.relname = i.indexname
                JOIN pg_index idx ON idx.indexrelid = c.oid
                JOIN pg_class t ON t.oid = idx.indrelid AND t.relname = 'mesh_compliance_reports'
                JOIN pg_attribute a ON a.attrelid = idx.indrelid AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'mesh_compliance_reports'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            found_domain = False
            found_asset = False
            found_compliance_status = False

            for index_name, column_names in indexes.items():
                if 'pkey' in index_name or 'unique' in index_name:
                    continue
                for col_name in column_names:
                    if 'domain' in col_name.lower():
                        found_domain = True
                    if 'asset' in col_name.lower():
                        found_asset = True
                    if 'compliance_status' in col_name.lower():
                        found_compliance_status = True

            self.assertTrue(found_domain, f"Index on domain column should exist. Found indexes: {indexes}")
            self.assertTrue(found_asset, f"Index on asset column should exist. Found indexes: {indexes}")
            self.assertTrue(found_compliance_status, f"Index on compliance_status column should exist. Found indexes: {indexes}")

    def test_migration_rollback_removes_tables(self):
        """Test that migration rollback removes the tables."""
        # First verify tables exist
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name IN ('policy_applications', 'mesh_compliance_reports')
                );
            """)
            tables_exist_before = cursor.fetchone()[0]
            self.assertTrue(tables_exist_before, "Tables should exist before rollback")

        # Rollback migration (rollback to 0001)
        call_command('migrate', 'mesh', '0001', verbosity=0, interactive=False)

        # Verify tables are removed
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'policy_applications'
                );
            """)
            policy_app_table_exists = cursor.fetchone()[0]
            self.assertFalse(policy_app_table_exists, "policy_applications table should not exist after rollback")

            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'mesh_compliance_reports'
                );
            """)
            compliance_table_exists = cursor.fetchone()[0]
            self.assertFalse(compliance_table_exists, "mesh_compliance_reports table should not exist after rollback")

        # Re-apply migration for other tests
        call_command('migrate', 'mesh', verbosity=0, interactive=False)

