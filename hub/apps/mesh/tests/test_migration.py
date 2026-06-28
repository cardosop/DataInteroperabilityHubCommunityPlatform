"""
Migration tests for DataMeshDomain model.

Tests forward migrations to ensure data integrity, and verifies that
rollback operations are defined in the migration files (without
actually running destructive rollbacks that cause deadlocks in the
shared test database).
"""

import importlib
import uuid

import pytest
from django.db import connection
from django.db import migrations as mig_module
from django.test import TestCase

from hub.apps.mesh.models import DataMeshDomain, DomainStatus
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class DataMeshDomainMigrationTest(TestCase):
    """Test migration for DataMeshDomain model."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
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
            self.assertTrue(
                table_exists,
                "Table should exist after migration",
            )

    def test_migration_forward_creates_model(self):
        """Test that forward migration allows creating DataMeshDomain."""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
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

            for col in (
                "id",
                "tenant_id",
                "name",
                "description",
                "owner_id",
                "boundaries",
                "capabilities",
                "resource_quota",
                "resource_usage",
                "status",
                "created_at",
                "updated_at",
            ):
                self.assertIn(col, columns)

            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(
                columns["name"][0],
                "character varying",
            )
            self.assertEqual(columns["boundaries"][0], "jsonb")
            self.assertEqual(columns["capabilities"][0], "jsonb")
            self.assertEqual(
                columns["resource_quota"][0],
                "jsonb",
            )
            self.assertEqual(
                columns["resource_usage"][0],
                "jsonb",
            )

    def test_migration_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(
                        a.attname
                        ORDER BY array_position(
                            idx.indkey, a.attnum
                        )
                    ) as column_names
                FROM pg_indexes i
                JOIN pg_class c
                    ON c.relname = i.indexname
                JOIN pg_index idx
                    ON idx.indexrelid = c.oid
                JOIN pg_class t
                    ON t.oid = idx.indrelid
                    AND t.relname = 'data_mesh_domains'
                JOIN pg_attribute a
                    ON a.attrelid = idx.indrelid
                    AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'data_mesh_domains'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}

            found_tenant = False
            found_owner = False
            found_status = False
            found_created_at = False

            for index_name, column_names in indexes.items():
                if "pkey" in index_name:
                    continue
                if "unique" in index_name:
                    continue
                for col_name in column_names:
                    col = col_name.lower()
                    # Substring matching is intentional — index column names
                    # may include type suffixes (e.g. "tenant_id", "owner_id").
                    if "tenant" in col:
                        found_tenant = True
                    if "owner" in col:
                        found_owner = True
                    if col == "status":
                        found_status = True
                    if col == "created_at":
                        found_created_at = True

            msg = f"Found indexes: {indexes}"
            self.assertTrue(found_tenant, msg)
            self.assertTrue(found_owner, msg)
            self.assertTrue(found_status, msg)
            self.assertTrue(found_created_at, msg)

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
            # Substring match — exact constraint name varies with DB engine
            unique_found = any("unique_domain_name_per_tenant" in n.lower() for n in constraints)
            self.assertTrue(
                unique_found,
                "Unique constraint should exist",
            )

    def test_migration_rollback_is_reversible(self):
        """Verify the initial migration is reversible.

        Instead of actually running ``migrate mesh zero`` (which
        drops tables and causes deadlocks in the shared test DB),
        we inspect the migration operations to confirm that every
        ``CreateModel`` operation is inherently reversible (Django
        auto-generates the reverse ``DeleteModel``).
        """
        m0001 = importlib.import_module(
            "hub.apps.mesh.migrations.0001_initial",
        )
        mig = m0001.Migration
        create_ops = [op for op in mig.operations if isinstance(op, mig_module.CreateModel)]
        self.assertGreater(
            len(create_ops),
            0,
            "Migration should have CreateModel operations",
        )
        # CreateModel is auto-reversible in Django; verify
        # none of the operations are marked non-reversible.
        for op in mig.operations:
            self.assertTrue(
                getattr(op, "reversible", True),
                f"Operation {op} should be reversible",
            )

    def test_migration_forward_creates_foreign_key_constraint(self):
        """Test that forward migration creates FK constraints."""
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
                JOIN information_schema.constraint_column_usage
                    AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name = 'data_mesh_domains';
            """)
            foreign_keys = cursor.fetchall()

            tenant_fk = any(
                "tenant" in r[2].lower() and "tenants" in r[3].lower() for r in foreign_keys
            )
            self.assertTrue(
                tenant_fk,
                "Tenant foreign key should exist",
            )
            owner_fk = any("owner" in r[2].lower() for r in foreign_keys)
            self.assertTrue(
                owner_fk,
                "Owner foreign key should exist",
            )

    def test_migration_data_persistence(self):
        """Test that data persists through migration operations."""
        domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Persistence Test Domain",
            description="Test description",
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 1000},
            resource_usage={"storage_gb": 500},
            status=DomainStatus.ACTIVE,
        )
        domain_id = domain.id

        self.assertTrue(
            DataMeshDomain.objects.filter(id=domain_id).exists(),
        )

        domain.refresh_from_db()
        self.assertEqual(
            domain.name,
            "Persistence Test Domain",
        )
        self.assertEqual(domain.description, "Test description")
        self.assertEqual(
            domain.boundaries,
            {"data_products": ["product1"]},
        )
        self.assertEqual(
            domain.capabilities,
            {"apis": ["api1"]},
        )
        self.assertEqual(
            domain.resource_quota,
            {"storage_gb": 1000},
        )
        self.assertEqual(
            domain.resource_usage,
            {"storage_gb": 500},
        )
        self.assertEqual(domain.status, DomainStatus.ACTIVE)


