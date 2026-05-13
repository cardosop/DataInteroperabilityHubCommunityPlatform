"""
Virtualization Service

Service layer for virtualization operations.
Provides business logic for virtual dataset management and query execution.
"""
from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone
import logging
import re

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError, ConflictError, PermissionError
from hub.apps.core.events.service_publishers import VirtualizationEventPublisher
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryExecution,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode,
)
from hub.apps.virtualization.business_rules import (
    QueryExecutionBusinessRules,
    VirtualizationBusinessRules,
)
from hub.apps.virtualization.metrics import (
    virtualization_dataset_created_total,
    virtualization_dataset_creation_duration_seconds,
    virtualization_query_execution_started_total,
    virtualization_query_execution_completed_total,
    virtualization_query_execution_failed_total,
    virtualization_query_execution_duration_seconds,
    virtualization_query_result_cache_hit_rate,
    virtualization_query_result_cache_misses_total,
    virtualization_query_result_size_bytes,
    virtualization_query_result_rows_total,
    get_tenant_id,
    get_query_type,
    get_execution_mode,
)

logger = logging.getLogger(__name__)


class VirtualizationService(BaseService, VirtualizationEventPublisher):
    """
    Service for virtualization operations.

    Provides business logic for:
    - Virtual dataset creation and management
    - Query execution management
    - Event publishing
    """

    service_name = "virtualization_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize VirtualizationService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        VirtualizationEventPublisher.__init__(self)

    def get_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: Optional[str] = None,
    ) -> VirtualDataset:
        """
        Get virtual dataset by ID.

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            VirtualDataset instance

        Raises:
            NotFoundError: If virtual dataset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        return self.execute_with_metrics(
            operation="get_virtual_dataset",
            tenant_id=effective_tenant_id,
            func=lambda: self.get_resource_or_raise(
                VirtualDataset,
                virtual_dataset_id,
                tenant_id=effective_tenant_id,
            ),
        )

    def get_virtual_datasets(
        self,
        tenant_id: Optional[str] = None,
        status: Optional[VirtualDatasetStatus] = None,
        query_type: Optional[QueryType] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[VirtualDataset]:
        """
        Get virtual datasets with optional filtering.

        Args:
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            status: Optional status filter
            query_type: Optional query type filter
            limit: Optional limit on results
            offset: Pagination offset

        Returns:
            List of VirtualDataset instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_virtual_datasets():
            queryset = VirtualDataset.objects.filter(tenant_id=effective_tenant_id)

            if status:
                queryset = queryset.filter(status=status)

            if query_type:
                queryset = queryset.filter(query_type=query_type)

            queryset = queryset.order_by("-created_at")

            if offset:
                queryset = queryset[offset:]

            if limit:
                queryset = queryset[:limit]

            return list(queryset)

        return self.execute_with_metrics(
            operation="get_virtual_datasets",
            tenant_id=effective_tenant_id,
            func=_get_virtual_datasets,
        )

    def get_query_execution(
        self,
        query_execution_id: str,
        tenant_id: Optional[str] = None,
    ) -> QueryExecution:
        """
        Get query execution by ID.

        Args:
            query_execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            QueryExecution instance

        Raises:
            NotFoundError: If query execution not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # QueryExecution doesn't have tenant_id directly, get via virtual_dataset
        try:
            execution = QueryExecution.objects.select_related('virtual_dataset').get(
                id=query_execution_id
            )
            # Verify tenant isolation (compare as strings to handle UUID vs string)
            if str(execution.virtual_dataset.tenant_id) != str(effective_tenant_id):
                raise NotFoundError(f"QueryExecution with id {query_execution_id} not found")
            return execution
        except QueryExecution.DoesNotExist:
            raise NotFoundError(f"QueryExecution with id {query_execution_id} not found")

    def get_query_executions(
        self,
        virtual_dataset_id: str,
        tenant_id: Optional[str] = None,
        status: Optional[QueryExecutionStatus] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[QueryExecution]:
        """
        Get query executions for a virtual dataset with optional filtering.

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            status: Optional status filter
            limit: Optional limit on results
            offset: Pagination offset

        Returns:
            List of QueryExecution instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # First verify virtual dataset exists and belongs to tenant
        virtual_dataset = self.get_virtual_dataset(virtual_dataset_id, effective_tenant_id)

        def _get_query_executions():
            queryset = QueryExecution.objects.filter(virtual_dataset_id=virtual_dataset_id)

            if status:
                queryset = queryset.filter(status=status)

            queryset = queryset.order_by("-started_at", "-created_at")

            if offset:
                queryset = queryset[offset:]

            if limit:
                queryset = queryset[:limit]

            return list(queryset)

        return self.execute_with_metrics(
            operation="get_query_executions",
            tenant_id=effective_tenant_id,
            func=_get_query_executions,
        )

    def _validate_query_syntax(
        self,
        query: str,
        query_type: QueryType
    ) -> None:
        """
        Validate query syntax based on query type.

        Args:
            query: Query string to validate
            query_type: Type of query (SQL, SPARQL, etc.)

        Raises:
            ValidationError: If query syntax is invalid
        """
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty")

        query_upper = query.upper().strip()

        if query_type == QueryType.SQL:
            # SQL validation - check for SQL keywords and basic syntax
            sql_keywords = ['SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
            if not any(keyword in query_upper for keyword in sql_keywords):
                raise ValidationError(
                    "SQL query should contain SQL keywords (SELECT, WITH, etc.)",
                    code="INVALID_SQL_SYNTAX"
                )

            # Check for dangerous operations (only allow SELECT and WITH for read-only queries)
            dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'TRUNCATE', 'ALTER', 'CREATE']
            for keyword in dangerous_keywords:
                if re.search(rf'\b{keyword}\b', query_upper):
                    raise ValidationError(
                        f"SQL query contains dangerous operation '{keyword}'. Only SELECT and WITH queries are allowed.",
                        code="DANGEROUS_SQL_OPERATION"
                    )

            # Basic syntax validation - check for balanced parentheses
            open_parens = query.count('(')
            close_parens = query.count(')')
            if open_parens != close_parens:
                raise ValidationError(
                    "SQL query has unbalanced parentheses",
                    code="INVALID_SQL_SYNTAX"
                )

        elif query_type == QueryType.SPARQL:
            # Check for SPARQL Update operations first (not allowed)
            # This check should come before keyword validation to provide better error messages
            update_keywords = ['INSERT', 'DELETE', 'DROP', 'CLEAR', 'LOAD', 'CREATE', 'MOVE', 'COPY', 'ADD']
            for keyword in update_keywords:
                if re.search(rf'\b{keyword}\b', query_upper):
                    raise ValidationError(
                        f"SPARQL Update operation '{keyword}' is not allowed. Only SELECT, CONSTRUCT, ASK, and DESCRIBE queries are permitted.",
                        code="DANGEROUS_SPARQL_OPERATION"
                    )

            # SPARQL validation - check for SPARQL keywords
            sparql_keywords = ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE', 'PREFIX']
            if not any(keyword in query_upper for keyword in sparql_keywords):
                raise ValidationError(
                    "SPARQL query should contain SPARQL keywords (SELECT, CONSTRUCT, ASK, DESCRIBE, PREFIX)",
                    code="INVALID_SPARQL_SYNTAX"
                )

            # Check for balanced braces
            open_braces = query.count('{')
            close_braces = query.count('}')
            if open_braces != close_braces:
                raise ValidationError(
                    "SPARQL query has unbalanced braces",
                    code="INVALID_SPARQL_SYNTAX"
                )

        elif query_type == QueryType.FEDERATED:
            # Federated query validation - should contain SERVICE or similar federated keywords
            federated_keywords = ['SERVICE', 'SERVICE', 'FEDERATED']
            if not any(keyword in query_upper for keyword in federated_keywords):
                logger.warning("Federated query may not contain federated keywords - this may be intentional")

        # Additional validation can be added for other query types

    def _validate_schema(
        self,
        schema: Optional[Dict[str, Any]]
    ) -> None:
        """
        Validate schema structure.

        Args:
            schema: Schema dictionary to validate

        Raises:
            ValidationError: If schema is invalid
        """
        if schema is None:
            return  # Schema is optional

        if not isinstance(schema, dict):
            raise ValidationError(
                "Schema must be a JSON object",
                code="INVALID_SCHEMA_FORMAT"
            )

        # Validate schema structure
        # Schema can be in different formats:
        # 1. {"fields": [{"name": "...", "type": "...", ...}, ...]}
        # 2. {"field_name": {"type": "...", ...}, ...}
        # 3. Custom format

        if "fields" in schema:
            # Format 1: fields array
            if not isinstance(schema["fields"], list):
                raise ValidationError(
                    "Schema 'fields' must be an array",
                    code="INVALID_SCHEMA_FORMAT"
                )
            for i, field in enumerate(schema["fields"]):
                if not isinstance(field, dict):
                    raise ValidationError(
                        f"Schema field at index {i} must be an object",
                        code="INVALID_SCHEMA_FORMAT"
                    )
                if "name" not in field:
                    raise ValidationError(
                        f"Schema field at index {i} must have a 'name' property",
                        code="INVALID_SCHEMA_FORMAT"
                    )

    @staticmethod
    def _map_source_type_to_connector_type(source_type: str) -> Optional[str]:
        """
        Map hub source type (postgresql, rest, etc.) to connector factory type (DATABASE, HTTP, S3, ...).
        Aligns with hub.apps.virtualization.business_rules.VirtualizationBusinessRules.
        """
        if not source_type:
            return None
        st = source_type.lower()
        if st in ("postgresql", "mysql", "sqlserver", "mssql", "oracle", "sqlite"):
            return "DATABASE"
        if st in ("rest", "http", "https"):
            return "HTTP"
        if st == "s3":
            return "S3"
        if st == "gcs":
            return "GCS"
        if st in ("azure_blob", "azureblob"):
            return "AZURE_BLOB"
        if st in ("ftp", "sftp"):
            return st.upper()
        # sparql, graphql, minio, federated_asset, external_resource have no connector
        return None

    def _validate_source_connectivity(
        self,
        sources: Optional[List[Dict[str, Any]]],
        tenant_id: str
    ) -> None:
        from hub.apps.assets.models import Asset, AssetSourceType, ExternalResourceReference
        from hub.apps.integrations.models import MarketplaceConnection
        from hub.apps.tenants.models import Tenant
        """
        Validate connectivity to data sources.

        Supports:
        - Traditional sources: postgresql, mysql, sqlserver, sparql, rest, graphql, s3, minio
        - Federated asset sources: {"type": "federated_asset", "asset_id": "uuid", "query": "SELECT * FROM ..."}
        - External resource sources: {"type": "external_resource", "resource_id": "uuid", "asset_id": "uuid"}

        Args:
            sources: List of source configurations
            tenant_id: Tenant ID for tenant isolation

        Raises:
            ValidationError: If source connectivity check fails
        """
        if not sources or not isinstance(sources, list):
            return  # Sources are optional

        if len(sources) == 0:
            return  # Empty sources list is valid

        # Get tenant object for cross-tenant access validation
        from hub.apps.tenants.models import Tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {tenant_id} not found")

        # Test connectivity to each source
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                raise ValidationError(
                    f"Source configuration at index {i} must be an object",
                    code="INVALID_SOURCE_CONFIG"
                )

            source_type = source_config.get("type")
            if not source_type:
                raise ValidationError(
                    f"Source configuration at index {i} must have a 'type' field",
                    code="INVALID_SOURCE_CONFIG"
                )

            # Handle federated asset sources
            if source_type == "federated_asset":
                self._validate_federated_asset_source(
                    source_config, tenant, source_index=i
                )
                continue  # Skip traditional connectivity check

            # Handle external resource sources
            if source_type == "external_resource":
                self._validate_external_resource_source(
                    source_config, tenant, source_index=i
                )
                continue  # Skip traditional connectivity check

            # Test connection using connector factory for traditional sources
            try:
                # Map hub source type (postgresql, rest, etc.) to connector factory type (DATABASE, HTTP, S3, ...)
                connector_type = self._map_source_type_to_connector_type(source_type)
                if connector_type is None:
                    # SPARQL, GraphQL, etc. have no connector - skip connectivity check
                    continue

                # Import connector factory
                import sys
                import os
                connector_path = os.path.join(
                    os.path.dirname(__file__),
                    '../../../services/prefect-integration'
                )
                sys.path.insert(0, connector_path)

                try:
                    from connectors.factory import SourceConnectorFactory
                except ImportError:
                    # Connector factory not available - skip connectivity check
                    logger.warning(
                        "Source connector factory not available, skipping connectivity check",
                        extra={"source_index": i, "source_type": source_type}
                    )
                    continue

                # Get connector (factory may not have DATABASE if optional dependency missing)
                try:
                    connector = SourceConnectorFactory.get_connector(connector_type)
                except ValueError:
                    # Connector type not registered (e.g. DATABASE when DatabaseConnector import failed)
                    logger.warning(
                        "Connector type %s not available in factory, skipping connectivity check",
                        connector_type,
                        extra={"source_index": i, "source_type": source_type}
                    )
                    continue

                if hasattr(connector, 'test_connection'):
                    # Some connectors return dict with 'success' key
                    test_result = connector.test_connection(source_config)
                    if isinstance(test_result, dict):
                        if not test_result.get("success", False):
                            error_msg = test_result.get("error", "Connection test failed")
                            raise ValidationError(
                                f"Source connectivity check failed for source {i} (type: {source_type}): {error_msg}",
                                code="SOURCE_CONNECTIVITY_FAILED",
                                details={"source_index": i, "source_type": source_type, "error": error_msg}
                            )
                    elif not test_result:
                        # Boolean result
                        raise ValidationError(
                            f"Source connectivity check failed for source {i} (type: {source_type})",
                            code="SOURCE_CONNECTIVITY_FAILED",
                            details={"source_index": i, "source_type": source_type}
                        )
                else:
                    logger.warning(
                        f"Connector for type '{source_type}' does not support test_connection method",
                        extra={"source_index": i, "source_type": source_type}
                    )

            except Exception as e:
                # If it's already a ValidationError, re-raise it
                if isinstance(e, ValidationError):
                    raise
                # Otherwise, wrap it in a ValidationError
                raise ValidationError(
                    f"Failed to test connectivity for source {i} (type: {source_type}): {str(e)}",
                    code="SOURCE_CONNECTIVITY_ERROR",
                    details={"source_index": i, "source_type": source_type, "error": str(e)}
                ) from e

    def _validate_federated_asset_source(
        self,
        source_config: Dict[str, Any],
        tenant,
        source_index: int = 0
    ) -> None:
        """
        Validate federated asset source configuration.

        Args:
            source_config: Source configuration dict with type="federated_asset"
            tenant: Tenant object for access validation
            source_index: Source index for error messages

        Raises:
            ValidationError: If validation fails
        """
        from hub.apps.assets.models import Asset, AssetSourceType
        from hub.apps.tenants.models import Tenant
        import uuid

        asset_id = source_config.get("asset_id")
        if not asset_id:
            raise ValidationError(
                f"Federated asset source at index {source_index} must have 'asset_id' field",
                code="MISSING_ASSET_ID",
                details={"source_index": source_index}
            )

        # Validate asset_id is a valid UUID
        try:
            asset_uuid = uuid.UUID(str(asset_id))
        except (ValueError, TypeError):
            raise ValidationError(
                f"Invalid asset_id format at source index {source_index}: {asset_id}",
                code="INVALID_ASSET_ID",
                details={"source_index": source_index, "asset_id": asset_id}
            )

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=asset_uuid)
        except Asset.DoesNotExist:
            raise ValidationError(
                f"Federated asset source at index {source_index} references non-existent asset: {asset_id}",
                code="ASSET_NOT_FOUND",
                details={"source_index": source_index, "asset_id": str(asset_id)}
            )

        # Validate asset is FEDERATED type
        if asset.source_type != AssetSourceType.FEDERATED:
            raise ValidationError(
                f"Asset {asset_id} at source index {source_index} is not a federated asset (source_type: {asset.source_type})",
                code="INVALID_ASSET_TYPE",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "source_type": asset.source_type
                }
            )

        # Validate cross-tenant access permissions
        self._validate_cross_tenant_source_access(asset, str(tenant.id), source_index=source_index)

        # Validate query is provided (optional but recommended)
        query = source_config.get("query")
        if query and not isinstance(query, str):
            raise ValidationError(
                f"Query field at source index {source_index} must be a string",
                code="INVALID_QUERY_TYPE",
                details={"source_index": source_index}
            )

        logger.info(
            f"Federated asset source validated at index {source_index}",
            extra={
                "source_index": source_index,
                "asset_id": str(asset.id),
                "asset_name": asset.name,
                "tenant_id": str(tenant.id)
            }
        )

    def _validate_external_resource_source(
        self,
        source_config: Dict[str, Any],
        tenant,
        source_index: int = 0
    ) -> None:
        """
        Validate external resource source configuration.

        Args:
            source_config: Source configuration dict with type="external_resource"
            tenant: Tenant object for access validation
            source_index: Source index for error messages

        Raises:
            ValidationError: If validation fails
        """
        from hub.apps.assets.models import Asset, AssetSourceType, ExternalResourceReference
        from hub.apps.tenants.models import Tenant
        import uuid

        resource_id = source_config.get("resource_id")
        asset_id = source_config.get("asset_id")

        if not resource_id:
            raise ValidationError(
                f"External resource source at index {source_index} must have 'resource_id' field",
                code="MISSING_RESOURCE_ID",
                details={"source_index": source_index}
            )

        if not asset_id:
            raise ValidationError(
                f"External resource source at index {source_index} must have 'asset_id' field",
                code="MISSING_ASSET_ID",
                details={"source_index": source_index}
            )

        # Validate UUIDs
        try:
            asset_uuid = uuid.UUID(str(asset_id))
        except (ValueError, TypeError):
            raise ValidationError(
                f"Invalid asset_id format at source index {source_index}: {asset_id}",
                code="INVALID_ASSET_ID",
                details={"source_index": source_index, "asset_id": asset_id}
            )

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=asset_uuid)
        except Asset.DoesNotExist:
            raise ValidationError(
                f"External resource source at index {source_index} references non-existent asset: {asset_id}",
                code="ASSET_NOT_FOUND",
                details={"source_index": source_index, "asset_id": str(asset_id)}
            )

        # Validate asset is FEDERATED type
        if asset.source_type != AssetSourceType.FEDERATED:
            raise ValidationError(
                f"Asset {asset_id} at source index {source_index} is not a federated asset (source_type: {asset.source_type})",
                code="INVALID_ASSET_TYPE",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "source_type": asset.source_type
                }
            )

        # Validate cross-tenant access permissions
        self._validate_cross_tenant_source_access(asset, str(tenant.id), source_index=source_index)

        # Validate external resource exists and belongs to asset
        try:
            external_resource = ExternalResourceReference.objects.get(
                asset=asset,
                resource_id=str(resource_id)
            )
        except ExternalResourceReference.DoesNotExist:
            raise ValidationError(
                f"External resource '{resource_id}' not found for asset {asset_id} at source index {source_index}",
                code="EXTERNAL_RESOURCE_NOT_FOUND",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "resource_id": str(resource_id)
                }
            )

        # Validate resource can be accessed (check data_strategy)
        if not asset.can_download_resource(str(resource_id)):
            raise ValidationError(
                f"External resource '{resource_id}' cannot be downloaded for asset {asset_id} "
                f"(data_strategy: {asset.data_strategy}) at source index {source_index}",
                code="RESOURCE_NOT_ACCESSIBLE",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "resource_id": str(resource_id),
                    "data_strategy": asset.data_strategy
                }
            )

        logger.info(
            f"External resource source validated at index {source_index}",
            extra={
                "source_index": source_index,
                "asset_id": str(asset.id),
                "resource_id": str(resource_id),
                "tenant_id": str(tenant.id)
            }
        )

    def _validate_compliance_for_sources(
        self,
        sources: Optional[List[Dict[str, Any]]],
        tenant_id: str
    ) -> None:
        """
        Validate compliance of federated sources via ComplianceService.

        For each source that references an asset (via asset_id), this method:
        1. Checks if the asset exists
        2. Validates cross-tenant access permissions if asset is from different tenant
        3. Runs compliance scan on asset's dataset file via ComplianceService
        4. Blocks creation if compliance violations are detected

        Args:
            sources: List of source configurations (may contain asset_id references)
            tenant_id: Tenant ID for tenant isolation

        Raises:
            ValidationError: If compliance validation fails
        """
        if not sources or not isinstance(sources, list):
            return  # Sources are optional

        if len(sources) == 0:
            return  # Empty sources list is valid

        from hub.apps.compliance.service_client import ComplianceServiceClient
        from hub.apps.assets.models import Asset
        from hub.apps.files.storage import S3StorageClient

        # Initialize compliance client
        compliance_client = ComplianceServiceClient()

        # Check compliance service health
        is_healthy, _ = compliance_client.health_check()
        if not is_healthy:
            logger.warning(
                "Compliance service unavailable, skipping compliance validation for sources",
                extra={"tenant_id": tenant_id, "source_count": len(sources)}
            )
            return  # Skip compliance check if service unavailable

        # Validate each source that references an asset
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                continue  # Skip invalid source configs (already validated in _validate_source_connectivity)

            asset_id = source_config.get("asset_id")
            if not asset_id:
                continue  # Source doesn't reference an asset, skip compliance check

            try:
                # Get asset
                asset = Asset.objects.select_related('tenant').get(id=asset_id)
            except Asset.DoesNotExist:
                raise ValidationError(
                    f"Source at index {i} references non-existent asset: {asset_id}",
                    code="SOURCE_ASSET_NOT_FOUND",
                    details={"source_index": i, "asset_id": asset_id}
                )

            # Check cross-tenant access permissions
            self._validate_cross_tenant_source_access(asset, tenant_id, source_index=i)

            # Get latest dataset for asset
            latest_dataset = asset.datasets.order_by('-version').first()
            if not latest_dataset or not latest_dataset.file:
                logger.warning(
                    f"Asset {asset_id} has no dataset or file, skipping compliance scan",
                    extra={"asset_id": asset_id, "source_index": i}
                )
                continue

            # Download file content for compliance scan
            try:
                storage_client = S3StorageClient()
                file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
                file_format = latest_dataset.format or 'csv'
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve file content for compliance scan: {e}",
                    extra={"asset_id": asset_id, "source_index": i, "error": str(e)}
                )
                # Continue with other sources even if one fails
                continue

            # Run compliance scan
            try:
                compliance_result = compliance_client.scan_file(
                    file_content=file_content,
                    file_format=file_format.lower(),
                    scan_mode="internal"
                )

                # Extract compliance status
                overall_status = compliance_result.get("overall_status", "UNKNOWN")
                risk_level = compliance_result.get("risk_level", "UNKNOWN")
                allowed_to_store = compliance_result.get("allowed_to_store", None)

                # Block creation if compliance violations detected
                if overall_status == "FAIL" or (allowed_to_store is False):
                    error_msg = (
                        f"Compliance check failed for source at index {i} (asset: {asset.name}). "
                        f"Overall status: {overall_status}, Risk level: {risk_level}. "
                        f"Compliance violations detected."
                    )
                    raise ValidationError(
                        error_msg,
                        code="COMPLIANCE_VIOLATION",
                        details={
                            "source_index": i,
                            "asset_id": str(asset.id),
                            "asset_name": asset.name,
                            "overall_status": overall_status,
                            "risk_level": risk_level,
                            "allowed_to_store": allowed_to_store,
                            "detected_categories": compliance_result.get("detected_categories", {}),
                            "column_findings": compliance_result.get("column_findings", []),
                            "regulation_mapping": compliance_result.get("regulation_mapping", {})
                        }
                    )

                # Log successful compliance check
                logger.info(
                    f"Compliance check passed for source at index {i} (asset: {asset.name})",
                    extra={
                        "source_index": i,
                        "asset_id": str(asset.id),
                        "overall_status": overall_status,
                        "risk_level": risk_level
                    }
                )

            except ValidationError:
                # Re-raise validation errors (compliance violations)
                raise
            except Exception as e:
                # Log error but don't fail dataset creation for compliance service errors
                logger.error(
                    f"Error running compliance check for source at index {i}: {e}",
                    extra={
                        "source_index": i,
                        "asset_id": str(asset.id),
                        "error": str(e)
                    },
                    exc_info=True
                )
                # Continue with other sources even if one fails
                continue

    def _validate_cross_tenant_source_access(
        self,
        asset: "Asset",
        tenant_id: str,
        source_index: Optional[int] = None
    ) -> None:
        """
        Check cross-tenant source access permissions.

        If the asset is from a different tenant, this method validates that
        the current tenant has proper access via entitlements.

        Args:
            asset: Asset instance to check access for
            tenant_id: Tenant ID requesting access
            source_index: Optional source index for error messages

        Raises:
            ValidationError: If cross-tenant access is denied
        """
        # Check if asset is from different tenant
        asset_tenant_id = str(asset.tenant_id)
        if asset_tenant_id == tenant_id:
            return  # Same tenant, access allowed

        # Cross-tenant access - check entitlements
        from hub.apps.marketplace.access_utils import check_entitlement

        has_access, error_code, entitlement = check_entitlement(
            consumer_tenant_id=tenant_id,
            asset_id=str(asset.id),
            provider_tenant_id=asset_tenant_id
        )

        if not has_access:
            error_messages = {
                'ENTITLEMENT_REQUIRED': 'Access to this asset requires an entitlement.',
                'ENTITLEMENT_EXPIRED': 'Your entitlement to this asset has expired.',
                'ENTITLEMENT_REVOKED': 'Your entitlement to this asset has been revoked.'
            }
            message = error_messages.get(error_code or 'UNKNOWN', 'Access denied.')

            source_context = f" for source at index {source_index}" if source_index is not None else ""
            error_msg = (
                f"Cross-tenant access denied{source_context} (asset: {asset.name}). "
                f"{message}"
            )

            raise ValidationError(
                error_msg,
                code="CROSS_TENANT_ACCESS_DENIED",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_tenant_id": asset_tenant_id,
                    "requesting_tenant_id": tenant_id,
                    "error_code": error_code
                }
            )

        # Log successful cross-tenant access
        logger.info(
            f"Cross-tenant access granted for asset {asset.name}",
            extra={
                "asset_id": str(asset.id),
                "asset_tenant_id": asset_tenant_id,
                "requesting_tenant_id": tenant_id,
                "entitlement_id": str(entitlement.id) if entitlement else None,
                "source_index": source_index
            }
        )

    def _validate_query_compliance(
        self,
        query: str,
        query_type: QueryType,
        sources: Optional[List[Dict[str, Any]]],
        tenant_id: str
    ) -> None:
        """
        Validate query doesn't violate compliance rules.

        This method checks if the query would access non-compliant data by:
        1. Checking if referenced assets (via sources) are compliant
        2. Validating query doesn't attempt to access restricted data

        Args:
            query: Query definition
            query_type: Type of query
            sources: Optional list of source configurations
            tenant_id: Tenant ID

        Raises:
            ValidationError: If query compliance validation fails
        """
        # If sources are provided, compliance for sources is already validated
        # in _validate_compliance_for_sources. This method can be extended
        # for additional query-level compliance checks.

        # For now, we rely on source-level compliance validation.
        # Future enhancements could include:
        # - Query pattern analysis for sensitive data access
        # - Column-level compliance checks
        # - Regulatory compliance validation based on query content

        # Basic validation: ensure query doesn't contain obvious compliance violations
        # This is a placeholder for future query-level compliance rules
        if not query or not query.strip():
            raise ValidationError(
                "Query cannot be empty",
                code="EMPTY_QUERY"
            )

        # Additional query compliance checks can be added here
        # For example, checking for specific patterns that might violate compliance rules

    def _check_user_permissions(
        self,
        user_id: str,
        tenant_id: str,
        request: Optional[Any] = None
    ) -> None:
        """
        Check user permissions for virtual dataset creation.

        Validates:
        - User has DATA_PROVIDER or TENANT_ADMIN role
        - User has virtualization:write scope (via API key or role-based)

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            request: Optional HTTP request object (for API key scope checking)

        Raises:
            PermissionError: If user lacks required permissions
        """
        from hub.apps.users.models import User
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise PermissionError(
                f"User {user_id} not found"
            )

        # Platform admins have all permissions (can operate on any tenant)
        if user.is_platform_admin:
            return

        # For non-platform admins, verify tenant matches
        if str(user.tenant_id) != tenant_id:
            raise PermissionError(
                f"User {user_id} does not belong to tenant {tenant_id}"
            )

        # Check if user has required role (DATA_PROVIDER or TENANT_ADMIN)
        has_required_role = user.has_role("DATA_PROVIDER", "TENANT_ADMIN")
        if not has_required_role:
            raise PermissionError(
                f"User {user_id} does not have required role (DATA_PROVIDER or TENANT_ADMIN) for virtual dataset creation"
            )

        # Check if user has virtualization:write scope
        # Priority: API key scopes > role-based assumption
        has_scope = False

        if request and hasattr(request, 'api_key_scopes'):
            # Check API key scopes if available
            required_scope = "virtualization:write"
            has_scope = required_scope in request.api_key_scopes
            if not has_scope:
                raise PermissionError(
                    f"API key does not have required scope '{required_scope}' for virtual dataset creation"
                )
        else:
            # For regular users without API key, assume users with DATA_PROVIDER or TENANT_ADMIN role
            # have virtualization:write scope (role-based permission model)
            has_scope = True

        logger.debug(
            f"User permissions checked: user_id={user_id}, tenant_id={tenant_id}, "
            f"has_role={has_required_role}, has_scope={has_scope}"
        )

    def _validate_resource_quota(
        self,
        tenant_id: str,
        query: str,
        query_type: QueryType,
        sources: Optional[List[Dict[str, Any]]],
        schema: Optional[Dict[str, Any]]
    ) -> None:
        """
        Validate resource quota (query quota, storage quota) for virtual dataset creation.

        Calculates estimated resource usage based on:
        - Query complexity (number of sources, query type)
        - Schema complexity (number of fields)
        - Source count

        Then validates via GovernanceService that quota is available.

        Args:
            tenant_id: Tenant ID
            query: Query definition
            query_type: Type of query
            sources: Optional list of source configurations
            schema: Optional output schema definition

        Raises:
            ValidationError: If resource quota validation fails
        """
        from hub.apps.governance.services import GovernanceService

        # Calculate estimated resource quota based on query and sources
        # Virtual datasets don't store data, but they consume:
        # - Query quota: based on query complexity and source count
        # - Metadata storage: minimal, but we track it

        source_count = len(sources) if sources else 0
        schema_field_count = 0
        if schema and isinstance(schema, dict):
            if "fields" in schema and isinstance(schema["fields"], list):
                schema_field_count = len(schema["fields"])
            elif isinstance(schema, dict):
                schema_field_count = len(schema.keys())

        # Estimate query quota based on complexity
        # Base quota: 1 query unit per dataset
        # Additional quota: 0.5 units per source, 0.1 units per schema field
        query_quota = 1.0 + (source_count * 0.5) + (schema_field_count * 0.1)

        # Estimate metadata storage (in MB)
        # Base: 1 MB per dataset
        # Additional: 0.1 MB per source, 0.01 MB per schema field
        metadata_storage_mb = 1.0 + (source_count * 0.1) + (schema_field_count * 0.01)

        # Convert to GB for quota validation
        metadata_storage_gb = metadata_storage_mb / 1024.0

        # Build requested quota dictionary
        requested_quota = {
            "query_quota": query_quota,
            "storage_gb": metadata_storage_gb
        }

        # Validate quota via GovernanceService
        governance_service = GovernanceService(
            tenant_id=tenant_id,
            user_id=self.user_id
        )

        try:
            # Validate and allocate resource quota
            validated_quota = governance_service.validate_resource_quota_allocation(
                tenant_id=tenant_id,
                requested_quota=requested_quota
            )

            # Enforce tenant-level resource limits
            governance_service.check_tenant_resource_limits(
                tenant_id=tenant_id,
                requested_quota=validated_quota
            )

            logger.debug(
                f"Resource quota validated: tenant_id={tenant_id}, "
                f"query_quota={query_quota}, storage_gb={metadata_storage_gb}"
            )

        except ValidationError as e:
            logger.warning(
                f"Resource quota validation failed: {e.message}",
                extra={
                    "tenant_id": tenant_id,
                    "requested_quota": requested_quota,
                    "error_code": e.code
                }
            )
            raise

    def _check_abac_policies(
        self,
        user_id: str,
        tenant_id: str,
        resource_id: Optional[str] = None,
        access_type: str = "WRITE"
    ) -> None:
        """
        Check ABAC policies for virtualization operations.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            resource_id: Optional resource ID (for existing datasets)
            access_type: Access type (default: WRITE)

        Raises:
            PermissionError: If ABAC policy denies access
        """
        from hub.apps.governance.abac import ABACEngine

        # For new virtual dataset creation, we use a placeholder resource ID
        effective_resource_id = resource_id or f"tenant:{tenant_id}:virtual_dataset:new"

        # Evaluate ABAC access
        result = ABACEngine.evaluate_access(
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type="VIRTUAL_DATASET",
            resource_id=effective_resource_id,
            access_type=access_type
        )

        if not result.allowed:
            # If a policy explicitly denied access, raise PermissionError
            if result.policy:
                policy_name = result.policy.name if result.policy else "Unknown"
                raise PermissionError(
                    f"ABAC policy denied access to VIRTUAL_DATASET operation. "
                    f"Policy: {policy_name}"
                )
            # If no policy matched (default deny), we allow access for new resource creation
            # This is a "fail open" approach for new resources when no policies are configured
            # For existing resources, we should still check ownership/tenant isolation
            logger.debug(
                f"ABAC policy check: No policy matched for VIRTUAL_DATASET, allowing access (fail open)",
                extra={
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "resource_type": "VIRTUAL_DATASET",
                    "resource_id": effective_resource_id,
                    "access_type": access_type
                }
            )

        logger.debug(
            f"ABAC policy checked: user_id={user_id}, tenant_id={tenant_id}, "
            f"resource_type=VIRTUAL_DATASET, access_type={access_type}, allowed={result.allowed}"
        )

    def _enforce_tenant_resource_limits(
        self,
        tenant_id: str,
        requested_quota: Dict[str, Any]
    ) -> None:
        """
        Enforce tenant-level resource limits.

        This method uses GovernanceService to check that the requested quota
        does not exceed tenant-level limits.

        Args:
            tenant_id: Tenant ID
            requested_quota: Requested resource quota dictionary

        Raises:
            ValidationError: If tenant resource limits would be exceeded
        """
        from hub.apps.governance.services import GovernanceService

        if not requested_quota:
            return

        governance_service = GovernanceService(
            tenant_id=tenant_id,
            user_id=self.user_id
        )

        try:
            governance_service.check_tenant_resource_limits(
                tenant_id=tenant_id,
                requested_quota=requested_quota
            )
        except ValidationError as e:
            logger.warning(
                f"Tenant resource limits check failed: {e.message}",
                extra={
                    "tenant_id": tenant_id,
                    "requested_quota": requested_quota,
                    "error_code": e.code
                }
            )
            raise

    @transaction.atomic
    def create_virtual_dataset(
        self,
        tenant_id: str,
        user_id: str,
        name: str,
        query: str,
        query_type: QueryType,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        version: Optional[str] = None,
        status: Optional[VirtualDatasetStatus] = None,
    ) -> VirtualDataset:
        """
        Create a virtual dataset with comprehensive validation.

        This method performs:
        1. Query validation (syntax, schema)
        2. Schema validation
        3. Source connectivity check
        4. User permissions check (role and scope)
        5. Resource quota validation (query quota, storage quota)
        6. ABAC policy checks
        7. Compliance validation for federated sources (via ComplianceService)
        8. Cross-tenant source access permission checks
        9. Query compliance validation
        10. Virtual dataset creation with transaction management
        11. Event publishing (virtualization.dataset.created)
        12. Audit logging

        Args:
            tenant_id: Tenant ID
            user_id: User ID creating the dataset
            name: Dataset name (unique per tenant)
            query: Query definition (SQL, SPARQL, etc.)
            query_type: Type of query (SQL, SPARQL, FEDERATED, etc.)
            description: Optional dataset description
            schema: Optional output schema definition
            sources: Optional list of source system configurations
            version: Optional version string (defaults to "1.0.0")
            status: Optional status (defaults to DRAFT)

        Returns:
            Created VirtualDataset instance

        Raises:
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions or ABAC policy denies access
            ConflictError: If dataset with same name/version already exists
        """
        import re
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.utils import create_audit_event

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Set defaults
        if version is None:
            version = "1.0.0"
        if status is None:
            status = VirtualDatasetStatus.DRAFT  # type: ignore[assignment]  # enum member assigned to str-typed var

        # Validate via VirtualizationBusinessRules before any mutation
        payload_dataset = VirtualDataset(
            tenant_id=effective_tenant_id,
            name=name,
            query=query,
            query_type=query_type,
            description=description or "",
            schema=schema or {},
            sources=sources or [],
            version=version,
            status=status,
        )
        rules = VirtualizationBusinessRules(
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
        )
        result = rules.validate(
            virtual_dataset=payload_dataset,
            tenant=tenant,
            user=user,
            query=query,
            validation_type="all",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # 1. Check user permissions (role and scope)
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset creation: {str(e)}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id
                }
            )
            raise

        # 2. Validate resource quota
        try:
            self._validate_resource_quota(
                tenant_id=effective_tenant_id,
                query=query,
                query_type=query_type,
                sources=sources,
                schema=schema
            )
        except ValidationError as e:
            logger.warning(
                f"Resource quota validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code
                }
            )
            raise

        # 3. Check ABAC policies
        try:
            self._check_abac_policies(
                user_id=effective_user_id,
                tenant_id=effective_tenant_id,
                access_type="WRITE"
            )
        except PermissionError as e:
            logger.warning(
                f"ABAC policy check failed for virtual dataset creation: {str(e)}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id
                }
            )
            raise

        # 4. Validate query syntax
        try:
            self._validate_query_syntax(query, query_type)
        except ValidationError as e:
            logger.warning(
                f"Query validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "query_type": query_type,
                    "error_code": e.code
                }
            )
            raise

        # 5. Validate schema
        try:
            self._validate_schema(schema)
        except ValidationError as e:
            logger.warning(
                f"Schema validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code
                }
            )
            raise

        # 6. Validate source connectivity
        try:
            self._validate_source_connectivity(sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Source connectivity check failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details
                }
            )
            raise

        # 7. Validate compliance of federated sources
        try:
            self._validate_compliance_for_sources(sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Compliance validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details
                }
            )
            raise

        # 8. Validate query compliance
        try:
            self._validate_query_compliance(query, query_type, sources, effective_tenant_id)
        except ValidationError as e:
            logger.warning(
                f"Query compliance validation failed for virtual dataset creation: {e.message}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "error_code": e.code,
                    "details": e.details
                }
            )
            raise

        # 9. Check for duplicate name/version combination
        existing = VirtualDataset.objects.filter(
            tenant_id=effective_tenant_id,
            name=name,
            version=version
        ).first()
        if existing:
            raise ConflictError(
                f"Virtual dataset with name '{name}' and version '{version}' already exists"
            )

        # 10. Create virtual dataset
        import time
        creation_start_time = time.time()
        try:
            virtual_dataset = VirtualDataset.objects.create(
                tenant=tenant,
                created_by=user,
                name=name,
                description=description,
                query=query,
                query_type=query_type,
                schema=schema or {},
                sources=sources or [],
                version=version,
                status=status,
            )

            # Track metrics for successful creation
            creation_duration = time.time() - creation_start_time
            tenant_id_str = get_tenant_id(effective_tenant_id)
            query_type_str = get_query_type(query_type)
            status_str = str(status)

            virtualization_dataset_created_total.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                status=status_str
            ).inc()

            virtualization_dataset_creation_duration_seconds.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                status=status_str
            ).observe(creation_duration)

        except Exception as e:
            # Track metrics for failed creation
            creation_duration = time.time() - creation_start_time
            tenant_id_str = get_tenant_id(effective_tenant_id)
            query_type_str = get_query_type(query_type)

            virtualization_dataset_created_total.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                status="FAILED"
            ).inc()

            virtualization_dataset_creation_duration_seconds.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                status="FAILED"
            ).observe(creation_duration)

            logger.error(
                f"Failed to create virtual dataset: {str(e)}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "dataset_name": name,  # Use dataset_name instead of name (name is reserved in LogRecord)
                    "query_type": query_type
                },
                exc_info=True
            )
            raise ValidationError(
                f"Failed to create virtual dataset: {str(e)}",
                code="DATASET_CREATION_FAILED"
            ) from e

        # 11. Publish event
        try:
            self.publish_virtual_dataset_created(
                virtual_dataset_id=str(virtual_dataset.id),
                name=virtual_dataset.name,
                query_type=virtual_dataset.query_type,
                status=virtual_dataset.status,
                version=virtual_dataset.version,
                tenant_id=effective_tenant_id,
            )
        except Exception as e:
            # Log but don't fail dataset creation if event publishing fails
            logger.warning(
                f"Failed to publish virtualization.dataset.created event for dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        # 9. Index for search
        try:
            from hub.apps.search.indexing import SearchIndexer
            SearchIndexer.index_virtual_dataset(virtual_dataset)
        except Exception as e:
            # Log but don't fail dataset creation if indexing fails
            logger.warning(
                f"Failed to index virtual dataset {virtual_dataset.id} for search: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        # 10. Create audit log
        try:
            audit_details = {
                "dataset_id": str(virtual_dataset.id),
                "name": virtual_dataset.name,
                "query_type": virtual_dataset.query_type,
                "sources": sources if sources else [],
                "status": virtual_dataset.status,
                "version": virtual_dataset.version,
                "source_count": len(sources) if sources else 0,
                "has_schema": schema is not None and bool(schema),
            }
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="CREATED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log but don't fail dataset creation if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        logger.info(
            f"Virtual dataset created successfully: {virtual_dataset.id}",
            extra={
                "virtual_dataset_id": str(virtual_dataset.id),
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
                "dataset_name": name,  # Use 'dataset_name' instead of 'name' to avoid LogRecord conflict
                "query_type": query_type,
                "status": status
            }
        )

        return virtual_dataset

    @transaction.atomic
    def update_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        name: Optional[str] = None,
        query: Optional[str] = None,
        query_type: Optional[QueryType] = None,
        description: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        version: Optional[str] = None,
        status: Optional[VirtualDatasetStatus] = None,
    ) -> VirtualDataset:
        """
        Update a virtual dataset with comprehensive validation and audit logging.

        Args:
            virtual_dataset_id: ID of the virtual dataset to update
            tenant_id: Tenant ID (optional, uses service default if not provided)
            user_id: User ID performing the update (optional, uses service default if not provided)
            name: Optional new name
            query: Optional new query definition
            query_type: Optional new query type
            description: Optional new description
            schema: Optional new schema definition
            sources: Optional new sources list
            version: Optional new version
            status: Optional new status

        Returns:
            Updated VirtualDataset instance

        Raises:
            NotFoundError: If virtual dataset not found
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions
        """
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.utils import create_audit_event

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Get virtual dataset
        try:
            virtual_dataset = VirtualDataset.objects.get(
                id=virtual_dataset_id,
                tenant_id=effective_tenant_id
            )
        except VirtualDataset.DoesNotExist:
            raise NotFoundError(f"Virtual dataset with id {virtual_dataset_id} not found")

        # Store original values for audit log
        original_values = {
            "name": virtual_dataset.name,
            "query": virtual_dataset.query,
            "query_type": virtual_dataset.query_type,
            "description": virtual_dataset.description,
            "schema": virtual_dataset.schema,
            "sources": virtual_dataset.sources,
            "version": virtual_dataset.version,
            "status": virtual_dataset.status,
        }

        # Check user permissions
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset update: {str(e)}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "virtual_dataset_id": virtual_dataset_id
                }
            )
            raise

        # Update fields if provided
        if name is not None:
            virtual_dataset.name = name
        if query is not None:
            # Validate query syntax if query is being updated
            self._validate_query_syntax(query, query_type or virtual_dataset.query_type)
            virtual_dataset.query = query
        if query_type is not None:
            virtual_dataset.query_type = query_type
        if description is not None:
            virtual_dataset.description = description
        if schema is not None:
            # Validate schema if provided
            self._validate_schema(schema)
            virtual_dataset.schema = schema
        if sources is not None:
            # Validate source connectivity if sources are being updated
            self._validate_source_connectivity(sources, effective_tenant_id)
            virtual_dataset.sources = sources
        if version is not None:
            virtual_dataset.version = version
        if status is not None:
            virtual_dataset.status = status

        # Validate via VirtualizationBusinessRules before save (updated state)
        rules = VirtualizationBusinessRules(
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
        )
        result = rules.validate(
            virtual_dataset=virtual_dataset,
            tenant=tenant,
            user=user,
            validation_type="all",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Save the updated dataset
        virtual_dataset.save()

        # Determine what changed (for both event and audit log)
        changes = {}
        if name is not None and name != original_values["name"]:
            changes["name"] = {"old": original_values["name"], "new": name}
        if query is not None and query != original_values["query"]:
            changes["query"] = {"old": "***REDACTED***", "new": "***REDACTED***"}  # Don't log full queries
        if query_type is not None and query_type != original_values["query_type"]:
            changes["query_type"] = {"old": original_values["query_type"], "new": query_type}
        if description is not None and description != original_values["description"]:
            changes["description"] = {"old": original_values["description"], "new": description}
        if schema is not None and schema != original_values["schema"]:
            changes["schema"] = {"old": "***REDACTED***", "new": "***REDACTED***"}  # Don't log full schemas
        if sources is not None and sources != original_values["sources"]:
            changes["sources"] = {"old": len(original_values["sources"]) if original_values["sources"] else 0, "new": len(sources) if sources else 0}
        if version is not None and version != original_values["version"]:
            changes["version"] = {"old": original_values["version"], "new": version}
        if status is not None and status != original_values["status"]:
            changes["status"] = {"old": original_values["status"], "new": status}

        # Update search index
        self._update_search_index(virtual_dataset)

        # Publish update event
        previous_status = original_values["status"]
        new_status = virtual_dataset.status
        self.publish_virtual_dataset_updated(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
            changes=changes,
            previous_status=str(previous_status) if previous_status else None,
            new_status=str(new_status) if new_status else None
        )

        # Create audit log
        try:
            if name is not None and name != original_values["name"]:
                changes["name"] = {"old": original_values["name"], "new": name}
            if query is not None and query != original_values["query"]:
                changes["query"] = {"old": "***REDACTED***", "new": "***REDACTED***"}  # Don't log full queries
            if query_type is not None and query_type != original_values["query_type"]:
                changes["query_type"] = {"old": original_values["query_type"], "new": query_type}
            if description is not None and description != original_values["description"]:
                changes["description"] = {"old": original_values["description"], "new": description}
            if schema is not None and schema != original_values["schema"]:
                changes["schema"] = {"old": "***REDACTED***", "new": "***REDACTED***"}  # Don't log full schemas
            if sources is not None and sources != original_values["sources"]:
                changes["sources"] = {"old": len(original_values["sources"]) if original_values["sources"] else 0, "new": len(sources) if sources else 0}
            if version is not None and version != original_values["version"]:
                changes["version"] = {"old": original_values["version"], "new": version}
            if status is not None and status != original_values["status"]:
                changes["status"] = {"old": original_values["status"], "new": status}

            audit_details = {
                "dataset_id": str(virtual_dataset.id),
                "query_type": virtual_dataset.query_type,
                "sources": virtual_dataset.sources if virtual_dataset.sources else [],
                "changes": changes if changes else {},
                "name": virtual_dataset.name,
                "version": virtual_dataset.version,
                "status": virtual_dataset.status,
            }
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="UPDATED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=audit_details,
            )
        except Exception as e:
            # Log but don't fail dataset update if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset update {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        logger.info(
            f"Virtual dataset updated successfully: {virtual_dataset.id}",
            extra={
                "virtual_dataset_id": str(virtual_dataset.id),
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
            }
        )

        return virtual_dataset

    @transaction.atomic
    def delete_virtual_dataset(
        self,
        virtual_dataset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Delete a virtual dataset with comprehensive audit logging.

        Args:
            virtual_dataset_id: ID of the virtual dataset to delete
            tenant_id: Tenant ID (optional, uses service default if not provided)
            user_id: User ID performing the deletion (optional, uses service default if not provided)

        Raises:
            NotFoundError: If virtual dataset not found
            ValidationError: If validation fails
            PermissionError: If user lacks required permissions
        """
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.utils import create_audit_event

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get tenant and user objects
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(f"Tenant with id {effective_tenant_id} not found")

        User = get_user_model()
        try:
            user = User.objects.get(id=effective_user_id)
        except User.DoesNotExist:
            raise NotFoundError(f"User with id {effective_user_id} not found")

        # Get virtual dataset
        try:
            virtual_dataset = VirtualDataset.objects.get(
                id=virtual_dataset_id,
                tenant_id=effective_tenant_id
            )
        except VirtualDataset.DoesNotExist:
            raise NotFoundError(f"Virtual dataset with id {virtual_dataset_id} not found")

        # Store dataset info for audit log before deletion
        dataset_info = {
            "dataset_id": str(virtual_dataset.id),
            "name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "sources": virtual_dataset.sources if virtual_dataset.sources else [],
            "version": virtual_dataset.version,
            "status": virtual_dataset.status,
        }

        # Check user permissions
        try:
            self._check_user_permissions(effective_user_id, effective_tenant_id)
        except PermissionError as e:
            logger.warning(
                f"User permission check failed for virtual dataset deletion: {str(e)}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "user_id": effective_user_id,
                    "virtual_dataset_id": virtual_dataset_id
                }
            )
            raise

        # Remove from search index
        self._remove_from_search_index(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=effective_tenant_id
        )

        # Publish delete event
        self.publish_virtual_dataset_deleted(
            virtual_dataset_id=str(virtual_dataset.id),
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
            reason="User requested deletion"
        )

        # Create audit log before deletion
        try:
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="DELETED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details=dataset_info,
            )
        except Exception as e:
            # Log but don't fail dataset deletion if audit logging fails
            logger.warning(
                f"Failed to create audit log for virtual dataset deletion {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        # Delete the virtual dataset
        virtual_dataset.delete()

        logger.info(
            f"Virtual dataset deleted successfully: {virtual_dataset_id}",
            extra={
                "virtual_dataset_id": virtual_dataset_id,
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
            }
        )

    def _update_search_index(self, virtual_dataset: VirtualDataset) -> None:
        """
        Update search index for a virtual dataset.

        This is a helper method that can be called from update methods
        to keep the search index in sync with virtual dataset changes.

        Args:
            virtual_dataset: VirtualDataset instance to index
        """
        try:
            from hub.apps.search.indexing import SearchIndexer
            SearchIndexer.index_virtual_dataset(virtual_dataset)
        except Exception as e:
            # Log but don't fail operation if indexing fails
            logger.warning(
                f"Failed to update search index for virtual dataset {virtual_dataset.id}: {e}",
                extra={
                    "virtual_dataset_id": str(virtual_dataset.id),
                    "tenant_id": str(virtual_dataset.tenant_id),
                    "error": str(e)
                },
                exc_info=True
            )

    def _remove_from_search_index(
        self,
        virtual_dataset_id: str,
        tenant_id: str
    ) -> None:
        """
        Remove virtual dataset from search index.

        This is a helper method that can be called from delete methods
        to remove the virtual dataset from the search index.

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID
        """
        try:
            from hub.apps.search.indexing import SearchIndexer
            SearchIndexer.delete_index(
                tenant_id=tenant_id,
                resource_type="VIRTUAL_DATASET",
                resource_id=virtual_dataset_id
            )
        except Exception as e:
            # Log but don't fail operation if index removal fails
            logger.warning(
                f"Failed to remove virtual dataset {virtual_dataset_id} from search index: {e}",
                extra={
                    "virtual_dataset_id": virtual_dataset_id,
                    "tenant_id": tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

    def execute_query(
        self,
        virtual_dataset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        execution_mode: Optional[QueryExecutionMode] = None,
        parameters: Optional[Dict[str, Any]] = None,
        force_async: bool = False,
        timeout_seconds: Optional[int] = None
    ) -> QueryExecution:
        """
        Execute a query for a virtual dataset using VirtualizationWorkflow.

        This method orchestrates query execution through the VirtualizationWorkflow,
        which performs:
        1. Query parsing and validation
        2. Source compatibility validation
        3. Query optimization
        4. Source query execution (PostgreSQL, MySQL, SQL Server, Jena Fuseki, MinIO, REST APIs, GraphQL APIs)
        5. Result aggregation from multiple sources
        6. Result caching (Redis, TTL: 1 hour)
        7. Result storage (if needed)
        8. Execution monitoring and progress tracking
        9. Event publishing (virtualization.query.execution.started, completed, failed)

        Args:
            virtual_dataset_id: Virtual dataset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID executing the query (uses service user_id if not provided)
            execution_mode: Execution mode (SYNC, ASYNC, etc.) - auto-determined if not provided
            parameters: Query parameters dictionary
            force_async: Force asynchronous execution even for small queries
            timeout_seconds: Query timeout in seconds (default: 300 for sync, 3600 for async)

        Returns:
            QueryExecution instance with workflow_instance linked

        Raises:
            NotFoundError: If virtual dataset not found
            ValidationError: If dataset is inactive or validation fails
        """
        from hub.apps.orchestration.workflows.virtualization import VirtualizationWorkflow
        from hub.apps.orchestration.workflow_engine import WorkflowEngine
        from hub.apps.orchestration.registry import WorkflowRegistry
        from django.core.cache import cache

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id
        if not effective_user_id:
            raise ValidationError("user_id is required")

        # Get virtual dataset
        virtual_dataset = self.get_virtual_dataset(virtual_dataset_id, effective_tenant_id)

        # Validate dataset is active
        if virtual_dataset.status != VirtualDatasetStatus.ACTIVE:
            raise ValidationError(
                f"Virtual dataset {virtual_dataset_id} is not active (status: {virtual_dataset.status})",
                code="DATASET_NOT_ACTIVE"
            )

        # Set defaults
        parameters = parameters or {}
        if timeout_seconds is None:
            timeout_seconds = 300 if execution_mode == QueryExecutionMode.SYNC else 3600

        # Check cache first (for sync mode with same parameters)
        if execution_mode != QueryExecutionMode.ASYNC and not force_async:
            cache_key = self._get_query_cache_key(virtual_dataset, parameters)
            cached_result = cache.get(cache_key)
            if cached_result:
                # Track cache hit
                tenant_id_str = get_tenant_id(effective_tenant_id)
                query_type_str = get_query_type(virtual_dataset.query_type)
                virtualization_query_result_cache_hit_rate.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str
                ).inc()

                # Create execution record for cached result (no workflow needed for cached results)
                execution = QueryExecution.objects.create(
                    virtual_dataset=virtual_dataset,
                    query=self._apply_parameters(virtual_dataset.query, parameters),
                    parameters=parameters,
                    execution_mode=QueryExecutionMode.SYNC,
                    status=QueryExecutionStatus.COMPLETED,
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                    result_cache_key=cache_key,
                    metrics={
                        "duration_ms": 0,
                        "rows_processed": cached_result.get("row_count", 0),
                        "cached": True
                    }
                )

                # Track execution metrics for cached result
                virtualization_query_execution_started_total.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str,
                    execution_mode="SYNC"
                ).inc()

                virtualization_query_execution_completed_total.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str,
                    execution_mode="SYNC",
                    status="COMPLETED"
                ).inc()

                # Track result size for cached result
                result_data = cached_result.get("data", [])
                if isinstance(result_data, list):
                    result_size_bytes = len(str(result_data).encode('utf-8'))
                    virtualization_query_result_size_bytes.labels(
                        tenant_id=tenant_id_str,
                        query_type=query_type_str,
                        execution_mode="SYNC"
                    ).observe(result_size_bytes)

                    row_count = cached_result.get("row_count", len(result_data))
                    virtualization_query_result_rows_total.labels(
                        tenant_id=tenant_id_str,
                        query_type=query_type_str,
                        execution_mode="SYNC"
                    ).observe(row_count)

                logger.info(
                    f"Query execution {execution.id} completed from cache",
                    extra={
                        "execution_id": str(execution.id),
                        "virtual_dataset_id": virtual_dataset_id,
                        "cache_key": cache_key
                    }
                )
                return execution
            else:
                # Track cache miss
                tenant_id_str = get_tenant_id(effective_tenant_id)
                query_type_str = get_query_type(virtual_dataset.query_type)
                virtualization_query_result_cache_misses_total.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str
                ).inc()

        # Determine execution mode if not provided using QueryExecutionBusinessRules
        if execution_mode is None:
            execution_rules = QueryExecutionBusinessRules(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id
            )
            execution_mode = execution_rules.select_execution_mode(
                virtual_dataset=virtual_dataset,
                parameters=parameters,
                force_async=force_async,
                raise_on_error=False
            )

        # Initialize workflow engine and registry
        engine = WorkflowEngine()
        registry = WorkflowRegistry()
        VirtualizationWorkflow.register_workflow(registry)
        VirtualizationWorkflow.register_tasks(engine)

        # Determine execution mode based on force_async flag
        # If force_async is True, override execution_mode to ASYNC
        if force_async:
            effective_execution_mode = QueryExecutionMode.ASYNC
        else:
            effective_execution_mode = execution_mode or QueryExecutionMode.SYNC

        # Track query execution started
        tenant_id_str = get_tenant_id(effective_tenant_id)
        query_type_str = get_query_type(virtual_dataset.query_type)
        execution_mode_str = get_execution_mode(effective_execution_mode)

        virtualization_query_execution_started_total.labels(
            tenant_id=tenant_id_str,
            query_type=query_type_str,
            execution_mode=execution_mode_str
        ).inc()

        # Execute workflow
        try:
            workflow_result = VirtualizationWorkflow.execute(
                virtual_dataset_id=virtual_dataset_id,
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
                parameters=parameters,
                execution_mode=effective_execution_mode,
                timeout_seconds=timeout_seconds,
                engine=engine,
                registry=registry
            )

            # Get execution from workflow result
            execution_id = workflow_result.get("execution_id")
            if not execution_id:
                raise ValidationError("Workflow execution did not return execution_id")

            execution = QueryExecution.objects.get(id=execution_id)

            # Link workflow instance to execution
            workflow_instance_id = workflow_result.get("workflow_instance_id")
            if workflow_instance_id:
                from hub.apps.orchestration.models import WorkflowInstance
                workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
                execution.workflow_instance = workflow_instance
                execution.save(update_fields=['workflow_instance'])

            return execution

        except ValueError as e:
            # Workflow execution failed - try to get execution from workflow instance
            from hub.apps.orchestration.models import WorkflowInstance
            workflow_instances = WorkflowInstance.objects.filter(
                workflow_name=VirtualizationWorkflow.WORKFLOW_NAME,
                tenant_id=effective_tenant_id
            ).order_by('-created_at')

            if workflow_instances.exists():
                workflow_instance = workflow_instances.first()
                execution_id = workflow_instance.state_data.get("execution_id")
                if execution_id:
                    try:
                        execution = QueryExecution.objects.get(id=execution_id)
                        execution.workflow_instance = workflow_instance
                        execution.save(update_fields=['workflow_instance'])
                        # Return the execution even though workflow failed
                        # This allows callers to check the execution status
                        return execution
                    except QueryExecution.DoesNotExist:
                        # Execution was referenced but doesn't exist (might have been rolled back)
                        pass

            # If no execution found, raise error with workflow context
            error_msg = f"Query execution failed: {str(e)}"
            if workflow_instances.exists():
                workflow_instance = workflow_instances.first()
                error_msg += f" (workflow_instance_id: {workflow_instance.id})"
            raise ValidationError(error_msg) from e

    def get_workflow_instance(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None
    ) -> Optional[Any]:
        """
        Get workflow instance for a query execution.

        Args:
            execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            WorkflowInstance or None if not found

        Raises:
            NotFoundError: If query execution not found
        """
        from hub.apps.orchestration.models import WorkflowInstance

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        try:
            execution = QueryExecution.objects.get(
                id=execution_id,
                virtual_dataset__tenant_id=effective_tenant_id
            )
            return execution.workflow_instance
        except QueryExecution.DoesNotExist:
            raise NotFoundError(f"Query execution {execution_id} not found")

    def get_workflow_state(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get workflow state data for a query execution.

        Args:
            execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Dictionary containing workflow state data

        Raises:
            NotFoundError: If query execution not found
        """
        workflow_instance = self.get_workflow_instance(execution_id, tenant_id)
        if not workflow_instance:
            return {}

        return {
            "workflow_instance_id": str(workflow_instance.id),
            "workflow_name": workflow_instance.workflow_name,
            "workflow_version": workflow_instance.workflow_version,
            "status": workflow_instance.status,
            "current_step": workflow_instance.state_data.get("current_step"),
            "progress_percentage": workflow_instance.state_data.get("progress_percentage", 0),
            "state_data": workflow_instance.state_data,
            "error_message": workflow_instance.error_message,
            "error_details": workflow_instance.error_details
        }

    def get_workflow_progress(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get workflow progress information for a query execution.

        Args:
            execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Dictionary containing progress information

        Raises:
            NotFoundError: If query execution not found
        """
        workflow_instance = self.get_workflow_instance(execution_id, tenant_id)
        if not workflow_instance:
            return {
                "progress_percentage": 0,
                "current_step": None,
                "status": "UNKNOWN"
            }

        return {
            "progress_percentage": workflow_instance.state_data.get("progress_percentage", 0),
            "current_step": workflow_instance.state_data.get("current_step"),
            "status": workflow_instance.status,
            "workflow_instance_id": str(workflow_instance.id)
        }

    def _get_query_cache_key(
        self,
        virtual_dataset: VirtualDataset,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Generate cache key for query result.

        Args:
            virtual_dataset: VirtualDataset instance
            parameters: Query parameters

        Returns:
            Cache key string
        """
        import hashlib
        import json

        # Create cache key from dataset ID, query hash, and parameters
        query_hash = hashlib.md5(virtual_dataset.query.encode()).hexdigest()[:8]
        params_hash = hashlib.md5(json.dumps(parameters, sort_keys=True).encode()).hexdigest()[:8]
        return f"virtual_query:{virtual_dataset.id}:{query_hash}:{params_hash}"

    # ------------------------------------------------------------------
    # Parameter handling helpers (Phase 87 — SQL injection fix)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_query_params(
        query: str,
        parameters: Dict[str, Any],
    ) -> tuple:
        """Convert mixed placeholder styles to DB-API ``%s`` positional params.

        Accepts ``:name`` and ``%(name)s`` placeholders.  Returns
        ``(normalised_query, ordered_values)`` ready for
        ``cursor.execute(query, values)``.

        Parameters are bound in **query-appearance order** so that positional
        ``%s`` markers always match the correct value, even when a query mixes
        ``:name`` and ``%(name)s`` styles.

        When ``PARAMETERIZED_VIRTUAL_QUERIES`` is *False* the legacy
        string-interpolation path is used instead (emergency rollback).
        """
        from django.conf import settings

        if not parameters:
            return query, ()

        use_parameterised = getattr(settings, "PARAMETERIZED_VIRTUAL_QUERIES", True)
        if not use_parameterised:
            return VirtualizationService._apply_parameters_legacy(query, parameters), ()

        # Build a list of all placeholder occurrences with their positions
        # so we can replace them left-to-right (query-appearance order).
        # Sort keys longest-first so ":name_full" is matched before ":name".
        occurrences: list = []  # [(position, placeholder_len, key), ...]
        sorted_keys = sorted(parameters, key=len, reverse=True)

        for key in sorted_keys:
            # Find all :key occurrences
            colon_ph = f":{key}"
            start = 0
            while True:
                idx = query.find(colon_ph, start)
                if idx == -1:
                    break
                occurrences.append((idx, len(colon_ph), key))
                start = idx + len(colon_ph)

            # Find all %(key)s occurrences
            pct_ph = f"%({key})s"
            start = 0
            while True:
                idx = query.find(pct_ph, start)
                if idx == -1:
                    break
                occurrences.append((idx, len(pct_ph), key))
                start = idx + len(pct_ph)

        # Sort by position (left-to-right in the query)
        occurrences.sort(key=lambda t: t[0])

        # Remove overlapping matches (longer keys matched first may overlap
        # with shorter key matches at the same position — keep first wins)
        filtered: list = []
        end = -1
        for pos, length, key in occurrences:
            if pos >= end:
                filtered.append((pos, length, key))
                end = pos + length

        # Build result by replacing left-to-right
        ordered_values: list = []
        result_parts: list = []
        prev_end = 0
        for pos, length, key in filtered:
            result_parts.append(query[prev_end:pos])
            result_parts.append("%s")
            ordered_values.append(parameters[key])
            prev_end = pos + length
        result_parts.append(query[prev_end:])

        return "".join(result_parts), tuple(ordered_values)

    @staticmethod
    def _normalise_query_params_named(
        query: str,
        parameters: Dict[str, Any],
    ) -> tuple:
        """Convert mixed placeholder styles to SQLAlchemy ``:name`` params.

        Returns ``(normalised_query, params_dict)`` for use with
        ``conn.execute(text(query), params)``.
        """
        from django.conf import settings

        if not parameters:
            return query, {}

        use_parameterised = getattr(settings, "PARAMETERIZED_VIRTUAL_QUERIES", True)
        if not use_parameterised:
            return VirtualizationService._apply_parameters_legacy(query, parameters), {}

        result = query
        for key in sorted(parameters, key=len, reverse=True):
            # %(key)s  →  :key
            result = result.replace(f"%({key})s", f":{key}")

        return result, dict(parameters)

    @staticmethod
    def _apply_parameters_legacy(
        query: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Legacy string-interpolation path (kept behind feature flag for rollback)."""
        if not parameters:
            return query
        result = query
        for key, value in parameters.items():
            result = result.replace(f":{key}", str(value))
            result = result.replace(f"%({key})s", str(value))
        return result

    def _apply_parameters(
        self,
        query: str,
        parameters: Dict[str, Any]
    ) -> str:
        """Render query with parameters for *display/logging only*.

        This method is ONLY used for storing the resolved query text in
        ``QueryExecution.query`` for audit purposes.  It MUST NOT be used
        to build queries sent to a database cursor — use
        ``_normalise_query_params`` / ``_normalise_query_params_named``
        for that.
        """
        if not parameters:
            return query
        result = query
        for key, value in parameters.items():
            result = result.replace(f":{key}", str(value))
            result = result.replace(f"%({key})s", str(value))
        return result

    def _execute_query_sync(
        self,
        execution: QueryExecution,
        virtual_dataset: VirtualDataset,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> QueryExecution:
        """
        Execute query synchronously.

        Args:
            execution: QueryExecution instance
            virtual_dataset: VirtualDataset instance
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            Updated QueryExecution instance
        """
        import time
        from django.core.cache import cache
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import Tenant
        from hub.apps.audit.utils import create_audit_event

        start_time = time.time()
        execution.mark_started()

        # Get user and tenant objects for audit logging
        user = None
        tenant = None
        if self.user_id:
            try:
                User = get_user_model()
                user = User.objects.get(id=self.user_id)
            except User.DoesNotExist:
                logger.warning(f"User {self.user_id} not found for audit logging")
        if self.tenant_id:
            try:
                tenant = Tenant.objects.get(id=self.tenant_id)
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant {self.tenant_id} not found for audit logging")

        # Log query execution start
        try:
            create_audit_event(
                resource_type="VIRTUAL_DATASET",
                action="QUERY_EXECUTION_STARTED",
                actor_user=user,
                tenant=tenant,
                resource_id=str(virtual_dataset.id),
                result="SUCCESS",
                details={
                    "execution_id": str(execution.id),
                    "dataset_id": str(virtual_dataset.id),
                    "dataset_name": virtual_dataset.name,
                    "query_type": virtual_dataset.query_type,
                    "sources": virtual_dataset.sources or [],
                    "execution_mode": execution.execution_mode,
                    "parameters": parameters
                }
            )
        except Exception as e:
            # Log but don't fail query execution if audit logging fails
            logger.warning(
                f"Failed to create audit log for query execution start {execution.id}: {e}",
                exc_info=True
            )

        try:
            # Parse and validate query
            self._parse_and_validate_query(virtual_dataset.query, virtual_dataset.query_type)

            # Run compliance checks before query execution
            try:
                self._run_compliance_check_before_query(
                    virtual_dataset,
                    execution,
                    str(self.tenant_id) if self.tenant_id else None
                )
            except ValidationError:
                # Re-raise validation errors (compliance violations)
                raise
            except Exception as e:
                # Log compliance check failure but don't fail query execution if service unavailable
                execution.add_log_entry(
                    "WARNING",
                    f"Compliance check failed: {str(e)}",
                    save=False
                )
                logger.warning(
                    f"Compliance check failed for query execution {execution.id}: {e}",
                    extra={
                        "execution_id": str(execution.id),
                        "error": str(e)
                    },
                    exc_info=True
                )
                # Only fail if it's a ValidationError (compliance violation)
                # Otherwise, continue with query execution

            # Optimize query
            optimized_query = self._optimize_query(virtual_dataset.query, virtual_dataset.query_type, virtual_dataset.sources)

            # Execute query against sources
            results = self._execute_query_against_sources(
                optimized_query,
                virtual_dataset.query_type,
                virtual_dataset.sources or [],
                parameters,
                timeout_seconds
            )

            # Aggregate results from multiple sources
            aggregated_results = self._aggregate_results(results, virtual_dataset.query_type)

            # Run quality checks on results (if results are available)
            quality_metrics = None
            if aggregated_results and len(aggregated_results) > 0:
                try:
                    quality_metrics = self._run_quality_check_on_results(
                        aggregated_results,
                        execution,
                        virtual_dataset
                    )
                except Exception as e:
                    # Log quality check failure but don't fail query execution
                    execution.add_log_entry(
                        "WARNING",
                        f"Quality check failed: {str(e)}",
                        save=False
                    )
                    logger.warning(
                        f"Quality check failed for query execution {execution.id}: {e}",
                        extra={
                            "execution_id": str(execution.id),
                            "error": str(e)
                        },
                        exc_info=True
                    )

            # Cache results (TTL: 1 hour = 3600 seconds)
            cache_key = self._get_query_cache_key(virtual_dataset, parameters)
            cache.set(
                cache_key,
                {
                    "data": aggregated_results,
                    "row_count": len(aggregated_results) if isinstance(aggregated_results, list) else 0,
                    "query_type": virtual_dataset.query_type,
                    "cached_at": timezone.now().isoformat()
                },
                timeout=3600  # 1 hour
            )

            # Calculate metrics
            duration_seconds = time.time() - start_time
            duration_ms = int(duration_seconds * 1000)
            row_count = len(aggregated_results) if isinstance(aggregated_results, list) else 0

            # Build metrics dictionary
            metrics = {
                "duration_ms": duration_ms,
                "rows_processed": row_count,
                "sources_count": len(virtual_dataset.sources) if virtual_dataset.sources else 0
            }

            # Track Prometheus metrics
            tenant_id_str = get_tenant_id(self.tenant_id)
            query_type_str = get_query_type(virtual_dataset.query_type)
            execution_mode_str = get_execution_mode(execution.execution_mode)

            virtualization_query_execution_completed_total.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                execution_mode=execution_mode_str,
                status="COMPLETED"
            ).inc()

            virtualization_query_execution_duration_seconds.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                execution_mode=execution_mode_str,
                status="COMPLETED"
            ).observe(duration_seconds)

            # Track result size
            if aggregated_results:
                result_size_bytes = len(str(aggregated_results).encode('utf-8'))
                virtualization_query_result_size_bytes.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str,
                    execution_mode=execution_mode_str
                ).observe(result_size_bytes)

                virtualization_query_result_rows_total.labels(
                    tenant_id=tenant_id_str,
                    query_type=query_type_str,
                    execution_mode=execution_mode_str
                ).observe(row_count)

            # Add quality metrics if available
            if quality_metrics:
                quality_score = quality_metrics.get("quality_score")
                if quality_score is not None:
                    metrics["quality_score"] = float(quality_score)
                metrics["quality_status"] = quality_metrics.get("overall_status")
                checks_passed = quality_metrics.get("checks_passed", 0)
                checks_failed = quality_metrics.get("checks_failed", 0)
                metrics["quality_checks_passed"] = int(checks_passed) if checks_passed is not None else 0
                metrics["quality_checks_failed"] = int(checks_failed) if checks_failed is not None else 0

            # Mark execution as completed
            execution.mark_completed(metrics=metrics)
            execution.result_cache_key = cache_key
            execution.save()

            # Log query execution completion
            try:
                create_audit_event(
                    resource_type="VIRTUAL_DATASET",
                    action="QUERY_EXECUTION_COMPLETED",
                    actor_user=user,
                    tenant=tenant,
                    resource_id=str(virtual_dataset.id),
                    result="SUCCESS",
                    details={
                        "execution_id": str(execution.id),
                        "dataset_id": str(virtual_dataset.id),
                        "dataset_name": virtual_dataset.name,
                        "query_type": virtual_dataset.query_type,
                        "sources": virtual_dataset.sources or [],
                        "execution_mode": execution.execution_mode,
                        "duration_ms": duration_ms,
                        "row_count": row_count,
                        "sources_count": len(virtual_dataset.sources) if virtual_dataset.sources else 0,
                        "quality_score": quality_metrics.get("quality_score") if quality_metrics else None,
                        "quality_status": quality_metrics.get("overall_status") if quality_metrics else None
                    }
                )
            except Exception as e:
                # Log but don't fail query execution if audit logging fails
                logger.warning(
                    f"Failed to create audit log for query execution completion {execution.id}: {e}",
                    exc_info=True
                )

            # Publish execution completed event
            self._publish_execution_completed(execution, row_count)

            logger.info(
                f"Query execution {execution.id} completed successfully",
                extra={
                    "execution_id": str(execution.id),
                    "duration_ms": duration_ms,
                    "row_count": row_count
                }
            )

        except Exception as e:
            duration_seconds = time.time() - start_time
            duration_ms = int(duration_seconds * 1000)
            execution.mark_failed(str(e), metrics={"duration_ms": duration_ms})

            # Track Prometheus metrics for failed execution
            tenant_id_str = get_tenant_id(self.tenant_id)
            query_type_str = get_query_type(virtual_dataset.query_type)
            execution_mode_str = get_execution_mode(execution.execution_mode)
            error_type = type(e).__name__

            virtualization_query_execution_failed_total.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                execution_mode=execution_mode_str,
                error_type=error_type
            ).inc()

            virtualization_query_execution_completed_total.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                execution_mode=execution_mode_str,
                status="FAILED"
            ).inc()

            virtualization_query_execution_duration_seconds.labels(
                tenant_id=tenant_id_str,
                query_type=query_type_str,
                execution_mode=execution_mode_str,
                status="FAILED"
            ).observe(duration_seconds)

            # Log query execution failure
            try:
                create_audit_event(
                    resource_type="VIRTUAL_DATASET",
                    action="QUERY_EXECUTION_FAILED",
                    actor_user=user,
                    tenant=tenant,
                    resource_id=str(virtual_dataset.id),
                    result="FAILURE",
                    details={
                        "execution_id": str(execution.id),
                        "dataset_id": str(virtual_dataset.id),
                        "dataset_name": virtual_dataset.name,
                        "query_type": virtual_dataset.query_type,
                        "sources": virtual_dataset.sources or [],
                        "execution_mode": execution.execution_mode,
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "error_type": type(e).__name__
                    }
                )
            except Exception as audit_error:
                # Log but don't fail query execution if audit logging fails
                logger.warning(
                    f"Failed to create audit log for query execution failure {execution.id}: {audit_error}",
                    exc_info=True
                )

            self._publish_execution_failed(execution, str(e))
            logger.error(
                f"Query execution {execution.id} failed: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e)
                },
                exc_info=True
            )
            raise

        return execution

    def _parse_and_validate_query(
        self,
        query: str,
        query_type: QueryType
    ) -> None:
        """
        Parse and validate query syntax.

        Args:
            query: Query string
            query_type: Query type

        Raises:
            ValidationError: If query is invalid
        """
        if not query or not query.strip():
            raise ValidationError("Query cannot be empty", code="EMPTY_QUERY")

        query_upper = query.upper().strip()

        if query_type == QueryType.SQL:
            # Basic SQL validation
            forbidden_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE TABLE', 'CREATE DATABASE']
            for keyword in forbidden_keywords:
                if keyword in query_upper:
                    raise ValidationError(
                        f"SQL query contains forbidden keyword: {keyword}",
                        code="FORBIDDEN_SQL_KEYWORD"
                    )

            # Check for basic SQL structure
            if not any(keyword in query_upper for keyword in ['SELECT', 'WITH', 'INSERT', 'UPDATE']):
                raise ValidationError(
                    "SQL query must contain SELECT, WITH, INSERT, or UPDATE",
                    code="INVALID_SQL_STRUCTURE"
                )

        elif query_type == QueryType.SPARQL:
            # Basic SPARQL validation
            forbidden_keywords = ['INSERT', 'DELETE', 'DROP', 'CREATE', 'LOAD', 'CLEAR']
            for keyword in forbidden_keywords:
                if keyword in query_upper:
                    raise ValidationError(
                        f"SPARQL query contains forbidden keyword: {keyword}",
                        code="FORBIDDEN_SPARQL_KEYWORD"
                    )

            # Check for basic SPARQL structure
            if not any(keyword in query_upper for keyword in ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE', 'PREFIX']):
                raise ValidationError(
                    "SPARQL query must contain SELECT, CONSTRUCT, ASK, DESCRIBE, or PREFIX",
                    code="INVALID_SPARQL_STRUCTURE"
                )

        # Additional validation can be added for other query types

    def _optimize_query(
        self,
        query: str,
        query_type: QueryType,
        sources: Optional[List[Dict[str, Any]]]
    ) -> str:
        """
        Optimize query for execution.

        This is a basic implementation. More sophisticated optimization
        can be added later (query rewriting, index hints, etc.).

        Args:
            query: Query string
            query_type: Query type
            sources: Source configurations

        Returns:
            Optimized query string
        """
        # For now, return query as-is
        # Future: Add query optimization logic
        # - Remove unnecessary columns
        # - Add index hints
        # - Rewrite subqueries
        # - Push down filters
        return query

    def _run_compliance_check_before_query(
        self,
        virtual_dataset: VirtualDataset,
        execution: QueryExecution,
        tenant_id: Optional[str]
    ) -> None:
        """
        Run compliance checks before query execution.

        This method:
        1. Checks compliance for each source that references an asset
        2. Validates query doesn't violate compliance rules
        3. Checks cross-tenant source access permissions
        4. Blocks execution if compliance violations detected

        Args:
            virtual_dataset: VirtualDataset instance
            execution: QueryExecution instance for logging
            tenant_id: Tenant ID for tenant isolation

        Raises:
            ValidationError: If compliance validation fails or violations detected
        """
        if not tenant_id:
            logger.warning(
                f"Tenant ID not available for compliance check on execution {execution.id}",
                extra={"execution_id": str(execution.id)}
            )
            return  # Skip compliance check if tenant_id not available

        from hub.apps.compliance.service_client import ComplianceServiceClient
        from hub.apps.assets.models import Asset
        from hub.apps.files.storage import S3StorageClient

        sources = virtual_dataset.sources or []
        if not sources or len(sources) == 0:
            # No sources to check - SPARQL queries without sources are allowed
            if virtual_dataset.query_type == QueryType.SPARQL:
                return
            # For other query types, compliance check is not applicable
            return

        # Initialize compliance client
        compliance_client = ComplianceServiceClient()

        # Check compliance service health
        is_healthy, _ = compliance_client.health_check()
        if not is_healthy:
            execution.add_log_entry(
                "WARNING",
                "Compliance service unavailable, skipping compliance check",
                save=False
            )
            logger.warning(
                f"Compliance service unavailable for query execution {execution.id}, skipping compliance check",
                extra={"execution_id": str(execution.id)}
            )
            return  # Skip compliance check if service unavailable

        execution.add_log_entry(
            "INFO",
            f"Running compliance check on {len(sources)} source(s) before query execution",
            save=False
        )

        # Validate each source that references an asset
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                continue  # Skip invalid source configs

            asset_id = source_config.get("asset_id")
            if not asset_id:
                # Source doesn't reference an asset - check if it's a direct database/API source
                # For direct sources, we can't run compliance checks without asset metadata
                # But we should still validate cross-tenant access if source has tenant info
                source_tenant_id = source_config.get("tenant_id")
                if source_tenant_id and str(source_tenant_id) != tenant_id:
                    # Cross-tenant direct source - this should be validated at source creation time
                    # For query execution, we log a warning but don't block
                    execution.add_log_entry(
                        "WARNING",
                        f"Source at index {i} is from different tenant, access should be validated",
                        save=False
                    )
                continue

            try:
                # Get asset
                asset = Asset.objects.select_related('tenant').get(id=asset_id)
            except Asset.DoesNotExist:
                raise ValidationError(
                    f"Source at index {i} references non-existent asset: {asset_id}",
                    code="SOURCE_ASSET_NOT_FOUND",
                    details={"source_index": i, "asset_id": asset_id}
                )

            # Check cross-tenant source access permissions
            self._validate_cross_tenant_source_access(asset, tenant_id, source_index=i)

            # Get latest dataset for asset
            latest_dataset = asset.datasets.order_by('-version').first()
            if not latest_dataset or not latest_dataset.file:
                logger.warning(
                    f"Asset {asset_id} has no dataset or file, skipping compliance scan",
                    extra={"asset_id": asset_id, "source_index": i, "execution_id": str(execution.id)}
                )
                continue

            # Download file content for compliance scan
            try:
                storage_client = S3StorageClient()
                file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
                file_format = latest_dataset.format or 'csv'
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve file content for compliance scan: {e}",
                    extra={
                        "asset_id": asset_id,
                        "source_index": i,
                        "execution_id": str(execution.id),
                        "error": str(e)
                    }
                )
                # Continue with other sources even if one fails
                continue

            # Run compliance scan
            try:
                compliance_result = compliance_client.scan_file(
                    file_content=file_content,
                    file_format=file_format.lower(),
                    scan_mode="internal"
                )

                # Extract compliance status
                overall_status = compliance_result.get("overall_status", "UNKNOWN")
                risk_level = compliance_result.get("risk_level", "UNKNOWN")
                allowed_to_store = compliance_result.get("allowed_to_store", None)

                # Block execution if compliance violations detected
                if overall_status == "FAIL" or (allowed_to_store is False):
                    error_msg = (
                        f"Compliance check failed for source at index {i} (asset: {asset.name}). "
                        f"Overall status: {overall_status}, Risk level: {risk_level}. "
                        f"Query execution blocked due to compliance violations."
                    )
                    execution.add_log_entry(
                        "ERROR",
                        error_msg,
                        save=False
                    )
                    raise ValidationError(
                        error_msg,
                        code="COMPLIANCE_VIOLATION",
                        details={
                            "source_index": i,
                            "asset_id": str(asset.id),
                            "asset_name": asset.name,
                            "overall_status": overall_status,
                            "risk_level": risk_level,
                            "allowed_to_store": allowed_to_store,
                            "detected_categories": compliance_result.get("detected_categories", {}),
                            "column_findings": compliance_result.get("column_findings", []),
                            "regulation_mapping": compliance_result.get("regulation_mapping", {})
                        }
                    )

                # Log successful compliance check
                execution.add_log_entry(
                    "INFO",
                    f"Compliance check passed for source at index {i} (asset: {asset.name}), "
                    f"status: {overall_status}, risk: {risk_level}",
                    save=False
                )
                logger.info(
                    f"Compliance check passed for source at index {i} (asset: {asset.name})",
                    extra={
                        "execution_id": str(execution.id),
                        "source_index": i,
                        "asset_id": str(asset.id),
                        "overall_status": overall_status,
                        "risk_level": risk_level
                    }
                )

            except ValidationError:
                # Re-raise validation errors (compliance violations)
                raise
            except Exception as e:
                # Log error but don't fail query execution for compliance service errors
                # unless it's a critical validation error
                execution.add_log_entry(
                    "WARNING",
                    f"Error running compliance check for source at index {i}: {str(e)}",
                    save=False
                )
                logger.error(
                    f"Error running compliance check for source at index {i}: {e}",
                    extra={
                        "execution_id": str(execution.id),
                        "source_index": i,
                        "asset_id": str(asset.id),
                        "error": str(e)
                    },
                    exc_info=True
                )
                # Continue with other sources even if one fails
                continue

        # Validate query doesn't violate compliance rules
        # Check for potentially sensitive operations in query
        query_upper = virtual_dataset.query.upper().strip()

        # Check for operations that might violate compliance
        # This is a basic check - more sophisticated rule-based validation can be added
        sensitive_operations = []

        # SQL-specific checks
        if virtual_dataset.query_type == QueryType.SQL:
            # Check for operations that might expose sensitive data
            if "SELECT *" in query_upper and "LIMIT" not in query_upper:
                # Unbounded SELECT * queries might expose too much data
                # This is a warning, not a block
                execution.add_log_entry(
                    "WARNING",
                    "Query uses SELECT * without LIMIT - may expose large amounts of data",
                    save=False
                )

        # Log compliance check completion
        execution.add_log_entry(
            "INFO",
            "Compliance check completed successfully - query execution allowed",
            save=False
        )
        logger.info(
            f"Compliance check completed for query execution {execution.id}",
            extra={
                "execution_id": str(execution.id),
                "source_count": len(sources)
            }
        )

    def _execute_query_against_sources(
        self,
        query: str,
        query_type: QueryType,
        sources: List[Dict[str, Any]],
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> List[Dict[str, Any]]:
        """
        Execute query against all sources.

        Args:
            query: Query string
            query_type: Query type
            sources: List of source configurations
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            List of results from each source
        """
        results = []

        if not sources:
            # No sources - execute query directly based on type
            if query_type == QueryType.SPARQL:
                result = self._execute_sparql_query(query, timeout_seconds)
                results.append(result)
            else:
                raise ValidationError(
                    "No sources configured for query execution",
                    code="NO_SOURCES"
                )
        else:
            # Execute against each source
            for i, source in enumerate(sources):
                try:
                    source_result = self._execute_query_against_source(
                        query,
                        query_type,
                        source,
                        parameters,
                        timeout_seconds,
                        source_index=i
                    )
                    results.append(source_result)
                except Exception as e:
                    logger.error(
                        f"Failed to execute query against source {i}: {e}",
                        extra={
                            "source_index": i,
                            "source_type": source.get("type"),
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    # For federated queries, we might want to continue with other sources
                    # For now, we'll raise the error
                    raise ValidationError(
                        f"Query execution failed for source {i}: {str(e)}",
                        code="SOURCE_EXECUTION_FAILED",
                        details={"source_index": i, "source_type": source.get("type")}
                    ) from e

        return results

    def _execute_query_against_source(
        self,
        query: str,
        query_type: QueryType,
        source: Dict[str, Any],
        parameters: Dict[str, Any],
        timeout_seconds: int,
        source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Execute query against a single source.

        Supports:
        - Traditional sources: postgresql, mysql, sqlserver, mssql, odbc, sparql, rest, graphql, s3, minio
        - Federated asset sources: {"type": "federated_asset", "asset_id": "uuid", "query": "SELECT * FROM ..."}
        - External resource sources: {"type": "external_resource", "resource_id": "uuid", "asset_id": "uuid"}

        Args:
            query: Query string
            query_type: Query type
            source: Source configuration
            parameters: Query parameters
            timeout_seconds: Timeout in seconds
            source_index: Source index (for logging)

        Returns:
            Result dictionary with data and metadata
        """
        source_type = source.get("type", "").lower()

        # Handle federated asset sources
        if source_type == "federated_asset":
            return self._execute_query_against_federated_asset(
                query, query_type, source, parameters, timeout_seconds, source_index
            )

        # Handle external resource sources
        if source_type == "external_resource":
            return self._execute_query_against_external_resource(
                query, query_type, source, parameters, timeout_seconds, source_index
            )

        # Traditional source handling
        if query_type == QueryType.SQL:
            # Execute SQL query against database
            if source_type in ["postgresql", "mysql", "sqlserver", "mssql"]:
                return self._execute_sql_query(source, query, parameters, timeout_seconds)
            elif source_type == "odbc":
                return self._execute_odbc_query(source, query, parameters, timeout_seconds)
            else:
                raise ValidationError(
                    f"Unsupported database type for SQL query: {source_type}",
                    code="UNSUPPORTED_DATABASE_TYPE"
                )

        elif query_type == QueryType.SPARQL:
            # Execute SPARQL query via semantic service
            return self._execute_sparql_query(query, timeout_seconds)

        elif query_type == QueryType.REST:
            # Execute REST API query
            return self._execute_rest_query(source, query, parameters, timeout_seconds)

        elif query_type == QueryType.GRAPHQL:
            # Execute GraphQL query
            return self._execute_graphql_query(source, query, parameters, timeout_seconds)

        elif query_type == QueryType.FEDERATED:
            # Federated query - execute against multiple sources
            # This is handled at a higher level
            raise ValidationError(
                "Federated queries should be executed at the dataset level, not source level",
                code="INVALID_FEDERATED_EXECUTION"
            )

        else:
            raise ValidationError(
                f"Unsupported query type: {query_type}",
                code="UNSUPPORTED_QUERY_TYPE"
            )

    def _execute_query_against_federated_asset(
        self,
        query: str,
        query_type: QueryType,
        source: Dict[str, Any],
        parameters: Dict[str, Any],
        timeout_seconds: int,
        source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Execute query against a federated asset source.

        For federated assets, we can:
        1. Query metadata-only (if data_strategy is METADATA_ONLY)
        2. Query downloaded resources (if datasets exist)
        3. Download and query external resources on-demand (if data_strategy allows)

        Args:
            query: Query string (can be overridden by source.query)
            query_type: Query type
            source: Source configuration with type="federated_asset"
            parameters: Query parameters
            timeout_seconds: Timeout in seconds
            source_index: Source index (for logging)

        Returns:
            Result dictionary with data and metadata
        """
        from hub.apps.assets.models import Asset, AssetSourceType, DataStrategy
        import uuid

        asset_id = source.get("asset_id")
        if not asset_id:
            raise ValidationError(
                f"Federated asset source at index {source_index} must have 'asset_id' field",
                code="MISSING_ASSET_ID",
                details={"source_index": source_index}
            )

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=uuid.UUID(str(asset_id)))
        except Asset.DoesNotExist:
            raise ValidationError(
                f"Federated asset not found: {asset_id}",
                code="ASSET_NOT_FOUND",
                details={"source_index": source_index, "asset_id": str(asset_id)}
            )

        # Use source-specific query if provided, otherwise use dataset query
        source_query = source.get("query") or query

        # Check if asset has downloaded datasets
        datasets = asset.datasets.all()
        if datasets.exists():
            # Asset has downloaded resources - query them directly
            # Get the latest dataset
            latest_dataset = datasets.order_by('-version').first()
            if latest_dataset and latest_dataset.file:
                # Read file content and execute query
                from hub.apps.files.storage import S3StorageClient
                storage_client = S3StorageClient()
                try:
                    file_content = storage_client.get_file_content(latest_dataset.file.storage_path)
                    file_format = latest_dataset.format or "CSV"

                    # Execute query against file content
                    return self._execute_query_against_file_content(
                        source_query, query_type, file_content, file_format, parameters, timeout_seconds
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to query downloaded dataset for federated asset {asset_id}: {e}",
                        extra={"asset_id": str(asset.id), "source_index": source_index, "error": str(e)},
                        exc_info=True
                    )
                    raise ValidationError(
                        f"Failed to query federated asset {asset_id}: {str(e)}",
                        code="FEDERATED_ASSET_QUERY_FAILED",
                        details={"source_index": source_index, "asset_id": str(asset.id), "error": str(e)}
                    ) from e

        # No downloaded datasets - check if we can query metadata or download on-demand
        if asset.data_strategy == DataStrategy.METADATA_ONLY:
            # Metadata-only queries - return schema/metadata information
            return self._execute_metadata_only_query(asset, source_query, query_type, source_index)

        # Try to download and query external resources on-demand
        if asset.has_external_resources():
            # Get first external resource (or use resource_id from source if specified)
            resource_id = source.get("resource_id")
            if resource_id:
                external_resources = asset.external_resource_references.filter(resource_id=str(resource_id))
            else:
                external_resources = asset.external_resource_references.all()

            if external_resources.exists():
                external_resource = external_resources.first()
                # Download resource on-demand
                try:
                    file_path, file_content = asset.download_external_resource(external_resource.resource_id)
                    file_format = external_resource.format or "CSV"

                    # Execute query against downloaded content
                    result = self._execute_query_against_file_content(
                        source_query, query_type, file_content, file_format, parameters, timeout_seconds
                    )

                    # Cleanup temp file
                    try:
                        import os
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass

                    return result
                except Exception as e:
                    logger.error(
                        f"Failed to download and query external resource for federated asset {asset_id}: {e}",
                        extra={
                            "asset_id": str(asset.id),
                            "resource_id": external_resource.resource_id,
                            "source_index": source_index,
                            "error": str(e)
                        },
                        exc_info=True
                    )
                    raise ValidationError(
                        f"Failed to download external resource for federated asset {asset_id}: {str(e)}",
                        code="EXTERNAL_RESOURCE_DOWNLOAD_FAILED",
                        details={
                            "source_index": source_index,
                            "asset_id": str(asset.id),
                            "resource_id": external_resource.resource_id,
                            "error": str(e)
                        }
                    ) from e

        # No resources available
        raise ValidationError(
            f"Federated asset {asset_id} has no downloadable resources and data_strategy is {asset.data_strategy}",
            code="NO_RESOURCES_AVAILABLE",
            details={
                "source_index": source_index,
                "asset_id": str(asset.id),
                "data_strategy": asset.data_strategy
            }
        )

    def _execute_query_against_external_resource(
        self,
        query: str,
        query_type: QueryType,
        source: Dict[str, Any],
        parameters: Dict[str, Any],
        timeout_seconds: int,
        source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Execute query against an external resource source.

        Downloads the external resource on-demand and executes the query against it.

        Args:
            query: Query string
            query_type: Query type
            source: Source configuration with type="external_resource"
            parameters: Query parameters
            timeout_seconds: Timeout in seconds
            source_index: Source index (for logging)

        Returns:
            Result dictionary with data and metadata
        """
        from hub.apps.assets.models import Asset, ExternalResourceReference
        import uuid

        asset_id = source.get("asset_id")
        resource_id = source.get("resource_id")

        if not asset_id or not resource_id:
            raise ValidationError(
                f"External resource source at index {source_index} must have both 'asset_id' and 'resource_id' fields",
                code="MISSING_RESOURCE_CONFIG",
                details={"source_index": source_index}
            )

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=uuid.UUID(str(asset_id)))
        except Asset.DoesNotExist:
            raise ValidationError(
                f"Asset not found: {asset_id}",
                code="ASSET_NOT_FOUND",
                details={"source_index": source_index, "asset_id": str(asset_id)}
            )

        # Download external resource on-demand
        try:
            file_path, file_content = asset.download_external_resource(str(resource_id))
        except Exception as e:
            logger.error(
                f"Failed to download external resource {resource_id} for asset {asset_id}: {e}",
                extra={
                    "asset_id": str(asset.id),
                    "resource_id": str(resource_id),
                    "source_index": source_index,
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"Failed to download external resource {resource_id}: {str(e)}",
                code="EXTERNAL_RESOURCE_DOWNLOAD_FAILED",
                details={
                    "source_index": source_index,
                    "asset_id": str(asset.id),
                    "resource_id": str(resource_id),
                    "error": str(e)
                }
            ) from e

        # Get resource format
        try:
            external_resource = ExternalResourceReference.objects.get(
                asset=asset, resource_id=str(resource_id)
            )
            file_format = external_resource.format or "CSV"
        except ExternalResourceReference.DoesNotExist:
            file_format = "CSV"  # Default format

        try:
            # Execute query against downloaded content
            result = self._execute_query_against_file_content(
                query, query_type, file_content, file_format, parameters, timeout_seconds
            )

            # Cleanup temp file
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

            return result
        except Exception as e:
            # Cleanup temp file on error
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            raise

    def _execute_query_against_file_content(
        self,
        query: str,
        query_type: QueryType,
        file_content: bytes,
        file_format: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute query against file content in memory.

        Supports CSV, JSON, and PARQUET formats.

        Args:
            query: Query string
            query_type: Query type
            file_content: File content as bytes
            file_format: File format (CSV, JSON, PARQUET)
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        import io
        import pandas as pd

        # Parse file content based on format
        if file_format.upper() == "CSV":
            try:
                df = pd.read_csv(io.BytesIO(file_content))
            except Exception as e:
                raise ValidationError(
                    f"Failed to parse CSV file: {str(e)}",
                    code="CSV_PARSE_ERROR",
                    details={"error": str(e)}
                ) from e
        elif file_format.upper() == "JSON":
            try:
                import json
                data = json.loads(file_content.decode('utf-8'))
                # Handle both list and dict JSON
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    # If dict, try to find list values
                    if any(isinstance(v, list) for v in data.values()):
                        # Use first list value
                        for key, value in data.items():
                            if isinstance(value, list):
                                df = pd.DataFrame(value)
                                break
                    else:
                        # Single record dict
                        df = pd.DataFrame([data])
                else:
                    raise ValidationError("Unsupported JSON structure", code="INVALID_JSON_STRUCTURE")
            except Exception as e:
                raise ValidationError(
                    f"Failed to parse JSON file: {str(e)}",
                    code="JSON_PARSE_ERROR",
                    details={"error": str(e)}
                ) from e
        elif file_format.upper() == "PARQUET":
            try:
                df = pd.read_parquet(io.BytesIO(file_content))
            except Exception as e:
                raise ValidationError(
                    f"Failed to parse PARQUET file: {str(e)}",
                    code="PARQUET_PARSE_ERROR",
                    details={"error": str(e)}
                ) from e
        else:
            raise ValidationError(
                f"Unsupported file format for query execution: {file_format}",
                code="UNSUPPORTED_FILE_FORMAT",
                details={"file_format": file_format}
            )

        # For SQL queries, use pandas query method
        if query_type == QueryType.SQL:
            try:
                # Apply parameters for display (file queries use pandas, not DB cursors)
                parameterized_query = self._apply_parameters(query, parameters)
                # For "SELECT * FROM X" or "SELECT *" return all rows; pandas query expects boolean expr
                remainder = parameterized_query.replace("SELECT *", "").strip()
                if "SELECT *" in parameterized_query.upper():
                    if not remainder or remainder.upper().startswith("FROM "):
                        result_df = df
                    elif remainder.upper().startswith("WHERE "):
                        result_df = df.query(remainder[6:].strip())  # "WHERE col > 5" -> "col > 5"
                    else:
                        result_df = df
                else:
                    result_df = df
                # Convert to list of dictionaries
                data = result_df.to_dict('records')
                columns = list(result_df.columns)
            except Exception as e:
                raise ValidationError(
                    f"Failed to execute query against file content: {str(e)}",
                    code="QUERY_EXECUTION_ERROR",
                    details={"error": str(e), "query": query[:100]}
                ) from e
        else:
            # For non-SQL queries, return all data
            data = df.to_dict('records')
            columns = list(df.columns)

        return {
            "data": data,
            "columns": columns,
            "row_count": len(data),
            "source_type": f"file_{file_format.lower()}"
        }

    def _execute_metadata_only_query(
        self,
        asset: "Asset",
        query: str,
        query_type: QueryType,
        source_index: int = 0
    ) -> Dict[str, Any]:
        """
        Execute metadata-only query against federated asset.

        Returns schema and metadata information without downloading data.

        Args:
            asset: Federated asset
            query: Query string (may contain metadata queries)
            query_type: Query type
            source_index: Source index (for logging)

        Returns:
            Result dictionary with metadata/schema information
        """
        # Extract schema from ODCS contract if available
        schema_info = {}
        odcs_contracts = asset.contracts.filter(original_spec_type="ODCS")
        if odcs_contracts.exists():
            odcs_contract = odcs_contracts.first()
            if odcs_contract and odcs_contract.hub_contract_json:
                schema_info = odcs_contract.hub_contract_json.get("schema", {})

        # Get external resource metadata
        external_resources = []
        if asset.has_external_resources():
            for ext_res in asset.external_resource_references.all():
                external_resources.append({
                    "resource_id": ext_res.resource_id,
                    "name": ext_res.name,
                    "url": ext_res.url,
                    "format": ext_res.format,
                    "size_bytes": ext_res.size_bytes,
                })

        # Return metadata result
        return {
            "data": [{
                "asset_id": str(asset.id),
                "asset_name": asset.name,
                "data_strategy": asset.data_strategy,
                "schema": schema_info,
                "external_resources": external_resources,
                "resource_count": len(external_resources)
            }],
            "columns": ["asset_id", "asset_name", "data_strategy", "schema", "external_resources", "resource_count"],
            "row_count": 1,
            "source_type": "federated_asset_metadata"
        }

    def _execute_sql_query(
        self,
        source: Dict[str, Any],
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute SQL query against database source.

        Args:
            source: Database source configuration
            query: SQL query
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        # Import database drivers conditionally
        try:
            import psycopg2
        except ImportError:
            psycopg2 = None

        try:
            import pymysql
        except ImportError:
            pymysql = None

        try:
            from sqlalchemy import create_engine, text
        except ImportError:
            create_engine = None
            text = None

        source_type = source.get("type", "postgresql").lower()
        host = source.get("host")
        port = source.get("port")
        database = source.get("database")
        username = source.get("username")
        password = source.get("password")
        schema = source.get("schema")

        if not host or not database:
            raise ValidationError(
                "Database host and database name are required",
                code="MISSING_DATABASE_CONFIG"
            )

        try:
            if source_type == "postgresql":
                if psycopg2 is None:
                    raise ValidationError(
                        "psycopg2 is required for PostgreSQL connections. Install it with: pip install psycopg2-binary",
                        code="MISSING_DEPENDENCY"
                    )

                if not port:
                    port = 5432

                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=username,
                    password=password,
                    connect_timeout=min(timeout_seconds, 10)
                )

                try:
                    cursor = conn.cursor()
                    safe_query, params = self._normalise_query_params(query, parameters)
                    cursor.execute(safe_query, params or None)
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()

                    # Convert to list of dictionaries
                    data = [dict(zip(columns, row)) for row in rows]

                    return {
                        "data": data,
                        "columns": columns,
                        "row_count": len(data),
                        "source_type": "postgresql"
                    }
                finally:
                    cursor.close()
                    conn.close()

            elif source_type == "mysql":
                if pymysql is None:
                    raise ValidationError(
                        "pymysql is required for MySQL connections. Install it with: pip install pymysql",
                        code="MISSING_DEPENDENCY"
                    )

                if not port:
                    port = 3306

                conn = pymysql.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=username,
                    password=password or "",
                    connect_timeout=min(timeout_seconds, 10)
                )

                try:
                    cursor = conn.cursor()
                    safe_query, params = self._normalise_query_params(query, parameters)
                    cursor.execute(safe_query, params or None)
                    columns = [desc[0] for desc in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()

                    data = [dict(zip(columns, row)) for row in rows]

                    return {
                        "data": data,
                        "columns": columns,
                        "row_count": len(data),
                        "source_type": "mysql"
                    }
                finally:
                    cursor.close()
                    conn.close()

            elif source_type in ["sqlserver", "mssql"]:
                if create_engine is None or text is None:
                    raise ValidationError(
                        "sqlalchemy is required for SQL Server connections. Install it with: pip install sqlalchemy pyodbc",
                        code="MISSING_DEPENDENCY"
                    )

                # Use SQLAlchemy for SQL Server
                if not port:
                    port = 1433

                connection_string = f"mssql+pyodbc://{username}:{password}@{host}:{port}/{database}?driver=ODBC+Driver+17+for+SQL+Server"
                engine = create_engine(connection_string, connect_args={"timeout": min(timeout_seconds, 10)})

                with engine.connect() as conn:
                    safe_query, params = self._normalise_query_params_named(query, parameters)
                    result = conn.execute(text(safe_query), params or None)
                    columns = result.keys()
                    rows = result.fetchall()

                    data = [dict(zip(columns, row)) for row in rows]

                    return {
                        "data": data,
                        "columns": list(columns),
                        "row_count": len(data),
                        "source_type": "sqlserver"
                    }

            else:
                raise ValidationError(
                    f"Unsupported database type: {source_type}",
                    code="UNSUPPORTED_DATABASE_TYPE"
                )

        except Exception as e:
            logger.error(
                f"SQL query execution failed: {e}",
                extra={
                    "source_type": source_type,
                    "host": host,
                    "database": database,
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"SQL query execution failed: {str(e)}",
                code="SQL_EXECUTION_FAILED"
            ) from e

    def _execute_odbc_query(
        self,
        source: Dict[str, Any],
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute SQL query against ODBC source.

        Supports:
        - connection_string: Full ODBC connection string (e.g. DSN=... or Driver=...;Server=...)
        - host + database: Build connection string from host, port, database, username, password.
          Optional: driver (default: PostgreSQL Unicode for PostgreSQL).

        Args:
            source: ODBC source configuration
            query: SQL query
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        try:
            import pyodbc
        except ImportError:
            raise ValidationError(
                "pyodbc is required for ODBC connections. Install it with: pip install pyodbc",
                code="MISSING_DEPENDENCY"
            )

        connection_string = source.get("connection_string")
        host = source.get("host")
        database = source.get("database")
        if connection_string:
            conn_str = connection_string
        else:
            if not host or not database:
                raise ValidationError(
                    "ODBC source requires 'connection_string' or both 'host' and 'database'",
                    code="MISSING_DATABASE_CONFIG"
                )
            port = source.get("port", 5432)
            username = source.get("username") or source.get("user")
            password = source.get("password", "")
            driver = source.get("driver", "PostgreSQL Unicode")

            # Build connection string for PostgreSQL (common case for Hub ODBC)
            if "postgresql" in driver.lower() or driver == "PostgreSQL Unicode":
                conn_str = (
                    f"DRIVER={{{driver}}};"
                    f"SERVER={host};"
                    f"PORT={port};"
                    f"DATABASE={database};"
                    f"UID={username or ''};"
                    f"PWD={password}"
                )
            else:
                # Generic ODBC format
                conn_str = (
                    f"DRIVER={{{driver}}};"
                    f"SERVER={host};"
                    f"PORT={port};"
                    f"DATABASE={database};"
                    f"UID={username or ''};"
                    f"PWD={password}"
                )

        try:
            conn = pyodbc.connect(
                conn_str,
                timeout=min(timeout_seconds, 30)
            )
            try:
                cursor = conn.cursor()
                safe_query, params = self._normalise_query_params(query, parameters)
                cursor.execute(safe_query, params or None)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchall()

                data = [dict(zip(columns, row)) for row in rows]

                return {
                    "data": data,
                    "columns": columns,
                    "row_count": len(data),
                    "source_type": "odbc"
                }
            finally:
                cursor.close()
                conn.close()
        except pyodbc.Error as e:
            logger.error(
                f"ODBC query execution failed: {e}",
                extra={
                    "source_type": "odbc",
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"ODBC query execution failed: {str(e)}",
                code="SQL_EXECUTION_FAILED"
            ) from e

        except Exception as e:
            logger.error(
                f"ODBC query execution failed: {e}",
                extra={
                    "source_type": "odbc",
                    "host": host,
                    "database": database,
                    "error": str(e)
                },
                exc_info=True
            )
            raise ValidationError(
                f"SQL query execution failed: {str(e)}",
                code="SQL_EXECUTION_FAILED"
            ) from e

    def _execute_sparql_query(
        self,
        query: str,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute SPARQL query via semantic service.

        Args:
            query: SPARQL query
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        from hub.apps.semantic.service_client import SemanticServiceClient

        try:
            client = SemanticServiceClient()
            result = client.query_sparql(
                query=query,
                output_format="json",
                timeout=timeout_seconds,
                tenant_id=self.tenant_id,
            )

            if "error" in result:
                raise ValidationError(
                    f"SPARQL query execution failed: {result['error']}",
                    code="SPARQL_EXECUTION_FAILED"
                )

            # Extract bindings from SPARQL result
            bindings = result.get("results", {}).get("bindings", [])
            data = []
            for binding in bindings:
                row = {}
                for key, value in binding.items():
                    # SPARQL results have type and value
                    row[key] = value.get("value") if isinstance(value, dict) else value
                data.append(row)

            return {
                "data": data,
                "columns": list(bindings[0].keys()) if bindings else [],
                "row_count": len(data),
                "source_type": "sparql"
            }

        except Exception as e:
            logger.error(
                f"SPARQL query execution failed: {e}",
                extra={"error": str(e)},
                exc_info=True
            )
            raise ValidationError(
                f"SPARQL query execution failed: {str(e)}",
                code="SPARQL_EXECUTION_FAILED"
            ) from e

    def _execute_rest_query(
        self,
        source: Dict[str, Any],
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute REST API query.

        Args:
            source: REST API source configuration
            query: Query/endpoint path
            parameters: Query parameters
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        import httpx
        import urllib.parse

        base_url = source.get("base_url") or source.get("url")
        if not base_url:
            raise ValidationError(
                "REST API base_url or url is required",
                code="MISSING_REST_CONFIG"
            )

        # Build full URL
        endpoint = query.strip()
        if not endpoint.startswith("http"):
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = f"{base_url.rstrip('/')}{endpoint}"

        # Add query parameters
        if parameters:
            query_params = urllib.parse.urlencode(parameters)
            url = f"{url}?{query_params}" if "?" not in url else f"{url}&{query_params}"

        try:
            headers = source.get("headers", {})
            method = source.get("method", "GET").upper()

            with httpx.Client(timeout=timeout_seconds) as client:
                if method == "GET":
                    response = client.get(url, headers=headers)
                elif method == "POST":
                    response = client.post(url, headers=headers, json=parameters)
                else:
                    raise ValidationError(
                        f"Unsupported HTTP method: {method}",
                        code="UNSUPPORTED_HTTP_METHOD"
                    )

                response.raise_for_status()
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text

                # Normalize REST API response to list of dictionaries
                if isinstance(data, dict):
                    # Try to extract array from common response structures
                    if "data" in data:
                        data = data["data"]
                    elif "results" in data:
                        data = data["results"]
                    elif "items" in data:
                        data = data["items"]
                    else:
                        # Single object - wrap in list
                        data = [data]
                elif not isinstance(data, list):
                    data = [{"value": data}]

                return {
                    "data": data,
                    "columns": list(data[0].keys()) if data and isinstance(data[0], dict) else [],
                    "row_count": len(data) if isinstance(data, list) else 1,
                    "source_type": "rest"
                }

        except Exception as e:
            logger.error(
                f"REST API query execution failed: {e}",
                extra={"url": url, "error": str(e)},
                exc_info=True
            )
            raise ValidationError(
                f"REST API query execution failed: {str(e)}",
                code="REST_EXECUTION_FAILED"
            ) from e

    def _execute_graphql_query(
        self,
        source: Dict[str, Any],
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute GraphQL query.

        Args:
            source: GraphQL API source configuration
            query: GraphQL query
            parameters: Query variables
            timeout_seconds: Timeout in seconds

        Returns:
            Result dictionary with data and metadata
        """
        import httpx

        endpoint = source.get("endpoint") or source.get("url")
        if not endpoint:
            raise ValidationError(
                "GraphQL endpoint or url is required",
                code="MISSING_GRAPHQL_CONFIG"
            )

        try:
            headers = source.get("headers", {})
            if "Content-Type" not in headers:
                headers["Content-Type"] = "application/json"

            payload = {
                "query": query,
                "variables": parameters
            }

            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if "errors" in result:
                    error_messages = [err.get("message", str(err)) for err in result["errors"]]
                    raise ValidationError(
                        f"GraphQL query errors: {', '.join(error_messages)}",
                        code="GRAPHQL_EXECUTION_FAILED"
                    )

                data = result.get("data", {})
                # Normalize GraphQL response
                if isinstance(data, dict):
                    # Extract first top-level field as array
                    for key, value in data.items():
                        if isinstance(value, list):
                            data = value
                            break
                    else:
                        # No array found - wrap in list
                        data = [data]

                return {
                    "data": data if isinstance(data, list) else [data],
                    "columns": list(data[0].keys()) if data and isinstance(data[0], dict) else [],
                    "row_count": len(data) if isinstance(data, list) else 1,
                    "source_type": "graphql"
                }

        except Exception as e:
            logger.error(
                f"GraphQL query execution failed: {e}",
                extra={"endpoint": endpoint, "error": str(e)},
                exc_info=True
            )
            raise ValidationError(
                f"GraphQL query execution failed: {str(e)}",
                code="GRAPHQL_EXECUTION_FAILED"
            ) from e

    def _aggregate_results(
        self,
        results: List[Dict[str, Any]],
        query_type: QueryType
    ) -> List[Dict[str, Any]]:
        """
        Aggregate results from multiple sources.

        Args:
            results: List of result dictionaries from each source
            query_type: Query type

        Returns:
            Aggregated results as list of dictionaries
        """
        if not results:
            return []

        if len(results) == 1:
            # Single source - return data directly
            return results[0].get("data", [])

        # Multiple sources - merge results
        # For SQL/FEDERATED queries, we can do UNION
        # For other query types, we concatenate

        aggregated = []
        all_columns = set()

        # Collect all columns from all sources
        for result in results:
            columns = result.get("columns", [])
            all_columns.update(columns)

        # Merge data from all sources
        for result in results:
            data = result.get("data", [])
            columns = result.get("columns", [])

            for row in data:
                # Ensure all columns are present
                normalized_row = {col: row.get(col) for col in all_columns}
                aggregated.append(normalized_row)

        return aggregated

    def _publish_execution_completed(
        self,
        execution: QueryExecution,
        row_count: int
    ) -> None:
        """Publish query execution completed event"""
        try:
            self.publish_query_execution_completed(
                query_execution_id=str(execution.id),
                virtual_dataset_id=str(execution.virtual_dataset_id),
                status="COMPLETED",
                duration_ms=execution.get_metric("duration_ms", 0),
                rows_processed=row_count,
                tenant_id=str(execution.virtual_dataset.tenant_id),
                user_id=str(execution.virtual_dataset.created_by_id) if execution.virtual_dataset.created_by_id else None
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish query execution completed event: {e}",
                exc_info=True
            )

    def _publish_execution_failed(
        self,
        execution: QueryExecution,
        error_message: str
    ) -> None:
        """Publish query execution failed event"""
        try:
            self.publish_query_execution_failed(
                query_execution_id=str(execution.id),
                virtual_dataset_id=str(execution.virtual_dataset_id),
                error_message=error_message,
                duration_ms=execution.get_metric("duration_ms", 0),
                tenant_id=str(execution.virtual_dataset.tenant_id),
                user_id=str(execution.virtual_dataset.created_by_id) if execution.virtual_dataset.created_by_id else None
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish query execution failed event: {e}",
                exc_info=True
            )

    def _run_quality_check_on_results(
        self,
        results: List[Dict[str, Any]],
        execution: QueryExecution,
        virtual_dataset: VirtualDataset,
        quality_threshold: float = 0.7,
        profile_key: str = "intake_basic_gx"
    ) -> Optional[Dict[str, Any]]:
        """
        Run quality checks on query results via QualityService.

        Args:
            results: Query results as list of dictionaries
            execution: QueryExecution instance for logging
            virtual_dataset: VirtualDataset instance
            quality_threshold: Minimum quality score threshold (default: 0.7)
            profile_key: DQ profile key to use (default: "intake_basic_gx")

        Returns:
            Quality metrics dictionary with:
            - quality_score: Overall quality score (0.0-1.0)
            - overall_status: Overall status (PASS, WARN, FAIL)
            - checks_passed: Number of checks passed
            - checks_failed: Number of checks failed
            - checks: List of individual check results
            - threshold_met: Whether quality threshold was met
            Or None if quality check failed or service unavailable
        """
        try:
            from hub.apps.dq.service_client import DQServiceClient
            import io
            import csv

            # Initialize DQ client
            dq_client = DQServiceClient()

            # Check DQ service health
            is_healthy, _ = dq_client.health_check()
            if not is_healthy:
                execution.add_log_entry(
                    "WARNING",
                    "DQ service unavailable, skipping quality check",
                    save=False
                )
                logger.warning(
                    f"DQ service unavailable for query execution {execution.id}, skipping quality check",
                    extra={"execution_id": str(execution.id)}
                )
                return None

            if not results or len(results) == 0:
                execution.add_log_entry(
                    "INFO",
                    "No results to run quality check on",
                    save=False
                )
                return None

            # Convert results to CSV format for DQ service
            # CSV is the most common format supported by DQ service
            # Use StringIO for text-based CSV writing, then encode to bytes
            csv_string_buffer = io.StringIO()

            # Get column names from first row
            if results and isinstance(results[0], dict):
                fieldnames = list(results[0].keys())
            else:
                execution.add_log_entry(
                    "WARNING",
                    "Results format not supported for quality check",
                    save=False
                )
                return None

            # Write CSV data
            writer = csv.DictWriter(csv_string_buffer, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                # Convert all values to strings for CSV
                csv_row = {k: str(v) if v is not None else "" for k, v in row.items()}
                writer.writerow(csv_row)

            csv_string = csv_string_buffer.getvalue()
            csv_string_buffer.close()

            # Encode to bytes for DQ service
            csv_content = csv_string.encode('utf-8')

            # Run DQ check
            execution.add_log_entry(
                "INFO",
                f"Running quality check on {len(results)} rows using profile {profile_key}",
                save=False
            )

            dq_result = dq_client.run_dq(
                file_content=csv_content,
                file_format="csv",
                profile_key=profile_key,
                use_cache=True
            )

            # Extract quality metrics
            quality_score = dq_result.get("quality_score", 0.0)
            overall_status = dq_result.get("overall_status", "UNKNOWN")
            checks = dq_result.get("checks", [])

            # Count passed and failed checks
            checks_passed = sum(1 for check in checks if check.get("status") == "PASS")
            checks_failed = sum(1 for check in checks if check.get("status") in ["FAIL", "ERROR"])

            # Validate quality threshold
            threshold_met = quality_score >= quality_threshold

            quality_metrics = {
                "quality_score": quality_score,
                "overall_status": overall_status,
                "checks_passed": checks_passed,
                "checks_failed": checks_failed,
                "checks_total": len(checks),
                "threshold": quality_threshold,
                "threshold_met": threshold_met,
                "checks": checks,
                "engine_type": dq_result.get("engine_type"),
                "engine_version": dq_result.get("engine_version"),
                "profile_key": profile_key
            }

            # Store quality metrics in execution_log
            execution.add_log_entry(
                "INFO",
                f"Quality check completed: score={quality_score:.2f}, status={overall_status}, "
                f"passed={checks_passed}, failed={checks_failed}, threshold_met={threshold_met}",
                save=False
            )

            # Log warning if threshold not met
            if not threshold_met:
                execution.add_log_entry(
                    "WARNING",
                    f"Quality threshold not met: score {quality_score:.2f} < threshold {quality_threshold:.2f}",
                    save=False
                )
                logger.warning(
                    f"Quality threshold not met for query execution {execution.id}: "
                    f"score {quality_score:.2f} < threshold {quality_threshold:.2f}",
                    extra={
                        "execution_id": str(execution.id),
                        "quality_score": quality_score,
                        "threshold": quality_threshold
                    }
                )

            # Store detailed quality metrics in execution_log as structured data
            # Add as a separate log entry with structured data
            quality_log_entry = {
                "timestamp": timezone.now().isoformat(),
                "level": "INFO",
                "message": "Quality check results",
                "quality_metrics": quality_metrics
            }
            if execution.execution_log is None:
                execution.execution_log = []
            execution.execution_log.append(quality_log_entry)

            logger.info(
                f"Quality check completed for query execution {execution.id}",
                extra={
                    "execution_id": str(execution.id),
                    "quality_score": quality_score,
                    "overall_status": overall_status,
                    "threshold_met": threshold_met
                }
            )

            return quality_metrics

        except Exception as e:
            execution.add_log_entry(
                "ERROR",
                f"Quality check failed: {str(e)}",
                save=False
            )
            logger.error(
                f"Quality check failed for query execution {execution.id}: {e}",
                extra={
                    "execution_id": str(execution.id),
                    "error": str(e)
                },
                exc_info=True
            )
            return None

    def get_query_result(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
        format: str = "json",
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        stream: bool = False,
        execution: Optional[QueryExecution] = None
    ) -> Dict[str, Any]:
        """
        Get query execution result.

        Supports:
        - Result retrieval from cache or storage
        - Multiple output formats (JSON, CSV, Parquet)
        - Pagination (page-based or offset-based)
        - Streaming (SSE) for large results

        Args:
            execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            format: Output format (json, csv, parquet) - default: json
            page: Page number for pagination (1-indexed, mutually exclusive with offset)
            page_size: Items per page (default: 50, max: 1000)
            offset: Offset for pagination (mutually exclusive with page)
            limit: Maximum number of items to return (default: 50, max: 1000)
            stream: Whether to stream results (SSE) for large datasets

        Returns:
            Dictionary containing:
            - data: Result data (list of rows or formatted string)
            - total_count: Total number of rows
            - format: Output format
            - pagination: Pagination metadata (if applicable)
            - stream_url: Streaming URL (if stream=True)

        Raises:
            NotFoundError: If execution not found
            ValidationError: If execution is not completed or invalid parameters
        """
        from django.core.cache import cache
        from hub.apps.files.storage import S3StorageClient
        import pandas as pd
        import io
        import json
        import base64

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Get execution (QueryExecution doesn't have tenant_id directly, get via virtual_dataset)
        # Use provided execution object if available, otherwise fetch it
        if execution is None:
            execution = self.get_query_execution(execution_id, effective_tenant_id)
        else:
            # Verify the provided execution matches the execution_id
            if str(execution.id) != execution_id:
                raise ValidationError(
                    f"Provided execution object ID {execution.id} does not match execution_id {execution_id}",
                    code="EXECUTION_ID_MISMATCH"
                )
            # Verify tenant isolation
            if str(execution.virtual_dataset.tenant_id) != effective_tenant_id:
                raise NotFoundError(f"QueryExecution with id {execution_id} not found")

        # Validate execution status
        if execution.status != QueryExecutionStatus.COMPLETED:
            raise ValidationError(
                f"Query execution is not completed (status: {execution.status})",
                code="EXECUTION_NOT_COMPLETED"
            )

        # Validate format
        format = format.lower()
        if format not in ["json", "csv", "parquet"]:
            raise ValidationError(
                f"Unsupported format: {format}. Supported formats: json, csv, parquet",
                code="UNSUPPORTED_FORMAT"
            )

        # Validate pagination parameters
        if page is not None and offset is not None:
            raise ValidationError(
                "Cannot use both 'page' and 'offset' parameters",
                code="INVALID_PAGINATION"
            )

        # Set default pagination values
        if page_size is None:
            page_size = 50
        if limit is None:
            limit = 50

        # Clamp page_size and limit
        page_size = max(1, min(page_size, 1000))
        limit = max(1, min(limit, 1000))

        # Retrieve results
        results_data = None
        total_count = 0

        # Try cache first
        if execution.result_cache_key:
            cached_data = cache.get(execution.result_cache_key)
            if cached_data:
                results_data = cached_data.get("data", [])
                total_count = cached_data.get("row_count", len(results_data) if isinstance(results_data, list) else 0)
                logger.debug(
                    f"Retrieved results from cache for execution {execution_id}",
                    extra={
                        "execution_id": execution_id,
                        "cache_key": execution.result_cache_key,
                        "row_count": total_count
                    }
                )

        # Try storage if cache miss
        if results_data is None and execution.result_storage_path:
            try:
                storage_client = S3StorageClient()
                file_content = storage_client.get_file_content(execution.result_storage_path)

                # Determine file format from path
                storage_path_lower = execution.result_storage_path.lower()
                if storage_path_lower.endswith('.json'):
                    results_data = json.loads(file_content.decode('utf-8'))
                    if isinstance(results_data, dict) and 'data' in results_data:
                        results_data = results_data['data']
                    total_count = len(results_data) if isinstance(results_data, list) else 0
                elif storage_path_lower.endswith('.csv'):
                    # Read CSV into list of dicts
                    df = pd.read_csv(io.BytesIO(file_content))
                    results_data = df.replace({pd.NA: None}).to_dict('records')
                    total_count = len(results_data)
                elif storage_path_lower.endswith('.parquet'):
                    # Read Parquet into list of dicts
                    df = pd.read_parquet(io.BytesIO(file_content))
                    results_data = df.replace({pd.NA: None}).to_dict('records')
                    total_count = len(results_data)
                else:
                    # Try JSON as default
                    try:
                        results_data = json.loads(file_content.decode('utf-8'))
                        if isinstance(results_data, dict) and 'data' in results_data:
                            results_data = results_data['data']
                        total_count = len(results_data) if isinstance(results_data, list) else 0
                    except json.JSONDecodeError:
                        raise ValidationError(
                            f"Unable to parse stored result file: {execution.result_storage_path}",
                            code="INVALID_STORAGE_FORMAT"
                        )

                logger.debug(
                    f"Retrieved results from storage for execution {execution_id}",
                    extra={
                        "execution_id": execution_id,
                        "storage_path": execution.result_storage_path,
                        "row_count": total_count
                    }
                )
            except Exception as e:
                logger.error(
                    f"Failed to retrieve results from storage for execution {execution_id}: {e}",
                    extra={
                        "execution_id": execution_id,
                        "storage_path": execution.result_storage_path,
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise ValidationError(
                    f"Failed to retrieve results from storage: {str(e)}",
                    code="STORAGE_RETRIEVAL_FAILED"
                )

        # If still no results, raise error
        if results_data is None:
            raise NotFoundError(
                f"No results found for execution {execution_id}",
                code="RESULTS_NOT_FOUND"
            )

        # Ensure results_data is a list
        if not isinstance(results_data, list):
            if isinstance(results_data, dict):
                results_data = [results_data]
            else:
                results_data = []

        # Apply pagination
        paginated_data = results_data
        pagination_metadata = None

        if page is not None:
            # Page-based pagination
            page = max(1, page)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_data = results_data[start_idx:end_idx]

            total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
            pagination_metadata = {
                "type": "page",
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "total_count": total_count,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
        elif offset is not None:
            # Offset-based pagination
            offset = max(0, offset)
            end_idx = offset + limit
            paginated_data = results_data[offset:end_idx]

            pagination_metadata = {
                "type": "offset",
                "offset": offset,
                "limit": limit,
                "total_count": total_count,
                "has_next": end_idx < total_count,
                "has_previous": offset > 0
            }
        elif len(results_data) > limit:
            # Auto-paginate if results exceed limit
            paginated_data = results_data[:limit]
            pagination_metadata = {
                "type": "auto",
                "limit": limit,
                "total_count": total_count,
                "has_more": len(results_data) > limit
            }

        # Format results
        formatted_data = None
        content_type = "application/json"

        if format == "json":
            formatted_data = paginated_data
            content_type = "application/json"
        elif format == "csv":
            if not paginated_data:
                formatted_data = ""
            else:
                df = pd.DataFrame(paginated_data)
                csv_buffer = io.StringIO()
                df.to_csv(csv_buffer, index=False)
                formatted_data = csv_buffer.getvalue()
            content_type = "text/csv"
        elif format == "parquet":
            if not paginated_data:
                # Return empty parquet file
                df = pd.DataFrame()
            else:
                df = pd.DataFrame(paginated_data)
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False)
            formatted_data = base64.b64encode(parquet_buffer.getvalue()).decode('utf-8')
            content_type = "application/parquet"

        # Build response
        response = {
            "execution_id": str(execution.id),
            "data": formatted_data,
            "total_count": total_count,
            "returned_count": len(paginated_data),
            "format": format,
            "content_type": content_type
        }

        if pagination_metadata:
            response["pagination"] = pagination_metadata

        # Handle streaming
        if stream and total_count > 1000:  # Stream only for large datasets
            # Generate streaming URL (to be implemented in views)
            response["stream_url"] = f"/api/v1/virtualization/executions/{execution_id}/results/stream?format={format}"
            response["stream_enabled"] = True
        else:
            response["stream_enabled"] = False

        logger.info(
            f"Retrieved query result for execution {execution_id}",
            extra={
                "execution_id": execution_id,
                "tenant_id": effective_tenant_id,
                "format": format,
                "total_count": total_count,
                "returned_count": len(paginated_data),
                "pagination": pagination_metadata is not None,
                "stream": stream
            }
        )

        return response

    def cancel_query_execution(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> QueryExecution:
        """
        Cancel a query execution.

        This method:
        1. Validates execution exists and belongs to tenant
        2. Checks if execution can be cancelled
        3. Cancels the execution (and linked job if exists)
        4. Releases tenant concurrency slot if job was running
        5. Publishes cancellation event
        6. Logs audit event

        Args:
            execution_id: Query execution ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID cancelling the execution (uses service user_id if not provided)
            reason: Optional cancellation reason

        Returns:
            Cancelled QueryExecution instance

        Raises:
            NotFoundError: If execution not found
            ValidationError: If execution cannot be cancelled
        """
        from django.contrib.auth import get_user_model
        from hub.apps.tenants.models import Tenant
        from hub.apps.jobs.models import JobStatus
        from hub.apps.jobs.utils import decrement_tenant_job_counter
        from hub.apps.audit.utils import create_audit_event

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        effective_user_id = user_id or self.user_id

        # Get execution
        execution = self.get_query_execution(execution_id, effective_tenant_id)

        # Check if execution can be cancelled
        if not execution.can_cancel():
            raise ValidationError(
                f"Query execution cannot be cancelled (current status: {execution.status})",
                code="EXECUTION_CANNOT_BE_CANCELLED"
            )

        # Store previous status for audit logging
        previous_status = execution.status

        # Cancel the execution
        cancellation_reason = reason or "User requested cancellation"
        execution.mark_cancelled(reason=cancellation_reason)

        # If execution has a job, cancel the job as well
        if execution.job and execution.job.can_cancel():
            job_previous_status = execution.job.status
            execution.job.mark_cancelled()

            # If job was running, release tenant concurrency slot
            if job_previous_status == JobStatus.RUNNING and execution.virtual_dataset.tenant:
                decrement_tenant_job_counter(
                    str(execution.virtual_dataset.tenant.id),
                    "running"
                )

            logger.info(
                f"Cancelled job {execution.job.id} for query execution {execution_id}",
                extra={
                    "execution_id": execution_id,
                    "job_id": str(execution.job.id),
                    "tenant_id": effective_tenant_id
                }
            )

        # Get tenant and user for audit logging
        try:
            tenant = Tenant.objects.get(id=effective_tenant_id)
        except Tenant.DoesNotExist:
            tenant = execution.virtual_dataset.tenant

        user = None
        if effective_user_id:
            User = get_user_model()
            try:
                user = User.objects.get(id=effective_user_id)
            except User.DoesNotExist:
                pass

        # Publish cancellation event
        try:
            self.publish_query_execution_cancelled(
                query_execution_id=str(execution.id),
                virtual_dataset_id=str(execution.virtual_dataset.id),
                reason=cancellation_reason,
                tenant_id=effective_tenant_id,
                user_id=effective_user_id
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish query execution cancelled event: {e}",
                extra={
                    "execution_id": execution_id,
                    "tenant_id": effective_tenant_id,
                    "error": str(e)
                },
                exc_info=True
            )

        # Log audit event
        if user:
            try:
                create_audit_event(
                    resource_type="QUERY_EXECUTION",
                    action="QUERY_EXECUTION_CANCELLED",
                    actor_user=user,
                    tenant=tenant,
                    resource_id=str(execution.id),
                    details={
                        "virtual_dataset_id": str(execution.virtual_dataset.id),
                        "virtual_dataset_name": execution.virtual_dataset.name,
                        "previous_status": previous_status,
                        "reason": cancellation_reason
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Failed to create audit event for query execution cancellation: {e}",
                    extra={
                        "execution_id": execution_id,
                        "tenant_id": effective_tenant_id,
                        "error": str(e)
                    },
                    exc_info=True
                )

        logger.info(
            f"Cancelled query execution {execution_id}",
            extra={
                "execution_id": execution_id,
                "tenant_id": effective_tenant_id,
                "user_id": effective_user_id,
                "previous_status": previous_status,
                "reason": cancellation_reason
            }
        )

        return execution

    def get_topology(
        self,
        tenant_id: Optional[str] = None,
        include_health_metrics: bool = True,
    ) -> Dict[str, Any]:
        """
        Get virtualization topology for a tenant.

        This method generates a comprehensive topology view including:
        1. All virtual datasets in the tenant
        2. Relationships between datasets (based on shared sources, query dependencies)
        3. Health metrics for each dataset
        4. Overall topology graph structure

        Args:
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            include_health_metrics: Whether to include health metrics (default: True)

        Returns:
            Dictionary containing topology graph with nodes (virtual datasets) and edges (relationships),
            health metrics, and summary statistics

        Raises:
            ValidationError: If tenant_id is required but not provided
        """
        import time
        from django.utils import timezone
        from django.db.models import Count, Q, Avg
        from datetime import timedelta

        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Track topology generation start time for metrics
        topology_start_time = time.time()

        # 1. Retrieve all virtual datasets for the tenant
        datasets = VirtualDataset.objects.filter(
            tenant_id=effective_tenant_id
        ).select_related('created_by', 'tenant').prefetch_related('executions')

        # 2. Build dataset nodes
        nodes = []
        dataset_map = {}  # Map dataset_id to index in nodes list

        for idx, dataset in enumerate(datasets):
            node = {
                "id": str(dataset.id),
                "name": dataset.name,
                "description": dataset.description,
                "status": dataset.status,
                "query_type": dataset.query_type,
                "version": dataset.version,
                "created_by_id": str(dataset.created_by.id) if dataset.created_by else None,
                "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                "updated_at": dataset.updated_at.isoformat() if dataset.updated_at else None,
            }

            # Add health metrics if requested
            if include_health_metrics:
                # Get execution statistics
                executions = dataset.executions.all()
                total_executions = executions.count()

                # Get execution counts by status
                completed_count = executions.filter(status=QueryExecutionStatus.COMPLETED).count()
                failed_count = executions.filter(status=QueryExecutionStatus.FAILED).count()
                running_count = executions.filter(status=QueryExecutionStatus.RUNNING).count()

                # Calculate success rate
                success_rate = (completed_count / total_executions * 100) if total_executions > 0 else None

                # Get recent executions (last 24 hours)
                recent_cutoff = timezone.now() - timedelta(hours=24)
                recent_executions = executions.filter(created_at__gte=recent_cutoff)
                recent_failed = recent_executions.filter(status=QueryExecutionStatus.FAILED).count()
                recent_total = recent_executions.count()
                recent_success_rate = (recent_executions.filter(status=QueryExecutionStatus.COMPLETED).count() / recent_total * 100) if recent_total > 0 else None

                # Get average execution duration from completed executions
                completed_executions = executions.filter(
                    status=QueryExecutionStatus.COMPLETED,
                    metrics__isnull=False
                )
                avg_duration_ms = None
                if completed_executions.exists():
                    durations = [
                        exec.metrics.get('duration_ms', 0)
                        for exec in completed_executions
                        if exec.metrics and isinstance(exec.metrics, dict)
                    ]
                    if durations:
                        avg_duration_ms = sum(durations) / len(durations)

                # Calculate health score (0-100)
                health_score = 100

                # Deduct points for inactive status
                if dataset.status != VirtualDatasetStatus.ACTIVE:
                    health_score -= 30

                # Deduct points for low success rate
                if success_rate is not None:
                    if success_rate < 50:
                        health_score -= 40
                    elif success_rate < 80:
                        health_score -= 20
                    elif success_rate < 95:
                        health_score -= 10

                # Deduct points for recent failures
                if recent_total > 0 and recent_failed > 0:
                    recent_failure_rate = (recent_failed / recent_total) * 100
                    if recent_failure_rate > 50:
                        health_score -= 20
                    elif recent_failure_rate > 25:
                        health_score -= 10

                # Deduct points if no executions (untested)
                if total_executions == 0:
                    health_score -= 15

                health_score = max(0, health_score)  # Ensure non-negative

                node["health_metrics"] = {
                    "health_score": health_score,
                    "total_executions": total_executions,
                    "completed_executions": completed_count,
                    "failed_executions": failed_count,
                    "running_executions": running_count,
                    "success_rate": success_rate,
                    "recent_success_rate": recent_success_rate,
                    "recent_failed_count": recent_failed,
                    "average_duration_ms": avg_duration_ms,
                    "is_active": dataset.status == VirtualDatasetStatus.ACTIVE,
                }

            nodes.append(node)
            dataset_map[str(dataset.id)] = idx

        # 3. Calculate relationships between datasets
        edges = []

        # Extract source identifiers from each dataset
        dataset_sources = {}
        for dataset in datasets:
            sources_list = dataset.sources if dataset.sources and isinstance(dataset.sources, list) else []
            # Extract source identifiers (could be connection strings, IDs, or names)
            source_ids = set()
            for source in sources_list:
                if isinstance(source, dict):
                    # Try common identifier fields
                    for key in ['id', 'source_id', 'connection_id', 'name', 'url', 'endpoint']:
                        if key in source and source[key]:
                            source_ids.add(str(source[key]))
                elif isinstance(source, str):
                    source_ids.add(source)
            dataset_sources[str(dataset.id)] = source_ids

        # Find relationships based on shared sources
        dataset_list = list(datasets)
        for i, dataset1 in enumerate(dataset_list):
            sources1 = dataset_sources.get(str(dataset1.id), set())
            for j, dataset2 in enumerate(dataset_list):
                if i >= j:  # Avoid duplicate relationships
                    continue

                sources2 = dataset_sources.get(str(dataset2.id), set())
                shared_sources = sources1 & sources2

                if shared_sources:
                    source_idx = dataset_map.get(str(dataset1.id))
                    target_idx = dataset_map.get(str(dataset2.id))
                    if source_idx is not None and target_idx is not None:
                        edges.append({
                            "source": str(dataset1.id),
                            "target": str(dataset2.id),
                            "type": "SHARED_SOURCE",
                            "weight": len(shared_sources),
                            "shared_sources": list(shared_sources)[:5]  # Limit to first 5 for response size
                        })

        # 4. Build topology graph
        topology = {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "tenant_id": effective_tenant_id,
                "dataset_count": len(nodes),
                "relationship_count": len(edges),
                "generated_at": timezone.now().isoformat(),
            }
        }

        # 5. Calculate summary statistics
        summary = {
            "total_datasets": len(nodes),
            "active_datasets": sum(1 for n in nodes if n.get("status") == VirtualDatasetStatus.ACTIVE),
            "total_relationships": len(edges),
            "average_health_score": sum(
                n.get("health_metrics", {}).get("health_score", 0) for n in nodes
            ) / len(nodes) if nodes and include_health_metrics else None,
        }

        topology["summary"] = summary

        # 6. Record metrics (if metrics module available)
        try:
            from hub.apps.virtualization.metrics import get_tenant_id
            tenant_label = get_tenant_id(effective_tenant_id)
            topology_duration = time.time() - topology_start_time

            # Note: Topology metrics would need to be added to metrics.py if not already present
            logger.debug(
                f"Generated topology for tenant {effective_tenant_id}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "dataset_count": len(nodes),
                    "relationship_count": len(edges),
                    "duration_seconds": topology_duration
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to record metrics for topology generation {effective_tenant_id}: {e}",
                exc_info=True,
            )

        # 7. Publish topology.updated event (if event publisher supports it)
        try:
            # Note: Would need to add publish_topology_updated to VirtualizationEventPublisher if needed
            logger.debug(
                f"Topology generated for tenant {effective_tenant_id}",
                extra={
                    "tenant_id": effective_tenant_id,
                    "dataset_count": len(nodes),
                    "relationship_count": len(edges)
                }
            )
        except Exception as e:
            logger.warning(
                f"Failed to publish topology event for tenant {effective_tenant_id}: {e}",
                exc_info=True,
            )

        return topology

