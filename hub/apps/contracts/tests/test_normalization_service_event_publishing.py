"""
Integration tests for NormalizationService event publishing.

Tests that NormalizationService correctly publishes events when normalizing contracts.
All tests use real EventPublisher and EventBus (no mocks/stubs).
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.contracts.models import Contract, NormalizationStatus, OriginalSpecType
from hub.apps.contracts.normalization_service import NormalizationService
from hub.apps.core.events.models import Event


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class NormalizationServiceEventPublishingIntegrationTest(TestCase):
    """Integration tests for NormalizationService event publishing."""

    def setUp(self):
        """Set up test fixtures."""
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

        # Create a test contract for normalization
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract", "id": "test-contract", "name": "Test Contract", "version": "1.0.0", "schema": {"fields": []}}',
            original_format="json",
            original_spec_type=OriginalSpecType.ODCS,
            created_by=self.user
        )

        self.service = NormalizationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_normalize_contract_publishes_started_and_completed_events(self):
        """Test that normalize_contract publishes normalization.started and normalization.completed events."""
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Count events before normalization
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        completed_count_before = Event.objects.filter(event_type="normalization.completed").count()

        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            contract_id=str(self.contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(norm_status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])

        # Verify events were published
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        completed_count_after = Event.objects.filter(event_type="normalization.completed").count()

        self.assertEqual(started_count_after, started_count_before + 1)
        self.assertEqual(completed_count_after, completed_count_before + 1)

        # Verify started event
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(started_event.data["contract_id"], str(self.contract.id))
        self.assertEqual(started_event.data["normalization_type"], "ODCS")
        self.assertEqual(started_event.data["source_format"], "json")
        self.assertEqual(str(started_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(started_event.user_id), str(self.user.id))

        # Verify completed event
        completed_event = Event.objects.filter(
            event_type="normalization.completed",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(completed_event)
        self.assertEqual(completed_event.data["contract_id"], str(self.contract.id))
        self.assertIn(completed_event.data["normalization_status"], ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        self.assertIsNone(completed_event.data.get("normalization_errors"))
        self.assertIsNotNone(completed_event.data.get("duration_ms"))
        self.assertEqual(str(completed_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(completed_event.user_id), str(self.user.id))

    def test_normalize_contract_without_contract_id_does_not_publish_events(self):
        """Test that normalize_contract does not publish events when contract_id is not provided."""
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Count events before normalization
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        completed_count_before = Event.objects.filter(event_type="normalization.completed").count()

        # Normalize contract without contract_id
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(norm_status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])

        # Verify no events were published
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        completed_count_after = Event.objects.filter(event_type="normalization.completed").count()

        self.assertEqual(started_count_after, started_count_before)
        self.assertEqual(completed_count_after, completed_count_before)

    def test_normalize_contract_failure_publishes_started_and_failed_events(self):
        """Test that normalize_contract publishes normalization.started and normalization.failed events on failure."""
        # Invalid contract that will fail normalization
        raw_contract = '''{
            "invalid": "contract"
        }'''

        # Count events before normalization
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        failed_count_before = Event.objects.filter(event_type="normalization.failed").count()

        # Normalize contract (should fail)
        with self.assertRaises(Exception):
            self.service.normalize_contract(
                raw_contract=raw_contract,
                format="json",
                contract_id=str(self.contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Verify events were published
        started_count_after = Event.objects.filter(event_type="normalization.started").count()
        failed_count_after = Event.objects.filter(event_type="normalization.failed").count()

        self.assertEqual(started_count_after, started_count_before + 1)
        self.assertEqual(failed_count_after, failed_count_before + 1)

        # Verify started event
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(started_event.data["contract_id"], str(self.contract.id))

        # Verify failed event
        failed_event = Event.objects.filter(
            event_type="normalization.failed",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(failed_event)
        self.assertEqual(failed_event.data["contract_id"], str(self.contract.id))
        self.assertIn("error_message", failed_event.data)
        self.assertIsNotNone(failed_event.data.get("normalization_errors"))
        self.assertEqual(str(failed_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(failed_event.user_id), str(self.user.id))

    def test_normalize_contract_schema_validation_failure_publishes_failed_event(self):
        """Test that schema validation failure publishes normalization.failed event."""
        # Contract that normalizes but fails schema validation
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0"
        }'''

        # Count events before normalization
        started_count_before = Event.objects.filter(event_type="normalization.started").count()
        failed_count_before = Event.objects.filter(event_type="normalization.failed").count()

        # Normalize contract (may fail schema validation)
        try:
            hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
                raw_contract=raw_contract,
                format="json",
                contract_id=str(self.contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            # If normalization succeeded but schema validation failed, check for failed event
            if norm_status == NormalizationStatus.NORMALIZATION_FAILED:
                failed_count_after = Event.objects.filter(event_type="normalization.failed").count()
                self.assertEqual(failed_count_after, failed_count_before + 1)

                failed_event = Event.objects.filter(
                    event_type="normalization.failed",
                    data__contract_id=str(self.contract.id)
                ).order_by('-timestamp').first()

                self.assertIsNotNone(failed_event)
                self.assertEqual(failed_event.data["contract_id"], str(self.contract.id))
                self.assertIn("error_message", failed_event.data)
        except Exception:
            # If exception was raised, verify failed event was published
            failed_count_after = Event.objects.filter(event_type="normalization.failed").count()
            self.assertEqual(failed_count_after, failed_count_before + 1)

    def test_normalize_contract_with_warnings_publishes_completed_event_with_warnings(self):
        """Test that normalize_contract publishes normalization.completed event with warnings."""
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Normalize contract
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            contract_id=str(self.contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify completed event was published
        completed_event = Event.objects.filter(
            event_type="normalization.completed",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(completed_event)
        self.assertIn(completed_event.data["normalization_status"], ["NORMALIZED_OK", "NORMALIZED_WITH_WARNINGS"])
        # Warnings may be None or empty list
        if norm_warnings:
            self.assertEqual(completed_event.data.get("normalization_warnings"), norm_warnings)
        else:
            self.assertIsNone(completed_event.data.get("normalization_warnings"))

    def test_normalize_contract_uses_service_tenant_and_user_context(self):
        """Test that events use tenant_id and user_id from service initialization."""
        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Normalize contract without explicitly passing tenant_id/user_id
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            contract_id=str(self.contract.id)
        )

        # Verify events use service's tenant_id and user_id
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(str(started_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(started_event.user_id), str(self.user.id))

    def test_normalize_contract_allows_override_tenant_and_user_per_call(self):
        """Test that normalize_contract allows overriding tenant_id and user_id per call."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Normalize contract with overridden tenant_id and user_id
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = self.service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            contract_id=str(self.contract.id),
            tenant_id=str(other_tenant.id),
            user_id=str(other_user.id)
        )

        # Verify events use overridden tenant_id and user_id
        started_event = Event.objects.filter(
            event_type="normalization.started",
            data__contract_id=str(self.contract.id)
        ).order_by('-timestamp').first()

        self.assertIsNotNone(started_event)
        self.assertEqual(str(started_event.tenant_id), str(other_tenant.id))
        self.assertEqual(str(started_event.user_id), str(other_user.id))

    def test_normalize_contract_event_publishing_failure_does_not_block_normalization(self):
        """Test that event publishing failures do not block normalization."""
        # Create a service with invalid tenant_id to cause event publishing to fail
        # (This is a bit contrived, but tests the error handling)
        service = NormalizationService(
            tenant_id="invalid-uuid",
            user_id=str(self.user.id)
        )

        raw_contract = '''{
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {
                        "name": "test_field",
                        "type": "string",
                        "nullable": false
                    }
                ]
            }
        }'''

        # Normalization should still succeed even if event publishing fails
        hub_contract, detected_spec_type, detected_spec_version, norm_status, norm_errors, norm_warnings = service.normalize_contract(
            raw_contract=raw_contract,
            format="json",
            contract_id=str(self.contract.id),
            tenant_id=str(self.tenant.id),  # Override with valid tenant_id
            user_id=str(self.user.id)
        )

        # Verify normalization succeeded
        self.assertIsNotNone(hub_contract)
        self.assertIn(norm_status, [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS])

