"""
Phase 121G-D — Data Migration Encryption Tests

Tests that the 7 idempotent data migrations correctly encrypt plaintext
rows and skip already-encrypted rows. Each test:
1. Inserts plaintext rows via raw SQL (bypassing model save() encryption)
2. Runs the forward migration function
3. Verifies rows are now encrypted ({"_encrypted": "..."})
4. Runs migration again to verify idempotency
5. Verifies decryption round-trip via model accessor
"""

import importlib
import json
import uuid

import pytest
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

pytestmark = pytest.mark.django_db(transaction=True)

ENCRYPTION_KEY = "test-migration-key-for-121g-d-tests"


def _load_migration_fn(module_path, fn_name):
    """Import a migration module by dotted path and return the named function."""
    mod = importlib.import_module(module_path)
    return getattr(mod, fn_name)


def _insert_raw(table, columns_values):
    """Insert a row via raw SQL, bypassing model save() encryption."""
    cols = ", ".join(columns_values.keys())
    placeholders = ", ".join(["%s"] * len(columns_values))
    with connection.cursor() as cur:
        cur.execute(
            f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
            list(columns_values.values()),
        )


def _read_json_field(table, pk_col, pk_val, field):
    """Read a JSON field via raw SQL."""
    with connection.cursor() as cur:
        cur.execute(
            f"SELECT {field} FROM {table} WHERE {pk_col} = %s",
            [str(pk_val)],
        )
        row = cur.fetchone()
        if row is None:
            return None
        val = row[0]
        if isinstance(val, str):
            return json.loads(val)
        return val


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class ScheduledIngestionMigrationTest(TestCase):
    """Test 121G-D.1: encrypt_source_config migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.scheduled_ingestion.migrations.0009_encrypt_source_config",
            "encrypt_source_config_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.users.models import UserStatus
        from django.contrib.auth import get_user_model
        from hub.apps.scheduled_ingestion.models import (
            ScheduledIngestion, SourceType, ScheduleType,
        )
        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="x", tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("scheduled_ingestions", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "name": f"test-{uid}",
            "source_type": SourceType.S3,
            "source_config": json.dumps({"bucket": "b1", "secret_key": "sk1"}),
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": json.dumps({"cron_expression": "0 0 * * *"}),
            "auto_create_asset": False,
            "auto_activate": False,
            "status": "ACTIVE",
            "created_by_id": str(user.id),
            "created_at": now,
            "updated_at": now,
            "prefect_work_pool_name": "default",
            "deployment_sync_status": "PENDING",
            "consecutive_failure_count": 0,
        })

        raw = _read_json_field("scheduled_ingestions", "id", row_id, "source_config")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("scheduled_ingestions", "id", row_id, "source_config")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)
        raw2 = _read_json_field("scheduled_ingestions", "id", row_id, "source_config")
        self.assertIn("_encrypted", raw2)

        # Round-trip via model accessor
        obj = ScheduledIngestion.objects.get(pk=row_id)
        decrypted = obj.get_source_config()
        self.assertEqual(decrypted["bucket"], "b1")
        self.assertEqual(decrypted["secret_key"], "sk1")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class ScheduledExportMigrationTest(TestCase):
    """Test 121G-D.2: encrypt_destination_config migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.scheduled_export.migrations.0005_encrypt_destination_config",
            "encrypt_destination_config_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("scheduled_exports", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "name": f"exp-{uid}",
            "schedule_config": json.dumps({"cron": "0 2 * * *"}),
            "destination_type": "S3",
            "destination_config": json.dumps({
                "bucket": "b2", "secret_key": "sk2",
            }),
            "source_scope": json.dumps({"asset_ids": []}),
            "status": "ACTIVE",
            "created_at": now,
            "updated_at": now,
            "deployment_sync_status": "PENDING",
            "consecutive_failure_count": 0,
        })

        raw = _read_json_field("scheduled_exports", "id", row_id, "destination_config")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("scheduled_exports", "id", row_id, "destination_config")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        from hub.apps.scheduled_export.models import ScheduledExport
        obj = ScheduledExport.objects.get(pk=row_id)
        decrypted = obj.get_destination_config()
        self.assertEqual(decrypted["bucket"], "b2")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class TenantConfigMigrationTest(TestCase):
    """Test 121G-D.3: encrypt_sso_config migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.tenants.migrations.0021_encrypt_sso_config",
            "encrypt_sso_config_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("tenant_configs", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "sso_config": json.dumps({
                "provider": "okta",
                "client_secret": "oidc-secret-123",
            }),
            "allowed_compliance_regimes": json.dumps([]),
            "default_compliance_regimes": json.dumps([]),
            "compliance_risk_threshold": "HIGH",
            "notification_opt_outs": json.dumps({}),
            "created_at": now,
            "updated_at": now,
        })

        raw = _read_json_field("tenant_configs", "id", row_id, "sso_config")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("tenant_configs", "id", row_id, "sso_config")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        obj = TenantConfig.objects.get(pk=row_id)
        decrypted = obj.get_sso_config()
        self.assertEqual(decrypted["provider"], "okta")
        self.assertEqual(decrypted["client_secret"], "oidc-secret-123")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class DQAlertingRuleMigrationTest(TestCase):
    """Test 121G-D.4: encrypt_channel_config migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.dq.migrations.0005_encrypt_channel_config",
            "encrypt_channel_config_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.dq.models import DQAlertingRule

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("dq_alerting_rules", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "name": f"rule-{uid}",
            "metric_type": "COMPLETENESS",
            "threshold": 90.0,
            "comparison_operator": "LESS_THAN",
            "severity": "CRITICAL",
            "alert_channels": json.dumps(["SLACK"]),
            "channel_config": json.dumps({
                "webhook_url": "https://hooks.slack.com/x",
                "token": "xoxb-secret",
            }),
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        })

        raw = _read_json_field("dq_alerting_rules", "id", row_id, "channel_config")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("dq_alerting_rules", "id", row_id, "channel_config")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        obj = DQAlertingRule.objects.get(pk=row_id)
        decrypted = obj.get_channel_config()
        self.assertEqual(decrypted["token"], "xoxb-secret")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class VirtualDatasetMigrationTest(TestCase):
    """Test 121G-D.5: encrypt_sources migration (list field)."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.virtualization.migrations.0006_encrypt_sources",
            "encrypt_sources_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.users.models import UserStatus
        from django.contrib.auth import get_user_model
        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="x", tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("virtual_datasets", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "created_by_id": str(user.id),
            "name": f"vds-{uid}",
            "query": "SELECT 1",
            "query_type": "SQL",
            "sources": json.dumps([
                {"type": "postgres", "host": "db.local", "password": "secret"},
            ]),
            "version": "1.0.0",
            "status": "DRAFT",
            "created_at": now,
            "updated_at": now,
        })

        raw = _read_json_field("virtual_datasets", "id", row_id, "sources")
        self.assertIsInstance(raw, list)

        fn(None, None)

        raw = _read_json_field("virtual_datasets", "id", row_id, "sources")
        self.assertIsInstance(raw, dict)
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        from hub.apps.virtualization.models import VirtualDataset
        obj = VirtualDataset.objects.get(pk=row_id)
        decrypted = obj.get_sources()
        self.assertEqual(len(decrypted), 1)
        self.assertEqual(decrypted[0]["host"], "db.local")
        self.assertEqual(decrypted[0]["password"], "secret")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class TransformationPipelineMigrationTest(TestCase):
    """Test 121G-D.6: encrypt_pipeline_definition migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.transformation.migrations.0002_encrypt_pipeline_definition",
            "encrypt_pipeline_definition_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.users.models import UserStatus
        from django.contrib.auth import get_user_model
        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="x", tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        row_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("transformation_pipelines", {
            "id": str(row_id),
            "tenant_id": str(tenant.id),
            "created_by_id": str(user.id),
            "name": f"pipe-{uid}",
            "pipeline_definition": json.dumps({
                "version": "1.0",
                "steps": [{"name": "s1", "type": "filter"}],
            }),
            "version": "1.0.0",
            "status": "DRAFT",
            "metadata": json.dumps({}),
            "created_at": now,
            "updated_at": now,
        })

        raw = _read_json_field("transformation_pipelines", "id", row_id, "pipeline_definition")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("transformation_pipelines", "id", row_id, "pipeline_definition")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        from hub.apps.transformation.models import TransformationPipeline
        obj = TransformationPipeline.objects.get(pk=row_id)
        decrypted = obj.get_pipeline_definition()
        self.assertEqual(decrypted["version"], "1.0")