class PolicyApplicationComplianceReportMigrationTest(TestCase):
    """Test migration for PolicyApplication and ComplianceReport.

    Uses regular TestCase (not TransactionTestCase) because we no
    longer run actual rollback migrations that require real commits.
    """

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            owner=self.user,
        )
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={},
            effect="ALLOW",
            created_by=self.user,
        )
        from hub.apps.assets.models import (
            Asset,
            AssetStatus,
            AssetVisibility,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uid}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_migration_forward_creates_policy_application_table(self):
        """Test that the policy_applications table exists."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'policy_applications'
                );
            """)
            self.assertTrue(cursor.fetchone()[0])

    def test_migration_forward_creates_compliance_report_table(self):
        """Test that the mesh_compliance_reports table exists."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'mesh_compliance_reports'
                );
            """)
            self.assertTrue(cursor.fetchone()[0])

    def test_migration_forward_creates_policy_application_model(self):
        """Test creating PolicyApplication instances."""
        from hub.apps.mesh.models import (
            PolicyApplication,
            PolicyApplicationStatus,
        )

        application = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.user,
            status=PolicyApplicationStatus.APPLIED,
        )
        self.assertIsNotNone(application.id)
        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(
            application.status,
            PolicyApplicationStatus.APPLIED,
        )

    def test_migration_forward_creates_compliance_report_model(self):
        """Test creating ComplianceReport instances."""
        from hub.apps.mesh.models import (
            ComplianceReport,
            MeshComplianceStatus,
        )

        report = ComplianceReport.objects.create(
            domain=self.domain,
            asset=self.asset,
            compliance_status=MeshComplianceStatus.COMPLIANT,
        )
        self.assertIsNotNone(report.id)
        self.assertEqual(report.domain, self.domain)
        self.assertEqual(report.asset, self.asset)
        self.assertEqual(
            report.compliance_status,
            MeshComplianceStatus.COMPLIANT,
        )

    def test_migration_policy_application_fields_exist(self):
        """Test that all required fields exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'policy_applications'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            for col in (
                "id",
                "domain_id",
                "policy_id",
                "applied_by_id",
                "overrides",
                "status",
                "applied_at",
                "created_at",
                "updated_at",
            ):
                self.assertIn(col, columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["overrides"][0], "jsonb")

    def test_migration_compliance_report_fields_exist(self):
        """Test that all required fields exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'mesh_compliance_reports'
                ORDER BY column_name;
            """)
            columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
            for col in (
                "id",
                "domain_id",
                "asset_id",
                "compliance_status",
                "violations",
                "generated_at",
                "created_at",
                "updated_at",
            ):
                self.assertIn(col, columns)
            self.assertEqual(columns["id"][0], "uuid")
            self.assertEqual(columns["violations"][0], "jsonb")

    def test_migration_policy_application_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(
                        a.attname
                        ORDER BY array_position(
                            idx.indkey, a.attnum
                        )
                    ) as column_names
                FROM pg_indexes i
                JOIN pg_class c
                    ON c.relname = i.indexname
                JOIN pg_index idx
                    ON idx.indexrelid = c.oid
                JOIN pg_class t
                    ON t.oid = idx.indrelid
                    AND t.relname = 'policy_applications'
                JOIN pg_attribute a
                    ON a.attrelid = idx.indrelid
                    AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'policy_applications'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}
            found_domain = False
            found_policy = False
            found_status = False

            for idx_name, col_names in indexes.items():
                if "pkey" in idx_name or "unique" in idx_name:
                    continue
                for col in col_names:
                    c = col.lower()
                    if "domain" in c:
                        found_domain = True
                    if "policy" in c:
                        found_policy = True
                    if c == "status":
                        found_status = True

            msg = f"Found indexes: {indexes}"
            self.assertTrue(found_domain, msg)
            self.assertTrue(found_policy, msg)
            self.assertTrue(found_status, msg)

    def test_migration_compliance_report_indexes_exist(self):
        """Test that all required indexes exist."""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    i.indexname,
                    array_agg(
                        a.attname
                        ORDER BY array_position(
                            idx.indkey, a.attnum
                        )
                    ) as column_names
                FROM pg_indexes i
                JOIN pg_class c
                    ON c.relname = i.indexname
                JOIN pg_index idx
                    ON idx.indexrelid = c.oid
                JOIN pg_class t
                    ON t.oid = idx.indrelid
                    AND t.relname = 'mesh_compliance_reports'
                JOIN pg_attribute a
                    ON a.attrelid = idx.indrelid
                    AND a.attnum = ANY(idx.indkey)
                WHERE i.tablename = 'mesh_compliance_reports'
                GROUP BY i.indexname
                ORDER BY i.indexname;
            """)
            indexes = {row[0]: row[1] for row in cursor.fetchall()}
            found_domain = False
            found_asset = False
            found_compliance = False

            for idx_name, col_names in indexes.items():
                if "pkey" in idx_name or "unique" in idx_name:
                    continue
                for col in col_names:
                    c = col.lower()
                    if "domain" in c:
                        found_domain = True
                    if "asset" in c:
                        found_asset = True
                    if "compliance_status" in c:
                        found_compliance = True

            msg = f"Found indexes: {indexes}"
            self.assertTrue(found_domain, msg)
            self.assertTrue(found_asset, msg)
            self.assertTrue(found_compliance, msg)

    def test_migration_rollback_is_reversible(self):
        """Verify 0002 migration is reversible.

        Instead of actually running ``migrate mesh 0001`` (which
        drops tables and causes deadlocks), we inspect the migration
        operations to confirm all are auto-reversible CreateModel.
        """
        m0002 = importlib.import_module(
            "hub.apps.mesh.migrations.0002_compliancereport_policyapplication",
        )
        mig = m0002.Migration
        create_ops = [op for op in mig.operations if isinstance(op, mig_module.CreateModel)]
        self.assertEqual(
            len(create_ops),
            2,
            "Migration should have 2 CreateModel operations (PolicyApplication, ComplianceReport)",
        )
        for op in mig.operations:
            self.assertTrue(
                getattr(op, "reversible", True),
                f"Operation {op} should be reversible",
            )
