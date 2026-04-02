"""
Unit Tests for AWS Data Exchange Connector

Tests the AWSDataExchangeConnector implementation including:
- Connector initialization
- Authentication (access keys and IAM role assumption)
- Connection testing
- Client management (Data Exchange and S3)
- Discovery operations (list_listings, get_listing, list_resources)
- Circuit breaker integration
- Error handling
"""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from botocore.exceptions import BotoCoreError, ClientError
from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.core.services.base import ConnectionError, NotFoundError, PermissionError
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.connectors.aws_data_exchange_connector import AWSDataExchangeConnector

import pytest

pytestmark = [pytest.mark.django_db]


class TestAWSDataExchangeConnectorInitialization(TestCase):
    """Test AWS Data Exchange connector initialization"""

    def test_init_with_access_keys(self):
        """Test connector initialization with access keys"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id",
            aws_secret_access_key="test-secret-key",
            region_name="us-west-2",
        )
        self.assertEqual(connector._aws_access_key_id, "test-key-id")
        self.assertEqual(connector._aws_secret_access_key, "test-secret-key")
        self.assertEqual(connector._region_name, "us-west-2")
        self.assertIsNone(connector._role_arn)
        self.assertFalse(connector._authenticated)

    def test_init_with_role_arn(self):
        """Test connector initialization with IAM role ARN"""
        connector = AWSDataExchangeConnector(
            role_arn="arn:aws:iam::123456789012:role/DataExchangeRole", region_name="eu-west-1"
        )
        self.assertEqual(connector._role_arn, "arn:aws:iam::123456789012:role/DataExchangeRole")
        self.assertEqual(connector._region_name, "eu-west-1")
        self.assertIsNone(connector._aws_access_key_id)
        self.assertIsNone(connector._aws_secret_access_key)

    def test_init_with_session_token(self):
        """Test connector initialization with session token"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id",
            aws_secret_access_key="test-secret-key",
            aws_session_token="test-session-token",
            region_name="ap-southeast-1",
        )
        self.assertEqual(connector._aws_session_token, "test-session-token")

    def test_init_default_region(self):
        """Test connector uses default region (us-east-1)"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        self.assertEqual(connector._region_name, "us-east-1")

    def test_marketplace_type_property(self):
        """Test marketplace_type property returns correct value"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        self.assertEqual(connector.marketplace_type, MarketplaceType.AWS_DATA_EXCHANGE)

    def test_supported_sync_directions_property(self):
        """Test supported_sync_directions property returns PULL only"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        directions = connector.supported_sync_directions
        self.assertEqual(len(directions), 1)
        self.assertIn(SyncDirection.PULL, directions)
        self.assertNotIn(SyncDirection.PUSH, directions)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, directions)

    def test_circuit_breaker_initialized(self):
        """Test circuit breaker is initialized"""
        connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        self.assertIsNotNone(connector._circuit_breaker)
        self.assertEqual(connector._circuit_breaker.service_name, "aws-data-exchange-connector")
        self.assertEqual(connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(connector._circuit_breaker.success_threshold, 2)


class TestAWSDataExchangeConnectorAuthentication(TestCase):
    """Test AWS Data Exchange connector authentication"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_success_with_access_keys(self, mock_test_connection):
        """Test successful authentication with access keys"""
        mock_test_connection.return_value = True

        credentials = {
            "aws_access_key_id": "new-key-id",
            "aws_secret_access_key": "new-secret-key",
            "region_name": "us-west-2",
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertTrue(self.connector._authenticated)
        self.assertEqual(self.connector._aws_access_key_id, "new-key-id")
        self.assertEqual(self.connector._aws_secret_access_key, "new-secret-key")
        self.assertEqual(self.connector._region_name, "us-west-2")
        mock_test_connection.assert_called_once()

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_with_alternative_key_names(self, mock_test_connection):
        """Test authentication accepts alternative credential key names"""
        mock_test_connection.return_value = True

        credentials = {
            "access_key_id": "alt-key-id",
            "secret_access_key": "alt-secret-key",
            "region_name": "eu-central-1",
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector._aws_access_key_id, "alt-key-id")
        self.assertEqual(self.connector._aws_secret_access_key, "alt-secret-key")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_with_session_token(self, mock_test_connection):
        """Test authentication with session token"""
        mock_test_connection.return_value = True

        credentials = {
            "aws_access_key_id": "key-id",
            "aws_secret_access_key": "secret-key",
            "aws_session_token": "session-token",
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(self.connector._aws_session_token, "session-token")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_with_role_arn(self, mock_test_connection):
        """Test authentication with IAM role ARN"""
        mock_test_connection.return_value = True

        credentials = {
            "role_arn": "arn:aws:iam::123456789012:role/DataExchangeRole",
            "region_name": "us-east-1",
        }
        result = self.connector.authenticate(credentials)

        self.assertTrue(result)
        self.assertEqual(
            self.connector._role_arn, "arn:aws:iam::123456789012:role/DataExchangeRole"
        )

    def test_authenticate_missing_credentials(self):
        """Test authentication raises error if credentials missing"""
        # Test with empty dict - should raise error about missing credentials
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate({})
        error_msg = str(cm.exception).lower()
        # Should mention either credentials required OR role_arn/access keys
        self.assertTrue(
            "credentials dictionary is required" in error_msg
            or ("role_arn" in error_msg and "aws_access_key_id" in error_msg),
            f"Expected error about credentials, got: {error_msg}",
        )

    def test_authenticate_empty_credentials(self):
        """Test authentication raises error if credentials dictionary is empty"""
        # None should raise TypeError (wrong type), empty dict should raise ValueError
        with self.assertRaises((ValueError, TypeError)) as cm:
            self.connector.authenticate(None)
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "required" in error_msg or "none" in error_msg,
            f"Expected error about credentials being required, got: {error_msg}",
        )

    def test_authenticate_missing_access_key(self):
        """Test authentication raises error if access key missing"""
        credentials = {"aws_secret_access_key": "secret-key"}
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn("aws_access_key_id", str(cm.exception).lower())

    def test_authenticate_missing_secret_key(self):
        """Test authentication raises error if secret key missing"""
        credentials = {"aws_access_key_id": "key-id"}
        with self.assertRaises(ValueError) as cm:
            self.connector.authenticate(credentials)
        self.assertIn("aws_secret_access_key", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_connection_error(self, mock_test_connection):
        """Test authentication raises ConnectionError on failure"""
        mock_test_connection.side_effect = ConnectionError("Connection failed")

        credentials = {"aws_access_key_id": "key-id", "aws_secret_access_key": "secret-key"}
        with self.assertRaises(ConnectionError):
            self.connector.authenticate(credentials)
        self.assertFalse(self.connector._authenticated)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.test_connection"
    )
    def test_authenticate_resets_clients(self, mock_test_connection):
        """Test authentication resets client instances"""
        mock_test_connection.return_value = True

        # Create clients first
        self.connector._dataexchange_client = Mock()
        self.connector._s3_client = Mock()
        self.connector._assumed_role_credentials = {"test": "data"}

        credentials = {"aws_access_key_id": "new-key-id", "aws_secret_access_key": "new-secret-key"}
        self.connector.authenticate(credentials)

        # Clients should be reset
        self.assertIsNone(self.connector._dataexchange_client)
        self.assertIsNone(self.connector._s3_client)
        self.assertIsNone(self.connector._assumed_role_credentials)


class TestAWSDataExchangeConnectorConnectionTest(TestCase):
    """Test AWS Data Exchange connector connection testing"""

    def setUp(self):
        """Set up test fixtures and reset shared circuit breaker for deterministic tests."""
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_success(self, mock_boto3):
        """Test successful connection test"""
        # Mock boto3 client
        mock_client = Mock()
        mock_client.list_data_sets.return_value = {"DataSets": []}
        mock_boto3.client.return_value = mock_client

        result = self.connector.test_connection()

        self.assertTrue(result)
        mock_client.list_data_sets.assert_called_once_with(MaxResults=1)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_access_denied(self, mock_boto3):
        """Test connection test raises PermissionError on AccessDeniedException"""
        # Mock boto3 client
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "User is not authorized to perform: dataexchange:ListDataSets",
            }
        }
        mock_client.list_data_sets.side_effect = ClientError(error_response, "ListDataSets")
        mock_boto3.client.return_value = mock_client

        with self.assertRaises(PermissionError) as cm:
            self.connector.test_connection()
        self.assertIn("Access denied", str(cm.exception))

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_other_client_error(self, mock_boto3):
        """Test connection test raises ConnectionError on other ClientError"""
        # Mock boto3 client
        mock_client = Mock()
        error_response = {
            "Error": {"Code": "InvalidRequestException", "Message": "Invalid request"}
        }
        mock_client.list_data_sets.side_effect = ClientError(error_response, "ListDataSets")
        mock_boto3.client.return_value = mock_client

        with self.assertRaises(ConnectionError) as cm:
            self.connector.test_connection()
        # Error message should contain either 'Unable to connect', 'AWS', or 'connection'
        error_msg = str(cm.exception)
        self.assertTrue(
            "Unable to connect" in error_msg
            or "AWS" in error_msg
            or "connection" in error_msg.lower(),
            f"Error message '{error_msg}' does not contain expected text",
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_boto_core_error(self, mock_boto3):
        """Test connection test raises ConnectionError on BotoCoreError"""
        mock_boto3.client.side_effect = BotoCoreError()

        with self.assertRaises(ConnectionError) as cm:
            self.connector.test_connection()
        error_msg = str(cm.exception)
        # Error message should mention connection failure or AWS Data Exchange
        self.assertTrue(
            "Unable to connect" in error_msg
            or "AWS Data Exchange" in error_msg
            or "connection" in error_msg.lower(),
            f"Expected connection error message, got: {error_msg}",
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_unexpected_error(self, mock_boto3):
        """Test connection test raises ConnectionError on unexpected error"""
        mock_boto3.client.side_effect = Exception("Unexpected error")

        with self.assertRaises(ConnectionError) as cm:
            self.connector.test_connection()
        self.assertIn("Unexpected error", str(cm.exception))

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_test_connection_uses_circuit_breaker(self, mock_boto3):
        """Test connection test uses circuit breaker"""
        mock_client = Mock()
        mock_client.list_data_sets.return_value = {"DataSets": []}
        mock_boto3.client.return_value = mock_client

        # Mock circuit breaker call
        with patch.object(self.connector._circuit_breaker, "call") as mock_cb_call:
            mock_cb_call.return_value = True
            result = self.connector.test_connection()

            self.assertTrue(result)
            mock_cb_call.assert_called_once()


class TestAWSDataExchangeConnectorClientManagement(TestCase):
    """Test AWS Data Exchange connector client management"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id",
            aws_secret_access_key="test-secret-key",
            region_name="us-west-2",
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_creates_client(self, mock_boto3):
        """Test _get_dataexchange_client creates boto3 client"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        client = self.connector._get_dataexchange_client()

        self.assertEqual(client, mock_client)
        mock_boto3.client.assert_called_once_with(
            "dataexchange",
            region_name="us-west-2",
            aws_access_key_id="test-key-id",
            aws_secret_access_key="test-secret-key",
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_caches_client(self, mock_boto3):
        """Test _get_dataexchange_client caches client instance"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        client1 = self.connector._get_dataexchange_client()
        client2 = self.connector._get_dataexchange_client()

        self.assertEqual(client1, client2)
        # Should only create client once
        self.assertEqual(mock_boto3.client.call_count, 1)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_with_session_token(self, mock_boto3):
        """Test _get_dataexchange_client includes session token if provided"""
        self.connector._aws_session_token = "session-token"
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        self.connector._get_dataexchange_client()

        mock_boto3.client.assert_called_once_with(
            "dataexchange",
            region_name="us-west-2",
            aws_access_key_id="test-key-id",
            aws_secret_access_key="test-secret-key",
            aws_session_token="session-token",
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_missing_credentials(self, mock_boto3):
        """Test _get_dataexchange_client raises ValueError if credentials missing"""
        self.connector._aws_access_key_id = None
        self.connector._aws_secret_access_key = None
        self.connector._role_arn = None

        with self.assertRaises(ValueError) as cm:
            self.connector._get_dataexchange_client()
        self.assertIn("role_arn", str(cm.exception).lower())
        self.assertIn("aws_access_key_id", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_with_role_assumption(self, mock_boto3):
        """Test _get_dataexchange_client handles IAM role assumption"""
        self.connector._role_arn = "arn:aws:iam::123456789012:role/DataExchangeRole"
        self.connector._aws_access_key_id = "base-key-id"
        self.connector._aws_secret_access_key = "base-secret-key"

        # Mock STS client and assume_role response
        mock_sts_client = Mock()
        mock_sts_client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "assumed-key-id",
                "SecretAccessKey": "assumed-secret-key",
                "SessionToken": "assumed-session-token",
            }
        }

        mock_dataexchange_client = Mock()

        def client_side_effect(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts_client
            elif service_name == "dataexchange":
                return mock_dataexchange_client
            return Mock()

        mock_boto3.client.side_effect = client_side_effect

        client = self.connector._get_dataexchange_client()

        self.assertEqual(client, mock_dataexchange_client)
        # Verify assume_role was called
        mock_sts_client.assume_role.assert_called_once_with(
            RoleArn="arn:aws:iam::123456789012:role/DataExchangeRole",
            RoleSessionName="data-exchange-connector-session",
        )
        # Verify Data Exchange client created with assumed role credentials
        self.assertEqual(len(mock_boto3.client.call_args_list), 2)  # STS + DataExchange
        dataexchange_call = mock_boto3.client.call_args_list[1]
        self.assertEqual(dataexchange_call[0][0], "dataexchange")
        self.assertEqual(dataexchange_call[1]["aws_access_key_id"], "assumed-key-id")
        self.assertEqual(dataexchange_call[1]["aws_secret_access_key"], "assumed-secret-key")
        self.assertEqual(dataexchange_call[1]["aws_session_token"], "assumed-session-token")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataexchange_client_role_assumption_access_denied(self, mock_boto3):
        """Test _get_dataexchange_client raises PermissionError on role assumption AccessDenied"""
        self.connector._role_arn = "arn:aws:iam::123456789012:role/DataExchangeRole"

        # Mock STS client with AccessDenied error
        mock_sts_client = Mock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        mock_sts_client.assume_role.side_effect = ClientError(error_response, "AssumeRole")

        def client_side_effect(service_name, **kwargs):
            if service_name == "sts":
                return mock_sts_client
            return Mock()

        mock_boto3.client.side_effect = client_side_effect

        with self.assertRaises(PermissionError) as cm:
            self.connector._get_dataexchange_client()
        self.assertIn("Access denied", str(cm.exception))

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_s3_client_creates_client(self, mock_boto3):
        """Test _get_s3_client creates boto3 S3 client"""
        # Mock Data Exchange client creation first
        mock_dataexchange_client = Mock()
        mock_s3_client = Mock()

        def client_side_effect(service_name, **kwargs):
            if service_name == "dataexchange":
                return mock_dataexchange_client
            elif service_name == "s3":
                return mock_s3_client
            return Mock()

        mock_boto3.client.side_effect = client_side_effect

        client = self.connector._get_s3_client()

        self.assertEqual(client, mock_s3_client)
        # Should create both Data Exchange and S3 clients
        self.assertEqual(mock_boto3.client.call_count, 2)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_s3_client_caches_client(self, mock_boto3):
        """Test _get_s3_client caches client instance"""
        mock_dataexchange_client = Mock()
        mock_s3_client = Mock()

        def client_side_effect(service_name, **kwargs):
            if service_name == "dataexchange":
                return mock_dataexchange_client
            elif service_name == "s3":
                return mock_s3_client
            return Mock()

        mock_boto3.client.side_effect = client_side_effect

        client1 = self.connector._get_s3_client()
        client2 = self.connector._get_s3_client()

        self.assertEqual(client1, client2)
        # Should only create clients once (DataExchange + S3)
        self.assertEqual(mock_boto3.client.call_count, 2)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_s3_client_uses_assumed_role_credentials(self, mock_boto3):
        """Test _get_s3_client uses assumed role credentials if available"""
        # Set up assumed role credentials
        self.connector._assumed_role_credentials = {
            "aws_access_key_id": "assumed-key-id",
            "aws_secret_access_key": "assumed-secret-key",
            "aws_session_token": "assumed-session-token",
        }

        mock_dataexchange_client = Mock()
        mock_s3_client = Mock()

        def client_side_effect(service_name, **kwargs):
            if service_name == "dataexchange":
                return mock_dataexchange_client
            elif service_name == "s3":
                return mock_s3_client
            return Mock()

        mock_boto3.client.side_effect = client_side_effect

        self.connector._get_s3_client()

        # Find S3 client call
        s3_calls = [call for call in mock_boto3.client.call_args_list if call[0][0] == "s3"]
        self.assertEqual(len(s3_calls), 1)
        s3_call = s3_calls[0]
        self.assertEqual(s3_call[1]["aws_access_key_id"], "assumed-key-id")
        self.assertEqual(s3_call[1]["aws_secret_access_key"], "assumed-secret-key")
        self.assertEqual(s3_call[1]["aws_session_token"], "assumed-session-token")


class TestAWSDataExchangeConnectorDiscoveryOperations(TestCase):
    """Test AWS Data Exchange connector discovery operations"""

    def setUp(self):
        """Set up test fixtures and reset shared circuit breaker for deterministic tests."""
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    def test_parse_aws_datetime_valid(self):
        """Test _parse_aws_datetime with valid ISO 8601 datetime"""
        dt_str = "2023-01-01T12:00:00Z"
        result = self.connector._parse_aws_datetime(dt_str)
        self.assertIsInstance(result, datetime)
        self.assertEqual(result.year, 2023)
        self.assertEqual(result.month, 1)
        self.assertEqual(result.day, 1)

    def test_parse_aws_datetime_with_timezone(self):
        """Test _parse_aws_datetime with timezone offset"""
        dt_str = "2023-01-01T12:00:00+00:00"
        result = self.connector._parse_aws_datetime(dt_str)
        self.assertIsInstance(result, datetime)

    def test_extract_tags_from_list_of_objects(self):
        """Test _extract_tags with list of tag objects"""
        tags_data = [{"Key": "tag1", "Value": "value1"}, {"Key": "tag2", "Value": "value2"}]
        result = self.connector._extract_tags(tags_data)
        self.assertEqual(len(result), 2)
        self.assertIn("tag1", result)
        self.assertIn("tag2", result)

    def test_extract_tags_from_list_of_strings(self):
        """Test _extract_tags with list of strings"""
        tags_data = ["tag1", "tag2", "tag3"]
        result = self.connector._extract_tags(tags_data)
        self.assertEqual(result, ["tag1", "tag2", "tag3"])

    def test_extract_tags_from_nested_dict(self):
        """Test _extract_tags with nested Tags dict"""
        tags_data = {"Tags": [{"Key": "tag1"}, {"Key": "tag2"}]}
        result = self.connector._extract_tags(tags_data)
        self.assertEqual(len(result), 2)

    def test_extract_tags_from_flat_dict(self):
        """Test _extract_tags with flat dict"""
        tags_data = {"tag1": "value1", "tag2": "value2"}
        result = self.connector._extract_tags(tags_data)
        self.assertEqual(len(result), 2)

    def test_extract_tags_from_comma_separated_string(self):
        """Test _extract_tags with comma-separated string"""
        tags_data = "tag1, tag2, tag3"
        result = self.connector._extract_tags(tags_data)
        self.assertEqual(len(result), 3)
        self.assertIn("tag1", result)
        self.assertIn("tag2", result)
        self.assertIn("tag3", result)

    def test_extract_tags_with_none(self):
        """Test _extract_tags with None"""
        result = self.connector._extract_tags(None)
        self.assertEqual(result, [])

    def test_extract_tags_with_empty_list(self):
        """Test _extract_tags with empty list"""
        result = self.connector._extract_tags([])
        self.assertEqual(result, [])

    def test_parse_aws_datetime_none(self):
        """Test _parse_aws_datetime with None"""
        result = self.connector._parse_aws_datetime(None)
        self.assertIsNone(result)

    def test_parse_aws_datetime_empty_string(self):
        """Test _parse_aws_datetime with empty string"""
        result = self.connector._parse_aws_datetime("")
        self.assertIsNone(result)

    def test_parse_aws_datetime_invalid(self):
        """Test _parse_aws_datetime with invalid format"""
        result = self.connector._parse_aws_datetime("invalid-date")
        self.assertIsNone(result)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataset_details_success(self, mock_boto3):
        """Test _get_dataset_details successfully retrieves dataset"""
        mock_client = Mock()
        mock_client.get_data_set.return_value = {
            "Id": "dataset-123",
            "Name": "Test Dataset",
            "Description": "Test Description",
            "AssetType": "S3_SNAPSHOT",
            "CreatedAt": "2023-01-01T12:00:00Z",
            "UpdatedAt": "2023-01-02T12:00:00Z",
        }
        mock_boto3.client.return_value = mock_client

        result = self.connector._get_dataset_details("dataset-123")

        self.assertEqual(result["Id"], "dataset-123")
        self.assertEqual(result["Name"], "Test Dataset")
        mock_client.get_data_set.assert_called_once_with(DataSetId="dataset-123")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_dataset_details_not_found(self, mock_boto3):
        """Test _get_dataset_details raises NotFoundError when dataset not found"""
        mock_client = Mock()
        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Dataset not found"}
        }
        mock_client.get_data_set.side_effect = ClientError(error_response, "GetDataSet")
        mock_boto3.client.return_value = mock_client

        with self.assertRaises(NotFoundError) as cm:
            self.connector._get_dataset_details("dataset-123")
        self.assertIn("not found", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_revisions_success(self, mock_boto3):
        """Test _list_revisions successfully lists revisions"""
        mock_client = Mock()
        mock_client.list_data_set_revisions.return_value = {
            "Revisions": [
                {"Id": "rev-1", "CreatedAt": "2023-01-01T12:00:00Z"},
                {"Id": "rev-2", "CreatedAt": "2023-01-02T12:00:00Z"},
            ]
        }
        mock_boto3.client.return_value = mock_client

        result = self.connector._list_revisions("dataset-123")

        self.assertEqual(len(result["Revisions"]), 2)
        mock_client.list_data_set_revisions.assert_called_once()

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_revisions_with_pagination(self, mock_boto3):
        """Test _list_revisions handles pagination"""
        mock_client = Mock()
        mock_client.list_data_set_revisions.return_value = {
            "Revisions": [{"Id": "rev-1"}],
            "NextToken": "next-token-123",
        }
        mock_boto3.client.return_value = mock_client

        result = self.connector._list_revisions(
            "dataset-123", max_results=1, next_token="token-123"
        )

        self.assertIn("Revisions", result)
        self.assertIn("NextToken", result)
        call_args = mock_client.list_data_set_revisions.call_args
        self.assertEqual(call_args[1]["NextToken"], "token-123")
        self.assertEqual(call_args[1]["MaxResults"], 1)

    def test_extract_odps_metadata(self):
        """Test _extract_odps_metadata extracts correct metadata"""
        dataset_data = {
            "Id": "dataset-123",
            "Name": "Test Dataset",
            "Description": "Test Description",
            "AssetType": "S3_SNAPSHOT",
        }
        revision_data = {"Id": "rev-1"}

        result = self.connector._extract_odps_metadata(dataset_data, revision_data)

        self.assertIn("product_details", result)
        self.assertEqual(result["product_details"]["productID"], "dataset-123")
        self.assertEqual(result["product_details"]["product_name"], "Test Dataset")
        self.assertIn("pricing_plans", result)
        self.assertIn("access_methods", result)
        self.assertIn("payment_gateways", result)

    def test_extract_odcs_metadata(self):
        """Test _extract_odcs_metadata extracts correct metadata"""
        dataset_data = {"Id": "dataset-123", "Name": "Test Dataset", "Origin": "OWNED"}
        revision_data = {"Id": "rev-1"}

        result = self.connector._extract_odcs_metadata(dataset_data, revision_data)

        self.assertIn("schema_hints", result)
        self.assertIn("quality_hints", result)
        self.assertIn("sla_hints", result)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_listings_success(self, mock_boto3, mock_get_details):
        """Test list_listings successfully lists datasets"""
        mock_client = Mock()
        mock_client.list_data_sets.return_value = {
            "DataSets": [
                {"Id": "dataset-1", "Name": "Dataset 1"},
                {"Id": "dataset-2", "Name": "Dataset 2"},
            ]
        }
        mock_boto3.client.return_value = mock_client

        mock_get_details.side_effect = [
            {
                "Id": "dataset-1",
                "Name": "Dataset 1",
                "Description": "Desc 1",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": "2023-01-01T12:00:00Z",
                "UpdatedAt": "2023-01-01T12:00:00Z",
            },
            {
                "Id": "dataset-2",
                "Name": "Dataset 2",
                "Description": "Desc 2",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": "2023-01-01T12:00:00Z",
                "UpdatedAt": "2023-01-01T12:00:00Z",
            },
        ]

        listings = self.connector.list_listings()

        self.assertEqual(len(listings), 2)
        self.assertIsInstance(listings[0], MarketplaceListing)
        self.assertEqual(listings[0].marketplace_id, "dataset-1")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_listings_with_filters(self, mock_boto3, mock_get_details):
        """Test list_listings applies filters correctly"""
        mock_client = Mock()
        mock_client.list_data_sets.return_value = {
            "DataSets": [{"Id": "dataset-1", "Name": "Dataset 1"}]
        }
        mock_boto3.client.return_value = mock_client

        mock_get_details.return_value = {
            "Id": "dataset-1",
            "Name": "Dataset 1",
            "Description": "Desc 1",
            "AssetType": "S3_SNAPSHOT",
            "CreatedAt": "2023-01-01T12:00:00Z",
            "UpdatedAt": "2023-01-01T12:00:00Z",
        }

        listings = self.connector.list_listings(filters={"origin": "OWNED", "name": "Dataset"})

        call_args = mock_client.list_data_sets.call_args
        self.assertEqual(call_args[1]["Origin"], "OWNED")
        self.assertEqual(call_args[1]["Name"], "Dataset")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_listings_with_limit(self, mock_boto3, mock_get_details):
        """Test list_listings respects limit parameter"""
        mock_client = Mock()
        mock_client.list_data_sets.return_value = {
            "DataSets": [
                {"Id": "dataset-1", "Name": "Dataset 1"},
                {"Id": "dataset-2", "Name": "Dataset 2"},
            ]
        }
        mock_boto3.client.return_value = mock_client

        mock_get_details.side_effect = [
            {
                "Id": "dataset-1",
                "Name": "Dataset 1",
                "Description": "Desc 1",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": "2023-01-01T12:00:00Z",
                "UpdatedAt": "2023-01-01T12:00:00Z",
            },
            {
                "Id": "dataset-2",
                "Name": "Dataset 2",
                "Description": "Desc 2",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": "2023-01-01T12:00:00Z",
                "UpdatedAt": "2023-01-01T12:00:00Z",
            },
        ]

        listings = self.connector.list_listings(limit=1)

        self.assertEqual(len(listings), 1)

    def test_list_listings_invalid_limit(self):
        """Test list_listings raises ValueError for invalid limit"""
        with self.assertRaises(ValueError):
            self.connector.list_listings(limit=-1)

        with self.assertRaises(ValueError):
            self.connector.list_listings(limit=101)  # Exceeds AWS max

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._list_revisions"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_listing_success(self, mock_boto3, mock_list_revisions, mock_get_details):
        """Test get_listing successfully retrieves a listing"""
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client

        mock_get_details.return_value = {
            "Id": "dataset-123",
            "Name": "Test Dataset",
            "Description": "Test Description",
            "AssetType": "S3_SNAPSHOT",
            "Origin": "OWNED",
            "CreatedAt": "2023-01-01T12:00:00Z",
            "UpdatedAt": "2023-01-01T12:00:00Z",
        }

        mock_list_revisions.return_value = {
            "Revisions": [{"Id": "rev-1", "CreatedAt": "2023-01-01T12:00:00Z"}]
        }

        listing = self.connector.get_listing("dataset-123")

        self.assertIsInstance(listing, MarketplaceListing)
        self.assertEqual(listing.marketplace_id, "dataset-123")
        self.assertEqual(listing.title, "Test Dataset")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_get_listing_not_found(self, mock_boto3, mock_get_details):
        """Test get_listing raises NotFoundError when dataset not found"""
        from hub.apps.core.services.base import NotFoundError, PermissionError

        mock_get_details.side_effect = NotFoundError("Dataset not found")

        with self.assertRaises(NotFoundError):
            self.connector.get_listing("dataset-123")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_resources_success(self, mock_boto3, mock_get_details):
        """Test list_resources successfully lists assets"""
        mock_client = Mock()
        mock_client.list_revision_assets.return_value = {
            "Assets": [
                {
                    "Id": "asset-1",
                    "Name": "Asset 1",
                    "AssetType": "S3_SNAPSHOT",
                    "Source": {"Bucket": "test-bucket", "Key": "data/file.csv"},
                }
            ]
        }
        mock_boto3.client.return_value = mock_client

        mock_get_details.return_value = {"Id": "dataset-123", "LatestRevision": {"Id": "rev-1"}}

        resources = self.connector.list_resources("dataset-123")

        self.assertEqual(len(resources), 1)
        self.assertIsInstance(resources[0], MarketplaceResource)
        self.assertEqual(resources[0].resource_id, "asset-1")
        self.assertEqual(resources[0].resource_type, "S3_OBJECT")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataset_details"
    )
    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_list_resources_not_found(self, mock_boto3, mock_get_details):
        """Test list_resources raises NotFoundError when dataset not found"""
        from hub.apps.core.services.base import NotFoundError, PermissionError

        mock_get_details.side_effect = NotFoundError("Dataset not found")

        with self.assertRaises(NotFoundError):
            self.connector.list_resources("dataset-123")


class TestAWSDataExchangeConnectorNotImplementedMethods(TestCase):
    """Test that methods not yet implemented raise NotImplementedError"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    # Discovery operations are now implemented - tests moved to TestAWSDataExchangeConnectorDiscoveryOperations

    def test_create_listing_not_supported(self):
        """Test create_listing raises NotImplementedError (push not supported)"""
        from hub.apps.integrations.base import MarketplaceListing

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE, title="Test"
        )
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_update_listing_not_supported(self):
        """Test update_listing raises NotImplementedError (push not supported)"""
        from hub.apps.integrations.base import MarketplaceListing

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE, title="Test"
        )
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test-id", listing)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_publish_resource_not_supported(self):
        """Test publish_resource raises NotImplementedError (push not supported)"""
        from hub.apps.integrations.base import MarketplaceResource

        resource = MarketplaceResource(
            resource_id="test", resource_type="FILE", name="Test Resource"
        )
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test-id", resource)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_map_from_hub_asset_not_supported(self):
        """Test map_from_hub_asset raises NotImplementedError (push not supported)"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset({"name": "Test"})
        self.assertIn("push operations", str(cm.exception).lower())

    def test_sync_push_not_supported(self):
        """Test sync_push raises NotImplementedError (push not supported)"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])
        self.assertIn("push operations", str(cm.exception).lower())


class TestAWSDataExchangeConnectorPullOperations(TestCase):
    """Test AWS Data Exchange connector pull operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        self.connector._authenticated = True

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_success(self, mock_list_resources):
        """Test map_to_hub_asset successfully maps listing to MarketplaceAssetMapping"""
        from hub.apps.assets.models import AssetSourceType
        from hub.apps.integrations.base import MarketplaceAssetMapping

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            description="Test Description",
            category="OWNED",
            tags=["tag1", "tag2"],
            metadata={
                "aws_data_exchange_dataset": {
                    "Id": "dataset-123",
                    "Name": "Test Dataset",
                    "Description": "Test Description",
                    "Origin": "OWNED",
                    "AssetType": "S3_SNAPSHOT",
                },
                "latest_revision": {"Id": "rev-1"},
                "odps_metadata": {"product_details": {"productID": "dataset-123"}},
                "odcs_metadata": {"schema_hints": {}},
            },
            url="https://console.aws.amazon.com/dataexchange/home?region=us-east-1#/datasets/dataset-123",
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertEqual(mapping.asset_data["name"], "Test Dataset")
        self.assertEqual(mapping.asset_data["description"], "Test Description")
        self.assertEqual(mapping.asset_data["key"], "aws-data-exchange-dataset-123")
        self.assertIn("tag1", mapping.asset_data["tags"])
        self.assertEqual(
            mapping.source_metadata["marketplace_type"], MarketplaceType.AWS_DATA_EXCHANGE.value
        )
        self.assertEqual(mapping.source_metadata["dataset_id"], "dataset-123")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_with_resources(self, mock_list_resources):
        """Test map_to_hub_asset includes resources with external metadata"""
        from hub.apps.integrations.base import MarketplaceAssetMapping

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {"Id": "dataset-123", "Name": "Test Dataset"},
                "latest_revision": {"Id": "rev-1"},
            },
        )

        resource = MarketplaceResource(
            resource_id="asset-1",
            resource_type="S3_OBJECT",
            name="Asset 1",
            metadata={"dataset_id": "dataset-123", "revision_id": "rev-1"},
        )
        mock_list_resources.return_value = [resource]

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(len(mapping.resources), 1)
        self.assertEqual(mapping.resources[0].resource_id, "asset-1")
        self.assertTrue(mapping.resources[0].metadata.get("external"))

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_empty_listing(self, mock_list_resources):
        """Test map_to_hub_asset raises ValueError for empty listing"""
        with self.assertRaises(ValueError) as cm:
            self.connector.map_to_hub_asset(None)
        self.assertIn("required", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_listings"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.map_to_hub_asset"
    )
    def test_sync_pull_success(self, mock_map_to_hub_asset, mock_list_listings):
        """Test sync_pull successfully syncs listings"""
        from hub.apps.assets.models import AssetSourceType
        from hub.apps.integrations.base import MarketplaceAssetMapping, SyncResult, SyncStatus

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
        )
        mock_list_listings.return_value = [listing]

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Dataset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_id": "dataset-123"},
            resources=[],
        )
        mock_map_to_hub_asset.return_value = mapping

        result = self.connector.sync_pull()

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.successful_items, 1)
        self.assertEqual(result.failed_items, 0)
        self.assertIn("mappings", result.metadata)
        self.assertEqual(len(result.metadata["mappings"]), 1)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.get_listing"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.map_to_hub_asset"
    )
    def test_sync_pull_with_listing_ids(self, mock_map_to_hub_asset, mock_get_listing):
        """Test sync_pull with specific listing IDs"""
        from hub.apps.assets.models import AssetSourceType
        from hub.apps.integrations.base import MarketplaceAssetMapping, SyncResult

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
        )
        mock_get_listing.return_value = listing

        mapping = MarketplaceAssetMapping(
            asset_data={"name": "Test Dataset"},
            source_type=AssetSourceType.FEDERATED,
            source_metadata={"marketplace_id": "dataset-123"},
            resources=[],
        )
        mock_map_to_hub_asset.return_value = mapping

        result = self.connector.sync_pull(listing_ids=["dataset-123"])

        self.assertEqual(result.successful_items, 1)
        mock_get_listing.assert_called_once_with("dataset-123")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_listings"
    )
    def test_sync_pull_dry_run(self, mock_list_listings):
        """Test sync_pull with dry_run option"""
        from hub.apps.integrations.base import SyncResult

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
        )
        mock_list_listings.return_value = [listing]

        result = self.connector.sync_pull(options={"dry_run": True})

        self.assertEqual(result.successful_items, 1)
        self.assertTrue(result.metadata.get("dry_run"))
        # Should not call map_to_hub_asset in dry_run mode
        self.assertEqual(len(result.metadata.get("mappings", [])), 0)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_subscribe_to_dataset_already_subscribed(self, mock_boto3):
        """Test _subscribe_to_dataset when already subscribed"""
        mock_client = Mock()
        mock_client.list_data_set_revisions.return_value = {"Revisions": [{"Id": "rev-1"}]}
        mock_boto3.client.return_value = mock_client

        # Should not raise exception
        self.connector._subscribe_to_dataset("dataset-123")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_subscribe_to_dataset_not_subscribed(self, mock_boto3):
        """Test _subscribe_to_dataset when not subscribed"""
        mock_client = Mock()
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Not subscribed"}}
        mock_client.list_data_set_revisions.side_effect = ClientError(
            error_response, "list_data_set_revisions"
        )
        mock_boto3.client.return_value = mock_client

        # PermissionError is Python's built-in exception
        with self.assertRaises(PermissionError):
            self.connector._subscribe_to_dataset("dataset-123")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._list_revisions"
    )
    def test_get_latest_revision_success(self, mock_list_revisions):
        """Test _get_latest_revision successfully gets latest revision"""
        mock_list_revisions.return_value = {
            "Revisions": [{"Id": "rev-1", "CreatedAt": "2023-01-01T12:00:00Z"}]
        }

        revision_id = self.connector._get_latest_revision("dataset-123")

        self.assertEqual(revision_id, "rev-1")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._list_revisions"
    )
    def test_get_latest_revision_no_revisions(self, mock_list_revisions):
        """Test _get_latest_revision raises NotFoundError when no revisions"""
        from hub.apps.core.services.base import NotFoundError, PermissionError

        mock_list_revisions.return_value = {"Revisions": []}

        with self.assertRaises(NotFoundError):
            self.connector._get_latest_revision("dataset-123")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_create_export_job_success(self, mock_boto3):
        """Test _create_export_job successfully creates export job"""
        mock_client = Mock()
        mock_client.create_job.return_value = {"Id": "job-123"}
        mock_boto3.client.return_value = mock_client

        job_id = self.connector._create_export_job(
            dataset_id="dataset-123", revision_id="rev-1", destination_bucket="test-bucket"
        )

        self.assertEqual(job_id, "job-123")
        mock_client.create_job.assert_called_once()
        call_args = mock_client.create_job.call_args[1]
        self.assertEqual(call_args["Type"], "EXPORT_ASSETS_TO_S3")
        self.assertEqual(call_args["Details"]["ExportAssetsToS3"]["DataSetId"], "dataset-123")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_create_export_job_missing_bucket(self, mock_boto3):
        """Test _create_export_job raises ValueError when bucket not specified"""
        with self.assertRaises(ValueError) as cm:
            self.connector._create_export_job(dataset_id="dataset-123", revision_id="rev-1")
        self.assertIn("bucket", str(cm.exception).lower())

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_start_job_success(self, mock_boto3):
        """Test _start_job successfully starts export job"""
        mock_client = Mock()
        mock_client.start_job.return_value = {}
        mock_boto3.client.return_value = mock_client

        # Should not raise exception
        self.connector._start_job("job-123")

        mock_client.start_job.assert_called_once_with(JobId="job-123")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_wait_for_job_completion_success(self, mock_boto3):
        """Test _wait_for_job_completion successfully waits for job completion"""
        import time
        from unittest.mock import patch as mock_patch

        mock_client = Mock()
        # First call returns IN_PROGRESS, second returns COMPLETED
        mock_client.get_job.side_effect = [
            {"Job": {"State": "IN_PROGRESS", "Id": "job-123"}},
            {"Job": {"State": "COMPLETED", "Id": "job-123"}},
        ]
        mock_boto3.client.return_value = mock_client

        with mock_patch("time.sleep"):  # Mock sleep to speed up test
            result = self.connector._wait_for_job_completion("job-123", timeout_seconds=10)

        self.assertEqual(result["State"], "COMPLETED")

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_wait_for_job_completion_timeout(self, mock_boto3):
        """Test _wait_for_job_completion raises TimeoutError on timeout"""
        import time
        from unittest.mock import patch as mock_patch

        mock_client = Mock()
        mock_client.get_job.return_value = {"Job": {"State": "IN_PROGRESS", "Id": "job-123"}}
        mock_boto3.client.return_value = mock_client

        # Patch time where the connector uses it so the mock is applied; provide enough
        # return values so the loop never exhausts side_effect (start_time=0, then
        # elapsed checks until timeout).
        time_module = "hub.apps.integrations.connectors.aws_data_exchange_connector.time"
        with (
            mock_patch("time.sleep"),
            mock_patch(f"{time_module}.time", side_effect=[0, 3700] + [3700] * 20),
        ):  # Exceed timeout
            with self.assertRaises(TimeoutError):
                self.connector._wait_for_job_completion("job-123", timeout_seconds=3600)

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.boto3")
    def test_wait_for_job_completion_failed(self, mock_boto3):
        """Test _wait_for_job_completion raises RuntimeError when job fails"""
        import time
        from unittest.mock import patch as mock_patch

        mock_client = Mock()
        mock_client.get_job.return_value = {
            "Job": {"State": "ERROR", "Id": "job-123", "Errors": [{"Message": "Job failed"}]}
        }
        mock_boto3.client.return_value = mock_client

        with mock_patch("time.sleep"):
            with self.assertRaises(RuntimeError) as cm:
                self.connector._wait_for_job_completion("job-123")
            self.assertIn("failed", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_s3_client"
    )
    def test_download_exported_assets_success(self, mock_get_s3_client):
        """Test _download_exported_assets successfully downloads assets"""
        import os
        import tempfile

        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "prefix/file1.csv", "Size": 100}]}
        ]
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_get_s3_client.return_value = mock_s3_client

        job_result = {
            "Details": {
                "ExportAssetsToS3": {
                    "AssetDestination": {
                        "S3Destination": {"Bucket": "test-bucket", "KeyPrefix": "prefix/"}
                    }
                }
            }
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            destination_path = os.path.join(tmpdir, "downloaded.csv")
            result_path = self.connector._download_exported_assets(job_result, destination_path)

            self.assertEqual(result_path, destination_path)
            mock_s3_client.download_file.assert_called_once()

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_s3_client"
    )
    def test_download_exported_assets_no_objects(self, mock_get_s3_client):
        """Test _download_exported_assets raises ValueError when no objects found"""
        mock_s3_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_get_s3_client.return_value = mock_s3_client

        job_result = {
            "Details": {
                "ExportAssetsToS3": {
                    "AssetDestination": {
                        "S3Destination": {"Bucket": "test-bucket", "KeyPrefix": "prefix/"}
                    }
                }
            }
        }

        with self.assertRaises(ValueError) as cm:
            self.connector._download_exported_assets(job_result, "/tmp/test.csv")
        self.assertIn("no objects", str(cm.exception).lower())

    def test_extract_schema_from_assets_csv(self):
        """Test _extract_schema_from_assets extracts schema from CSV"""
        import csv
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.DictWriter(f, fieldnames=["col1", "col2"])
            writer.writeheader()
            writer.writerow({"col1": "value1", "col2": "value2"})
            temp_path = f.name

        try:
            result = self.connector._extract_schema_from_assets(temp_path)

            self.assertIn("schema", result)
            self.assertIn("fields", result["schema"])
            self.assertEqual(len(result["schema"]["fields"]), 2)
            self.assertEqual(result["schema"]["format"], "CSV")
        finally:
            os.unlink(temp_path)

    def test_extract_schema_from_assets_json(self):
        """Test _extract_schema_from_assets extracts schema from JSON"""
        import json
        import os
        import tempfile

        data = [{"field1": "value1", "field2": 123, "field3": True}]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = self.connector._extract_schema_from_assets(temp_path)

            self.assertIn("schema", result)
            self.assertIn("fields", result["schema"])
            self.assertEqual(len(result["schema"]["fields"]), 3)
            self.assertEqual(result["schema"]["format"], "JSON")
        finally:
            os.unlink(temp_path)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._download_exported_assets"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._wait_for_job_completion"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._start_job"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._create_export_job"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_latest_revision"
    )
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._subscribe_to_dataset"
    )
    @patch("django.conf.settings")
    def test_download_resource_success(
        self,
        mock_settings,
        mock_subscribe,
        mock_get_revision,
        mock_create_job,
        mock_start_job,
        mock_wait,
        mock_download,
    ):
        """Test download_resource successfully downloads resource"""
        mock_settings.AWS_DATA_EXCHANGE_EXPORT_BUCKET = "test-bucket"

        mock_subscribe.return_value = None
        mock_get_revision.return_value = "rev-1"
        mock_create_job.return_value = "job-123"
        mock_start_job.return_value = None
        mock_wait.return_value = {"State": "COMPLETED"}
        mock_download.return_value = "/tmp/downloaded.csv"

        result = self.connector.download_resource("dataset-123", "/tmp/test.csv")

        self.assertEqual(result, "/tmp/downloaded.csv")
        mock_subscribe.assert_called_once_with("dataset-123")
        mock_get_revision.assert_called_once_with("dataset-123")
        mock_create_job.assert_called_once()
        mock_start_job.assert_called_once_with("job-123")
        mock_wait.assert_called_once_with("job-123")
        mock_download.assert_called_once()

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._subscribe_to_dataset"
    )
    def test_download_resource_subscription_warning(self, mock_subscribe):
        """Test download_resource continues even if subscription check fails"""
        from unittest.mock import patch as mock_patch

        # PermissionError is Python's built-in exception
        mock_subscribe.side_effect = PermissionError("Not subscribed")

        with (
            mock_patch.object(self.connector, "_get_latest_revision", return_value="rev-1"),
            mock_patch.object(self.connector, "_create_export_job", return_value="job-123"),
            mock_patch.object(self.connector, "_start_job"),
            mock_patch.object(
                self.connector, "_wait_for_job_completion", return_value={"State": "COMPLETED"}
            ),
            mock_patch.object(
                self.connector, "_download_exported_assets", return_value="/tmp/test.csv"
            ),
            mock_patch("django.conf.settings", AWS_DATA_EXCHANGE_EXPORT_BUCKET="test-bucket"),
        ):
            # Should not raise exception, just log warning
            result = self.connector.download_resource("dataset-123", "/tmp/test.csv")
            self.assertEqual(result, "/tmp/test.csv")


class TestAWSDataExchangeConnectorMetadataMapping(TestCase):
    """Test AWS Data Exchange connector metadata mapping operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )
        self.connector._authenticated = True

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_extracts_all_metadata(self, mock_list_resources):
        """Test map_to_hub_asset extracts all required metadata fields"""
        from hub.apps.assets.models import AssetSourceType
        from hub.apps.integrations.base import MarketplaceAssetMapping

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            description="Test Description",
            category="OWNED",
            tags=["tag1", "tag2"],
            metadata={
                "aws_data_exchange_dataset": {
                    "Id": "dataset-123",
                    "Name": "Test Dataset",
                    "Description": "Test Description",
                    "Origin": "OWNED",
                    "AssetType": "S3_SNAPSHOT",
                    "OriginDetails": {"ProductId": "provider-123", "Name": "Provider Name"},
                },
                "latest_revision": {"Id": "rev-1"},
                "odps_metadata": {
                    "product_details": {"productID": "dataset-123"},
                    "pricing_plans": [],
                    "access_methods": {},
                    "payment_gateways": {},
                },
                "odcs_metadata": {"schema_hints": {}, "quality_hints": {}, "sla_hints": {}},
            },
            url="https://console.aws.amazon.com/dataexchange/home?region=us-east-1#/datasets/dataset-123",
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing, sync_job_id="job-123")

        # Verify asset_data
        self.assertEqual(mapping.asset_data["name"], "Test Dataset")
        self.assertEqual(mapping.asset_data["description"], "Test Description")
        self.assertEqual(mapping.asset_data["domain"], "OWNED")
        self.assertEqual(mapping.asset_data["status"], "ACTIVE")
        self.assertEqual(mapping.asset_data["visibility"], "PUBLIC")
        self.assertIn("tag1", mapping.asset_data["tags"])
        self.assertIn("tag2", mapping.asset_data["tags"])

        # Verify source_type
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

        # Verify source_metadata
        self.assertEqual(
            mapping.source_metadata["marketplace_type"], MarketplaceType.AWS_DATA_EXCHANGE.value
        )
        self.assertEqual(mapping.source_metadata["marketplace_id"], "dataset-123")
        self.assertEqual(mapping.source_metadata["listing_id"], "dataset-123")
        self.assertEqual(mapping.source_metadata["dataset_id"], "dataset-123")
        self.assertEqual(mapping.source_metadata["revision_id"], "rev-1")
        self.assertEqual(mapping.source_metadata["sync_job_id"], "job-123")
        self.assertEqual(mapping.source_metadata["provider"], "provider-123")
        self.assertIn("synced_at", mapping.source_metadata)

        # Verify ODPS and ODCS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIsNotNone(mapping.odcs_metadata)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_with_provider_from_name(self, mock_list_resources):
        """Test map_to_hub_asset extracts Provider from OriginDetails.Name"""
        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {
                    "Id": "dataset-123",
                    "Name": "Test Dataset",
                    "OriginDetails": {"Name": "Provider Name"},
                },
                "latest_revision": {},
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(mapping.source_metadata.get("provider"), "Provider Name")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_without_provider(self, mock_list_resources):
        """Test map_to_hub_asset handles missing Provider gracefully"""
        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {"Id": "dataset-123", "Name": "Test Dataset"},
                "latest_revision": {},
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertNotIn("provider", mapping.source_metadata)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_extracts_odps_metadata(self, mock_list_resources):
        """Test map_to_hub_asset extracts ODPS metadata correctly"""
        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {
                    "Id": "dataset-123",
                    "Name": "Test Dataset",
                    "AssetType": "S3_SNAPSHOT",
                },
                "latest_revision": {"Id": "rev-1"},
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIn("product_details", mapping.odps_metadata)
        self.assertEqual(mapping.odps_metadata["product_details"]["productID"], "dataset-123")
        self.assertIn("pricing_plans", mapping.odps_metadata)
        self.assertIn("access_methods", mapping.odps_metadata)
        self.assertIn("payment_gateways", mapping.odps_metadata)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_extracts_odcs_metadata(self, mock_list_resources):
        """Test map_to_hub_asset extracts ODCS metadata correctly"""
        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {"Id": "dataset-123", "Name": "Test Dataset"},
                "latest_revision": {},
            },
        )

        mock_list_resources.return_value = []

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping.odcs_metadata)
        self.assertIn("schema_hints", mapping.odcs_metadata)
        self.assertIn("quality_hints", mapping.odcs_metadata)
        self.assertIn("sla_hints", mapping.odcs_metadata)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_includes_resources(self, mock_list_resources):
        """Test map_to_hub_asset includes resources with external metadata"""
        from hub.apps.integrations.base import MarketplaceResource

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            metadata={
                "aws_data_exchange_dataset": {"Id": "dataset-123"},
                "latest_revision": {"Id": "rev-1"},
            },
        )

        resource = MarketplaceResource(
            resource_id="asset-1", resource_type="S3_OBJECT", name="Asset 1"
        )
        mock_list_resources.return_value = [resource]

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertEqual(len(mapping.resources), 1)
        self.assertEqual(mapping.resources[0].resource_id, "asset-1")
        self.assertTrue(mapping.resources[0].metadata.get("external"))
        self.assertEqual(mapping.resources[0].metadata.get("dataset_id"), "dataset-123")
        self.assertEqual(mapping.resources[0].metadata.get("revision_id"), "rev-1")

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test map_from_hub_asset raises NotImplementedError"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset({"name": "Test Asset"})
        self.assertIn("push operations", str(cm.exception).lower())

    def test_create_listing_raises_not_implemented(self):
        """Test create_listing raises NotImplementedError"""
        from hub.apps.integrations.base import MarketplaceListing

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE, title="Test"
        )

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_update_listing_raises_not_implemented(self):
        """Test update_listing raises NotImplementedError"""
        from hub.apps.integrations.base import MarketplaceListing

        listing = MarketplaceListing(
            marketplace_id="test", marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE, title="Test"
        )

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test-id", listing)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_publish_resource_raises_not_implemented(self):
        """Test publish_resource raises NotImplementedError"""
        from hub.apps.integrations.base import MarketplaceResource

        resource = MarketplaceResource(
            resource_id="test-resource", resource_type="FILE", name="Test Resource"
        )

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test-listing", resource)
        self.assertIn("push operations", str(cm.exception).lower())

    def test_sync_push_raises_not_implemented(self):
        """Test sync_push raises NotImplementedError"""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])
        self.assertIn("push operations", str(cm.exception).lower())


