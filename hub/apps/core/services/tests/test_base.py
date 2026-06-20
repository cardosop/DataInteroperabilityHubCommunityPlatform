"""
Unit tests for BaseService

Comprehensive tests covering:
- Error handling and exception types
- Logging functionality
- Metrics recording
- Transaction management
- Tenant validation
- Resource retrieval
- Field validation
- Operation execution with metrics

Target: 100% coverage
"""

import uuid
from unittest import mock
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.services.base import (
    BaseService,
    ConflictError,
    NotFoundError,
    PermissionError,
    ServiceError,
    ValidationError,
)
from hub.apps.tenants.models import Tenant


def _uid():
    return uuid.uuid4().hex[:8]


class SampleService(BaseService):
    """Test service implementation for testing BaseService functionality."""

    service_name = "test_service"

    def test_operation(self, value: str) -> str:
        """Test operation that returns a value."""
        return self.execute_with_metrics(
            operation="test_operation", func=lambda: f"result: {value}"
        )

    def test_operation_with_error(self, error_message: str):
        """Test operation that raises an error."""

        def _raise_error():
            raise ValueError(error_message)

        return self.execute_with_metrics(operation="test_operation_with_error", func=_raise_error)

    def test_operation_with_transaction(self, value: str) -> str:
        """Test operation with transaction."""

        def _create_asset():
            tenant = Tenant.objects.get(id=self.tenant_id)
            return Asset.objects.create(
                tenant=tenant,
                key=f"test-{value}-{uuid.uuid4().hex[:6]}",
                name=f"Test Asset {value}",
                status=AssetStatus.ACTIVE,
            )

        return self.execute_with_transaction(
            operation="test_operation_with_transaction", func=_create_asset
        )


class ServiceErrorTest(TestCase):
    """Test ServiceError and its subclasses."""

    def test_service_error_basic(self):
        """Test basic ServiceError creation."""
        error = ServiceError("Test error", code="TEST_ERROR")
        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.code, "TEST_ERROR")
        self.assertEqual(error.http_status, 500)
        self.assertEqual(error.details, {})

    def test_service_error_with_details(self):
        """Test ServiceError with details."""
        details = {"field": "value"}
        error = ServiceError("Test error", details=details)
        self.assertEqual(error.details, details)

    def test_validation_error(self):
        """Test ValidationError."""
        error = ValidationError("Invalid input", details={"field": "email"})
        self.assertEqual(error.code, "VALIDATION_ERROR")
        self.assertEqual(error.http_status, 400)
        self.assertEqual(error.details, {"field": "email"})

    def test_not_found_error(self):
        """Test NotFoundError."""
        error = NotFoundError("Resource", "123")
        self.assertEqual(error.code, "NOT_FOUND")
        self.assertEqual(error.http_status, 404)
        self.assertEqual(error.details["resource_type"], "Resource")
        self.assertEqual(error.details["resource_id"], "123")

    def test_permission_error(self):
        """Test PermissionError."""
        error = PermissionError("Access denied")
        self.assertEqual(error.code, "PERMISSION_DENIED")
        self.assertEqual(error.http_status, 403)

    def test_conflict_error(self):
        """Test ConflictError."""
        error = ConflictError("Resource conflict")
        self.assertEqual(error.code, "CONFLICT_ERROR")
        self.assertEqual(error.http_status, 409)


class BaseServiceInitializationTest(TestCase):
    """Test BaseService initialization."""

    def test_init_with_all_params(self):
        """Test initialization with all parameters."""
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        service = SampleService(tenant_id=tenant_id, user_id=user_id, request_id=request_id)

        self.assertEqual(service.tenant_id, tenant_id)
        self.assertEqual(service.user_id, user_id)
        self.assertEqual(service.request_id, request_id)
        self.assertEqual(service.service_name, "test_service")

    def test_init_without_params(self):
        """Test initialization without parameters."""
        service = SampleService()
        self.assertIsNone(service.tenant_id)
        self.assertIsNone(service.user_id)
        self.assertIsNotNone(service.request_id)  # Should generate UUID

    def test_get_context(self):
        """Test get_context method."""
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        service = SampleService(tenant_id=tenant_id, user_id=user_id, request_id=request_id)

        context = service._get_context()
        self.assertEqual(context["tenant_id"], tenant_id)
        self.assertEqual(context["user_id"], user_id)
        self.assertEqual(context["request_id"], request_id)
        self.assertEqual(context["service"], "test_service")