@override_settings(ENCRYPTION_KEY=ENCRYPTION_KEY)
class TransformationNodeMigrationTest(TestCase):
    """Test 121G-D.7: encrypt_node_config migration."""

    def test_encrypts_plaintext_rows(self):
        fn = _load_migration_fn(
            "hub.apps.transformation.migrations.0003_encrypt_node_config",
            "encrypt_node_config_forward",
        )
        from hub.apps.tenants.models import KYCStatus, Tenant
        from hub.apps.users.models import UserStatus
        from django.contrib.auth import get_user_model
        from hub.apps.transformation.models import TransformationNode
        User = get_user_model()

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"T-{uid}", slug=f"t-{uid}", kyc_status=KYCStatus.VERIFIED,
        )
        user = User.objects.create_user(
            email=f"u-{uid}@test.com", password="x", tenant=tenant,
            status=UserStatus.ACTIVE,
        )

        # Create pipeline first (needed for FK)
        pipe_id = uuid.uuid4()
        now = timezone.now()
        _insert_raw("transformation_pipelines", {
            "id": str(pipe_id),
            "tenant_id": str(tenant.id),
            "created_by_id": str(user.id),
            "name": f"pipe-{uid}",
            "pipeline_definition": json.dumps({"_encrypted": "already"}),
            "version": "1.0.0",
            "status": "DRAFT",
            "metadata": json.dumps({}),
            "created_at": now,
            "updated_at": now,
        })

        node_id = uuid.uuid4()
        with connection.cursor() as cur:
            cur.execute(
                'INSERT INTO transformation_nodes '
                '(id, pipeline_id, node_type, node_config, position, "order", created_at, updated_at) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                [
                    str(node_id), str(pipe_id), "filter",
                    json.dumps({"expression": "age > 18", "connection_string": "postgres://u:p@h/d"}),
                    json.dumps({"x": 0, "y": 0}), 1, now, now,
                ],
            )

        raw = _read_json_field("transformation_nodes", "id", node_id, "node_config")
        self.assertNotIn("_encrypted", raw)

        fn(None, None)

        raw = _read_json_field("transformation_nodes", "id", node_id, "node_config")
        self.assertIn("_encrypted", raw)

        # Idempotency
        fn(None, None)

        obj = TransformationNode.objects.get(pk=node_id)
        decrypted = obj.get_node_config()
        self.assertEqual(decrypted["expression"], "age > 18")
        self.assertEqual(decrypted["connection_string"], "postgres://u:p@h/d")
