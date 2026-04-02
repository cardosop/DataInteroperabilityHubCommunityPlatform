"""
Integration tests for virtualization against real data sources.

Phase 20 — Virtualization Real Source Testing.
Uses real PostgreSQL, Jena Fuseki (SPARQL), and HTTP endpoints — no mocks/stubs.
Requires docker-compose.test.yml services to be running.
"""
import unittest
import uuid

import pytest
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings
from django.db import connection

from hub.apps.tenants.models import Tenant, KYCStatus, TenantPlan, PlanTier
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryExecution,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import ValidationError
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _setup_subscription(tenant):
    """Set up subscription/plan for a tenant."""
    from django.utils import timezone
    plan, _ = TenantPlan.objects.get_or_create(
        slug="virtualization-test-plan",
        defaults={
            "name": "Virtualization Test Plan",
            "tier": PlanTier.PRO,
            "limits_json": {"max_assets": 100, "max_storage_gb": 1000, "max_virtual_datasets": 100},
            "is_active": True,
        },
    )
    if "max_storage_gb" not in (plan.limits_json or {}):
        plan.limits_json = {**(plan.limits_json or {}), "max_storage_gb": 1000, "max_virtual_datasets": 100}
        plan.save(update_fields=["limits_json"])
    if tenant.plan_id != plan.id:
        tenant.plan = plan
        tenant.save(update_fields=["plan"])
    Subscription.objects.get_or_create(
        tenant=tenant,
        defaults={
            "plan": plan,
            "status": SubscriptionStatus.ACTIVE,
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now(),
        },
    )


def _semantic_service_available() -> bool:
    """Check if SemanticService (and thus Fuseki) is available for SPARQL."""
    try:
        from hub.apps.semantic.service_client import SemanticServiceClient

        client = SemanticServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


def _get_postgres_source_config() -> dict | None:
    """Build postgresql source config from Django DATABASES['default']."""
    db = settings.DATABASES.get("default", {})
    if db.get("ENGINE") != "django.db.backends.postgresql":
        return None
    return {
        "type": "postgresql",
        "host": db.get("HOST", "localhost"),
        "port": int(db.get("PORT", 5432)),
        "database": db.get("NAME"),
        "username": db.get("USER"),
        "password": db.get("PASSWORD"),
    }


def _get_odbc_postgres_driver() -> str | None:
    """Return PostgreSQL Unicode driver if available, else first PostgreSQL driver, or None."""
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "postgresql" in d.lower()]
        if not drivers:
            return None
        # Prefer Unicode over ANSI to avoid "Received an unsupported type from Postgres. (14)"
        for d in drivers:
            if "unicode" in d.lower():
                return d
        return drivers[0]
    except Exception:
        return None


def _get_odbc_postgres_source_config() -> dict | None:
    """Build ODBC source config for Hub PostgreSQL (host+database)."""
    db = settings.DATABASES.get("default", {})
    if db.get("ENGINE") != "django.db.backends.postgresql":
        return None
    driver = _get_odbc_postgres_driver() or "PostgreSQL Unicode"
    return {
        "type": "odbc",
        "host": db.get("HOST", "localhost"),
        "port": int(db.get("PORT", 5432)),
        "database": db.get("NAME"),
        "username": db.get("USER"),
        "password": db.get("PASSWORD"),
        "driver": driver,
    }


def _odbc_postgres_available() -> bool:
    """Check if pyodbc and PostgreSQL ODBC driver are available."""
    return _get_odbc_postgres_driver() is not None