class TestAWSDataExchangeConnectorRetryLogic(TestCase):
    """Test AWS Data Exchange connector retry logic"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_retry_on_throttling_exception(self, mock_get_client, mock_sleep):
        """Test retry logic on ThrottlingException"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate retry: first call fails with ThrottlingException, second succeeds
        call_count = [0]

        def list_datasets_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = {
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                }
                raise ClientError(error_response, "list_data_sets")
            return {"DataSets": []}

        mock_client.list_data_sets.side_effect = list_datasets_side_effect

        # Mock circuit breaker to pass through
        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify retry was attempted (should be called twice: once fails, once succeeds)
        self.assertEqual(mock_client.list_data_sets.call_count, 2)
        # Verify sleep was called for backoff
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_retry_on_service_unavailable_exception(self, mock_get_client, mock_sleep):
        """Test retry logic on ServiceUnavailableException"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        call_count = [0]

        def get_dataset_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = {
                    "Error": {
                        "Code": "ServiceUnavailableException",
                        "Message": "Service unavailable",
                    }
                }
                raise ClientError(error_response, "get_data_set")
            return {"Id": "dataset-123", "Name": "Test Dataset"}

        mock_client.get_data_set.side_effect = get_dataset_side_effect
        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector._get_dataset_details("dataset-123")

        self.assertIsNotNone(result)
        self.assertEqual(mock_client.get_data_set.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_retry_on_internal_server_exception(self, mock_get_client, mock_sleep):
        """Test retry logic on InternalServerException"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        call_count = [0]

        def list_revisions_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                error_response = {
                    "Error": {"Code": "InternalServerException", "Message": "Internal server error"}
                }
                raise ClientError(error_response, "list_data_set_revisions")
            return {"Revisions": []}

        mock_client.list_data_set_revisions.side_effect = list_revisions_side_effect
        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector._list_revisions("dataset-123")

        self.assertIsNotNone(result)
        self.assertEqual(mock_client.list_data_set_revisions.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_no_retry_on_access_denied_exception(self, mock_get_client, mock_sleep):
        """Test that AccessDeniedException is not retried"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        mock_client.list_data_sets.side_effect = ClientError(error_response, "list_data_sets")

        # Mock circuit breaker to pass through exceptions
        def circuit_breaker_call(func):
            try:
                return func()
            except Exception as e:
                raise e

        self.connector._circuit_breaker.call = circuit_breaker_call

        from hub.apps.core.services.base import PermissionError

        # Should raise PermissionError without retrying
        with self.assertRaises(PermissionError):
            self.connector.test_connection()

        # Should not retry on AccessDeniedException (only called once)
        self.assertEqual(mock_client.list_data_sets.call_count, 1)
        # Should not sleep since we don't retry
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_no_retry_on_resource_not_found_exception(self, mock_get_client, mock_sleep):
        """Test that ResourceNotFoundException is not retried"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Resource not found"}
        }
        mock_client.get_data_set.side_effect = ClientError(error_response, "get_data_set")
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises(NotFoundError):
            self.connector._get_dataset_details("dataset-123")

        # Should not retry on ResourceNotFoundException
        self.assertEqual(mock_client.get_data_set.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_max_retries_exceeded(self, mock_get_client, mock_sleep):
        """Test that max retries are respected"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_client.list_data_sets.side_effect = ClientError(error_response, "list_data_sets")
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises(ConnectionError):
            self.connector.test_connection()

        # Should retry max_retries + 1 times (initial attempt + retries)
        self.assertEqual(mock_client.list_data_sets.call_count, self.connector.max_retries + 1)
        # Should sleep for each retry attempt
        self.assertEqual(mock_sleep.call_count, self.connector.max_retries)

    @patch("time.sleep")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_exponential_backoff(self, mock_get_client, mock_sleep):
        """Test that exponential backoff is used"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        call_count = [0]

        def list_datasets_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                error_response = {
                    "Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}
                }
                raise ClientError(error_response, "list_data_sets")
            return {"DataSets": []}

        mock_client.list_data_sets.side_effect = list_datasets_side_effect
        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify exponential backoff delays
        expected_delays = [
            self.connector.backoff_factor * (2**0),  # First retry: 1 * 2^0 = 1
            self.connector.backoff_factor * (2**1),  # Second retry: 1 * 2^1 = 2
        ]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        self.assertEqual(actual_delays, expected_delays)


class TestAWSDataExchangeConnectorErrorHandling(TestCase):
    """Test AWS Data Exchange connector error handling"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_map_resource_not_found_to_not_found_error(self, mock_get_client):
        """Test that ResourceNotFoundException maps to NotFoundError"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {
            "Error": {"Code": "ResourceNotFoundException", "Message": "Dataset not found"}
        }
        mock_client.get_data_set.side_effect = ClientError(error_response, "get_data_set")
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises(NotFoundError) as cm:
            self.connector._get_dataset_details("dataset-123")

        self.assertIn("not found", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_map_access_denied_to_permission_error(self, mock_get_client):
        """Test that AccessDeniedException maps to PermissionError"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        mock_client.list_data_sets.side_effect = ClientError(error_response, "list_data_sets")

        # Mock circuit breaker to pass through exceptions
        def circuit_breaker_call(func):
            try:
                return func()
            except Exception as e:
                raise e

        self.connector._circuit_breaker.call = circuit_breaker_call

        from hub.apps.core.services.base import PermissionError

        # Should raise PermissionError (not ConnectionError)
        with self.assertRaises(PermissionError) as cm:
            self.connector.test_connection()

        # Verify error message contains 'access denied'
        self.assertIn("access denied", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_map_validation_exception_to_value_error(self, mock_get_client):
        """Test that ValidationException maps to ValueError"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "ValidationException", "Message": "Invalid parameter"}}
        mock_client.create_job.side_effect = ClientError(error_response, "create_job")
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises(ValueError) as cm:
            self.connector._create_export_job("dataset-123", "revision-123", "bucket-123")

        self.assertIn("invalid", str(cm.exception).lower())

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_map_transient_errors_to_connection_error(self, mock_get_client):
        """Test that transient errors map to ConnectionError"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        error_response = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_client.list_data_sets.side_effect = ClientError(error_response, "list_data_sets")
        self.connector._circuit_breaker.call = lambda func: func()

        # ConnectionError is a built-in Python exception
        with self.assertRaises(ConnectionError) as cm:
            self.connector.test_connection()

        # Check that error message contains either 'transient' or 'throttling' or 'aws'
        error_msg = str(cm.exception).lower()
        self.assertTrue("transient" in error_msg or "throttling" in error_msg or "aws" in error_msg)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_map_boto_core_error_to_connection_error(self, mock_get_client):
        """Test that BotoCoreError maps to ConnectionError"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        mock_client.list_data_sets.side_effect = BotoCoreError()
        self.connector._circuit_breaker.call = lambda func: func()

        # ConnectionError is a built-in Python exception
        with self.assertRaises(ConnectionError):
            self.connector.test_connection()


class TestAWSDataExchangeConnectorCircuitBreaker(TestCase):
    """Test AWS Data Exchange connector circuit breaker integration"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    def test_circuit_breaker_initialized(self):
        """Test that circuit breaker is initialized"""
        self.assertIsNotNone(self.connector._circuit_breaker)
        self.assertTrue(hasattr(self.connector._circuit_breaker, "call"))

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_circuit_breaker_protection(self, mock_get_client):
        """Test that circuit breaker is used for API calls"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        # Mock circuit breaker to track calls
        circuit_breaker_called = [False]

        def circuit_breaker_call(func):
            circuit_breaker_called[0] = True
            return func()

        self.connector._circuit_breaker.call = circuit_breaker_call

        result = self.connector.test_connection()

        self.assertTrue(result)
        self.assertTrue(circuit_breaker_called[0])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_circuit_breaker_open_state(self, mock_get_client):
        """Test handling of circuit breaker open state"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Simulate circuit breaker open state
        from hub.apps.core.resilience.circuit_breaker import CircuitBreakerError

        def circuit_breaker_call(func):
            raise CircuitBreakerError("Circuit breaker is open")

        self.connector._circuit_breaker.call = circuit_breaker_call

        with self.assertRaises(ConnectionError):
            self.connector.test_connection()

    def test_circuit_breaker_configuration(self):
        """Test circuit breaker configuration matches CKAN connector pattern"""
        # Circuit breaker should have same configuration as CKAN connector
        self.assertEqual(
            self.connector._circuit_breaker.service_name, "aws-data-exchange-connector"
        )
        self.assertEqual(self.connector._circuit_breaker.failure_threshold, 5)
        self.assertEqual(self.connector._circuit_breaker.timeout_seconds, 60)
        self.assertEqual(self.connector._circuit_breaker.success_threshold, 2)


class TestAWSDataExchangeConnectorDistributedTracing(TestCase):
    """Test AWS Data Exchange connector distributed tracing"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch("hub.apps.integrations.connectors.aws_data_exchange_connector.structlog")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_logging_with_correlation_context(self, mock_get_client, mock_structlog):
        """Test that logging includes correlation context"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        # Mock structlog contextvars
        mock_structlog.contextvars.get_contextvars.return_value = {
            "trace_id": "test-trace-id",
            "span_id": "test-span-id",
        }

        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify that logging was called with correlation context
        # (structlog logger should be called during the operation)

    @patch("hub.apps.api.middleware.trace_propagation.get_current_request")
    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_correlation_context_from_request(self, mock_get_client, mock_get_request):
        """Test that correlation context is extracted from request"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        # Mock request with trace context
        mock_request = Mock()
        mock_request.trace_id = "request-trace-id"
        mock_request.span_id = "request-span-id"
        mock_get_request.return_value = mock_request

        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.test_connection()

        self.assertTrue(result)
        # Verify correlation context was retrieved
        mock_get_request.assert_called()

    def test_get_correlation_context(self):
        """Test _get_correlation_context method"""
        context = self.connector._get_correlation_context()

        # Should return a dictionary
        self.assertIsInstance(context, dict)
        # May or may not have trace_id/span_id depending on context


class TestAWSDataExchangeConnectorEdgeCases(TestCase):
    """Comprehensive edge case tests for AWS Data Exchange connector"""

    def setUp(self):
        """Set up test fixtures"""
        self.connector = AWSDataExchangeConnector(
            aws_access_key_id="test-key-id", aws_secret_access_key="test-secret-key"
        )

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_empty_result(self, mock_get_client):
        """Test list_listings with empty result set"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        self.connector._circuit_breaker.call = lambda func: func()

        listings = self.connector.list_listings()

        self.assertEqual(listings, [])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_missing_fields(self, mock_get_client):
        """Test list_listings with missing optional fields"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {
            "DataSets": [
                {
                    "Id": "dataset-123",
                    "Name": "Test Dataset",
                    # Missing Description, Origin, Tags, etc.
                }
            ]
        }

        # Mock _get_dataset_details to return proper dataset details with missing fields
        def get_dataset_details_side_effect(dataset_id):
            return {
                "Id": dataset_id,
                "Name": "Test Dataset",
                # Missing Description, OriginDetails, Tags, etc.
            }

        self.connector._circuit_breaker.call = lambda func: func()

        with patch.object(
            self.connector, "_get_dataset_details", side_effect=get_dataset_details_side_effect
        ):
            listings = self.connector.list_listings()

            self.assertEqual(len(listings), 1)
            self.assertEqual(listings[0].marketplace_id, "dataset-123")
            self.assertEqual(listings[0].title, "Test Dataset")
            # Should handle missing fields gracefully (may be None or empty string)
            description = listings[0].description
            self.assertTrue(description is None or description == "")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_get_listing_not_found(self, mock_get_client):
        """Test get_listing with non-existent dataset"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Dataset not found"}},
            "GetDataSet",
        )
        mock_client.get_data_set.side_effect = error

        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises(NotFoundError):
            self.connector.get_listing("non-existent-dataset")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_resources_no_revisions(self, mock_get_client):
        """Test list_resources when dataset has no revisions"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_data_set.return_value = {"Id": "dataset-123", "Name": "Test Dataset"}
        mock_client.list_data_set_revisions.return_value = {"Revisions": []}

        self.connector._circuit_breaker.call = lambda func: func()

        resources = self.connector.list_resources("dataset-123")

        self.assertEqual(resources, [])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_resources_revision_no_assets(self, mock_get_client):
        """Test list_resources when revision has no assets"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_data_set.return_value = {"Id": "dataset-123", "Name": "Test Dataset"}
        mock_client.list_data_set_revisions.return_value = {
            "Revisions": [{"Id": "revision-123", "CreatedAt": "2023-01-01T00:00:00Z"}]
        }
        mock_client.list_revision_assets.return_value = {"Assets": []}

        self.connector._circuit_breaker.call = lambda func: func()

        resources = self.connector.list_resources("dataset-123")

        self.assertEqual(resources, [])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_pagination_edge_cases(self, mock_get_client):
        """Test list_listings pagination edge cases"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # Mock _get_dataset_details to return dataset details for each dataset
        def get_dataset_details_side_effect(dataset_id):
            return {
                "Id": dataset_id,
                "Name": dataset_id.replace("dataset-", "Dataset "),
                "Description": "",
                "Origin": "OWNED",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": "2023-01-01T00:00:00Z",
                "UpdatedAt": "2023-01-01T00:00:00Z",
            }

        # First page: 5 items with NextToken
        # Second page: 3 items, no NextToken
        mock_client.list_data_sets.side_effect = [
            {
                "DataSets": [{"Id": f"dataset-{i}", "Name": f"Dataset {i}"} for i in range(5)],
                "NextToken": "token-1",
            },
            {"DataSets": [{"Id": f"dataset-{i}", "Name": f"Dataset {i}"} for i in range(5, 8)]},
        ]

        # Mock _get_dataset_details
        with patch.object(
            self.connector, "_get_dataset_details", side_effect=get_dataset_details_side_effect
        ):
            self.connector._circuit_breaker.call = lambda func: func()

            listings = self.connector.list_listings(limit=10)

            self.assertEqual(len(listings), 8)
            self.assertEqual(mock_client.list_data_sets.call_count, 2)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_offset_beyond_results(self, mock_get_client):
        """Test list_listings with offset beyond available results"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        self.connector._circuit_breaker.call = lambda func: func()

        listings = self.connector.list_listings(limit=10, offset=1000)

        self.assertEqual(listings, [])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_sync_pull_empty_marketplace(self, mock_get_client):
        """Test sync_pull when marketplace has no datasets"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}

        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.sync_pull()

        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.successful_items, 0)
        self.assertIn("mappings", result.metadata)
        self.assertEqual(result.metadata["mappings"], [])

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_sync_pull_with_invalid_listing_id(self, mock_get_client):
        """Test sync_pull with invalid listing IDs"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        error = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Dataset not found"}},
            "GetDataSet",
        )
        mock_client.get_data_set.side_effect = error

        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector.sync_pull(listing_ids=["invalid-dataset"])

        # When a listing is not found, it's marked as skipped, not failed
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, 1)
        self.assertEqual(result.successful_items, 0)
        self.assertGreater(result.skipped_items, 0)
        self.assertGreater(len(result.errors), 0)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector.list_resources"
    )
    def test_map_to_hub_asset_missing_metadata(self, mock_list_resources):
        """Test map_to_hub_asset with minimal dataset metadata"""
        mock_list_resources.return_value = []

        listing = MarketplaceListing(
            marketplace_id="dataset-123",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
            title="Test Dataset",
            description=None,
            metadata={
                "Id": "dataset-123",
                "Name": "Test Dataset",
                # Missing Description, OriginDetails, Tags, etc.
            },
        )

        mapping = self.connector.map_to_hub_asset(listing)

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping.source_metadata["marketplace_id"], "dataset-123")
        self.assertEqual(mapping.asset_data["name"], "Test Dataset")
        # Should handle missing fields gracefully (may be None or empty string)
        description = mapping.asset_data.get("description")
        self.assertTrue(description is None or description == "")

    def test_download_resource_invalid_resource_id_format(self):
        """Test download_resource with invalid resource ID format"""
        self.connector._circuit_breaker.call = lambda func: func()

        # Empty resource_id should raise ValueError
        with self.assertRaises(ValueError):
            self.connector.download_resource("", "/tmp/test")

    def test_download_resource_missing_dataset_id(self):
        """Test download_resource with resource ID missing dataset ID"""
        self.connector._circuit_breaker.call = lambda func: func()

        # Resource ID format "revision-123:asset-123" (missing dataset_id) will parse as:
        # dataset_id=None, revision_id="revision-123", asset_id="asset-123"
        # This will cause ValueError when dataset_id is None
        with self.assertRaises(ValueError):
            self.connector.download_resource(":revision-123:asset-123", "/tmp/test")

    def test_parse_aws_datetime_none(self):
        """Test _parse_aws_datetime with None input"""
        result = self.connector._parse_aws_datetime(None)
        self.assertIsNone(result)

    def test_extract_tags_none(self):
        """Test _extract_tags with None input"""
        result = self.connector._extract_tags(None)
        self.assertEqual(result, [])

    def test_extract_tags_invalid_format(self):
        """Test _extract_tags with invalid tag format"""
        # Tags should be a list of dicts with Key/Value, but test with wrong format
        invalid_tags = ["tag1", "tag2"]  # Wrong format
        result = self.connector._extract_tags(invalid_tags)
        # Should handle gracefully
        self.assertIsInstance(result, list)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_get_dataset_details_missing_fields(self, mock_get_client):
        """Test _get_dataset_details with missing optional fields"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.get_data_set.return_value = {
            "Id": "dataset-123",
            "Name": "Test Dataset",
            # Missing Description, OriginDetails, Tags, etc.
        }

        self.connector._circuit_breaker.call = lambda func: func()

        details = self.connector._get_dataset_details("dataset-123")

        self.assertEqual(details["Id"], "dataset-123")
        self.assertEqual(details["Name"], "Test Dataset")
        # Should handle missing fields gracefully

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_revisions_empty_result(self, mock_get_client):
        """Test _list_revisions with empty result"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_set_revisions.return_value = {"Revisions": []}

        self.connector._circuit_breaker.call = lambda func: func()

        result = self.connector._list_revisions("dataset-123")

        self.assertEqual(result["Revisions"], [])

    def test_extract_odps_metadata_minimal(self):
        """Test _extract_odps_metadata with minimal dataset data"""
        dataset_data = {"Id": "dataset-123", "Name": "Test Dataset"}

        metadata = self.connector._extract_odps_metadata(dataset_data)

        self.assertIsInstance(metadata, dict)
        self.assertIn("product_details", metadata)
        self.assertEqual(metadata["product_details"]["product_name"], "Test Dataset")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_extract_odcs_metadata_minimal(self, mock_get_client):
        """Test _extract_odcs_metadata with minimal dataset data"""
        dataset_data = {"Id": "dataset-123", "Name": "Test Dataset"}

        metadata = self.connector._extract_odcs_metadata(dataset_data)

        self.assertIsInstance(metadata, dict)
        self.assertIn("schema_hints", metadata)
        self.assertIn("quality_hints", metadata)
        self.assertIn("sla_hints", metadata)

    def test_extract_odcs_metadata_with_none(self):
        """Test _extract_odcs_metadata() error handling with None"""
        with self.assertRaises((ValueError, TypeError, AttributeError)):
            self.connector._extract_odcs_metadata(None)  # type: ignore[arg-type]

    def test_extract_odcs_metadata_with_empty_dict(self):
        """Test _extract_odcs_metadata() error handling with empty dict"""
        metadata = self.connector._extract_odcs_metadata({})
        # Should handle gracefully and return metadata with defaults
        self.assertIsInstance(metadata, dict)
        self.assertIn("schema_hints", metadata)
        self.assertIn("quality_hints", metadata)
        self.assertIn("sla_hints", metadata)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_with_zero_limit(self, mock_get_client):
        """Test list_listings() edge case with zero limit"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}
        self.connector._circuit_breaker.call = lambda func: func()

        listings = self.connector.list_listings(limit=0)
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_listings_with_none_limit(self, mock_get_client):
        """Test list_listings() error handling with None limit"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_client.list_data_sets.return_value = {"DataSets": []}
        self.connector._circuit_breaker.call = lambda func: func()

        # Should handle None limit gracefully (may use default)
        try:
            listings = self.connector.list_listings(limit=None)  # type: ignore[arg-type]
            self.assertIsInstance(listings, list)
        except (ValueError, TypeError):
            # Expected if validation is strict
            pass

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_get_listing_with_empty_id(self, mock_get_client):
        """Test get_listing() error handling with empty ID"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises((ValueError, NotFoundError, ConnectionError)):
            self.connector.get_listing("")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_get_listing_with_none_id(self, mock_get_client):
        """Test get_listing() error handling with None ID"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises((ValueError, TypeError, NotFoundError, ConnectionError)):
            self.connector.get_listing(None)  # type: ignore[arg-type]

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_resources_with_empty_listing_id(self, mock_get_client):
        """Test list_resources() error handling with empty listing ID"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises((ValueError, NotFoundError, ConnectionError)):
            self.connector.list_resources("")

    @patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.AWSDataExchangeConnector._get_dataexchange_client"
    )
    def test_list_resources_with_none_listing_id(self, mock_get_client):
        """Test list_resources() error handling with None listing ID"""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        self.connector._circuit_breaker.call = lambda func: func()

        with self.assertRaises((ValueError, TypeError, NotFoundError, ConnectionError)):
            self.connector.list_resources(None)  # type: ignore[arg-type]
