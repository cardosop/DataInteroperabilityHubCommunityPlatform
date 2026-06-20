"""Phase 110: Migration data integrity — constraints enforced."""

import uuid

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant


class MigrationDataIntegrityTest(TestCase):
    """Verify DB constraints from migrations are enforced."""

    def test_unique_constraint_on_tenant_slug(self):
        """Tenant slug uniqueness enforced by DB (raw SQL bypasses ORM patches)."""
        uid = uuid.uuid4().hex[:8]
        slug = f"slug-{uid}"
        # Use the ORM for the first insert so all NOT-NULL columns with
        # Python-level defaults (JSONField, BooleanField, etc.) are populated.
        # The second insert goes through raw SQL to validate the DB-level
        # unique constraint directly.
        Tenant.objects.create(name=f"A {uid}", slug=slug, status="ACTIVE", kyc_status="UNVERIFIED")
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                # Include NOT NULL JSONField columns that lack DB-level
                # defaults so the UNIQUE constraint on slug is the one
                # that fires, not a NOT NULL violation.
                cursor.execute(
                    "INSERT INTO tenants (id, name, slug, status, kyc_status, "
                    "lineage_redact_field_patterns, tenant_dq_warehouse_profile, "
                    "notification_opt_outs, created_at, updated_at) "
                    "VALUES (%s, %s, %s, 'ACTIVE', 'UNVERIFIED', %s, %s, %s, NOW(), NOW())",
                    [str(uuid.uuid4()), f"B {uid}", slug, "[]", "{}", "{}"],
                )

    def test_unique_constraint_on_asset_key_per_tenant(self):
        """Asset key uniqueness per tenant enforced by DB."""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"DI {uid}", slug=f"di-{uid}")
        Asset.objects.create(
            tenant=tenant,
            key=f"key-{uid}",
            name="A",
            status=AssetStatus.DRAFT,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Asset.objects.create(
                tenant=tenant,
                key=f"key-{uid}",
                name="B",
                status=AssetStatus.DRAFT,
            )

    def test_fk_constraint_on_asset_tenant(self):
        """Asset.tenant FK references existing tenant (raw SQL bypasses ORM)."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO assets (id, tenant_id, key, name, status, "
                    "version, created_at, updated_at) "
                    "VALUES (%s, %s, 'orphan', 'Orphan', 'DRAFT', 1, NOW(), NOW())",
                    [str(uuid.uuid4()), str(uuid.uuid4())],
                )

    def test_check_constraint_on_asset_status(self):
        """Asset status check constraint enforced (Phase 92)."""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"CC {uid}", slug=f"cc-{uid}")
        with self.assertRaises((IntegrityError, Exception)):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO assets (id, tenant_id, key, name, status, version, created_at, updated_at) "
                        "VALUES (%s, %s, 'bad', 'Bad', 'INVALID', 1, NOW(), NOW())",
                        [str(uuid.uuid4()), str(tenant.id)],
                    )
