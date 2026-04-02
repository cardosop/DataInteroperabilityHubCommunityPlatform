"""
Comprehensive unit tests for GDPR services.

Tests cover:
- DataPortabilityService methods (create_export_job, _collect_user_data, _build_archive, etc.)
- ErasureService methods (create_request, execute_erasure)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- Validation

All tests use real implementations (no mocks/stubs).
Storage operations gracefully handle when S3/MinIO unavailable.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.baas.models import APIKey, APITier, APITierModel
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.gdpr.models import (
    DataExportJob,
    DataExportStatus,
    ErasureRequest,
    ErasureRequestStatus,
)
from hub.apps.gdpr.services import DataPortabilityService, ErasureService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DataPortabilityServiceTest(TestCase):
    """Comprehensive tests for DataPortabilityService"""

    def setUp(self):
        """Set up test fixtures (unique names for --reuse-db compatibility)."""
        unique = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"GDPR DPS Tenant {unique}",
            slug=f"gdpr-dps-tenant-{unique}",
            status="ACTIVE",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"gdpr-dps-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create service instance
        self.service = DataPortabilityService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Check storage availability
        self.storage_available = False
        try:
            storage_client = S3StorageClient()
            storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    # ========== CREATE EXPORT JOB TESTS ==========

    def test_create_export_job_success(self):
        """Test successful export job creation"""
        job = self.service.create_export_job(user_id=str(self.user.id))

        self.assertIsNotNone(job.id)
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.tenant, self.tenant)
        self.assertIn(job.status, [DataExportStatus.PENDING, DataExportStatus.COMPLETED])

    def test_create_export_job_creates_job_in_db(self):
        """Test that export job is persisted to database"""
        job = self.service.create_export_job(user_id=str(self.user.id))

        # Verify job exists in DB
        db_job = DataExportJob.objects.get(id=job.id)
        self.assertEqual(db_job.user, self.user)
        self.assertEqual(db_job.tenant, self.tenant)

    def test_create_export_job_with_existing_pending_job(self):
        """Test that creating export job when pending job exists raises ValidationError"""
        # Create pending job
        DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.PENDING,
        )

        # Try to create another job
        with self.assertRaises(ValidationError) as cm:
            self.service.create_export_job(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "EXPORT_IN_PROGRESS")

    def test_create_export_job_with_existing_processing_job(self):
        """Test that creating export job when processing job exists raises ValidationError"""
        # Create processing job
        DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.PROCESSING,
        )

        # Try to create another job
        with self.assertRaises(ValidationError) as cm:
            self.service.create_export_job(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "EXPORT_IN_PROGRESS")

    def test_create_export_job_allows_multiple_completed_jobs(self):
        """Test that multiple completed jobs are allowed"""
        # Create completed job
        DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.COMPLETED,
        )

        # Should be able to create another job
        job = self.service.create_export_job(user_id=str(self.user.id))
        self.assertIsNotNone(job.id)

    def test_create_export_job_allows_multiple_failed_jobs(self):
        """Test that multiple failed jobs are allowed"""
        # Create failed job
        DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.FAILED,
        )

        # Should be able to create another job
        job = self.service.create_export_job(user_id=str(self.user.id))
        self.assertIsNotNone(job.id)

    def test_create_export_job_with_nonexistent_user(self):
        """Test that creating export job with nonexistent user raises NotFoundError"""
        fake_user_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.create_export_job(user_id=fake_user_id)

    def test_create_export_job_processes_job(self):
        """Test that export job is processed (if storage available)"""
        if not self.storage_available:
            self.skipTest("Storage not available - skipping test that requires storage")

        job = self.service.create_export_job(user_id=str(self.user.id))

        # Job should be processed (status could be COMPLETED or FAILED)
        job.refresh_from_db()
        self.assertIn(
            job.status,
            [DataExportStatus.COMPLETED, DataExportStatus.FAILED, DataExportStatus.PROCESSING],
        )

    # ========== COLLECT USER DATA TESTS ==========

    def test_collect_user_data_includes_user_profile(self):
        """Test that _collect_user_data includes user profile"""
        data = self.service._collect_user_data(self.user)

        self.assertIn("user_profile", data)
        self.assertEqual(data["user_profile"]["id"], str(self.user.id))
        self.assertEqual(data["user_profile"]["email"], self.user.email)
        self.assertEqual(data["user_profile"]["display_name"], self.user.display_name)

    def test_collect_user_data_includes_audit_events(self):
        """Test that _collect_user_data includes audit events"""
        # Create audit events
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"key": "test-asset"},
        )

        data = self.service._collect_user_data(self.user)

        self.assertIn("audit_events", data)
        self.assertEqual(len(data["audit_events"]), 1)
        self.assertEqual(data["audit_events"][0]["action"], "ASSET_CREATED")

    def test_collect_user_data_includes_assets(self):
        """Test that _collect_user_data includes assets"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        data = self.service._collect_user_data(self.user)

        self.assertIn("assets", data)
        self.assertEqual(len(data["assets"]), 1)
        self.assertEqual(data["assets"][0]["id"], str(asset.id))
        self.assertEqual(data["assets"][0]["name"], asset.name)

    def test_collect_user_data_includes_datasets(self):
        """Test that _collect_user_data includes datasets"""
        # Create dataset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset,
            file=file_obj,
            format="CSV",
            created_by=self.user,
        )

        data = self.service._collect_user_data(self.user)

        self.assertIn("datasets", data)
        self.assertEqual(len(data["datasets"]), 1)
        self.assertEqual(data["datasets"][0]["id"], str(dataset.id))

    def test_collect_user_data_includes_contracts(self):
        """Test that _collect_user_data includes contracts"""
        from hub.apps.contracts.models import OriginalFormat, OriginalSpecType

        # Create asset for contract (optional but gives a meaningful label)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-contract",
            name="Test Asset for Contract",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create contract with required fields (no name field on Contract)
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"apiVersion":"odcs.io/v3.0.2","kind":"DataContract"}',
            created_by=self.user,
        )

        data = self.service._collect_user_data(self.user)

        self.assertIn("contracts", data)
        self.assertEqual(len(data["contracts"]), 1)
        self.assertEqual(data["contracts"][0]["id"], str(contract.id))

    def test_collect_user_data_limits_audit_events(self):
        """Test that _collect_user_data limits audit events to 1000"""
        # Use bulk_create for efficiency: avoids 1005 individual INSERT
        # transactions and the per-row immutability check in AuditEvent.save().
        # bulk_create is safe here because we're creating new records (append-only
        # invariant is preserved) and the test only needs the count to exceed 1000.
        from hub.apps.audit.models import AuditEvent as AuditEventModel
        events = [
            AuditEventModel(
                resource_type="ASSET",
                action="ASSET_CREATED",
                actor_user=self.user,
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                details_json={"key": f"test-asset-{i}"},
            )
            for i in range(1005)
        ]
        AuditEventModel.objects.bulk_create(events)

        data = self.service._collect_user_data(self.user)

        self.assertLessEqual(len(data["audit_events"]), 1000)

    def test_collect_user_data_empty_when_no_data(self):
        """Test that _collect_user_data returns empty lists when user has no data"""
        data = self.service._collect_user_data(self.user)

        self.assertEqual(data["audit_events"], [])
        self.assertEqual(data["assets"], [])
        self.assertEqual(data["datasets"], [])
        self.assertEqual(data["contracts"], [])

    # ========== BUILD ARCHIVE TESTS ==========

    def test_build_archive_creates_zip(self):
        """Test that _build_archive creates a ZIP file"""
        data = self.service._collect_user_data(self.user)
        archive_bytes = self.service._build_archive(data, self.user)

        self.assertIsInstance(archive_bytes, bytes)
        self.assertGreater(len(archive_bytes), 0)

        # Verify it's a valid ZIP file
        import io
        import zipfile

        zip_file = zipfile.ZipFile(io.BytesIO(archive_bytes))
        self.assertIsNotNone(zip_file)

    def test_build_archive_includes_user_data_json(self):
        """Test that _build_archive includes user_data.json"""
        data = self.service._collect_user_data(self.user)
        archive_bytes = self.service._build_archive(data, self.user)

        import io
        import json
        import zipfile

        zip_file = zipfile.ZipFile(io.BytesIO(archive_bytes))
        self.assertIn("user_data.json", zip_file.namelist())

        # Verify JSON content
        json_data = json.loads(zip_file.read("user_data.json"))
        self.assertEqual(json_data["user_profile"]["email"], self.user.email)

    def test_build_archive_includes_readme(self):
        """Test that _build_archive includes README.txt"""
        data = self.service._collect_user_data(self.user)
        archive_bytes = self.service._build_archive(data, self.user)

        import io
        import zipfile

        zip_file = zipfile.ZipFile(io.BytesIO(archive_bytes))
        self.assertIn("README.txt", zip_file.namelist())

        readme_content = zip_file.read("README.txt").decode("utf-8")
        self.assertIn(self.user.email, readme_content)

    # ========== EDGE CASES TESTS ==========

    def test_create_export_job_different_users(self):
        """Test that different users can have export jobs simultaneously"""
        unique = str(uuid.uuid4())[:8]
        # Create another user
        user2 = User.objects.create_user(
            email=f"gdpr-dps-user2-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Create job for first user
        job1 = self.service.create_export_job(user_id=str(self.user.id))

        # Create job for second user (should succeed)
        service2 = DataPortabilityService(tenant_id=str(self.tenant.id), user_id=str(user2.id))
        job2 = service2.create_export_job(user_id=str(user2.id))

        self.assertNotEqual(job1.id, job2.id)
        self.assertEqual(job1.user, self.user)
        self.assertEqual(job2.user, user2)

    def test_create_export_job_different_tenants(self):
        """Test that different tenants can have export jobs simultaneously"""
        unique = str(uuid.uuid4())[:8]
        # Create another tenant and user
        tenant2 = Tenant.objects.create(
            name=f"GDPR DPS Tenant2 {unique}",
            slug=f"gdpr-dps-tenant2-{unique}",
            status="ACTIVE",
        )
        user2 = User.objects.create_user(
            email=f"gdpr-dps-tenant2-{unique}@example.com",
            password="testpass123",
            tenant=tenant2,
        )

        # Create job for first tenant
        job1 = self.service.create_export_job(user_id=str(self.user.id))

        # Create job for second tenant (should succeed)
        service2 = DataPortabilityService(tenant_id=str(tenant2.id), user_id=str(user2.id))
        job2 = service2.create_export_job(user_id=str(user2.id))

        self.assertNotEqual(job1.id, job2.id)
        self.assertEqual(job1.tenant, self.tenant)
        self.assertEqual(job2.tenant, tenant2)


class ErasureServiceTest(TestCase):
    """Comprehensive tests for ErasureService"""

    def setUp(self):
        """Set up test fixtures (unique names for --reuse-db compatibility)."""
        unique = str(uuid.uuid4())[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"GDPR ES Tenant {unique}",
            slug=f"gdpr-es-tenant-{unique}",
            status="ACTIVE",
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"gdpr-es-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API tier
        self.tier = APITierModel.objects.get_or_create(
            name=APITier.FREE,
            defaults={
                "rate_limit_per_hour": 1000,
                "rate_limit_per_day": 10000,
                "max_requests_per_month": 100000,
            },
        )[0]

        # Create API key
        key_value = APIKey.generate_key()
        key_hash = APIKey.hash_key(key_value)
        self.api_key = APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="Test API Key",
            key_hash=key_hash,
            tier=self.tier,
        )

        # Create service instance
        self.service = ErasureService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    # ========== CREATE REQUEST TESTS ==========

    def test_create_request_success(self):
        """Test successful erasure request creation"""
        request = self.service.create_request(user_id=str(self.user.id))

        self.assertIsNotNone(request.id)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.status, ErasureRequestStatus.PENDING)

    def test_create_request_creates_audit_event(self):
        """Test that create_request creates audit event (self-requested; no source)."""
        initial_count = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED"
        ).count()

        self.service.create_request(user_id=str(self.user.id))

        final_count = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED"
        ).count()

        self.assertEqual(final_count, initial_count + 1)

        # Self-requested: actor_user = target user; no initiated_by/source
        event = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED"
        ).order_by("-timestamp").first()
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.actor_user_id, self.user.id)
        self.assertNotIn("source", event.details_json)
        self.assertNotIn("initiated_by", event.details_json)

    def test_create_request_platform_admin_actor_in_audit(self):
        """Task 29.67.2.3: Platform admin creates erasure → audit actor_user = platform admin."""
        unique = str(uuid.uuid4())[:8]
        platform_admin = User.objects.create_user(
            email=f"platform-admin-{unique}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        target_user = self.user  # Different from platform_admin

        service = ErasureService(
            tenant_id=str(self.tenant.id), user_id=str(platform_admin.id)
        )
        service.create_request(user_id=str(target_user.id))

        event = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_REQUESTED"
        ).order_by("-timestamp").first()

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.actor_user_id, platform_admin.id)
        self.assertEqual(event.details_json.get("source"), "platform_admin")
        self.assertEqual(event.details_json.get("initiated_by"), str(platform_admin.id))

    def test_create_request_with_existing_pending_request(self):
        """Test that creating request when pending request exists raises ValidationError"""
        # Create pending request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )

        # Try to create another request
        with self.assertRaises(ValidationError) as cm:
            self.service.create_request(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "ERASURE_IN_PROGRESS")

    def test_create_request_with_existing_processing_request(self):
        """Test that creating request when processing request exists raises ValidationError"""
        # Create processing request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PROCESSING,
        )

        # Try to create another request
        with self.assertRaises(ValidationError) as cm:
            self.service.create_request(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "ERASURE_IN_PROGRESS")

    def test_create_request_allows_multiple_completed_requests(self):
        """Test that multiple completed requests are allowed"""
        # Create completed request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.COMPLETED,
        )

        # Should be able to create another request
        request = self.service.create_request(user_id=str(self.user.id))
        self.assertIsNotNone(request.id)

    def test_create_request_with_nonexistent_user(self):
        """Test that creating request with nonexistent user raises NotFoundError"""
        fake_user_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.create_request(user_id=fake_user_id)

    # ========== EXECUTE ERASURE TESTS ==========

    def test_execute_erasure_success(self):
        """Test successful erasure execution"""
        request = self.service.create_request(user_id=str(self.user.id))
        original_email = self.user.email

        request = self.service.execute_erasure(request_id=str(request.id))

        # Refresh user from DB
        self.user.refresh_from_db()

        # Check user is anonymized
        self.assertNotEqual(self.user.email, original_email)
        self.assertIn("deleted-", self.user.email)
        self.assertEqual(self.user.display_name, "Deleted User")

        # Check request is completed
        self.assertEqual(request.status, ErasureRequestStatus.COMPLETED)
        self.assertIsNotNone(request.completed_at)
        self.assertIn("email", request.anonymized_fields)
        self.assertIn("display_name", request.anonymized_fields)

    def test_execute_erasure_revokes_api_keys(self):
        """Test that execute_erasure deactivates API keys"""
        request = self.service.create_request(user_id=str(self.user.id))
        request = self.service.execute_erasure(request_id=str(request.id))

        # Refresh API key from DB
        self.api_key.refresh_from_db()

        # Check API key is revoked
        self.assertIsNotNone(self.api_key.revoked_at)
        self.assertFalse(self.api_key.is_active())
        self.assertIn("api_keys", request.deleted_resources)

    def test_execute_erasure_handles_already_completed(self):
        """Test that executing already completed erasure returns request"""
        request = self.service.create_request(user_id=str(self.user.id))
        request = self.service.execute_erasure(request_id=str(request.id))

        # Execute again
        request2 = self.service.execute_erasure(request_id=str(request.id))

        self.assertEqual(request.id, request2.id)
        self.assertEqual(request2.status, ErasureRequestStatus.COMPLETED)

    def test_execute_erasure_with_nonexistent_request(self):
        """Test that executing erasure with nonexistent request raises NotFoundError"""
        fake_request_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.execute_erasure(request_id=fake_request_id)

    def test_execute_erasure_creates_audit_event(self):
        """Test that execute_erasure creates audit event"""
        request = self.service.create_request(user_id=str(self.user.id))

        initial_count = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_COMPLETED"
        ).count()

        self.service.execute_erasure(request_id=str(request.id))

        final_count = AuditEvent.objects.filter(
            resource_type="ERASURE_REQUEST", action="ERASURE_COMPLETED"
        ).count()

        self.assertEqual(final_count, initial_count + 1)

    def test_execute_erasure_anonymizes_audit_events(self):
        """Test that execute_erasure anonymizes PII in audit event details_json"""
        # Create audit event with PII in details — use a unique resource_id
        # so we can find this specific event after erasure creates its own events
        test_resource_id = uuid.uuid4()
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(test_resource_id),
            details={"user_email": self.user.email, "actor_email": self.user.email},
        )

        request = self.service.create_request(user_id=str(self.user.id))
        self.service.execute_erasure(request_id=str(request.id))

        # Find the specific event we created (not the erasure service's own events)
        audit_event = AuditEvent.objects.filter(
            actor_user=self.user, resource_id=test_resource_id
        ).first()
        self.assertIsNotNone(audit_event, "Test audit event should still exist after erasure")
        self.assertIsInstance(audit_event.details_json, dict)
        self.assertEqual(
            audit_event.details_json["user_email"], "deleted@deleted.local"
        )
        self.assertEqual(
            audit_event.details_json["actor_email"], "deleted@deleted.local"
        )

    def test_execute_erasure_records_retention_exceptions(self):
        """Test that execute_erasure records retention exceptions"""
        request = self.service.create_request(user_id=str(self.user.id))
        request = self.service.execute_erasure(request_id=str(request.id))

        # Audit events should be in retention exceptions
        self.assertIn("audit_events", request.retention_exceptions)

    # ========== ERROR HANDLING TESTS ==========

    def test_execute_erasure_handles_failure_gracefully(self):
        """Test that execute_erasure handles failures gracefully.

        Uses IntegrityError: pre-create a user with the anonymized email so that
        user.save() fails during anonymization. The request survives (no CASCADE)
        and is marked FAILED by the service.
        """
        request = self.service.create_request(user_id=str(self.user.id))

        # Pre-create user with anonymized email so user.save() fails (unique constraint)
        unique = str(uuid.uuid4())[:8]
        anon_email = f"deleted-{self.user.id}@deleted.local"
        User.objects.create_user(
            email=anon_email,
            password="unused",
            tenant=self.tenant,
            display_name=f"Collision User {unique}",
        )

        # Should raise exception, but request should be marked as FAILED
        with self.assertRaises(Exception):
            self.service.execute_erasure(request_id=str(request.id))

        # Request should be marked as failed (request survives; no CASCADE)
        request.refresh_from_db()
        self.assertEqual(request.status, ErasureRequestStatus.FAILED)
        self.assertIsNotNone(request.error_message)

    # ========== EDGE CASES TESTS ==========

    def test_create_request_different_users(self):
        """Test that different users can have erasure requests simultaneously"""
        unique = str(uuid.uuid4())[:8]
        # Create another user
        user2 = User.objects.create_user(
            email=f"gdpr-es-user2-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Create request for first user
        request1 = self.service.create_request(user_id=str(self.user.id))

        # Create request for second user (should succeed)
        service2 = ErasureService(tenant_id=str(self.tenant.id), user_id=str(user2.id))
        request2 = service2.create_request(user_id=str(user2.id))

        self.assertNotEqual(request1.id, request2.id)
        self.assertEqual(request1.user, self.user)
        self.assertEqual(request2.user, user2)

    def test_execute_erasure_multiple_times_idempotent(self):
        """Test that executing erasure multiple times is idempotent"""
        request = self.service.create_request(user_id=str(self.user.id))

        # Execute first time
        request1 = self.service.execute_erasure(request_id=str(request.id))
        status1 = request1.status
        completed_at1 = request1.completed_at

        # Execute second time
        request2 = self.service.execute_erasure(request_id=str(request.id))
        status2 = request2.status
        completed_at2 = request2.completed_at

        # Should be the same
        self.assertEqual(status1, status2)
        self.assertEqual(completed_at1, completed_at2)
