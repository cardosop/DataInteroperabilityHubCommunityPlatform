"""Phase 110: Migration data integrity — constraints enforced."""
import uuid
from django.test import TestCase
from django.db import connection, IntegrityError, transaction
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus


class MigrationDataIntegrityTest(TestCase):
    """Verify DB constraints from migrations are enforced."""

    def test_unique_constraint_on_tenant_slug(self):
        """Tenant slug uniqueness enforced by DB (raw SQL bypasses ORM patches)."""
        uid = uuid.uuid4().hex[:8]
        slug = f"slug-{uid}"
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO tenants (id, name, slug, status, kyc_status, created_at, updated_at) "
                "VALUES (%s, %s, %s, 'ACTIVE', 'UNVERIFIED', NOW(), NOW())",
                [str(uuid.uuid4()), f"A {uid}", slug],
            )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO tenants (id, name, slug, status, kyc_status, created_at, updated_at) "
                        "VALUES (%s, %s, %s, 'ACTIVE', 'UNVERIFIED', NOW(), NOW())",
                        [str(uuid.uuid4()), f"B {uid}", slug],
                    )

    def test_unique_constraint_on_asset_key_per_tenant(self):
        """Asset key uniqueness per tenant enforced by DB."""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"DI {uid}", slug=f"di-{uid}")
        Asset.objects.create(
            tenant=tenant, key=f"key-{uid}", name="A",
            status=AssetStatus.DRAFT,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Asset.objects.create(
                    tenant=tenant, key=f"key-{uid}", name="B",
                    status=AssetStatus.DRAFT,
                )

    def test_fk_constraint_on_asset_tenant(self):
        """Asset.tenant FK references existing tenant (raw SQL bypasses ORM)."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
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
