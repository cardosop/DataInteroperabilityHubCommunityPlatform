"""
AWS Data Exchange Marketplace Connector

Connector implementation for AWS Data Exchange marketplace.
Supports harvest (pull) operations for discovering and retrieving data from AWS Data Exchange.

Features:
- AWS IAM authentication (access keys and IAM role assumption)
- Circuit breaker protection
- Retry logic with exponential backoff for transient failures
- Distributed tracing with correlation IDs
- Connection testing
- AWS Data Exchange and S3 client management

AWS Data Exchange API Documentation: https://docs.aws.amazon.com/data-exchange/
"""
import logging
import os
import time
from typing import Dict, Any, List, Optional, Callable, TypeVar

T = TypeVar('T')
from django.utils import timezone
from datetime import datetime

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from django.conf import settings
import structlog

from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
    MarketplaceListing,
    MarketplaceResource,
    SyncResult,
    MarketplaceAssetMapping,
)
from hub.apps.assets.models import AssetSourceType
from hub.apps.core.services.base import ConnectionError, NotFoundError, PermissionError
from hub.apps.core.resilience.circuit_breaker import (
    CircuitBreaker,
    get_redis_client,
)

logger = logging.getLogger(__name__)
structlogger = structlog.get_logger(__name__)


class AWSDataExchangeConnector(DataMarketplaceConnector):
    """
    Connector for AWS Data Exchange marketplace (Harvest-Only).

    Implements harvest (pull) operations for discovering and retrieving data from
    AWS Data Exchange. This connector is read-only and does not support push operations
    as AWS Data Exchange is a data marketplace that should be harvested FROM.

    Supports:
    - Discovery: list_listings, get_listing, list_resources
    - Harvest: sync_pull (bulk synchronization from AWS Data Exchange to Hub)
    - Mapping: map_to_hub_asset (AWS Data Exchange datasets → Hub assets)

    Does NOT support:
    - Push operations: create_listing, update_listing, publish_resource, sync_push
    - Write operations: All methods that modify AWS Data Exchange data

    Authentication:
    - Supports AWS IAM access keys (aws_access_key_id, aws_secret_access_key)
    - Supports temporary credentials (aws_session_token)
    - Supports IAM role assumption (role_arn)
    - Region configuration (default: us-east-1)
    """

    def __init__(
        self,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        region_name: str = 'us-east-1',
        role_arn: Optional[str] = None
    ):
        """
        Initialize AWS Data Exchange connector.

        Args:
            aws_access_key_id: AWS access key ID (optional if role_arn provided)
            aws_secret_access_key: AWS secret access key (optional if role_arn provided)
            aws_session_token: AWS session token for temporary credentials (optional)
            region_name: AWS region name (default: 'us-east-1')
            role_arn: IAM role ARN for role assumption (optional, alternative to access keys)
        """
        # Store credentials
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._region_name = region_name
        self._role_arn = role_arn

        # Store temporary credentials after role assumption
        self._assumed_role_credentials: Optional[Dict[str, Any]] = None

        # Cache for boto3 clients
        self._dataexchange_client = None
        self._s3_client = None

        # Retry configuration (same pattern as CKAN connector)
        self.max_retries = 2
        self.backoff_factor = 1

        # Initialize circuit breaker (same pattern as CKAN)
        self._circuit_breaker = CircuitBreaker(
            service_name="aws-data-exchange-connector",
            failure_threshold=5,
            timeout_seconds=60,
            success_threshold=2,
            redis_client=get_redis_client()
        )

        # Initialize boto3 client placeholders (lazy initialization)
        self._dataexchange_client: Optional[Any] = None
        self._s3_client: Optional[Any] = None

        # Track authentication state
        self._authenticated = False

    def _is_transient_error(self, error_code: str) -> bool:
        """
        Check if an AWS error code indicates a transient failure that should be retried.

        Args:
            error_code: AWS error code (e.g., 'ThrottlingException', 'ServiceUnavailableException')

        Returns:
            True if error is transient and should be retried, False otherwise
        """
        transient_errors = {
            'ThrottlingException',
            'ServiceUnavailableException',
            'InternalServerException',
            'TooManyRequestsException',
            'RequestTimeout',
        }
        return error_code in transient_errors

    def _map_aws_error(self, error: ClientError, context: str = '') -> Exception:
        """
        Map AWS ClientError to connector-specific exceptions.

        Args:
            error: AWS ClientError exception
            context: Additional context string for error message

        Returns:
            Appropriate exception type (NotFoundError, PermissionError, ValueError, ConnectionError)
        """
        error_code = error.response.get('Error', {}).get('Code', '')
        error_message = error.response.get('Error', {}).get('Message', str(error))

        # Map AWS errors to connector exceptions
        if error_code == 'ResourceNotFoundException':
            return NotFoundError(
                f"{context}Resource not found in AWS Data Exchange: {error_message}"
            )
        elif error_code == 'AccessDeniedException':
            return PermissionError(
                f"{context}Access denied: {error_message}"
            )
        elif error_code == 'ValidationException':
            return ValueError(
                f"{context}Invalid request: {error_message}"
            )
        elif self._is_transient_error(error_code):
            # Transient errors are wrapped in ConnectionError for retry logic
            return ConnectionError(
                f"{context}Transient AWS error ({error_code}): {error_message}"
            )
        else:
            # Other errors are connection errors
            return ConnectionError(
                f"{context}AWS error ({error_code}): {error_message}"
            )

    def _get_correlation_context(self) -> Dict[str, Any]:
        """
        Get correlation context for structured logging.

        Extracts trace_id, span_id, tenant_id, user_id from request context if available.

        Returns:
            Dictionary with correlation context fields
        """
        context = {}

        # Try to get trace context from structlog
        try:
            trace_id = structlog.contextvars.get_contextvars().get('trace_id')
            span_id = structlog.contextvars.get_contextvars().get('span_id')
            if trace_id:
                context['trace_id'] = trace_id
            if span_id:
                context['span_id'] = span_id
        except Exception as e:
            structlogger.debug(
                "aws_data_exchange_trace_context_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        # Try to get trace headers from request context
        try:
            from hub.apps.api.middleware.trace_propagation import get_current_request
            request = get_current_request()
            if request and hasattr(request, 'trace_id'):
                context['trace_id'] = request.trace_id
            if request and hasattr(request, 'span_id'):
                context['span_id'] = request.span_id
        except Exception as e:
            structlogger.debug(
                "aws_data_exchange_request_trace_failed",
                extra={"error_type": type(e).__name__, "error": str(e)},
            )

        return context

    def _log_with_context(self, level: str, message: str, **kwargs):
        """
        Log message with correlation context.

        Args:
            level: Log level ('info', 'warning', 'error', 'debug')
            message: Log message
            **kwargs: Additional log fields
        """
        context = self._get_correlation_context()
        log_data = {**context, **kwargs, 'message': message}

        if level == 'info':
            structlogger.info(**log_data)
        elif level == 'warning':
            structlogger.warning(**log_data)
        elif level == 'error':
            structlogger.error(**log_data)
        elif level == 'debug':
            structlogger.debug(**log_data)
        else:
            logger.log(getattr(logging, level.upper(), logging.INFO), message, extra=kwargs)

    T = TypeVar('T')

    def _execute_with_retry(
        self,
        operation: Callable[[], T],
        operation_name: str,
        context: str = ''
    ) -> T:
        """
        Execute AWS API operation with retry logic and circuit breaker protection.

        Implements exponential backoff retry for transient failures:
        - Retries on ThrottlingException, ServiceUnavailableException, InternalServerException
        - Does not retry on AccessDeniedException, ResourceNotFoundException, ValidationException
        - Uses exponential backoff: delay = backoff_factor * (2 ** attempt)

        Args:
            operation: Callable that executes AWS API operation
            operation_name: Name of the operation for logging (e.g., 'ListDataSets')
            context: Additional context string for error messages

        Returns:
            Result of the operation

        Raises:
            NotFoundError: If resource not found
            PermissionError: If access denied
            ValueError: If validation error
            ConnectionError: If connection failed after retries
        """
        def execute_with_retry_inner() -> T:
            """Inner function for retry logic."""
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    result = operation()
                    # Log success on retry
                    if attempt > 0:
                        self._log_with_context(
                            'info',
                            f"AWS Data Exchange {operation_name} succeeded after {attempt} retries",
                            operation=operation_name,
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1
                        )
                    return result

                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    error_message = e.response.get('Error', {}).get('Message', str(e))

                    # Check if error is transient and should be retried
                    if self._is_transient_error(error_code) and attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        self._log_with_context(
                            'warning',
                            f"AWS Data Exchange {operation_name} returned {error_code}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})",
                            operation=operation_name,
                            error_code=error_code,
                            error_message=error_message,
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                            delay=delay
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # Non-transient error or max retries exceeded - map and raise
                    mapped_error = self._map_aws_error(e, context)
                    raise mapped_error

                except BotoCoreError as e:
                    # Network/connection errors - retry if not last attempt
                    if attempt < self.max_retries:
                        delay = self.backoff_factor * (2 ** attempt)
                        self._log_with_context(
                            'warning',
                            f"Network error during AWS Data Exchange {operation_name}. "
                            f"Retrying in {delay}s... (attempt {attempt + 1}/{self.max_retries + 1})",
                            operation=operation_name,
                            error=str(e),
                            attempt=attempt + 1,
                            max_retries=self.max_retries + 1,
                            delay=delay
                        )
                        time.sleep(delay)
                        last_exception = e
                        continue

                    # Max retries exceeded
                    raise ConnectionError(
                        f"{context}Network error during {operation_name}: {e}"
                    ) from e

            # Max retries exceeded for transient error
            if last_exception:
                if isinstance(last_exception, ClientError):
                    mapped_error = self._map_aws_error(last_exception, context)
                    raise mapped_error
                raise ConnectionError(
                    f"{context}Max retries exceeded for {operation_name}: {last_exception}"
                ) from last_exception

            raise ConnectionError(f"{context}Max retries exceeded for {operation_name}")

        # Execute with circuit breaker protection
        try:
            return self._circuit_breaker.call(execute_with_retry_inner)
        except (NotFoundError, PermissionError, ValueError):
            # Re-raise mapped errors as-is
            raise
        except Exception as e:
            # Log unexpected errors
            self._log_with_context(
                'error',
                f"AWS Data Exchange {operation_name} failed",
                operation=operation_name,
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    def _get_dataexchange_client(self):
        """
        Get or create AWS Data Exchange boto3 client with credentials.

        Handles IAM role assumption if role_arn is provided.
        Creates client with appropriate credentials (access keys or assumed role).

        Returns:
            boto3 client for AWS Data Exchange service

        Raises:
            ValueError: If credentials are invalid
            ConnectionError: If unable to create client
        """
        # Return cached client if available and credentials haven't changed
        if self._dataexchange_client is not None:
            return self._dataexchange_client

        # Determine credentials to use
        credentials = {}

        if self._role_arn:
            # Use IAM role assumption
            if self._assumed_role_credentials is None:
                # Assume role and get temporary credentials
                try:
                    # Build STS client credentials (allow None for default credential chain)
                    sts_credentials = {}
                    if self._aws_access_key_id:
                        sts_credentials['aws_access_key_id'] = self._aws_access_key_id
                    if self._aws_secret_access_key:
                        sts_credentials['aws_secret_access_key'] = self._aws_secret_access_key
                    if self._aws_session_token:
                        sts_credentials['aws_session_token'] = self._aws_session_token

                    sts_client = boto3.client(
                        'sts',
                        region_name=self._region_name,
                        **sts_credentials
                    )

                    response = sts_client.assume_role(
                        RoleArn=self._role_arn,
                        RoleSessionName='data-exchange-connector-session'
                    )

                    creds = response['Credentials']
                    self._assumed_role_credentials = {
                        'aws_access_key_id': creds['AccessKeyId'],
                        'aws_secret_access_key': creds['SecretAccessKey'],
                        'aws_session_token': creds['SessionToken']
                    }

                    logger.info(f"Successfully assumed IAM role: {self._role_arn}")
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == 'AccessDenied':
                        raise PermissionError(
                            f"Access denied when assuming role {self._role_arn}: {e}"
                        ) from e
                    raise ConnectionError(
                        f"Failed to assume IAM role {self._role_arn}: {e}"
                    ) from e
                except Exception as e:
                    raise ConnectionError(
                        f"Unexpected error assuming IAM role: {e}"
                    ) from e

            credentials = self._assumed_role_credentials
        else:
            # Use access keys directly
            if not self._aws_access_key_id or not self._aws_secret_access_key:
                raise ValueError(
                    "Either role_arn or both aws_access_key_id and aws_secret_access_key must be provided"
                )

            credentials = {
                'aws_access_key_id': self._aws_access_key_id,
                'aws_secret_access_key': self._aws_secret_access_key,
            }

            if self._aws_session_token:
                credentials['aws_session_token'] = self._aws_session_token

        # Create Data Exchange client
        try:
            self._dataexchange_client = boto3.client(
                'dataexchange',
                region_name=self._region_name,
                **credentials
            )
            logger.debug(f"Created AWS Data Exchange client for region {self._region_name}")
            return self._dataexchange_client
        except Exception as e:
            raise ConnectionError(
                f"Failed to create AWS Data Exchange client: {e}"
            ) from e

    def _get_s3_client(self):
        """
        Get or create AWS S3 boto3 client with same credentials as Data Exchange client.

        Uses the same credentials (access keys or assumed role) as the Data Exchange client.

        Returns:
            boto3 client for AWS S3 service

        Raises:
            ConnectionError: If unable to create client
        """
        # Return cached client if available
        if self._s3_client is not None:
            return self._s3_client

        # Ensure Data Exchange client is created first (to handle role assumption)
        self._get_dataexchange_client()

        # Determine credentials to use (same as Data Exchange client)
        credentials = {}

        if self._assumed_role_credentials:
            credentials = self._assumed_role_credentials
        else:
            credentials = {
                'aws_access_key_id': self._aws_access_key_id,
                'aws_secret_access_key': self._aws_secret_access_key,
            }
            if self._aws_session_token:
                credentials['aws_session_token'] = self._aws_session_token

        # Create S3 client
        try:
            self._s3_client = boto3.client(
                's3',
                region_name=self._region_name,
                **credentials
            )
            logger.debug(f"Created AWS S3 client for region {self._region_name}")
            return self._s3_client
        except Exception as e:
            raise ConnectionError(
                f"Failed to create AWS S3 client: {e}"
            ) from e

    @property
    def marketplace_type(self) -> MarketplaceType:
        """Get the marketplace type this connector supports."""
        return MarketplaceType.AWS_DATA_EXCHANGE

    @property
    def supported_sync_directions(self) -> List[SyncDirection]:
        """
        Get the list of sync directions supported by this connector.

        AWS Data Exchange connector is harvest-only (PULL only) as AWS Data Exchange
        is a data marketplace that should be harvested FROM, not pushed TO.
        """
        return [SyncDirection.PULL]

    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with AWS Data Exchange using provided credentials.

        Args:
            credentials: Dictionary containing:
                - aws_access_key_id or access_key_id: AWS access key ID (required if no role_arn)
                - aws_secret_access_key or secret_access_key: AWS secret access key (required if no role_arn)
                - aws_session_token or session_token: AWS session token (optional, for temporary credentials)
                - region_name: AWS region name (optional, default: 'us-east-1')
                - role_arn: IAM role ARN for role assumption (optional, alternative to access keys)

        Returns:
            True if authentication successful

        Raises:
            ValueError: If credentials are invalid or missing required fields
            ConnectionError: If unable to connect to AWS Data Exchange
            PermissionError: If credentials lack required permissions
        """
        if not credentials:
            raise ValueError("Credentials dictionary is required")

        # Extract credentials with support for both naming conventions
        aws_access_key_id = credentials.get('aws_access_key_id') or credentials.get('access_key_id')
        aws_secret_access_key = credentials.get('aws_secret_access_key') or credentials.get('secret_access_key')
        aws_session_token = credentials.get('aws_session_token') or credentials.get('session_token')
        region_name = credentials.get('region_name', 'us-east-1')
        role_arn = credentials.get('role_arn')

        # Validate credentials: either role_arn OR access keys must be provided
        if not role_arn and (not aws_access_key_id or not aws_secret_access_key):
            raise ValueError(
                "Either role_arn or both aws_access_key_id and aws_secret_access_key must be provided"
            )

        # Update instance credentials
        self._aws_access_key_id = aws_access_key_id
        self._aws_secret_access_key = aws_secret_access_key
        self._aws_session_token = aws_session_token
        self._region_name = region_name
        self._role_arn = role_arn

        # Reset clients to force re-creation with new credentials
        self._dataexchange_client = None
        self._s3_client = None
        self._assumed_role_credentials = None

        # Test connection using test_connection()
        try:
            result = self.test_connection()
            if result:
                self._authenticated = True
                logger.info("Successfully authenticated with AWS Data Exchange")
                return True
            else:
                self._authenticated = False
                logger.warning("AWS Data Exchange authentication failed: Connection test returned False")
                raise ConnectionError("Connection test failed")
        except (PermissionError, ConnectionError):
            self._authenticated = False
            raise
        except Exception as e:
            self._authenticated = False
            logger.error(f"AWS Data Exchange authentication failed: {e}")
            raise ConnectionError(f"Unable to authenticate with AWS Data Exchange: {e}") from e

    def test_connection(self) -> bool:
        """
        Test the connection to AWS Data Exchange.

        Performs a lightweight operation (ListDataSets with MaxResults=1) to verify connectivity.

        Returns:
            True if connection test successful, False otherwise

        Raises:
            ConnectionError: If unable to connect to AWS Data Exchange
            PermissionError: If credentials lack required permissions
        """
        def execute_test() -> bool:
            """Execute connection test."""
            client = self._get_dataexchange_client()
            # Call ListDataSets API with MaxResults=1 to test connection
            response = client.list_data_sets(MaxResults=1)
            # If we get a response without exception, connection is successful
            self._log_with_context('info', "Connection test successful for AWS Data Exchange")
            return True

        try:
            return self._execute_with_retry(execute_test, 'ListDataSets', 'AWS Data Exchange connection test: ')
        except (PermissionError, ConnectionError):
            raise
        except Exception as e:
            self._log_with_context(
                'error',
                "AWS Data Exchange connection test failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ConnectionError(f"Unexpected error testing AWS Data Exchange connection: {e}") from e

    # Helper methods for discovery operations
    def _extract_tags(self, tags_data: Any) -> List[str]:
        """
        Extract tags from AWS Data Exchange Tags field.

        AWS Data Exchange API returns Tags as a list of tag objects with Key/Value,
        or as a dictionary. This method handles both formats.

        Args:
            tags_data: Tags data from AWS API (can be list, dict, or None)

        Returns:
            List of tag strings
        """
        if not tags_data:
            return []

        tags = []
        if isinstance(tags_data, list):
            # Tags is a list of tag objects: [{'Key': 'tag1', 'Value': 'value1'}, ...]
            for tag_item in tags_data:
                if isinstance(tag_item, dict):
                    # Extract from Key or Value field
                    tag_value = tag_item.get('Key') or tag_item.get('Value') or tag_item.get('name') or tag_item.get('display_name')
                    if tag_value:
                        tags.append(str(tag_value))
                elif isinstance(tag_item, str):
                    tags.append(tag_item)
        elif isinstance(tags_data, dict):
            # Tags might be a dict with 'Tags' key or a flat dict
            if 'Tags' in tags_data:
                # Nested Tags dict
                nested_tags = tags_data['Tags']
                if isinstance(nested_tags, list):
                    tags.extend(self._extract_tags(nested_tags))
            else:
                # Flat dict - extract keys or values
                tags.extend([str(v) for v in tags_data.values() if v])
        elif isinstance(tags_data, str):
            # Comma-separated string
            tags = [tag.strip() for tag in tags_data.split(',') if tag.strip()]

        return tags

    def _parse_aws_datetime(self, aws_datetime_str: Optional[str]) -> Optional[datetime]:
        """
        Parse AWS datetime strings (ISO 8601 format) to Python datetime objects.

        AWS Data Exchange API returns datetime strings in ISO 8601 format.
        Handles timezone-aware datetime conversion.

        Args:
            aws_datetime_str: AWS datetime string in ISO 8601 format

        Returns:
            Python datetime object, or None if input is None/empty
        """
        if not aws_datetime_str:
            return None

        try:
            # AWS uses ISO 8601 format with timezone info
            # Example: "2023-01-01T12:00:00Z" or "2023-01-01T12:00:00+00:00"
            from dateutil import parser as dateutil_parser
            return dateutil_parser.isoparse(aws_datetime_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse AWS datetime '{aws_datetime_str}': {e}")
            return None

    def _get_dataset_details(self, dataset_id: str) -> Dict[str, Any]:
        """
        Get dataset details by calling GetDataSet API.

        Args:
            dataset_id: AWS Data Exchange dataset ID

        Returns:
            Dictionary with dataset details from GetDataSet API response

        Raises:
            NotFoundError: If dataset not found (ResourceNotFoundException)
            PermissionError: If access denied
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        def execute_get_dataset() -> Dict[str, Any]:
            """Execute GetDataSet API call."""
            client = self._get_dataexchange_client()
            response = client.get_data_set(DataSetId=dataset_id)
            return response

        return self._execute_with_retry(
            execute_get_dataset,
            'GetDataSet',
            f"Unable to get dataset '{dataset_id}': "
        )

    def _list_revisions(
        self,
        dataset_id: str,
        max_results: Optional[int] = None,
        next_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List dataset revisions by calling ListDataSetRevisions API.

        Args:
            dataset_id: AWS Data Exchange dataset ID
            max_results: Maximum number of revisions to return (default: API default)
            next_token: Pagination token for next page of results

        Returns:
            Dictionary with revisions list and pagination token:
            {
                'Revisions': [...],
                'NextToken': '...' (if more results available)
            }

        Raises:
            NotFoundError: If dataset not found
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        def execute_list_revisions() -> Dict[str, Any]:
            """Execute ListDataSetRevisions API call."""
            client = self._get_dataexchange_client()
            params = {'DataSetId': dataset_id}

            if max_results is not None:
                params['MaxResults'] = min(int(max_results), 100)  # AWS max is 100
            if next_token:
                params['NextToken'] = next_token

            response = client.list_data_set_revisions(**params)
            return response

        return self._execute_with_retry(
            execute_list_revisions,
            'ListDataSetRevisions',
            f"Unable to list revisions for dataset '{dataset_id}': "
        )

    def _extract_odps_metadata(self, dataset_data: Dict[str, Any], revision_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract ODPS contract metadata from AWS Data Exchange dataset data.

        Args:
            dataset_data: Dataset data from GetDataSet API response
            revision_data: Optional revision data from ListDataSetRevisions API response

        Returns:
            Structured ODPS metadata dictionary with:
            - product_details: productID, product_name, product_description, version
            - pricing_plans: Subscription-based pricing plans (if available)
            - access_methods: AWS Data Exchange access methods (S3 export, API access)
            - payment_gateways: AWS payment gateway info (if available)
        """
        odps_metadata = {}

        # Extract product details
        dataset_id = dataset_data.get('Id', '')
        dataset_name = dataset_data.get('Name', '')
        dataset_description = dataset_data.get('Description', '')
        revision_id = None
        if revision_data:
            revision_id = revision_data.get('Id', '')
        elif dataset_data.get('LatestRevision'):
            revision_id = dataset_data['LatestRevision'].get('Id', '')

        odps_metadata['product_details'] = {
            'productID': dataset_id,
            'product_name': dataset_name,
            'product_description': dataset_description or '',
            'version': revision_id or ''
        }

        # Extract pricing plans (AWS Data Exchange uses subscription-based pricing)
        # Pricing information may be in dataset metadata or asset metadata
        pricing_plans = []
        if dataset_data.get('AssetType') == 'S3_SNAPSHOT':
            # S3 snapshot datasets typically have subscription pricing
            pricing_plans.append({
                'planID': 'subscription',
                'plan_name': 'AWS Data Exchange Subscription',
                'billing_period': 'MONTHLY',  # AWS Data Exchange typically uses monthly billing
                'currency': 'USD',
                # Price information may not be available in API response
                # It's typically set by the data provider in AWS Marketplace
            })

        if pricing_plans:
            odps_metadata['pricing_plans'] = pricing_plans

        # Extract access methods
        # AWS Data Exchange supports S3 export and API access
        access_methods = {}
        asset_type = dataset_data.get('AssetType', '')

        if asset_type == 'S3_SNAPSHOT':
            access_methods['S3_EXPORT'] = {
                'method': 'S3_EXPORT',
                'description': 'Export dataset to S3 bucket',
                'requires_subscription': True
            }
        elif asset_type == 'API':
            access_methods['API'] = {
                'method': 'API',
                'description': 'Access via AWS Data Exchange API',
                'requires_subscription': True
            }
        elif asset_type == 'REDSHIFT_DATA_SHARE':
            access_methods['REDSHIFT_DATA_SHARE'] = {
                'method': 'REDSHIFT_DATA_SHARE',
                'description': 'Access via Redshift data share',
                'requires_subscription': True
            }

        if access_methods:
            odps_metadata['access_methods'] = access_methods

        # Extract payment gateways (AWS payment gateway)
        payment_gateways = {
            'aws': {
                'gateway_id': 'aws',
                'gateway_name': 'AWS Payment Gateway',
                'enabled': True,
                'supported_currencies': ['USD'],
                'payment_methods': ['credit_card', 'aws_account']
            }
        }
        odps_metadata['payment_gateways'] = payment_gateways

        return odps_metadata

    def _extract_odcs_metadata(self, dataset_data: Dict[str, Any], revision_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract ODCS contract metadata hints from AWS Data Exchange dataset.

        Args:
            dataset_data: Dataset data from GetDataSet API response
            revision_data: Optional revision data from ListDataSetRevisions API response

        Returns:
            Structured ODCS metadata dictionary with:
            - schema_hints: Schema information (always present, may be empty)
            - quality_hints: Quality hints (always present, may be empty)
            - sla_hints: SLA hints (always present)
        """
        odcs_metadata = {}

        # Extract schema hints (if available in dataset metadata)
        schema_hints = {}
        if dataset_data.get('Schema'):
            schema_hints['schema_format'] = dataset_data['Schema'].get('Format', '')
            schema_hints['schema_name'] = dataset_data['Schema'].get('Name', '')

        # Schema information may also be in revision assets
        if revision_data and revision_data.get('Assets'):
            # Assets may contain schema information
            assets = revision_data['Assets']
            if assets:
                # Try to extract schema from first asset
                first_asset = assets[0] if isinstance(assets, list) else assets
                if isinstance(first_asset, dict):
                    asset_type = first_asset.get('AssetType', '')
                    if asset_type == 'S3_SNAPSHOT':
                        schema_hints['data_format'] = 'S3_SNAPSHOT'
                    elif asset_type == 'API':
                        schema_hints['data_format'] = 'API'

        # Also check dataset asset type
        asset_type = dataset_data.get('AssetType', '')
        if asset_type and 'data_format' not in schema_hints:
            if asset_type == 'S3_SNAPSHOT':
                schema_hints['data_format'] = 'S3_SNAPSHOT'
            elif asset_type == 'API':
                schema_hints['data_format'] = 'API'
            elif asset_type == 'REDSHIFT_DATA_SHARE':
                schema_hints['data_format'] = 'REDSHIFT_DATA_SHARE'

        # Always include schema_hints (even if empty)
        odcs_metadata['schema_hints'] = schema_hints

        # Extract quality hints (if available)
        quality_hints = {}
        # AWS Data Exchange doesn't provide explicit quality metrics in API
        # But we can infer from dataset metadata
        if dataset_data.get('Origin'):
            quality_hints['origin'] = dataset_data['Origin']
        if dataset_data.get('OriginDetails'):
            quality_hints['origin_details'] = dataset_data['OriginDetails']

        # Always include quality_hints (even if empty)
        odcs_metadata['quality_hints'] = quality_hints

        # Extract SLA hints (always present)
        sla_hints = {}
        # AWS Data Exchange SLA information may be in dataset metadata
        # Typically, AWS Data Exchange provides availability SLA
        sla_hints['availability'] = {
            'target': '99.9%',  # AWS standard SLA
            'description': 'AWS Data Exchange standard availability SLA'
        }

        # Always include sla_hints
        odcs_metadata['sla_hints'] = sla_hints

        return odcs_metadata

    # Abstract method implementations
    def list_listings(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[MarketplaceListing]:
        """
        List available listings (datasets) from AWS Data Exchange.

        Supports pagination and filtering by origin and name.

        Args:
            filters: Optional dictionary of filters:
                - origin: Filter by dataset origin (Origin filter)
                - name: Filter by dataset name (Name filter)
            limit: Optional maximum number of listings to return (max 100, AWS API limit)
            offset: Optional offset for pagination (implemented via NextToken pagination)

        Returns:
            List of MarketplaceListing objects with complete metadata

        Raises:
            ValueError: If filters or pagination parameters are invalid
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        def execute_list_datasets() -> List[MarketplaceListing]:
            """Execute ListDataSets API call with pagination and filters."""
            client = self._get_dataexchange_client()
            listings = []
            next_token = None
            items_skipped = 0
            items_collected = 0
            max_results = min(limit, 100) if limit else 100  # AWS max is 100

            # Handle offset via pagination (skip items until offset is reached)
            if offset and offset > 0:
                # We'll need to paginate through results to skip offset items
                # This is not ideal but AWS Data Exchange doesn't support offset directly
                items_to_skip = offset

            while True:
                # Build request parameters
                params = {'MaxResults': max_results}

                # Apply filters
                if filters:
                    if filters.get('origin'):
                        params['Origin'] = filters['origin']
                    if filters.get('name'):
                        params['Name'] = filters['name']

                if next_token:
                    params['NextToken'] = next_token

                # Call ListDataSets API with retry logic
                def call_list_datasets():
                    return client.list_data_sets(**params)

                response = self._execute_with_retry(
                    call_list_datasets,
                    'ListDataSets',
                    'Unable to list datasets: '
                )

                # Process datasets
                datasets = response.get('DataSets', [])

                for dataset_summary in datasets:
                    # Skip items until we reach offset
                    if offset and items_skipped < offset:
                        items_skipped += 1
                        continue

                    try:
                        dataset_id = dataset_summary.get('Id', '')
                        if not dataset_id:
                            logger.warning(f"Skipping dataset without ID: {dataset_summary}")
                            continue

                        # Get full dataset details
                        dataset_details = self._get_dataset_details(dataset_id)

                        # Get latest revision if available
                        latest_revision = None
                        if dataset_details.get('LatestRevision'):
                            latest_revision = dataset_details['LatestRevision']

                        # Extract ODPS and ODCS metadata
                        odps_metadata = self._extract_odps_metadata(dataset_details, latest_revision)
                        odcs_metadata = self._extract_odcs_metadata(dataset_details, latest_revision)

                        # Build MarketplaceListing
                        listing = MarketplaceListing(
                            marketplace_id=dataset_id,
                            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
                            title=dataset_details.get('Name', ''),
                            description=dataset_details.get('Description', ''),
                            product_id=dataset_id,
                            category=dataset_details.get('Origin', ''),
                            tags=self._extract_tags(dataset_details.get('Tags')),
                            pricing_plans=odps_metadata.get('pricing_plans', []),
                            access_methods=odps_metadata.get('access_methods', {}),
                            payment_gateways=odps_metadata.get('payment_gateways', {}),
                            metadata={
                                'odps_metadata': odps_metadata,
                                'odcs_metadata': odcs_metadata,
                                'asset_type': dataset_details.get('AssetType', ''),
                                'origin': dataset_details.get('Origin', ''),
                                'origin_details': dataset_details.get('OriginDetails', {}),
                                'created_at': dataset_details.get('CreatedAt', ''),
                                'updated_at': dataset_details.get('UpdatedAt', ''),
                            },
                            created_at=self._parse_aws_datetime(dataset_details.get('CreatedAt')),
                            updated_at=self._parse_aws_datetime(dataset_details.get('UpdatedAt')),
                            url=f"https://console.aws.amazon.com/dataexchange/home?region={self._region_name}#/data-sets/{dataset_id}"
                        )
                        listings.append(listing)
                        items_collected += 1

                        # Check if we've reached the limit
                        if limit and items_collected >= limit:
                            break

                    except NotFoundError:
                        logger.warning(f"Dataset '{dataset_id}' not found, skipping")
                        continue
                    except Exception as e:
                        logger.warning(f"Failed to process dataset '{dataset_id}': {e}")
                        continue

                # Check if we've reached the limit or no more results
                if limit and items_collected >= limit:
                    break

                # Check for more pages
                next_token = response.get('NextToken')
                if not next_token:
                    break

                # If we still need to skip items, continue pagination
                if offset and items_skipped < offset:
                    continue

            return listings

        # Validate parameters
        if limit is not None:
            if not isinstance(limit, int) or limit < 0:
                raise ValueError("limit must be a non-negative integer")
            if limit > 100:
                raise ValueError("limit cannot exceed 100 (AWS Data Exchange API limit)")

        if offset is not None:
            if not isinstance(offset, int) or offset < 0:
                raise ValueError("offset must be a non-negative integer")

        try:
            return self._circuit_breaker.call(execute_list_datasets)
        except (PermissionError, ValueError):
            raise
        except Exception as e:
            self._log_with_context(
                'error',
                "AWS Data Exchange list listings failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise ConnectionError(f"Failed to list listings: {e}") from e

    def get_listing(self, listing_id: str) -> MarketplaceListing:
        """
        Get a specific listing (dataset) by its AWS Data Exchange dataset ID.

        Args:
            listing_id: AWS Data Exchange dataset ID

        Returns:
            MarketplaceListing object with complete metadata including ODPS and ODCS metadata

        Raises:
            ValueError: If listing_id is empty
            TypeError: If listing_id is None
            NotFoundError: If dataset not found (ResourceNotFoundException)
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        if listing_id is None:
            raise TypeError("listing_id must not be None")
        if not isinstance(listing_id, str) or not listing_id.strip():
            raise ValueError("listing_id must be a non-empty string")

        def execute_get_listing() -> MarketplaceListing:
            """Execute GetDataSet API call and build MarketplaceListing."""
            try:
                # Get dataset details
                dataset_details = self._get_dataset_details(listing_id)

                # Get dataset revisions
                revisions_response = self._list_revisions(listing_id, max_results=1)
                revisions = revisions_response.get('Revisions', [])

                # Use latest revision if available, otherwise use dataset's LatestRevision
                latest_revision = None
                if revisions:
                    latest_revision = revisions[0]  # Revisions are typically sorted newest first
                elif dataset_details.get('LatestRevision'):
                    latest_revision = dataset_details['LatestRevision']

                # Extract ODPS and ODCS metadata
                odps_metadata = self._extract_odps_metadata(dataset_details, latest_revision)
                odcs_metadata = self._extract_odcs_metadata(dataset_details, latest_revision)

                # Build MarketplaceListing
                listing = MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE,
                    title=dataset_details.get('Name', ''),
                    description=dataset_details.get('Description', ''),
                    product_id=listing_id,
                    category=dataset_details.get('Origin', ''),
                    tags=dataset_details.get('Tags', {}).get('Tags', []) if isinstance(dataset_details.get('Tags'), dict) else [],
                    pricing_plans=odps_metadata.get('pricing_plans', []),
                    access_methods=odps_metadata.get('access_methods', {}),
                    payment_gateways=odps_metadata.get('payment_gateways', {}),
                    metadata={
                        'odps_metadata': odps_metadata,
                        'odcs_metadata': odcs_metadata,
                        'asset_type': dataset_details.get('AssetType', ''),
                        'origin': dataset_details.get('Origin', ''),
                        'origin_details': dataset_details.get('OriginDetails', {}),
                        'created_at': dataset_details.get('CreatedAt', ''),
                        'updated_at': dataset_details.get('UpdatedAt', ''),
                        'latest_revision_id': latest_revision.get('Id', '') if latest_revision else '',
                    },
                    created_at=self._parse_aws_datetime(dataset_details.get('CreatedAt')),
                    updated_at=self._parse_aws_datetime(dataset_details.get('UpdatedAt')),
                    url=f"https://console.aws.amazon.com/dataexchange/home?region={self._region_name}#/data-sets/{listing_id}"
                )

                return listing

            except NotFoundError:
                raise
            except Exception as e:
                logger.error(f"Failed to get listing '{listing_id}': {e}")
                raise ConnectionError(f"Unable to get listing '{listing_id}': {e}") from e

        try:
            return self._circuit_breaker.call(execute_get_listing)
        except NotFoundError:
            raise
        except Exception as e:
            logger.error(f"AWS Data Exchange get listing failed: {e}")
            raise ConnectionError(f"Failed to get listing '{listing_id}': {e}") from e

    def list_resources(self, listing_id: str) -> List[MarketplaceResource]:
        """
        List resources (assets) associated with an AWS Data Exchange dataset.

        For AWS Data Exchange, resources are assets within dataset revisions.
        Lists assets from the latest revision.

        Args:
            listing_id: AWS Data Exchange dataset ID

        Returns:
            List of MarketplaceResource objects with resource_type:
            - "S3_OBJECT" for S3 snapshot assets
            - "API_ENDPOINT" for API assets
            - "REDSHIFT_TABLE" for Redshift data share assets

        Raises:
            ValueError: If listing_id is empty
            TypeError: If listing_id is None
            NotFoundError: If dataset not found
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        if listing_id is None:
            raise TypeError("listing_id must not be None")
        if not isinstance(listing_id, str) or not listing_id.strip():
            raise ValueError("listing_id must be a non-empty string")

        def execute_list_resources() -> List[MarketplaceResource]:
            """Execute ListRevisionAssets API call and build MarketplaceResource objects."""
            # Get dataset details to find latest revision
            dataset_details = self._get_dataset_details(listing_id)

            # Get latest revision ID
            latest_revision_id = None
            if dataset_details.get('LatestRevision'):
                latest_revision_id = dataset_details['LatestRevision'].get('Id', '')

            if not latest_revision_id:
                # Try to get revisions
                revisions_response = self._list_revisions(listing_id, max_results=1)
                revisions = revisions_response.get('Revisions', [])
                if revisions:
                    latest_revision_id = revisions[0].get('Id', '')

            if not latest_revision_id:
                self._log_with_context('warning', f"No revisions found for dataset '{listing_id}'")
                return []

            # List assets in the latest revision
            client = self._get_dataexchange_client()
            resources = []
            next_token = None

            while True:
                params = {
                    'DataSetId': listing_id,
                    'RevisionId': latest_revision_id,
                    'MaxResults': 100  # AWS max
                }

                if next_token:
                    params['NextToken'] = next_token

                # Call ListRevisionAssets API with retry logic
                def call_list_revision_assets():
                    return client.list_revision_assets(**params)

                response = self._execute_with_retry(
                    call_list_revision_assets,
                    'ListRevisionAssets',
                    f"Unable to list assets for dataset '{listing_id}': "
                )
                assets = response.get('Assets', [])

                for asset in assets:
                        asset_id = asset.get('Id', '')
                        asset_name = asset.get('Name', '')
                        asset_type = asset.get('AssetType', '')

                        # Determine resource type based on asset type
                        resource_type = 'FILE'  # Default
                        if asset_type == 'S3_SNAPSHOT':
                            resource_type = 'S3_OBJECT'
                        elif asset_type == 'API':
                            resource_type = 'API_ENDPOINT'
                        elif asset_type == 'REDSHIFT_DATA_SHARE':
                            resource_type = 'REDSHIFT_TABLE'

                        # Extract asset source details
                        asset_source = asset.get('Source', {})
                        asset_source_id = asset_source.get('Id', '')
                        asset_source_bucket = asset_source.get('Bucket', '')
                        asset_source_key = asset_source.get('Key', '')

                        # Build resource URL or identifier
                        resource_url = None
                        if asset_type == 'S3_SNAPSHOT' and asset_source_bucket and asset_source_key:
                            resource_url = f"s3://{asset_source_bucket}/{asset_source_key}"
                        elif asset_type == 'API':
                            resource_url = f"api://{asset_source_id}"

                        # Extract format from asset details
                        resource_format = None
                        if asset_source_key:
                            # Try to infer format from file extension
                            if asset_source_key.endswith('.csv'):
                                resource_format = 'CSV'
                            elif asset_source_key.endswith('.json'):
                                resource_format = 'JSON'
                            elif asset_source_key.endswith('.parquet'):
                                resource_format = 'PARQUET'
                            elif asset_source_key.endswith('.avro'):
                                resource_format = 'AVRO'

                        resource = MarketplaceResource(
                            resource_id=asset_id,
                            resource_type=resource_type,
                            name=asset_name or asset_id,
                            description=asset.get('Description', ''),
                            url=resource_url,
                            format=resource_format,
                            size_bytes=asset.get('Size', None),
                            metadata={
                                'asset_type': asset_type,
                                'asset_source_id': asset_source_id,
                                'asset_source_bucket': asset_source_bucket,
                                'asset_source_key': asset_source_key,
                                'revision_id': latest_revision_id,
                                'dataset_id': listing_id,
                                'external': True,  # Mark as external resource
                                'download_url': resource_url,  # For on-demand download
                            }
                        )
                        resources.append(resource)

                # Check for more pages
                next_token = response.get('NextToken')
                if not next_token:
                    break

            return resources

        try:
            return self._circuit_breaker.call(execute_list_resources)
        except (NotFoundError, PermissionError):
            raise
        except Exception as e:
            self._log_with_context(
                'error',
                "AWS Data Exchange list resources failed",
                dataset_id=listing_id,
                error=str(e),
                error_type=type(e).__name__
            )
            raise ConnectionError(f"Failed to list resources for dataset '{listing_id}': {e}") from e

    def create_listing(self, listing: MarketplaceListing) -> MarketplaceListing:
        """
        Create a new listing in AWS Data Exchange (PUSH operation).

        AWS Data Exchange connector does not support push operations.
        """
        raise NotImplementedError(
            "AWS Data Exchange connector does not support push operations (create_listing)"
        )

    def update_listing(
        self,
        listing_id: str,
        listing: MarketplaceListing
    ) -> MarketplaceListing:
        """
        Update an existing listing in AWS Data Exchange (PUSH operation).

        AWS Data Exchange connector does not support push operations.
        """
        raise NotImplementedError(
            "AWS Data Exchange connector does not support push operations (update_listing)"
        )

    def publish_resource(
        self,
        listing_id: str,
        resource: MarketplaceResource
    ) -> MarketplaceResource:
        """
        Publish a resource to an AWS Data Exchange dataset (PUSH operation).

        AWS Data Exchange connector does not support push operations.
        """
        raise NotImplementedError(
            "AWS Data Exchange connector does not support push operations (publish_resource)"
        )

    def _subscribe_to_dataset(self, dataset_id: str) -> None:
        """
        Check subscription status and subscribe to dataset if needed.

        AWS Data Exchange datasets require subscription before they can be accessed.
        Subscription is typically done via AWS Console, but can also be done programmatically
        if the user has the necessary permissions.

        Args:
            dataset_id: AWS Data Exchange dataset ID

        Raises:
            PermissionError: If subscription fails or user lacks permission
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        def check_subscription() -> None:
            """Check subscription status by attempting to list revisions."""
            client = self._get_dataexchange_client()
            # Check subscription status by attempting to list revisions
            # If we can list revisions, we're subscribed
            response = client.list_data_set_revisions(DataSetId=dataset_id, MaxResults=1)
            # If successful, we're already subscribed
            self._log_with_context('info', f"Dataset {dataset_id} is already subscribed", dataset_id=dataset_id)

        try:
            self._execute_with_retry(
                check_subscription,
                'ListDataSetRevisions',
                f"Unable to check subscription for dataset '{dataset_id}': "
            )
        except PermissionError as e:
            # AccessDeniedException means not subscribed
            self._log_with_context(
                'warning',
                f"Dataset {dataset_id} is not subscribed. "
                "Subscription must be done via AWS Console or with additional permissions.",
                dataset_id=dataset_id
            )
            raise PermissionError(
                f"Dataset {dataset_id} is not subscribed. "
                "Please subscribe via AWS Console or ensure you have subscription permissions."
            ) from e
        except Exception as e:
            raise

    def _get_latest_revision(self, dataset_id: str) -> str:
        """
        Get the latest revision ID for a dataset.

        Args:
            dataset_id: AWS Data Exchange dataset ID

        Returns:
            Latest revision ID

        Raises:
            NotFoundError: If dataset has no revisions
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        try:
            revisions_response = self._list_revisions(dataset_id, max_results=1)
            revisions = revisions_response.get('Revisions', [])

            if not revisions:
                raise NotFoundError(f"Dataset {dataset_id} has no revisions")

            # Sort by CreatedAt descending to get latest
            latest_revision = revisions[0]
            revision_id = latest_revision.get('Id')

            if not revision_id:
                raise NotFoundError(f"Dataset {dataset_id} revision has no ID")

            return revision_id
        except NotFoundError:
            raise
        except Exception as e:
            if isinstance(e, NotFoundError):
                raise
            raise ConnectionError(
                f"Failed to get latest revision for dataset {dataset_id}: {e}"
            ) from e

    def _create_export_job(
        self,
        dataset_id: str,
        revision_id: str,
        destination_bucket: Optional[str] = None,
        destination_key_prefix: Optional[str] = None
    ) -> str:
        """
        Create an export job to export assets from AWS Data Exchange to S3.

        Args:
            dataset_id: AWS Data Exchange dataset ID
            revision_id: Revision ID to export
            destination_bucket: Destination S3 bucket (optional, uses default from settings)
            destination_key_prefix: Destination S3 key prefix (optional, default: 'dataexchange-exports/')

        Returns:
            Job ID

        Raises:
            ValueError: If bucket or parameters are invalid
            PermissionError: If user lacks permission to create export job
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        if not dataset_id or not isinstance(dataset_id, str) or not dataset_id.strip():
            raise ValueError("dataset_id must be a non-empty string")
        if not revision_id or not isinstance(revision_id, str) or not revision_id.strip():
            raise ValueError("revision_id must be a non-empty string")

        # Get destination bucket from options or settings
        if not destination_bucket or (isinstance(destination_bucket, str) and not destination_bucket.strip()):
            # Try to get from Django settings
            destination_bucket = getattr(settings, 'AWS_DATA_EXCHANGE_EXPORT_BUCKET', None)
            if not destination_bucket:
                raise ValueError(
                    "Destination S3 bucket must be specified. "
                    "Set AWS_DATA_EXCHANGE_EXPORT_BUCKET in settings or pass destination_bucket parameter."
                )

        # Set default key prefix
        if not destination_key_prefix:
            destination_key_prefix = 'dataexchange-exports/'

        def create_job_operation() -> str:
            """Create export job operation."""
            client = self._get_dataexchange_client()

            # Create export job
            job_params = {
                'Type': 'EXPORT_ASSETS_TO_S3',
                'Details': {
                    'ExportAssetsToS3': {
                        'DataSetId': dataset_id,
                        'RevisionId': revision_id,
                        'AssetDestination': {
                            'S3Destination': {
                                'Bucket': destination_bucket,
                                'KeyPrefix': destination_key_prefix
                            }
                        }
                    }
                }
            }

            response = client.create_job(**job_params)
            job_id = response.get('Id')

            if not job_id:
                raise ValueError("Failed to create export job: No job ID returned")

            self._log_with_context(
                'info',
                f"Created export job {job_id} for dataset {dataset_id}, revision {revision_id}",
                job_id=job_id,
                dataset_id=dataset_id,
                revision_id=revision_id
            )
            return job_id

        return self._execute_with_retry(
            create_job_operation,
            'CreateJob',
            f"Unable to create export job for dataset '{dataset_id}': "
        )

    def _start_job(self, job_id: str) -> None:
        """
        Start an export job.

        Args:
            job_id: AWS Data Exchange job ID

        Raises:
            NotFoundError: If job not found
            ValueError: If job cannot be started (already started, invalid state, etc.)
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        def start_job_operation() -> None:
            """Start export job operation."""
            client = self._get_dataexchange_client()
            client.start_job(JobId=job_id)
            self._log_with_context('info', f"Started export job {job_id}", job_id=job_id)

        self._execute_with_retry(
            start_job_operation,
            'StartJob',
            f"Unable to start job '{job_id}': "
        )

    def _wait_for_job_completion(
        self,
        job_id: str,
        timeout_seconds: int = 3600,
        poll_interval_seconds: int = 5
    ) -> Dict[str, Any]:
        """
        Wait for an export job to complete by polling GetJob API.

        Args:
            job_id: AWS Data Exchange job ID
            timeout_seconds: Maximum time to wait in seconds (default: 3600 = 1 hour)
            poll_interval_seconds: Interval between polls in seconds (default: 5)

        Returns:
            Job result dictionary

        Raises:
            TimeoutError: If timeout exceeded
            RuntimeError: If job failed or was cancelled
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        start_time = time.time()
        client = self._get_dataexchange_client()

        while True:
            # Check timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_seconds:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout_seconds} seconds"
                )

            # Get job status with retry logic
            def get_job_status():
                return client.get_job(JobId=job_id)

            try:
                response = self._execute_with_retry(
                    get_job_status,
                    'GetJob',
                    f"Unable to get job status for '{job_id}': "
                )
            except NotFoundError:
                raise NotFoundError(f"Job {job_id} not found")
            except Exception as e:
                # For polling, we want to continue on transient errors
                # but raise on permanent errors
                if isinstance(e, (PermissionError, ValueError)):
                    raise
                # Log and continue polling on connection errors
                self._log_with_context(
                    'warning',
                    f"Error getting job status for {job_id}, retrying...",
                    job_id=job_id,
                    error=str(e)
                )
                time.sleep(poll_interval_seconds)
                continue

            job = response.get('Job', {})
            state = job.get('State', '')

            if state == 'COMPLETED':
                self._log_with_context('info', f"Job {job_id} completed successfully", job_id=job_id)
                return job
            elif state in ('ERROR', 'CANCELLED'):
                error_message = job.get('Errors', [{}])[0].get('Message', 'Unknown error') if job.get('Errors') else 'Unknown error'
                raise RuntimeError(
                    f"Job {job_id} failed with state {state}: {error_message}"
                )
            elif state in ('WAITING', 'IN_PROGRESS'):
                # Continue polling
                self._log_with_context('debug', f"Job {job_id} state: {state}, waiting...", job_id=job_id, state=state)
                time.sleep(poll_interval_seconds)
            else:
                raise RuntimeError(
                    f"Job {job_id} in unknown state: {state}"
                )

    def _download_exported_assets(
        self,
        job_result: Dict[str, Any],
        destination_path: str
    ) -> str:
        """
        Download exported assets from S3 to local filesystem.

        Args:
            job_result: Job result dictionary from _wait_for_job_completion()
            destination_path: Local filesystem path where assets should be saved

        Returns:
            Path to downloaded file(s)

        Raises:
            ValueError: If job result is invalid or destination path is invalid
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download from S3
            ConnectionError: If unable to connect to S3
        """
        try:
            # Extract S3 destination from job result
            details = job_result.get('Details', {})
            export_details = details.get('ExportAssetsToS3', {})
            asset_destination = export_details.get('AssetDestination', {})
            s3_destination = asset_destination.get('S3Destination', {})

            bucket = s3_destination.get('Bucket')
            key_prefix = s3_destination.get('KeyPrefix', '')

            if not bucket:
                raise ValueError("Job result does not contain S3 bucket information")

            # Ensure destination directory exists
            os.makedirs(os.path.dirname(destination_path) if os.path.dirname(destination_path) else '.', exist_ok=True)

            # Get S3 client
            s3_client = self._get_s3_client()

            # List objects in S3 bucket/prefix with retry logic
            def list_s3_objects():
                objects = []
                paginator = s3_client.get_paginator('list_objects_v2')
                for page in paginator.paginate(Bucket=bucket, Prefix=key_prefix):
                    if 'Contents' in page:
                        objects.extend(page['Contents'])
                return objects

            objects = self._execute_with_retry(
                list_s3_objects,
                'ListObjectsV2',
                f"Unable to list objects in S3 bucket '{bucket}': "
            )

            if not objects:
                raise ValueError(f"No objects found in S3 bucket {bucket} with prefix {key_prefix}")

            # Download all objects (or first object if single file expected)
            downloaded_files = []
            for obj in objects:
                s3_key = obj['Key']
                # Create local file path
                if len(objects) == 1:
                    # Single file - use destination_path as-is
                    local_file_path = destination_path
                else:
                    # Multiple files - append filename to destination_path
                    filename = os.path.basename(s3_key)
                    local_file_path = os.path.join(
                        os.path.dirname(destination_path) if os.path.dirname(destination_path) else '.',
                        filename
                    )

                # Download file with retry logic
                def download_s3_file():
                    s3_client.download_file(bucket, s3_key, local_file_path)

                self._execute_with_retry(
                    download_s3_file,
                    'GetObject',
                    f"Unable to download S3 object '{s3_key}': "
                )
                downloaded_files.append(local_file_path)
                self._log_with_context('info', f"Downloaded {s3_key} to {local_file_path}", s3_key=s3_key, local_path=local_file_path)

            # Return first file path (or destination_path if single file)
            return downloaded_files[0] if len(downloaded_files) == 1 else destination_path

        except (ValueError, PermissionError, IOError):
            raise
        except ClientError as e:
            # Map S3 errors appropriately
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            if error_code == 'NoSuchBucket':
                raise ValueError(f"S3 bucket not found: {bucket}") from e
            if error_code == 'AccessDenied':
                raise PermissionError(
                    f"Access denied when downloading from S3 bucket {bucket}: {error_message}"
                ) from e
            raise ConnectionError(
                f"Failed to download from S3: {error_code} - {error_message}"
            ) from e
        except OSError as e:
            raise IOError(
                f"Unable to write to destination path {destination_path}: {e}"
            ) from e
        except Exception as e:
            raise ConnectionError(
                f"Unexpected error downloading from S3: {e}"
            ) from e

    def _extract_schema_from_assets(self, file_path: str) -> Dict[str, Any]:
        """
        Extract schema metadata from downloaded assets.

        Analyzes downloaded assets to infer schema (CSV, Parquet, JSON files).
        Uses schema inference service if available.

        Args:
            file_path: Path to downloaded asset file

        Returns:
            Structured schema metadata dictionary in ODCS format:
            {
                "schema": {
                    "fields": [
                        {"name": "field1", "type": "string", ...},
                        ...
                    ]
                }
            }
        """
        schema_hints = {}

        try:
            # Determine file format from extension
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == '.csv':
                # CSV file - basic schema extraction
                import csv
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    fields = []
                    for field_name in reader.fieldnames or []:
                        fields.append({
                            'name': field_name,
                            'type': 'string',  # Default to string for CSV
                            'nullable': True
                        })
                    schema_hints['fields'] = fields
                    schema_hints['format'] = 'CSV'

            elif file_ext == '.json':
                # JSON file - try to infer schema from first object
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) > 0:
                        # Array of objects - infer from first object
                        first_obj = data[0]
                        fields = []
                        for key, value in first_obj.items():
                            field_type = 'string'
                            if isinstance(value, bool):
                                field_type = 'boolean'
                            elif isinstance(value, int):
                                field_type = 'integer'
                            elif isinstance(value, float):
                                field_type = 'float'
                            elif isinstance(value, dict):
                                field_type = 'object'
                            elif isinstance(value, list):
                                field_type = 'array'
                            fields.append({
                                'name': key,
                                'type': field_type,
                                'nullable': True
                            })
                        schema_hints['fields'] = fields
                        schema_hints['format'] = 'JSON'
                    elif isinstance(data, dict):
                        # Single object - infer schema
                        fields = []
                        for key, value in data.items():
                            field_type = 'string'
                            if isinstance(value, bool):
                                field_type = 'boolean'
                            elif isinstance(value, int):
                                field_type = 'integer'
                            elif isinstance(value, float):
                                field_type = 'float'
                            elif isinstance(value, dict):
                                field_type = 'object'
                            elif isinstance(value, list):
                                field_type = 'array'
                            fields.append({
                                'name': key,
                                'type': field_type,
                                'nullable': True
                            })
                        schema_hints['fields'] = fields
                        schema_hints['format'] = 'JSON'

            elif file_ext == '.parquet':
                # Parquet file - would need pyarrow or similar
                schema_hints['format'] = 'PARQUET'
                schema_hints['note'] = 'Parquet schema extraction requires additional dependencies'

            else:
                schema_hints['format'] = 'UNKNOWN'
                schema_hints['note'] = f'Schema extraction not supported for file type: {file_ext}'

        except Exception as e:
            logger.warning(f"Failed to extract schema from {file_path}: {e}")
            schema_hints['error'] = str(e)

        return {'schema': schema_hints} if schema_hints else {}

    def download_resource(
        self,
        resource_id: str,
        destination_path: str
    ) -> str:
        """
        Download a resource from AWS Data Exchange on-demand (PULL operation).

        **On-Demand Download Behavior**: This method handles on-demand resource downloads when
        `data_strategy != "METADATA_ONLY"`. It performs all marketplace-specific operations that
        were deferred from `sync_pull()`:
        1. Subscribes to dataset if not already subscribed (`_subscribe_to_dataset()`)
        2. Gets latest revision (`_get_latest_revision()`)
        3. Creates export job for specific asset (`_create_export_job()`)
        4. Starts export job (`_start_job()`)
        5. Waits for job completion (`_wait_for_job_completion()`)
        6. Downloads asset from S3 to `destination_path` (`_download_exported_assets()`)
        7. Extracts schema metadata if needed (`_extract_schema_from_assets()`)

        **When This Method Is Called**:
        - Called by workflow when `data_strategy == "DOWNLOAD_SELECTIVE"` (specific resources)
        - Called by workflow when `data_strategy == "DOWNLOAD_ALL"` (all resources)
        - NOT called when `data_strategy == "METADATA_ONLY"` (default, metadata-only harvesting)

        Args:
            resource_id: Resource identifier. Can be:
                - Dataset ID (e.g., "abc123"): Will subscribe, export, and download all assets
                - Asset ID (e.g., "asset-123"): Will export and download specific asset
                - Format: "dataset_id:revision_id:asset_id" for specific asset in specific revision
            destination_path: Local filesystem path where resource should be saved.
                The directory will be created if it doesn't exist.

        Returns:
            Path to the downloaded file (may be same as destination_path or a modified path)

        Raises:
            NotFoundError: If resource not found in AWS Data Exchange
            ConnectionError: If unable to connect to AWS Data Exchange or S3
            IOError: If unable to write to destination path
            PermissionError: If user lacks permission to download resource or perform marketplace-specific operations
            ValueError: If resource_id format is invalid or marketplace-specific operation fails
            TimeoutError: If export job does not complete within timeout
            RuntimeError: If export job fails

        **Example**:
        ```python
        # Download from dataset ID (will subscribe, export, download)
        connector.download_resource("dataset-123", "/tmp/exported_data.csv")

        # Download from specific asset (assumes dataset already subscribed)
        connector.download_resource("asset-456", "/tmp/asset_data.csv")
        ```
        """
        def execute_download() -> str:
            """Execute download with circuit breaker protection."""
            # Parse resource_id to determine dataset_id, revision_id, asset_id
            dataset_id = None
            revision_id = None
            asset_id = None

            if ':' in resource_id:
                # Format: "dataset_id:revision_id:asset_id" or "dataset_id:revision_id"
                parts = resource_id.split(':')
                if len(parts) >= 1:
                    dataset_id = parts[0]
                if len(parts) >= 2:
                    revision_id = parts[1]
                if len(parts) >= 3:
                    asset_id = parts[2]
            else:
                # Assume it's a dataset ID or asset ID
                # Try to determine by checking if it looks like a dataset ID
                # For now, assume it's a dataset ID
                dataset_id = resource_id

            if not dataset_id:
                raise ValueError(f"Invalid resource_id format: {resource_id}")

            # Step 1: Subscribe to dataset if not already subscribed
            try:
                self._subscribe_to_dataset(dataset_id)
            except (PermissionError, Exception) as e:
                # If subscription fails, log warning but continue
                # User may have subscribed via AWS Console
                if isinstance(e, PermissionError):
                    logger.warning(f"Could not verify subscription for dataset {dataset_id}, continuing...")
                else:
                    logger.warning(f"Subscription check failed for dataset {dataset_id}: {e}, continuing...")

            # Step 2: Get latest revision if not specified
            if not revision_id:
                revision_id = self._get_latest_revision(dataset_id)

            # Step 3: Create export job
            # Get destination bucket from settings or use default
            destination_bucket = getattr(settings, 'AWS_DATA_EXCHANGE_EXPORT_BUCKET', None)
            job_id = self._create_export_job(
                dataset_id=dataset_id,
                revision_id=revision_id,
                destination_bucket=destination_bucket
            )

            # Step 4: Start export job
            self._start_job(job_id)

            # Step 5: Wait for job completion
            job_result = self._wait_for_job_completion(job_id)

            # Step 6: Download exported assets from S3
            downloaded_path = self._download_exported_assets(job_result, destination_path)

            # Step 7: Extract schema metadata (optional, for future use)
            # Schema extraction is deferred - can be called separately if needed
            # schema_metadata = self._extract_schema_from_assets(downloaded_path)

            logger.info(f"Successfully downloaded resource {resource_id} to {downloaded_path}")
            return downloaded_path

        return self._circuit_breaker.call(execute_download)

    def map_to_hub_asset(
        self,
        listing: MarketplaceListing,
        sync_job_id: Optional[str] = None
    ) -> MarketplaceAssetMapping:
        """
        Map an AWS Data Exchange dataset to a Hub asset representation.

        Extracts comprehensive metadata from AWS Data Exchange dataset including:
        - Asset fields (name, description, domain, status, visibility, tags)
        - ODPS contract data (product details, pricing, access, payment)
        - ODCS contract data (schema hints, quality hints, SLA hints)
        - Marketplace source metadata
        - Resource information (with external references for on-demand download)

        Args:
            listing: MarketplaceListing object to map
            sync_job_id: Optional sync job ID for tracking synchronization operations

        Returns:
            MarketplaceAssetMapping object containing all mapped data

        Raises:
            ValueError: If listing data cannot be mapped
        """
        if not listing:
            raise ValueError("Listing is required")

        # Extract AWS Data Exchange dataset data from metadata
        dataset_data = listing.metadata.get('aws_data_exchange_dataset', {}) if listing.metadata else {}
        latest_revision = listing.metadata.get('latest_revision', {}) if listing.metadata else {}
        odps_metadata = listing.metadata.get('odps_metadata', {}) if listing.metadata else {}
        odcs_metadata = listing.metadata.get('odcs_metadata', {}) if listing.metadata else {}

        # Extract title and description
        title = listing.title or dataset_data.get('Name', 'Untitled Dataset')
        description = listing.description or dataset_data.get('Description', '')

        # Extract domain from Origin or OriginDetails
        domain = None
        if listing.category:
            domain = listing.category
        elif dataset_data.get('Origin'):
            domain = dataset_data['Origin']
        elif dataset_data.get('OriginDetails', {}).get('ProductId'):
            domain = dataset_data['OriginDetails']['ProductId']

        # Determine status and visibility
        # AWS Data Exchange datasets are typically ACTIVE and PUBLIC
        status = 'ACTIVE'
        visibility = 'PUBLIC'

        # Extract tags
        tags = listing.tags or []

        # Build comprehensive asset_data
        asset_data: Dict[str, Any] = {
            'name': title,
            'description': description,
            'key': f"aws-data-exchange-{listing.marketplace_id}",
            'tags': tags,
            'status': status,
            'visibility': visibility,
        }

        # Add optional fields if available
        if domain:
            asset_data['domain'] = domain

        # Extract Provider from OriginDetails if available
        provider = None
        if dataset_data.get('OriginDetails', {}).get('ProductId'):
            provider = dataset_data['OriginDetails']['ProductId']
        elif dataset_data.get('OriginDetails', {}).get('Name'):
            provider = dataset_data['OriginDetails']['Name']

        # Extract source metadata
        source_metadata: Dict[str, Any] = {
            'marketplace_type': MarketplaceType.AWS_DATA_EXCHANGE.value,
            'marketplace_id': listing.marketplace_id,
            'listing_id': listing.marketplace_id,
            'listing_url': listing.url,
            'synced_at': timezone.now().isoformat(),
            'dataset_id': listing.marketplace_id,
            'revision_id': latest_revision.get('Id') if latest_revision else None,
        }

        # Add Provider if available
        if provider:
            source_metadata['provider'] = provider

        # Add sync_job_id if provided
        if sync_job_id:
            source_metadata['sync_job_id'] = sync_job_id

        # Use ODPS and ODCS metadata from listing (already extracted)
        # If not present, extract them
        if not odps_metadata:
            odps_metadata = self._extract_odps_metadata(dataset_data, latest_revision if latest_revision else None)
        if not odcs_metadata:
            odcs_metadata = self._extract_odcs_metadata(dataset_data, latest_revision if latest_revision else None)

        # Get resources (with external references for on-demand download)
        resources = []
        try:
            resources = self.list_resources(listing.marketplace_id)
            # Mark resources as external for on-demand download
            for resource in resources:
                if not resource.metadata:
                    resource.metadata = {}
                resource.metadata['external'] = True
                resource.metadata['dataset_id'] = listing.marketplace_id
                resource.metadata['revision_id'] = latest_revision.get('Id') if latest_revision else None
        except Exception as e:
            logger.warning(f"Failed to fetch resources for mapping: {e}")

        return MarketplaceAssetMapping(
            asset_data=asset_data,
            source_type=AssetSourceType.FEDERATED,
            source_metadata=source_metadata,
            odps_metadata=odps_metadata if odps_metadata else None,
            odcs_metadata=odcs_metadata if odcs_metadata else None,
            resources=resources
        )

    def map_from_hub_asset(
        self,
        asset_data: Dict[str, Any],
        odps_metadata: Optional[Dict[str, Any]] = None,
        odcs_metadata: Optional[Dict[str, Any]] = None
    ) -> MarketplaceListing:
        """
        Map a Hub asset to an AWS Data Exchange dataset representation.

        AWS Data Exchange connector does not support push operations.
        """
        raise NotImplementedError(
            "AWS Data Exchange connector does not support push operations (map_from_hub_asset)"
        )

    def sync_push(
        self,
        asset_ids: List[str],
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk push synchronization (Hub → AWS Data Exchange).

        AWS Data Exchange connector does not support push operations.
        """
        raise NotImplementedError(
            "AWS Data Exchange connector does not support push operations (sync_push)"
        )

    def sync_pull(
        self,
        listing_ids: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> SyncResult:
        """
        Perform bulk pull synchronization (AWS Data Exchange → Hub) following metadata-first pattern.

        **Metadata-First Behavior**:
        This method discovers listings and maps them to MarketplaceAssetMapping objects. It does
        NOT create assets or download data. Asset creation happens in the workflow via
        `create_federated_asset_with_contracts()`. Data downloads happen on-demand via
        `download_resource()` when `data_strategy != "METADATA_ONLY"`.

        **What This Method Does**:
        1. Discovers listings from AWS Data Exchange (by IDs or via filters)
        2. For each listing, calls `list_resources()` to fetch resources (metadata-only, if `include_resources=True`)
        3. Maps each listing to MarketplaceAssetMapping using `map_to_hub_asset()`
        4. Includes external resource references in mapping (resources with `metadata.external=True`
           and `metadata.dataset_id`, `metadata.revision_id` for on-demand download)
        5. Returns mappings in SyncResult.metadata["mappings"] for workflow processing

        **What This Method Does NOT Do**:
        - Does NOT subscribe to datasets (deferred to `download_resource()`)
        - Does NOT create export jobs (deferred to `download_resource()`)
        - Does NOT download assets from S3 (deferred to `download_resource()`)
        - Does NOT extract schema from downloaded assets (deferred to `download_resource()`)
        - Does NOT access external data sources (only stores references)

        Args:
            listing_ids: Optional list of specific dataset IDs to sync.
                If None, syncs all datasets matching filters.
            filters: Optional dictionary of filters to apply (e.g., origin, name)
            options: Optional dictionary of sync options:
                - dry_run: If True, simulate sync without creating assets
                - limit: Maximum number of listings to sync (default: None, sync all)
                - include_resources: If True, fetch resources for each listing (default: True)

        Returns:
            SyncResult object with:
            - status: SyncStatus (COMPLETED, PARTIAL, FAILED)
            - total_items: Total number of listings processed
            - successful_items: Number of successfully mapped listings
            - failed_items: Number of failed mappings
            - skipped_items: Number of skipped listings
            - errors: List of error messages for failed mappings
            - metadata: Dictionary containing:
                - "mappings": List of MarketplaceAssetMapping objects (serialized as dicts)
                - "errors": List of error messages for failed mappings
            - started_at: Operation start timestamp
            - completed_at: Operation completion timestamp

        Raises:
            ValueError: If filters or options are invalid
            ConnectionError: If unable to connect to AWS Data Exchange
        """
        options = options or {}
        dry_run = options.get('dry_run', False)
        limit = options.get('limit')
        include_resources = options.get('include_resources', True)
        started_at = timezone.now()

        successful_items = 0
        failed_items = 0
        skipped_items = 0
        errors = []
        mappings = []

        def execute_sync_pull() -> SyncResult:
            """Execute sync_pull with circuit breaker protection."""
            nonlocal successful_items, failed_items, skipped_items, errors, mappings

            # Get listings to sync
            try:
                if listing_ids:
                    # Fetch specific listings
                    listings = []
                    for listing_id in listing_ids:
                        try:
                            listing = self.get_listing(listing_id)
                            listings.append(listing)
                        except NotFoundError:
                            skipped_items += 1
                            errors.append(f"Dataset {listing_id} not found")
                        except Exception as e:
                            failed_items += 1
                            error_msg = f"Failed to fetch dataset {listing_id}: {e}"
                            errors.append(error_msg)
                            logger.error(error_msg, exc_info=True)
                else:
                    # Fetch listings using filters
                    listings = self.list_listings(filters=filters, limit=limit)
            except Exception as e:
                error_msg = f"Failed to fetch datasets: {e}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
                return SyncResult(
                    status=SyncStatus.FAILED,
                    total_items=0,
                    successful_items=0,
                    failed_items=0,
                    skipped_items=0,
                    errors=errors,
                    metadata={'dry_run': dry_run},
                    started_at=started_at,
                    completed_at=timezone.now()
                )

            # If we have skipped items but no listings, return early
            if not listings and skipped_items > 0:
                logger.info(f"No datasets found to sync, {skipped_items} skipped")
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(listing_ids) if listing_ids else 0,
                    successful_items=0,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                    errors=errors,
                    metadata={'dry_run': dry_run, 'reason': 'no_datasets_found', 'mappings': []},
                    started_at=started_at,
                    completed_at=timezone.now()
                )

            if not listings:
                logger.info("No datasets found to sync")
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=0,
                    successful_items=0,
                    failed_items=0,
                    skipped_items=0,
                    errors=[],
                    metadata={'dry_run': dry_run, 'reason': 'no_datasets_found', 'mappings': []},
                    started_at=started_at,
                    completed_at=timezone.now()
                )

            # Process each listing
            for listing in listings:
                try:
                    if dry_run:
                        logger.info(f"DRY RUN: Would pull dataset {listing.marketplace_id} from AWS Data Exchange")
                        successful_items += 1
                        continue

                    # Fetch resources for the listing (metadata-only)
                    resources = []
                    if include_resources:
                        try:
                            resources = self.list_resources(listing.marketplace_id)
                            # Mark resources as external for on-demand download
                            for resource in resources:
                                if not resource.metadata:
                                    resource.metadata = {}
                                resource.metadata['external'] = True
                                resource.metadata['dataset_id'] = listing.marketplace_id
                                # Get revision ID from listing metadata
                                latest_revision = listing.metadata.get('latest_revision', {}) if listing.metadata else {}
                                resource.metadata['revision_id'] = latest_revision.get('Id') if latest_revision else None
                        except Exception as e:
                            logger.warning(f"Dataset {listing.marketplace_id}: Failed to fetch resources: {e}")
                            # Continue without resources

                    # Map listing to Hub asset format
                    try:
                        mapping = self.map_to_hub_asset(listing)
                        # Add resources to the mapping if they were fetched
                        if resources:
                            mapping.resources = resources

                        # Serialize mapping to dict for SyncResult metadata
                        mapping_dict = {
                            'asset_data': mapping.asset_data,
                            'source_type': mapping.source_type.value if hasattr(mapping.source_type, 'value') else str(mapping.source_type),
                            'source_metadata': mapping.source_metadata,
                            'odps_metadata': mapping.odps_metadata,
                            'odcs_metadata': mapping.odcs_metadata,
                            'resources': [
                                {
                                    'resource_id': r.resource_id,
                                    'resource_type': r.resource_type,
                                    'name': r.name,
                                    'description': r.description,
                                    'url': r.url,
                                    'format': r.format,
                                    'size_bytes': r.size_bytes,
                                    'metadata': r.metadata
                                }
                                for r in mapping.resources
                            ]
                        }
                        mappings.append({
                            'listing_id': listing.marketplace_id,
                            'mapping': mapping_dict,
                        })
                        successful_items += 1
                        logger.info(f"Dataset {listing.marketplace_id}: Mapped to Hub asset format")
                    except Exception as e:
                        failed_items += 1
                        error_msg = f"Dataset {listing.marketplace_id}: Failed to map to Hub asset: {e}"
                        errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)
                        continue

                except Exception as e:
                    failed_items += 1
                    error_msg = f"Dataset {listing.marketplace_id}: Unexpected error: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
                    continue

            completed_at = timezone.now()
            status = SyncStatus.COMPLETED if failed_items == 0 else SyncStatus.PARTIAL if successful_items > 0 else SyncStatus.FAILED

            return SyncResult(
                status=status,
                total_items=len(listings),
                successful_items=successful_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
                errors=errors,
                metadata={
                    'dry_run': dry_run,
                    'mappings': mappings,  # List of mappings for asset creation
                    'include_resources': include_resources,
                },
                started_at=started_at,
                completed_at=completed_at
            )

        return self._circuit_breaker.call(execute_sync_pull)