class BaseServiceLoggingTest(TestCase):
    """Test BaseService logging functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.service = SampleService(tenant_id=str(self.tenant.id))

    def test_log_operation_start(self):
        """Test logging operation start - verify no exceptions raised and logger is configured."""
        # Verify logger is properly configured
        self.assertIsNotNone(self.service._logger)

        # Verify logging method executes without error
        # The actual logging is verified through integration tests where log output is visible
        try:
            self.service._log_operation_start("test_operation", key="value")
        except Exception as e:
            self.fail(f"_log_operation_start raised {type(e).__name__}: {e}")

    def test_log_operation_success(self):
        """Test logging operation success - verify no exceptions raised and logger is configured."""
        # Verify logger is properly configured
        self.assertIsNotNone(self.service._logger)

        # Verify logging method executes without error
        # The actual logging is verified through integration tests where log output is visible
        try:
            self.service._log_operation_success("test_operation", 123.45, key="value")
        except Exception as e:
            self.fail(f"_log_operation_success raised {type(e).__name__}: {e}")

    def test_log_operation_error(self):
        """Test logging operation error - verify no exceptions raised and logger is configured."""
        # Verify logger is properly configured
        self.assertIsNotNone(self.service._logger)

        # Verify logging method executes without error
        # The actual logging is verified through integration tests where log output is visible
        error = ValueError("Test error")
        try:
            self.service._log_operation_error("test_operation", error, 123.45, key="value")
        except Exception as e:
            self.fail(f"_log_operation_error raised {type(e).__name__}: {e}")

    def test_logger_initialization(self):
        """Test that logger is properly initialized with service context."""
        tenant_id = str(self.tenant.id)
        user_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        service = SampleService(tenant_id=tenant_id, user_id=user_id, request_id=request_id)

        # Verify logger is initialized
        self.assertIsNotNone(service._logger)

        # Verify context is set correctly (verified through get_context method)
        context = service._get_context()
        self.assertEqual(context["service"], "test_service")
        self.assertEqual(context["tenant_id"], tenant_id)
        self.assertEqual(context["user_id"], user_id)
        self.assertEqual(context["request_id"], request_id)


class BaseServiceMetricsTest(TestCase):
    """Test BaseService metrics functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.service = SampleService(tenant_id=str(self.tenant.id))

    @patch("hub.apps.core.services.base.service_operations_total")
    @patch("hub.apps.core.services.base.service_operation_duration_seconds")
    @patch("hub.apps.core.services.base.service_operation_errors_total")
    def test_record_metrics_success(self, mock_errors, mock_duration, mock_operations):
        """Test recording metrics for successful operation."""
        self.service._record_metrics("test_operation", 0.5, success=True)

        # Check operation count
        mock_operations.labels.assert_called_once_with(
            service="test_service", operation="test_operation", tenant_id=str(self.tenant.id)
        )
        mock_operations.labels.return_value.inc.assert_called_once()

        # Check duration
        mock_duration.labels.assert_called_once_with(
            service="test_service", operation="test_operation", tenant_id=str(self.tenant.id)
        )
        mock_duration.labels.return_value.observe.assert_called_once_with(0.5)

        # Errors should not be recorded
        mock_errors.labels.assert_not_called()

    @patch("hub.apps.core.services.base.service_operations_total")
    @patch("hub.apps.core.services.base.service_operation_duration_seconds")
    @patch("hub.apps.core.services.base.service_operation_errors_total")
    def test_record_metrics_error(self, mock_errors, mock_duration, mock_operations):
        """Test recording metrics for failed operation."""
        self.service._record_metrics("test_operation", 0.5, success=False, error_code="TEST_ERROR")

        # Check error count
        mock_errors.labels.assert_called_once_with(
            service="test_service",
            operation="test_operation",
            error_code="TEST_ERROR",
            tenant_id=str(self.tenant.id),
        )
        mock_errors.labels.return_value.inc.assert_called_once()


