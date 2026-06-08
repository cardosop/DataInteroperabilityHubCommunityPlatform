"""
Integration tests for ODPS notification emails.
"""
import uuid

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.notifications.models import EmailDelivery, EmailDeliveryStatus, EmailType
from hub.apps.notifications.services import EmailServiceError
from hub.apps.notifications.tasks import (
    send_odps_creation_completion_email,
    send_odps_linking_status_email,
    send_odps_normalization_failure_email,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class ODPSNotificationIntegrationTest(TestCase):
    """Integration tests for ODPS notification emails"""

    def setUp(self):
        """Set up test fixtures"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, display_name="Test User"
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            key=f"test-asset-{uuid.uuid4().hex[:8]}",  # Unique key per test run
            created_by=self.user,
        )
        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=1,  # Explicit version to avoid constraint violation
            original_raw='{"product": {"name": "Test Product"}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"product": {"name": "Test Product"}},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            normalization_errors=[],
            normalization_warnings=[],
            status=ContractStatus.DRAFT,
            created_by=self.user,
        )
        # Create ODCS contract with different version to avoid unique constraint violation
        # The constraint is on (tenant, asset, version), so we need version=2
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            version=2,  # Different version to avoid constraint violation
            original_raw='{"openapi": "3.0.0"}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            hub_contract_json={"openapi": "3.0.0"},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            normalization_errors=[],
            normalization_warnings=[],
            status=ContractStatus.DRAFT,
            created_by=self.user,
        )

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_creation_completion_email(self, mock_get_service):
        """Test sending ODPS creation completion email"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {"success": True, "message_id": "test-message-id"}
        mock_get_service.return_value = mock_service

        # Send email
        result = send_odps_creation_completion_email(str(self.odps_contract.id))

        # Verify email was sent
        self.assertTrue(result["success"])
        mock_service.send_email.assert_called_once()

        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.ODPS_CREATION_COMPLETION, to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)
        self.assertEqual(delivery.message_id, "test-message-id")

        # Verify email content includes contract ID
        call_args = mock_service.send_email.call_args
        self.assertIn(str(self.odps_contract.id), call_args[1]["html_content"])

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_creation_completion_email_no_user(self, mock_get_service):
        """Test that email is not sent when contract has no created_by user"""
        # Create contract without created_by
        # Use a different asset to avoid version constraint issues
        import uuid

        asset_no_user = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset No User",
            key=f"test-asset-no-user-{uuid.uuid4().hex[:8]}",  # Unique key
            created_by=None,
        )
        contract_no_user = Contract.objects.create(
            tenant=self.tenant,
            asset=asset_no_user,
            version=1,
            original_raw='{"product": {"name": "Test Product"}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"product": {"name": "Test Product"}},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            normalization_errors=[],
            normalization_warnings=[],
            status=ContractStatus.DRAFT,
            created_by=None,
        )

        # Setup mock email service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Send email
        result = send_odps_creation_completion_email(str(contract_no_user.id))

        # Verify email was not sent
        self.assertIsNone(result)
        mock_service.send_email.assert_not_called()

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_normalization_failure_email(self, mock_get_service):
        """Test sending ODPS normalization failure email"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {"success": True, "message_id": "test-message-id"}
        mock_get_service.return_value = mock_service

        # Update contract to have normalization failure
        self.odps_contract.normalization_status = NormalizationStatus.NORMALIZATION_FAILED
        self.odps_contract.normalization_errors = ["Error 1", "Error 2"]
        self.odps_contract.save()

        # Send email
        result = send_odps_normalization_failure_email(
            contract_id=str(self.odps_contract.id),
            error_message="ODPS normalization failed",
            error_code="ODPS_NORMALIZATION_ERROR",
            errors=["Error 1", "Error 2"],
            field_path="product.name",
        )

        # Verify email was sent
        self.assertTrue(result["success"])
        mock_service.send_email.assert_called_once()

        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.ODPS_NORMALIZATION_FAILURE, to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)

        # Verify email content includes error information
        call_args = mock_service.send_email.call_args
        html_content = call_args[1]["html_content"]
        self.assertIn("ODPS normalization failed", html_content)
        self.assertIn("Error 1", html_content)
        self.assertIn("Error 2", html_content)

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_linking_status_email_completed(self, mock_get_service):
        """Test sending ODPS linking status email for completed linking"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {"success": True, "message_id": "test-message-id"}
        mock_get_service.return_value = mock_service

        # Send email
        result = send_odps_linking_status_email(
            odps_contract_id=str(self.odps_contract.id),
            status="completed",
            status_message="Contracts linked successfully",
            odcs_contract_id=str(self.odcs_contract.id),
            progress_percentage=100.0,
            current_phase="completed",
            validation_passed=True,
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
        )

        # Verify email was sent
        self.assertTrue(result["success"])
        mock_service.send_email.assert_called_once()

        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.ODPS_LINKING_STATUS, to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)

        # Verify email content includes linking information
        call_args = mock_service.send_email.call_args
        html_content = call_args[1]["html_content"]
        self.assertIn("completed", html_content)
        self.assertIn("Contracts linked successfully", html_content)
        self.assertIn(str(self.odps_contract.id), html_content)
        self.assertIn(str(self.odcs_contract.id), html_content)

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_linking_status_email_failed(self, mock_get_service):
        """Test sending ODPS linking status email for failed linking"""
        # Setup mock email service
        mock_service = Mock()
        mock_service.send_email.return_value = {"success": True, "message_id": "test-message-id"}
        mock_get_service.return_value = mock_service

        # Send email
        result = send_odps_linking_status_email(
            odps_contract_id=str(self.odps_contract.id),
            status="failed",
            status_message="Linking validation failed",
            odcs_contract_id=str(self.odcs_contract.id),
            progress_percentage=50.0,
            current_phase="validation",
            validation_passed=False,
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
        )

        # Verify email was sent
        self.assertTrue(result["success"])
        mock_service.send_email.assert_called_once()

        # Verify email delivery record
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.ODPS_LINKING_STATUS, to_email=self.user.email
        ).first()
        self.assertIsNotNone(delivery)
        self.assertEqual(delivery.status, EmailDeliveryStatus.SENT)

        # Verify email content includes failure information
        call_args = mock_service.send_email.call_args
        html_content = call_args[1]["html_content"]
        self.assertIn("failed", html_content)
        self.assertIn("Linking validation failed", html_content)

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_linking_status_email_no_user(self, mock_get_service):
        """Test that email is not sent when no user is available"""
        # Create contract without created_by
        # Use a different asset to avoid version constraint issues
        import uuid

        asset_no_user = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset No User Linking",
            key=f"test-asset-no-user-linking-{uuid.uuid4().hex[:8]}",  # Unique key
            created_by=None,
        )
        contract_no_user = Contract.objects.create(
            tenant=self.tenant,
            asset=asset_no_user,
            version=1,
            original_raw='{"product": {"name": "Test Product"}}',
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={"product": {"name": "Test Product"}},
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            normalization_errors=[],
            normalization_warnings=[],
            status=ContractStatus.DRAFT,
            created_by=None,
        )

        # Setup mock email service
        mock_service = Mock()
        mock_get_service.return_value = mock_service

        # Send email without user_id
        result = send_odps_linking_status_email(
            odps_contract_id=str(contract_no_user.id),
            status="completed",
            status_message="Contracts linked successfully",
            odcs_contract_id=str(self.odcs_contract.id),
            progress_percentage=100.0,
            current_phase="completed",
            validation_passed=True,
            user_id=None,
            tenant_id=str(self.tenant.id),
        )

        # Verify email was not sent
        self.assertIsNone(result)
        mock_service.send_email.assert_not_called()

    @patch("hub.apps.notifications.tasks.get_email_service")
    def test_send_odps_notification_email_service_error(self, mock_get_service):
        """Test that notification handles email service errors gracefully"""
        # Setup mock to raise error
        mock_service = Mock()
        mock_service.send_email.side_effect = EmailServiceError("Service unavailable")
        mock_get_service.return_value = mock_service

        # Send email - task records failure and propagates EmailServiceError to caller.
        # The ERROR log is expected — verified with assertLogs to keep CI output clean.
        with self.assertRaises(EmailServiceError), \
             self.assertLogs('hub.apps.notifications.tasks', level='ERROR'):
            send_odps_creation_completion_email(str(self.odps_contract.id))

        # Verify delivery record was created with failure status
        delivery = EmailDelivery.objects.filter(
            email_type=EmailType.ODPS_CREATION_COMPLETION, to_email=self.user.email
        ).first()
        # The delivery record might be in DEFERRED status if retry is scheduled
        # or FAILED if max retries reached, depending on retry_count
        self.assertIsNotNone(delivery)
        self.assertIn(delivery.status, [EmailDeliveryStatus.DEFERRED, EmailDeliveryStatus.FAILED])

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
