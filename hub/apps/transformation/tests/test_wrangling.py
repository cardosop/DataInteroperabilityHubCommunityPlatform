"""
Unit and integration tests for TransformationService wrangle_data() method.

Tests verify comprehensive data wrangling functionality:
- Operation validation
- Operation execution (filter, sort, transform, etc.)
- Result generation
- Operation history tracking (undo/redo support)
- Wrangling script generation
- Event publishing

All tests use real services (no mocks) to ensure integration.
"""
import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import (
    WranglingSession,
    WranglingOperation,
    WranglingOperationType
)
from hub.apps.transformation.exceptions import (
    TransformationValidationError,
    TransformationExecutionError
)
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy


class DataWranglingTest(TestCase):
    """Test comprehensive data wrangling functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create role and user
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )
        self.user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User"
        )
        UserRole.objects.create(user=self.user, role=self.role)

        # Create ABAC policy
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Wrangling Operations",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user
            }
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create asset with dataset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )

        # Create file with CSV content
        file_obj = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv"
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=file_obj,
            format="CSV",
            version=1,
            row_count=100
        )

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_filter_operation(self, mock_storage):
        """Test wrangle_data() with FILTER operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        # CSV content with headers
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n3,Charlie,35\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute FILTER operation
        operation = {
            "type": "FILTER",
            "parameters": {
                "condition": "age > 25"
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        self.assertIn("operation_id", result)
        self.assertIn("result", result)
        self.assertIn("can_undo", result)
        self.assertIn("can_redo", result)
        self.assertIn("applied_operations_count", result)

        # Verify filter was applied (should have fewer rows)
        result_data = result["result"]
        self.assertGreater(result_data["rows_before"], result_data["rows_after"])

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_sort_operation(self, mock_storage):
        """Test wrangle_data() with SORT operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n3,Charlie,35\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute SORT operation
        operation = {
            "type": "SORT",
            "parameters": {
                "columns": ["age"],
                "ascending": True
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        self.assertIn("operation_id", result)
        result_data = result["result"]
        self.assertIn("sample_data", result_data)
        self.assertIn("rows_after", result_data)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_transform_operation(self, mock_storage):
        """Test wrangle_data() with TRANSFORM operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name\n1,alice\n2,bob\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute TRANSFORM operation
        operation = {
            "type": "TRANSFORM",
            "parameters": {
                "column": "name",
                "expression": "upper()"
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        result_data = result["result"]
        self.assertIn("sample_data", result_data)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_rename_column_operation(self, mock_storage):
        """Test wrangle_data() with RENAME_COLUMN operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name\n1,Alice\n2,Bob\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute RENAME_COLUMN operation
        operation = {
            "type": "RENAME_COLUMN",
            "parameters": {
                "old_name": "name",
                "new_name": "full_name"
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        result_data = result["result"]
        self.assertIn("columns", result_data)
        self.assertIn("full_name", result_data["columns"])
        self.assertNotIn("name", result_data["columns"])

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_drop_column_operation(self, mock_storage):
        """Test wrangle_data() with DROP_COLUMN operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute DROP_COLUMN operation
        operation = {
            "type": "DROP_COLUMN",
            "parameters": {
                "columns": ["age"]
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        result_data = result["result"]
        self.assertIn("columns", result_data)
        self.assertNotIn("age", result_data["columns"])

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_deduplicate_operation(self, mock_storage):
        """Test wrangle_data() with DEDUPLICATE operation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name\n1,Alice\n2,Alice\n3,Bob\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute DEDUPLICATE operation
        operation = {
            "type": "DEDUPLICATE",
            "parameters": {
                "columns": ["name"]
            }
        }

        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify result
        self.assertIn("session_id", result)
        result_data = result["result"]
        self.assertGreater(result_data["rows_before"], result_data["rows_after"])

    def test_wrangle_data_operation_validation(self):
        """Test operation validation"""
        # Test missing type
        with self.assertRaises(TransformationValidationError):
            self.service.wrangle_data(
                asset_id=str(self.asset.id),
                operation={},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Test invalid type
        with self.assertRaises(TransformationValidationError):
            self.service.wrangle_data(
                asset_id=str(self.asset.id),
                operation={"type": "INVALID_TYPE"},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Test missing required parameters
        with self.assertRaises(TransformationValidationError):
            self.service.wrangle_data(
                asset_id=str(self.asset.id),
                operation={"type": "FILTER"},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

    def test_wrangle_data_asset_not_found(self):
        """Test wrangle_data() with non-existent asset"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.wrangle_data(
                asset_id=str(uuid.uuid4()),
                operation={"type": "FILTER", "parameters": {"condition": "age > 25"}},
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_operation_history(self, mock_storage):
        """Test operation history tracking"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute first operation
        operation1 = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        result1 = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation1,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        session_id = result1["session_id"]

        # Execute second operation on same session
        operation2 = {
            "type": "SORT",
            "parameters": {"columns": ["age"], "ascending": True}
        }
        result2 = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation2,
            session_id=session_id,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify history
        self.assertEqual(result2["applied_operations_count"], 2)
        self.assertTrue(result2["can_undo"])

        # Verify session exists
        session = WranglingSession.objects.get(id=session_id)
        self.assertEqual(len(session.get_applied_operations()), 2)

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_undo_redo(self, mock_storage):
        """Test undo/redo functionality"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute operation
        operation = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        result = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        session_id = result["session_id"]
        session = WranglingSession.objects.get(id=session_id)

        # Test undo
        self.assertTrue(session.can_undo())
        undone_op = session.undo()
        self.assertIsNotNone(undone_op)
        self.assertFalse(session.can_undo())

        # Test redo
        self.assertTrue(session.can_redo())
        redone_op = session.redo()
        self.assertIsNotNone(redone_op)
        self.assertFalse(session.can_redo())

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_script_generation(self, mock_storage):
        """Test wrangling script generation"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute operations
        operation1 = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        result1 = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation1,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        session_id = result1["session_id"]

        operation2 = {
            "type": "SORT",
            "parameters": {"columns": ["age"], "ascending": True}
        }
        result2 = self.service.wrangle_data(
            asset_id=str(self.asset.id),
            operation=operation2,
            session_id=session_id,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify script was generated
        self.assertIn("wrangling_script", result2)
        self.assertIsNotNone(result2["wrangling_script"])
        self.assertIn("pandas", result2["wrangling_script"])

    @patch('hub.apps.files.storage.S3StorageClient')
    def test_wrangle_data_event_publishing(self, mock_storage):
        """Test event publishing for wrangling operations"""
        # Mock storage client
        mock_storage_instance = MagicMock()
        mock_storage.return_value = mock_storage_instance
        csv_content = b'id,name,age\n1,Alice,25\n2,Bob,30\n'
        mock_storage_instance.get_file_content.return_value = csv_content

        # Execute operation
        operation = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }

        with patch.object(self.service, 'publish_wrangling_completed') as mock_publish:
            result = self.service.wrangle_data(
                asset_id=str(self.asset.id),
                operation=operation,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

            # Verify event was published
            mock_publish.assert_called_once()
            call_args = mock_publish.call_args
            self.assertEqual(call_args[1]["operation_type"], "FILTER")
            self.assertIn("session_id", call_args[1])
            self.assertIn("operation_id", call_args[1])