class BaseServiceExecuteWithMetricsTest(TestCase):
    """Test execute_with_metrics functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.service = SampleService(tenant_id=str(self.tenant.id))

    @patch("hub.apps.core.services.base.BaseService._record_metrics")
    @patch("hub.apps.core.services.base.BaseService._log_operation_start")
    @patch("hub.apps.core.services.base.BaseService._log_operation_success")
    def test_execute_with_metrics_success(self, mock_log_success, mock_log_start, mock_record):
        """Test execute_with_metrics with successful operation."""
        result = self.service.test_operation("test_value")

        self.assertEqual(result, "result: test_value")
        mock_log_start.assert_called_once()
        mock_log_success.assert_called_once()
        mock_record.assert_called_once_with("test_operation", mock.ANY, success=True)

    @patch("hub.apps.core.services.base.BaseService._record_metrics")
    @patch("hub.apps.core.services.base.BaseService._log_operation_start")
    @patch("hub.apps.core.services.base.BaseService._log_operation_error")
    def test_execute_with_metrics_error(self, mock_log_error, mock_log_start, mock_record):
        """Test execute_with_metrics with error."""
        with self.assertRaises(ServiceError) as cm:
            self.service.test_operation_with_error("Test error")

        self.assertEqual(cm.exception.code, "INTERNAL_ERROR")
        mock_log_start.assert_called_once()
        mock_log_error.assert_called_once()
        mock_record.assert_called_once_with(
            "test_operation_with_error", mock.ANY, success=False, error_code="INTERNAL_ERROR"
        )

    @patch("hub.apps.core.services.base.BaseService._record_metrics")
    def test_execute_with_metrics_django_validation_error(self, mock_record):
        """Test execute_with_metrics with Django ValidationError."""

        def _raise_django_error():
            raise DjangoValidationError("Django validation error")

        with self.assertRaises(ValidationError) as cm:
            self.service.execute_with_metrics(operation="test_operation", func=_raise_django_error)

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        mock_record.assert_called_once_with(
            "test_operation", mock.ANY, success=False, error_code="VALIDATION_ERROR"
        )

    def test_execute_with_metrics_service_error_passthrough(self):
        """Test that ServiceError is passed through without transformation."""

        def _raise_service_error():
            raise ValidationError("Service validation error")

        with self.assertRaises(ValidationError) as cm:
            self.service.execute_with_metrics(operation="test_operation", func=_raise_service_error)

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertEqual(str(cm.exception), "Service validation error")

    def test_execute_with_metrics_tenant_override(self):
        """Test execute_with_metrics with tenant_id override."""
        _local_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_local_uid}",
            slug=f"other-tenant-{_local_uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        result = self.service.execute_with_metrics(
            operation="test_operation", func=lambda: "result", tenant_id=str(other_tenant.id)
        )

        self.assertEqual(result, "result")


class BaseServiceTransactionTest(TestCase):
    """Test BaseService transaction management."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.service = SampleService(tenant_id=str(self.tenant.id))

    def test_transaction_context_success(self):
        """Test transaction context with successful operation."""
        asset_key = f"ctx-ok-{_uid()}"
        with self.service.transaction_context():
            asset = Asset.objects.create(
                tenant=self.tenant, key=asset_key, name="Test Asset", status=AssetStatus.ACTIVE
            )
            self.assertIsNotNone(asset.id)

        # Asset should still exist after context
        self.assertTrue(Asset.objects.filter(id=asset.id).exists())

    def test_transaction_context_rollback(self):
        """Test transaction context with rollback on error."""
        asset_key = f"ctx-rb-{_uid()}"
        with self.assertRaises(ValueError), self.service.transaction_context():
            Asset.objects.create(
                tenant=self.tenant, key=asset_key, name="Test Asset", status=AssetStatus.ACTIVE
            )
            raise ValueError("Test error")

        # Asset should not exist after rollback
        self.assertFalse(Asset.objects.filter(key=asset_key).exists())

    def test_execute_with_transaction_success(self):
        """Test execute_with_transaction with successful operation."""
        result = self.service.test_operation_with_transaction("test")

        self.assertIsNotNone(result)
        self.assertTrue(result.key.startswith("test-test-"))
        self.assertTrue(Asset.objects.filter(id=result.id).exists())

    def test_execute_with_transaction_rollback(self):
        """Test execute_with_transaction with rollback."""
        asset_key = f"ewt-rb-{_uid()}"

        def _create_and_fail():
            Asset.objects.create(
                tenant=self.tenant, key=asset_key, name="Test Asset", status=AssetStatus.ACTIVE
            )
            raise ValueError("Test error")

        with self.assertRaises(ServiceError):
            self.service.execute_with_transaction(operation="test_operation", func=_create_and_fail)

        # Asset should not exist after rollback
        self.assertFalse(Asset.objects.filter(key=asset_key).exists())


