"""pilot-readiness 4.4 — seed the exit-clause drill tenant (idempotent).

The exit-clause drill (``scripts/run_exit_clause_drill.py``) needs a REAL
sacrificial tenant it can export and then hard-delete end-to-end. This
command provisions ``pilot-exit-drill`` — deliberately NOT the privacy
pack's ``pilot-co`` tenant (that one carries the DPIA/RoPA/DPA pack and
must survive) — with one TENANT_ADMIN user, one asset, one uploaded file
object, and one audit event, so every data class the export/deletion path
must cover exists.

Deterministic UUIDs let re-runs fetch-or-create the same rows (mirrors
``seed_pilot_privacy_tenant``); after a completed drill the tenant is gone
and the next drill re-creates it.

Usage (in the test stack):
    docker exec hub-test-api python hub/manage.py seed_pilot_exit_drill_tenant
"""

import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus

# Deterministic IDs — referenced by the drill runner.
PILOT_TENANT_ID = uuid.UUID("bbbbbbb1-0001-4001-8001-000000000001")
PILOT_ASSET_ID = uuid.UUID("bbbbbbb2-0002-4002-8002-000000000002")
PILOT_FILE_ID = uuid.UUID("bbbbbbb3-0003-4003-8003-000000000003")

SLUG = "pilot-exit-drill"
NAME = "Pilot Exit Drill Tenant"
ADMIN_EMAIL = "pilot_exit_admin@example.com"
PASSWORD = "TestPass123"  # E2E persona convention

ASSET_KEY = "exit-drill-dataset"
FILE_NAME = "exit-drill-report.csv"


class Command(BaseCommand):
    help = "Seed the pilot exit-clause drill tenant (idempotent)."

    def handle(self, *_args, **_options):
        # all_objects: the default manager filters soft-deleted rows — a
        # leftover DELETED tenant would be invisible to get_or_create and
        # the INSERT would collide on the PK (drill re-run finding).
        tenant, created = Tenant.all_objects.get_or_create(
            id=PILOT_TENANT_ID,
            defaults={
                "slug": SLUG,
                "name": NAME,
                "status": TenantStatus.ACTIVE,
                "kyc_status": KYCStatus.VERIFIED,
                "onboarding_completed_at": timezone.now(),
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created drill tenant {SLUG}."))

        # TENANT_ADMIN user with the tenant-admin role.
        user, _ = User.objects.get_or_create(
            email=ADMIN_EMAIL,
            defaults={
                "tenant": tenant,
                "password": "unused-hash",
                "status": UserStatus.ACTIVE,
            },
        )
        if not user.tenant_id or str(user.tenant_id) != str(tenant.id):
            user.tenant = tenant
            user.save()
        user.set_password(PASSWORD)
        user.save()
        role, _ = Role.objects.get_or_create(
            tenant=tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Exit-clause drill TENANT_ADMIN"},
        )
        UserRole.objects.get_or_create(user=user, role=role, tenant=tenant)

        # One asset.
        Asset.objects.get_or_create(
            id=PILOT_ASSET_ID,
            defaults={
                "tenant": tenant,
                "key": ASSET_KEY,
                "name": "Exit Drill Dataset",
                "status": AssetStatus.ACTIVE,
                "created_by": user,
            },
        )

        # One uploaded file object (metadata row + real storage object).
        file_obj, _ = File.objects.get_or_create(
            id=PILOT_FILE_ID,
            defaults={
                "tenant": tenant,
                "created_by": user,
                "name": FILE_NAME,
                "storage_path": f"tenant-files/{tenant.id}/{FILE_NAME}",
                "size": 12,
                "content_type": "text/csv",
                "content_sha256": "0" * 64,
                "status": FileStatus.ACTIVE,
            },
        )
        from hub.apps.files.storage import S3StorageClient

        storage = S3StorageClient()
        storage._ensure_bucket_exists()
        try:
            storage.upload_file(
                file_path=file_obj.storage_path,
                file_content=b"col1,col2\n1,2\n",
                content_type="text/csv",
            )
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"File object upload skipped: {exc}"))

        # One audit event so the audit-trail export leg has real content.
        create_audit_event(
            resource_type="TENANT",
            action="TENANT_CREATED",
            tenant=tenant,
            actor_user=None,
            resource_id=str(tenant.id),
            details={"source": "seed_pilot_exit_drill_tenant"},
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Drill tenant ready: {SLUG} ({tenant.id}) "
                f"admin={ADMIN_EMAIL} asset={ASSET_KEY} file={FILE_NAME}"
            )
        )
