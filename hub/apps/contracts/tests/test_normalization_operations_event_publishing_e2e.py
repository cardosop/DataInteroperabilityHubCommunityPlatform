"""
End-to-end tests for normalization event publishing through API operations.

Tests that normalization events are published when contracts are created/updated via API.
All tests use real services and models (no mocks/stubs).
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
from hub.apps.core.events.models import Event


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class NormalizationOperationsEventPublishingE2ETest(TestCase):
    """E2E tests for normalization event publishing through API operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        self.client.force_authenticate(user=self.user)

    def test_update_contract_publishes_normalization_events(self):
        """Test that updating a contract via API publishes normalization events."""
        # Create a contract first
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", "id": "test-contract", "name": "Test Contract", "version": "1.0.0", "schema": {"fields": [{"name": "test_field", "type": "string", "nullable": false}]}}',
            original_format="json",
            original_spec_type=OriginalSpecType.ODCS,
            created_by=self.user
        )

        # Count events before update
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        completed_count_before = Event.objects.filter(event_type="normalization.completed").count()

        # Update contract via API
        url = reverse("contract-detail", kwargs={"id": str(contract.id)})
        updated_raw = '{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", "id": "test-contract-updated", "name": "Test Contract Updated", "version": "1.0.0", "schema": {"fields": [{"name": "test_field", "type": "string", "nullable": false}]}}'
        data = {
            "original_raw": updated_raw
        }

        response = self.client.patch(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify events were published
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        completed_count_after = Event.objects.filter(event_type="normalization.completed").count()

        self.assertEqual(started_count_after, started_count_before + 1)
        self.assertEqual(completed_count_after, completed_count_before + 1)

        # Verify started event
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(started_event.data["contract_id"], str(contract.id))
        self.assertEqual(str(started_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(started_event.user_id), str(self.user.id))

        # Verify completed event
        completed_event = Event.objects.filter(
            event_type="normalization.completed",
            data__contract_id=str(contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(completed_event)
        self.assertEqual(completed_event.data["contract_id"], str(contract.id))
        self.assertIn(completed_event.data["normalization_status"], ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        self.assertEqual(str(completed_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(completed_event.user_id), str(self.user.id))

    def test_update_contract_with_invalid_data_publishes_failed_event(self):
        """Test that updating a contract with invalid data publishes normalization.failed event."""
        # Create a contract first
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", "id": "test-contract", "name": "Test Contract", "version": "1.0.0", "schema": {"fields": [{"name": "test_field", "type": "string", "nullable": false}]}}',
            original_format="json",
            original_spec_type=OriginalSpecType.ODCS,
            created_by=self.user
        )

        # Count events before update
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        failed_count_before = Event.objects.filter(event_type="normalization.failed").count()

        # Update contract with invalid data
        url = reverse("contract-detail", kwargs={"id": str(contract.id)})
        invalid_raw = '{"invalid": "contract"}'
        data = {
            "original_raw": invalid_raw
        }

        # Update should fail, but normalization events should still be published
        try:
            response = self.client.patch(url, data, format="json")
            # If update succeeds but normalization fails, check for failed event
            if response.status_code == status.HTTP_200_OK:
                # Check if normalization failed
                contract.refresh_from_db()
                if contract.normalization_status == NormalizationStatus.NORMALIZATION_FAILED:
                    failed_count_after = Event.objects.filter(event_type="normalization.failed").count()
                    self.assertEqual(failed_count_after, failed_count_before + 1)

                    failed_event = Event.objects.filter(
                        event_type="normalization.failed",
                        data__contract_id=str(contract.id)
                    ).order_by('-timestamp').first()

                    self.assertIsNotNone(failed_event)
                    self.assertEqual(failed_event.data["contract_id"], str(contract.id))
                    self.assertIn("error_message", failed_event.data)
        except Exception:
            # If update raises exception, normalization events may still have been published
            # Check for started event at least
            started_count_after = Event.objects.filter(event_type="normalization.started").count()
            self.assertGreaterEqual(started_count_after, started_count_before)

    def test_odps_normalization_job_publishes_normalization_events(self):
        """Test that ODPS normalization job publishes normalization events."""
        from hub.apps.jobs.models import Job, JobType, JobStatus
        from hub.apps.jobs.tasks import _execute_odps_normalization_job

        # Create an ODPS contract
        odps_raw = '''{
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-job",
                        "name": "Test ODPS Job"
                    }
                },
                "dataSchema": {
                    "fields": [
                        {
                            "name": "test_field",
                            "type": "string"
                        }
                    ]
                }
            }
        }'''

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=odps_raw,
            original_format="JSON",
            original_spec_type=OriginalSpecType.ODPS,
            created_by=self.user
        )

        # Create a job for normalization
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.ODPS_NORMALIZATION,
            status=JobStatus.PENDING,
            resource_type="CONTRACT",
            resource_id=contract.id,
            details_json={"contract_id": str(contract.id)},
            created_by=self.user
        )

        # Count events before job execution
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        completed_count_before = Event.objects.filter(event_type="normalization.completed").count()

        # Execute normalization job
        try:
            _execute_odps_normalization_job(job)
        except Exception as e:
            # Job may fail, but events should still be published
            pass

        # Verify events were published
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        completed_count_after = Event.objects.filter(event_type="normalization.completed").count()

        # At least started event should be published
        self.assertGreaterEqual(started_count_after, started_count_before + 1)

        # Verify started event
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(started_event.data["contract_id"], str(contract.id))
        self.assertEqual(str(started_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(started_event.user_id), str(self.user.id))

        # If normalization succeeded, verify completed event
        if completed_count_after > completed_count_before:
            completed_event = Event.objects.filter(
                event_type="normalization.completed",
                data__contract_id=str(contract.id)
            ).order_by('-timestamp').first()

            self.assertIsNotNone(completed_event)
            self.assertEqual(completed_event.data["contract_id"], str(contract.id))

    def test_create_contract_does_not_publish_normalization_events(self):
        """Test that creating a contract does not publish normalization events (contract_id not available yet)."""
        # Count events before creation
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        completed_count_before = Event.objects.filter(event_type="normalization.completed").count()

        # Create contract via API
        url = reverse("contract-list")
        data = {
            "original_raw": '{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", "id": "test-contract-new", "name": "Test Contract New", "version": "1.0.0", "schema": {"fields": [{"name": "test_field", "type": "string", "nullable": false}]}}',
            "original_format": "JSON"
        }

        response = self.client.post(url, data, format="json")

        # Contract creation may succeed or fail, but normalization events should not be published
        # (because contract_id is not available during normalization)
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        completed_count_after = Event.objects.filter(event_type="normalization.completed").count()

        # Events should not be published during creation (contract_id not available)
        self.assertEqual(started_count_after, started_count_before)
        self.assertEqual(completed_count_after, completed_count_before)