class BaseServiceTenantValidationTest(TestCase):
    """Test BaseService tenant validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SampleService()

    def test_validate_tenant_success(self):
        """Test validate_tenant with active tenant."""
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        # Should not raise
        self.service.validate_tenant(str(tenant.id))

    def test_validate_tenant_not_found(self):
        """Test validate_tenant with non-existent tenant."""
        with self.assertRaises(NotFoundError) as cm:
            self.service.validate_tenant(str(uuid.uuid4()))

        self.assertEqual(cm.exception.code, "NOT_FOUND")

    def test_validate_tenant_inactive(self):
        """Test validate_tenant with inactive tenant."""
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="SUSPENDED",
            kyc_status="VERIFIED",
        )

        with self.assertRaises(PermissionError) as cm:
            self.service.validate_tenant(str(tenant.id))

        self.assertEqual(cm.exception.code, "PERMISSION_DENIED")

    def test_get_tenant_or_raise_success(self):
        """Test get_tenant_or_raise with existing tenant."""
        tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        result = self.service.get_tenant_or_raise(str(tenant.id))
        self.assertEqual(result.id, tenant.id)

    def test_get_tenant_or_raise_not_found(self):
        """Test get_tenant_or_raise with non-existent tenant."""
        with self.assertRaises(NotFoundError):
            self.service.get_tenant_or_raise(str(uuid.uuid4()))


class BaseServiceResourceRetrievalTest(TestCase):
    """Test BaseService resource retrieval."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {_uid()}",
            slug=f"test-tenant-{_uid()}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.service = SampleService(tenant_id=str(self.tenant.id))
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

    def test_get_resource_or_raise_success(self):
        """Test get_resource_or_raise with existing resource."""
        result = self.service.get_resource_or_raise(
            Asset, str(self.asset.id), resource_type="Asset"
        )
        self.assertEqual(result.id, self.asset.id)

    def test_get_resource_or_raise_not_found(self):
        """Test get_resource_or_raise with non-existent resource."""
        with self.assertRaises(NotFoundError) as cm:
            self.service.get_resource_or_raise(Asset, str(uuid.uuid4()), resource_type="Asset")

        self.assertEqual(cm.exception.code, "NOT_FOUND")
        self.assertEqual(cm.exception.details["resource_type"], "Asset")

    def test_get_resource_or_raise_with_filters(self):
        """Test get_resource_or_raise with additional filters."""
        result = self.service.get_resource_or_raise(
            Asset, str(self.asset.id), resource_type="Asset", status=AssetStatus.ACTIVE
        )
        self.assertEqual(result.id, self.asset.id)

    def test_get_resource_or_raise_with_wrong_filter(self):
        """Test get_resource_or_raise with filter that doesn't match."""
        with self.assertRaises(NotFoundError):
            self.service.get_resource_or_raise(
                Asset,
                str(self.asset.id),
                resource_type="Asset",
                status=AssetStatus.DRAFT,  # Wrong status
            )

    def test_get_resource_or_raise_tenant_isolation(self):
        """Test get_resource_or_raise enforces tenant isolation."""
        _local_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_local_uid}",
            slug=f"other-tenant-{_local_uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        # Should not find asset from other tenant
        with self.assertRaises(NotFoundError):
            self.service.get_resource_or_raise(Asset, str(other_asset.id), resource_type="Asset")

    def test_get_resource_or_raise_with_tenant_override(self):
        """Test get_resource_or_raise with tenant_id override."""
        _local_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_local_uid}",
            slug=f"other-tenant-{_local_uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        # Should find asset when tenant_id is explicitly provided
        result = self.service.get_resource_or_raise(
            Asset, str(other_asset.id), resource_type="Asset", tenant_id=str(other_tenant.id)
        )
        self.assertEqual(result.id, other_asset.id)


class BaseServiceFieldValidationTest(TestCase):
    """Test BaseService field validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SampleService()

    def test_validate_required_fields_success(self):
        """Test validate_required_fields with all fields present."""
        data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        required_fields = ["field1", "field2"]

        # Should not raise
        self.service.validate_required_fields(data, required_fields)

    def test_validate_required_fields_missing(self):
        """Test validate_required_fields with missing fields."""
        data = {"field1": "value1"}
        required_fields = ["field1", "field2", "field3"]

        with self.assertRaises(ValidationError) as cm:
            self.service.validate_required_fields(data, required_fields)

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("field2", cm.exception.details["missing_fields"])
        self.assertIn("field3", cm.exception.details["missing_fields"])

    def test_validate_required_fields_none_value(self):
        """Test validate_required_fields treats None as missing."""
        data = {"field1": "value1", "field2": None}
        required_fields = ["field1", "field2"]

        with self.assertRaises(ValidationError) as cm:
            self.service.validate_required_fields(data, required_fields)

        self.assertIn("field2", cm.exception.details["missing_fields"])