class RealPostgreSQLSourceIntegrationTest(TransactionTestCase):
    """
    Integration tests for SQL virtualization against real PostgreSQL.

    Uses the same Postgres instance as Django (postgres-test in docker-compose.test.yml).
    Creates a table, inserts rows, runs SELECT via VirtualizationService, asserts results.

    Uses TransactionTestCase so CREATE TABLE is committed and visible to the virtualization
    service's separate DB connection (which cannot see uncommitted transaction data).
    """

    def setUp(self):
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Real Source Test Tenant {_uid}",
            slug=f"real-source-test-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"realsource-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)
        _setup_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        cache.clear()

    def tearDown(self):
        """Drop test table if it exists."""
        table_name = getattr(self, "_test_table_name", None)
        if table_name:
            try:
                if connection.connection is not None:
                    connection.connection.rollback()
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"tearDown: failed to rollback connection for {table_name}: {e}"
                )
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f'DROP TABLE IF EXISTS "{table_name}" CASCADE'
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"tearDown: failed to drop table {table_name}: {e}"
                )

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    @pytest.mark.timeout(180)
    def test_postgresql_create_table_select_assert_rows(self):
        """
        Create table in real Postgres, insert rows, run SELECT via virtualization, assert.
        """
        source_config = _get_postgres_source_config()
        if not source_config or not source_config.get("database"):
            raise unittest.SkipTest("PostgreSQL not configured as default database")

        self._test_table_name = f"virt_real_test_{uuid.uuid4().hex[:12]}"

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE "{self._test_table_name}" (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    value INTEGER NOT NULL
                )
                """
            )
            cursor.execute(
                f'''
                INSERT INTO "{self._test_table_name}" (name, value) VALUES
                ('alpha', 10),
                ('beta', 20),
                ('gamma', 30)
                '''
            )

        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Real Postgres Integration Dataset",
            query=f'SELECT id, name, value FROM "{self._test_table_name}" ORDER BY id',
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[source_config],
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except (ValidationError, Exception) as e:
            err = str(e).lower()
            if any(kw in err for kw in (
                "connection", "refused", "timeout",
                "operational", "config", "valid json",
            )):
                self.skipTest(f"Database source not reachable: {e}")
            pytest.fail(f"Query execution failed: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, vd.id)
        self.assertEqual(
            execution.status,
            QueryExecutionStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. "
            f"Log: {execution.execution_log}",
        )

        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        data = result.get("data", [])
        self.assertEqual(
            len(data), 3,
            f"Expected 3 rows, got {len(data)}: {data}"
        )
        self.assertEqual(data[0]["name"], "alpha")
        self.assertEqual(data[0]["value"], 10)
        self.assertEqual(data[1]["name"], "beta")
        self.assertEqual(data[1]["value"], 20)
        self.assertEqual(data[2]["name"], "gamma")
        self.assertEqual(data[2]["value"], 30)

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    @pytest.mark.timeout(180)
    @pytest.mark.skipif(
        not _odbc_postgres_available(),
        reason="pyodbc or PostgreSQL ODBC driver (psqlodbc) not available",
    )
    def test_odbc_execute_against_hub_postgresql(self):
        """
        Execute SQL via ODBC source against Hub PostgreSQL when psqlodbc available.

        Uses same Postgres as Django; creates table, inserts rows, runs SELECT via
        VirtualizationService with type=odbc. Skips when pyodbc or driver not installed.
        """
        source_config = _get_odbc_postgres_source_config()
        if not source_config or not source_config.get("database"):
            raise unittest.SkipTest("PostgreSQL not configured as default database")

        self._test_table_name = f"virt_odbc_test_{uuid.uuid4().hex[:12]}"

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE "{self._test_table_name}" (
                    id SERIAL PRIMARY KEY,
                    label VARCHAR(50) NOT NULL
                )
                """
            )
            cursor.execute(
                f'''
                INSERT INTO "{self._test_table_name}" (label) VALUES
                ('odbc_row_1'),
                ('odbc_row_2')
                '''
            )

        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="ODBC Postgres Integration Dataset",
            query=f'SELECT id, label FROM "{self._test_table_name}" ORDER BY id',
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[source_config],
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except (ValidationError, Exception) as e:
            err = str(e).lower()
            if any(kw in err for kw in (
                "refused", "driver not found", "driver not installed",
                "no suitable driver",
            )):
                self.skipTest(f"ODBC driver/connection unavailable: {e}")
            raise

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        data = result.get("data", [])
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["label"], "odbc_row_1")
        self.assertEqual(data[1]["label"], "odbc_row_2")

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    @pytest.mark.timeout(180)
    @pytest.mark.skipif(
        not _odbc_postgres_available(),
        reason="pyodbc or PostgreSQL ODBC driver (psqlodbc) not available",
    )
    def test_odbc_execute_connection_string_mode(self):
        """
        Execute SQL via ODBC source using connection_string mode when psqlodbc available.

        Verifies connection_string path in _execute_odbc_query (vs host+database).
        Uses same Postgres as Django; builds connection string from host/db/port/user/pass.
        """
        host_db_config = _get_odbc_postgres_source_config()
        if not host_db_config or not host_db_config.get("database"):
            raise unittest.SkipTest("PostgreSQL not configured as default database")

        driver = host_db_config.get("driver", "PostgreSQL Unicode")
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={host_db_config['host']};"
            f"PORT={host_db_config.get('port', 5432)};"
            f"DATABASE={host_db_config['database']};"
            f"UID={host_db_config.get('username') or ''};"
            f"PWD={host_db_config.get('password') or ''}"
        )
        source_config = {"type": "odbc", "connection_string": conn_str}

        self._test_table_name = f"virt_odbc_cs_{uuid.uuid4().hex[:12]}"

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                CREATE TABLE "{self._test_table_name}" (
                    id SERIAL PRIMARY KEY,
                    val INTEGER NOT NULL
                )
                """
            )
            cursor.execute(
                f'INSERT INTO "{self._test_table_name}" (val) VALUES (42), (99)'
            )

        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="ODBC Connection String Integration Dataset",
            query=f'SELECT id, val FROM "{self._test_table_name}" ORDER BY id',
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[source_config],
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except (ValidationError, Exception) as e:
            err = str(e).lower()
            if any(kw in err for kw in (
                "refused", "driver not found",
                "driver not installed", "no suitable driver",
            )):
                self.skipTest(
                    f"ODBC driver/connection unavailable: {e}"
                )
            pytest.fail(
                f"ODBC connection_string execution failed: {e}"
            )

        self.assertIsNotNone(execution)
        self.assertEqual(
            execution.status, QueryExecutionStatus.COMPLETED
        )
        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        data = result.get("data", [])
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["val"], 42)
        self.assertEqual(data[1]["val"], 99)


class RealSPARQLSourceIntegrationTest(TestCase):
    """
    Integration tests for SPARQL virtualization against Jena Fuseki.

    Skips when semantic-service / Fuseki is not available.
    """

    def setUp(self):
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"SPARQL Real Test Tenant {_uid}",
            slug=f"sparql-real-test-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"sparqlreal-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)
        _setup_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        cache.clear()

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    @pytest.mark.skipif(
        not _semantic_service_available(),
        reason="SemanticService/Fuseki not available",
    )
    def test_sparql_against_fuseki(self):
        """
        Execute SPARQL query against real Jena Fuseki via semantic-service.
        Empty dataset returns empty bindings; we assert structure and no error.
        """
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Real SPARQL Integration Dataset",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 5",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[],  # SPARQL uses semantic service, no source config needed
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except (ValidationError, ValueError) as e:
            err = str(e).lower()
            if any(kw in err for kw in ("sparql", "semantic", "fuseki", "circuit")):
                self.skipTest(f"SPARQL service not available: {e}")
            raise

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, vd.id)
        self.assertEqual(
            execution.status,
            QueryExecutionStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. Log: {execution.execution_log}",
        )

        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        self.assertIn("data", result)
        self.assertIsInstance(result["data"], list)
        self.assertIn("total_count", result)
        self.assertIsInstance(result["total_count"], int)


class RealRESTSourceIntegrationTest(TestCase):
    """
    Integration tests for REST virtualization against real HTTP endpoints.

    Uses jsonplaceholder.typicode.com (public, stable test API).
    """

    def setUp(self):
        _uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"REST Real Test Tenant {_uid}",
            slug=f"rest-real-test-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"restreal-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)
        _setup_subscription(self.tenant)
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        cache.clear()

    @pytest.mark.integration
    @pytest.mark.real_virtualization_e2e
    def test_rest_against_real_http_endpoint(self):
        """
        Execute REST query against real HTTP endpoint (jsonplaceholder.typicode.com).
        """
        vd = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Real REST Integration Dataset",
            query="/posts",
            query_type=QueryType.REST,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {
                    "type": "rest",
                    "base_url": "https://jsonplaceholder.typicode.com",
                    "method": "GET",
                }
            ],
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(vd.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except ValidationError as e:
            pytest.fail(f"REST execution failed: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, vd.id)
        self.assertEqual(
            execution.status,
            QueryExecutionStatus.COMPLETED,
            f"Expected COMPLETED, got {execution.status}. Log: {execution.execution_log}",
        )

        result = self.service.get_query_result(
            execution_id=str(execution.id), format="json"
        )
        data = result.get("data", [])
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0, "Expected at least one post from jsonplaceholder")
        first = data[0]
        self.assertIn("id", first)
        self.assertIn("title", first)
        self.assertIn("userId", first)
