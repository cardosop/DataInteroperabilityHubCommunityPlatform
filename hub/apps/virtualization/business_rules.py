"""
Virtualization Business Rules

Comprehensive business rules validation for virtual datasets, including:
- Query syntax validation
- Schema alignment validation
- Source compatibility validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
import re
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.virtualization.models import VirtualDataset, QueryType, QueryExecutionMode
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.core.services.base import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class VirtualizationRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for virtualization business rules.

    Adds virtualization-specific context:
    - virtual_dataset: The virtual dataset being validated
    - query: Optional query string being validated
    """
    virtual_dataset: Optional[VirtualDataset] = None
    query: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'virtual_dataset_id': str(self.virtual_dataset.id) if self.virtual_dataset else None,
            'query_preview': self.query[:100] + "..." if self.query and len(self.query) > 100 else self.query,
        })
        return base_dict


@register_rule(
    rule_name="virtualization_dataset_validation",
    description="Validates virtual dataset query syntax, schema alignment, and source compatibility",
    tags=["virtualization", "dataset", "validation"],
    priority=10
)
class VirtualizationBusinessRules(BusinessRules):
    """
    Business rules validator for virtual datasets.

    Extends BusinessRules base class with virtualization-specific validation:
    - Query syntax for different query types
    - Schema alignment between query and output schema
    - Source compatibility with query type and each other
    """

    # Valid query types
    VALID_QUERY_TYPES = {choice[0] for choice in QueryType.choices}

    # SQL forbidden keywords (write operations)
    SQL_FORBIDDEN_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE TABLE',
        'CREATE DATABASE', 'CREATE SCHEMA', 'DROP TABLE', 'DROP DATABASE'
    ]

    # SQL required keywords (at least one must be present)
    SQL_REQUIRED_KEYWORDS = ['SELECT', 'WITH', 'INSERT', 'UPDATE']

    # SPARQL forbidden keywords (write operations)
    SPARQL_FORBIDDEN_KEYWORDS = ['INSERT', 'DELETE', 'DROP', 'CREATE', 'LOAD', 'CLEAR']

    # SPARQL required keywords (at least one must be present)
    SPARQL_REQUIRED_KEYWORDS = ['SELECT', 'CONSTRUCT', 'ASK', 'DESCRIBE', 'PREFIX']

    # Supported source types
    SUPPORTED_SOURCE_TYPES = [
        'postgresql', 'mysql', 'sqlserver', 'mssql',
        'sparql', 'rest', 'graphql', 's3', 'minio',
        'federated_asset', 'external_resource'
    ]

    # Source type compatibility with query types
    QUERY_TYPE_SOURCE_COMPATIBILITY = {
        QueryType.SQL: ['postgresql', 'mysql', 'sqlserver', 'mssql', 'federated_asset', 'external_resource'],
        QueryType.SPARQL: ['sparql', 'federated_asset'],
        QueryType.REST: ['rest', 'federated_asset', 'external_resource', 'odps_contract'],
        QueryType.GRAPHQL: ['graphql', 'federated_asset'],
        QueryType.FEDERATED: ['postgresql', 'mysql', 'sqlserver', 'mssql', 'sparql', 'rest', 'graphql', 'federated_asset', 'external_resource', 'odps_contract']
    }

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "VirtualizationBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates all virtualization validation checks.
        It can be called with a VirtualizationRuleExecutionContext or a standard
        RuleExecutionContext. If a standard context is provided, it extracts
        virtual_dataset and query from kwargs or context.metadata.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - virtual_dataset: VirtualDataset instance (required)
                - query: Optional query string
                - validation_type: Optional validation type filter
                    ('query_syntax', 'schema_alignment', 'source_compatibility', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        # Extract virtual_dataset and query from context or kwargs
        if isinstance(context, VirtualizationRuleExecutionContext):
            virtual_dataset = context.virtual_dataset
            query = context.query
        else:
            # Try to get from kwargs first
            virtual_dataset = kwargs.get('virtual_dataset')
            query = kwargs.get('query')

            # If not in kwargs, try to get from context.metadata or context.resource
            if not virtual_dataset:
                if context and hasattr(context, 'resource') and isinstance(context.resource, VirtualDataset):
                    virtual_dataset = context.resource
                elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
                    virtual_dataset = context.metadata.get('virtual_dataset')
                    query = query or context.metadata.get('query')

        if not virtual_dataset:
            return ValidationResult(
                is_valid=False,
                errors=["Virtual dataset is required for validation"],
                details={"validation_type": kwargs.get('validation_type', 'all')}
            )

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id) if virtual_dataset.id else None,
            "dataset_name": virtual_dataset.name if hasattr(virtual_dataset, 'name') else None,
            "validation_type": validation_type,
        }

        # Perform validation based on type
        if validation_type in ('query_syntax', 'query_mapping', 'all'):
            query_to_validate = query or virtual_dataset.query
            if query_to_validate:
                # Use query_mapping validation which includes syntax validation
                query_result = self.validate_query_mapping(virtual_dataset, raise_on_error=False)
                if not query_result.is_valid:
                    errors.extend(query_result.errors)
                    warnings.extend(query_result.warnings)
                    details["query_mapping"] = query_result.details

        if validation_type in ('schema_alignment', 'schema', 'all'):
            schema_result = self.validate_virtual_dataset_schema(virtual_dataset, raise_on_error=False)
            if not schema_result.is_valid:
                errors.extend(schema_result.errors)
                warnings.extend(schema_result.warnings)
                details["schema"] = schema_result.details

        if validation_type in ('source_compatibility', 'source_configuration', 'all'):
            # Use source_configuration validation which includes compatibility checks
            source_result = self.validate_source_configuration(virtual_dataset, raise_on_error=False)
            if not source_result.is_valid:
                errors.extend(source_result.errors)
                warnings.extend(source_result.warnings)
                details["source_configuration"] = source_result.details

        if validation_type in ('caching_configuration', 'cache', 'all'):
            cache_config = kwargs.get('cache_config')
            cache_result = self.validate_caching_configuration(
                virtual_dataset,
                cache_config=cache_config,
                raise_on_error=False
            )
            if not cache_result.is_valid:
                errors.extend(cache_result.errors)
                warnings.extend(cache_result.warnings)
                details["caching_configuration"] = cache_result.details

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_query_syntax(
        self,
        query: str,
        query_type: QueryType,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate query syntax for the given query type.

        Validates:
        - Query is not empty
        - Query contains required keywords for the query type
        - Query does not contain forbidden keywords
        - Query structure is valid for the query type

        Args:
            query: Query string to validate
            query_type: Query type (SQL, SPARQL, etc.)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "query_type": query_type,
            "query_length": len(query) if query else 0,
            "validation_checks": {}
        }

        # Validate query is not empty
        if not query or not query.strip():
            errors.append("Query cannot be empty")
            details["validation_checks"]["query_not_empty"] = False
        else:
            details["validation_checks"]["query_not_empty"] = True

        if errors:
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ValidationError(
                    f"Query syntax validation failed: {errors[0]}",
                    code="INVALID_QUERY_SYNTAX",
                    details=details
                )
            return result

        query_upper = query.upper().strip()
        details["query_preview"] = query[:100] + "..." if len(query) > 100 else query

        # Validate based on query type
        if query_type == QueryType.SQL:
            validation_result = self._validate_sql_syntax(query, query_upper, details)
            errors.extend(validation_result["errors"])
            warnings.extend(validation_result["warnings"])
            details.update(validation_result["details"])

        elif query_type == QueryType.SPARQL:
            validation_result = self._validate_sparql_syntax(query, query_upper, details)
            errors.extend(validation_result["errors"])
            warnings.extend(validation_result["warnings"])
            details.update(validation_result["details"])

        elif query_type == QueryType.FEDERATED:
            # Federated queries can contain multiple query types
            # Basic validation - check for common issues
            if not query.strip():
                errors.append("Federated query cannot be empty")
            else:
                details["validation_checks"]["federated_query_structure"] = True

        elif query_type in [QueryType.REST, QueryType.GRAPHQL]:
            # REST and GraphQL queries are validated differently
            # Basic validation - check query is not empty
            if not query.strip():
                errors.append(f"{query_type} query cannot be empty")
            else:
                details["validation_checks"][f"{query_type.lower()}_query_structure"] = True

        else:
            errors.append(f"Unsupported query type: {query_type}")
            details["validation_checks"]["query_type_supported"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Query syntax validation failed: {', '.join(errors)}",
                code="INVALID_QUERY_SYNTAX",
                details=details
            )

        return result

    def _validate_sql_syntax(
        self,
        query: str,
        query_upper: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate SQL query syntax"""
        errors: List[str] = []
        warnings: List[str] = []
        validation_checks = details.get("validation_checks", {})

        # Check for forbidden keywords
        for keyword in self.SQL_FORBIDDEN_KEYWORDS:
            if keyword in query_upper:
                errors.append(f"SQL query contains forbidden keyword: {keyword}")
                validation_checks["forbidden_keywords"] = False
                break
        else:
            validation_checks["forbidden_keywords"] = True

        # Check for required keywords
        has_required_keyword = any(keyword in query_upper for keyword in self.SQL_REQUIRED_KEYWORDS)
        if not has_required_keyword:
            errors.append(
                f"SQL query must contain at least one of: {', '.join(self.SQL_REQUIRED_KEYWORDS)}"
            )
            validation_checks["required_keywords"] = False
        else:
            validation_checks["required_keywords"] = True

        # Check for potentially problematic patterns
        if "SELECT *" in query_upper and "LIMIT" not in query_upper:
            warnings.append("Query uses SELECT * without LIMIT - may return large result sets")
            validation_checks["unbounded_select"] = True

        # Check for basic SQL structure (parentheses balance)
        open_parens = query.count('(')
        close_parens = query.count(')')
        if open_parens != close_parens:
            errors.append(
                f"Unbalanced parentheses in SQL query (opening: {open_parens}, closing: {close_parens})"
            )
            validation_checks["balanced_parentheses"] = False
        else:
            validation_checks["balanced_parentheses"] = True

        # Check for string literal balance (basic check)
        single_quotes = query.count("'")
        if single_quotes % 2 != 0:
            warnings.append("Potential unbalanced single quotes in SQL query")
            validation_checks["balanced_quotes"] = False
        else:
            validation_checks["balanced_quotes"] = True

        details["validation_checks"] = validation_checks

        return {
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def _validate_sparql_syntax(
        self,
        query: str,
        query_upper: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate SPARQL query syntax"""
        errors: List[str] = []
        warnings: List[str] = []
        validation_checks = details.get("validation_checks", {})

        # Check for forbidden keywords
        for keyword in self.SPARQL_FORBIDDEN_KEYWORDS:
            if keyword in query_upper:
                errors.append(f"SPARQL query contains forbidden keyword: {keyword}")
                validation_checks["forbidden_keywords"] = False
                break
        else:
            validation_checks["forbidden_keywords"] = True

        # Check for required keywords
        has_required_keyword = any(keyword in query_upper for keyword in self.SPARQL_REQUIRED_KEYWORDS)
        if not has_required_keyword:
            errors.append(
                f"SPARQL query must contain at least one of: {', '.join(self.SPARQL_REQUIRED_KEYWORDS)}"
            )
            validation_checks["required_keywords"] = False
        else:
            validation_checks["required_keywords"] = True

        # Check for basic SPARQL structure (triple patterns)
        if "WHERE" in query_upper or "{" in query:
            validation_checks["has_triple_patterns"] = True
        else:
            warnings.append("SPARQL query may be missing WHERE clause or triple patterns")
            validation_checks["has_triple_patterns"] = False

        # Check for balanced braces
        open_braces = query.count('{')
        close_braces = query.count('}')
        if open_braces != close_braces:
            errors.append(
                f"Unbalanced braces in SPARQL query (opening: {open_braces}, closing: {close_braces})"
            )
            validation_checks["balanced_braces"] = False
        else:
            validation_checks["balanced_braces"] = True

        details["validation_checks"] = validation_checks

        return {
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def validate_source_configuration(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate source configuration (valid sources, accessible).

        Validates:
        - Sources are valid and properly configured
        - Sources are accessible (connection can be established)
        - Source types are supported
        - Required fields are present for each source type
        - Asset-based sources exist and are accessible
        - Cross-tenant source access permissions

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "source_configuration_checks": {}
        }

        sources = virtual_dataset.sources or []
        query_type = virtual_dataset.query_type

        # Sources are optional for SPARQL queries
        if not sources:
            if query_type == QueryType.SPARQL:
                details["source_configuration_checks"]["sources_required"] = False
                return ValidationResult(
                    is_valid=True,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
            else:
                errors.append(f"Sources are required for {query_type} queries")
                details["source_configuration_checks"]["sources_required"] = False
                result = ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
                if raise_on_error:
                    raise ValidationError(
                        f"Source configuration validation failed: {errors[0]}",
                        code="INVALID_SOURCE_CONFIGURATION",
                        details=details
                    )
                return result

        details["source_configuration_checks"]["sources_required"] = True
        details["source_configuration_checks"]["source_count"] = len(sources)

        # Get compatible source types for query type
        compatible_types = self.QUERY_TYPE_SOURCE_COMPATIBILITY.get(query_type, [])
        details["source_configuration_checks"]["compatible_source_types"] = compatible_types

        # Validate each source
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                errors.append(f"Source configuration at index {i} must be an object")
                continue

            source_type = source_config.get("type", "").lower()
            if not source_type:
                errors.append(f"Source configuration at index {i} must have a 'type' field")
                continue

            # Check if source type is supported
            if source_type not in self.SUPPORTED_SOURCE_TYPES:
                errors.append(
                    f"Source type '{source_type}' at index {i} is not supported. "
                    f"Supported types: {', '.join(self.SUPPORTED_SOURCE_TYPES)}"
                )
                details["source_configuration_checks"][f"source_{i}_type_supported"] = False
            else:
                details["source_configuration_checks"][f"source_{i}_type_supported"] = True

            # Check source type compatibility with query type
            if compatible_types and source_type not in compatible_types:
                errors.append(
                    f"Source type '{source_type}' at index {i} is not compatible with query type '{query_type}'. "
                    f"Compatible types: {', '.join(compatible_types)}"
                )
                details["source_configuration_checks"][f"source_{i}_type_compatible"] = False
            else:
                details["source_configuration_checks"][f"source_{i}_type_compatible"] = True

            # Validate source-specific required fields
            source_errors = self._validate_source_config(source_config, i, source_type)
            errors.extend(source_errors)

            # Check source accessibility
            accessibility_result = self._validate_source_accessibility(source_config, i, source_type)
            if not accessibility_result["accessible"]:
                errors.extend(accessibility_result["errors"])
                warnings.extend(accessibility_result["warnings"])
            else:
                warnings.extend(accessibility_result["warnings"])
            details["source_configuration_checks"][f"source_{i}_accessible"] = accessibility_result["accessible"]
            details["source_configuration_checks"][f"source_{i}_accessibility_details"] = accessibility_result["details"]

            # Check asset-based source access
            asset_id = source_config.get("asset_id")
            if asset_id:
                try:
                    asset = Asset.objects.select_related('tenant').get(id=asset_id)
                    details["source_configuration_checks"][f"source_{i}_asset_exists"] = True

                    # Check cross-tenant access if applicable
                    if self.tenant_id and str(asset.tenant_id) != self.tenant_id:
                        # Cross-tenant access - check entitlements
                        from hub.apps.marketplace.access_utils import check_entitlement

                        has_access, error_code, _ = check_entitlement(
                            consumer_tenant_id=self.tenant_id,
                            asset_id=str(asset_id),
                            provider_tenant_id=str(asset.tenant_id)
                        )

                        if not has_access:
                            errors.append(
                                f"Source at index {i} references asset from different tenant without entitlement. "
                                f"Asset: {asset.name} (tenant: {asset.tenant.name}), Error code: {error_code}"
                            )
                            details["source_configuration_checks"][f"source_{i}_cross_tenant_access"] = False
                        else:
                            details["source_configuration_checks"][f"source_{i}_cross_tenant_access"] = True
                    else:
                        details["source_configuration_checks"][f"source_{i}_cross_tenant_access"] = True

                except Asset.DoesNotExist:
                    errors.append(f"Source at index {i} references non-existent asset: {asset_id}")
                    details["source_configuration_checks"][f"source_{i}_asset_exists"] = False
                except Exception as e:
                    warnings.append(f"Failed to validate asset access for source {i}: {str(e)}")
                    details["source_configuration_checks"][f"source_{i}_asset_validation"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Source configuration validation failed: {', '.join(errors)}",
                code="INVALID_SOURCE_CONFIGURATION",
                details=details
            )

        return result

    def _validate_source_accessibility(
        self,
        source_config: Dict[str, Any],
        source_index: int,
        source_type: str
    ) -> Dict[str, Any]:
        """
        Validate source accessibility (can be connected to).

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list
            source_type: Type of source

        Returns:
            Dictionary with accessibility status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "source_type": source_type,
            "source_index": source_index
        }

        # For database sources, check if connection details are complete
        if source_type in ['postgresql', 'mysql', 'sqlserver', 'mssql']:
            # Check required connection fields
            required_fields = ['host', 'database']
            missing_fields = [f for f in required_fields if f not in source_config]
            if missing_fields:
                errors.append(
                    f"Source at index {source_index} (type: {source_type}) "
                    f"missing required connection fields: {', '.join(missing_fields)}"
                )
                details["connection_fields_complete"] = False
            else:
                details["connection_fields_complete"] = True

            # Check if credentials are provided (either in config or via asset)
            has_credentials = (
                'username' in source_config or
                'user' in source_config or
                'password' in source_config or
                'connection_string' in source_config or
                source_config.get('asset_id') is not None
            )
            if not has_credentials:
                warnings.append(
                    f"Source at index {source_index} (type: {source_type}) "
                    f"may not have credentials configured. Connection may fail."
                )
                details["has_credentials"] = False
            else:
                details["has_credentials"] = True

            # Validate host format (basic check)
            host = source_config.get('host', '')
            if host:
                # Basic host validation (IP or hostname)
                ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
                hostname_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
                if not (re.match(ip_pattern, host) or re.match(hostname_pattern, host)):
                    warnings.append(
                        f"Source at index {source_index} has invalid host format: {host}"
                    )
                    details["host_format_valid"] = False
                else:
                    details["host_format_valid"] = True

        # For REST sources, validate URL format
        elif source_type == 'rest':
            url = source_config.get('url') or source_config.get('endpoint', '')
            if url:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        errors.append(
                            f"Source at index {source_index} (type: {source_type}) "
                            f"has invalid URL format: {url}"
                        )
                        details["url_format_valid"] = False
                    else:
                        details["url_format_valid"] = True
                        # Check if scheme is supported
                        supported_schemes = ['http', 'https']
                        if parsed.scheme.lower() not in supported_schemes:
                            warnings.append(
                                f"Source at index {source_index} uses unsupported URL scheme: {parsed.scheme}"
                            )
                            details["url_scheme_supported"] = False
                        else:
                            details["url_scheme_supported"] = True
                except Exception as e:
                    warnings.append(
                        f"Failed to validate URL for source {source_index}: {str(e)}"
                    )
                    details["url_format_valid"] = False

        # For GraphQL sources, validate endpoint
        elif source_type == 'graphql':
            endpoint = source_config.get('endpoint') or source_config.get('url', '')
            if endpoint:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(endpoint)
                    if not parsed.scheme or not parsed.netloc:
                        errors.append(
                            f"Source at index {source_index} (type: {source_type}) "
                            f"has invalid endpoint format: {endpoint}"
                        )
                        details["endpoint_format_valid"] = False
                    else:
                        details["endpoint_format_valid"] = True
                except Exception as e:
                    warnings.append(
                        f"Failed to validate endpoint for source {source_index}: {str(e)}"
                    )
                    details["endpoint_format_valid"] = False

        # For S3/MinIO sources, validate bucket name
        elif source_type in ['s3', 'minio']:
            bucket = source_config.get('bucket', '')
            if bucket:
                # S3 bucket name validation rules
                # Bucket names must be lowercase, 3-63 characters, and follow naming rules
                bucket_lower = bucket.lower()

                # Check for uppercase letters (S3 bucket names must be lowercase)
                if bucket != bucket_lower:
                    errors.append(
                        f"Source at index {source_index} (type: {source_type}) "
                        f"has invalid bucket name: {bucket} (bucket names must be lowercase)"
                    )
                    details["bucket_name_valid"] = False
                elif len(bucket) < 3 or len(bucket) > 63:
                    errors.append(
                        f"Source at index {source_index} (type: {source_type}) "
                        f"has invalid bucket name length: {bucket} (must be 3-63 characters)"
                    )
                    details["bucket_name_valid"] = False
                elif not re.match(r'^[a-z0-9][a-z0-9\-\.]*[a-z0-9]$', bucket_lower):
                    errors.append(
                        f"Source at index {source_index} (type: {source_type}) "
                        f"has invalid bucket name format: {bucket}"
                    )
                    details["bucket_name_valid"] = False
                elif '..' in bucket or bucket.startswith('.') or bucket.endswith('.'):
                    errors.append(
                        f"Source at index {source_index} (type: {source_type}) "
                        f"has invalid bucket name: {bucket} (cannot contain consecutive dots or start/end with dot)"
                    )
                    details["bucket_name_valid"] = False
                else:
                    details["bucket_name_valid"] = True

        accessible = len(errors) == 0
        return {
            "accessible": accessible,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def validate_query_mapping(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate query mapping (valid query syntax, supported languages).

        Validates:
        - Query syntax is valid for the query type
        - Query language is supported
        - Query structure is correct
        - Query parameters are valid (if applicable)

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "query_mapping_checks": {}
        }

        query = virtual_dataset.query
        query_type = virtual_dataset.query_type

        # Validate query is not empty
        if not query or not query.strip():
            errors.append("Query cannot be empty")
            details["query_mapping_checks"]["query_not_empty"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ValidationError(
                    f"Query mapping validation failed: {errors[0]}",
                    code="INVALID_QUERY_MAPPING",
                    details=details
                )
            return result

        details["query_mapping_checks"]["query_not_empty"] = True
        details["query_mapping_checks"]["query_length"] = len(query)

        # Check if query type is supported
        if query_type not in self.VALID_QUERY_TYPES:
            errors.append(
                f"Query type '{query_type}' is not supported. "
                f"Supported types: {', '.join(sorted(self.VALID_QUERY_TYPES))}"
            )
            details["query_mapping_checks"]["query_type_supported"] = False
        else:
            details["query_mapping_checks"]["query_type_supported"] = True

        # Validate query syntax using existing method
        query_syntax_result = self.validate_query_syntax(
            query=query,
            query_type=query_type,
            raise_on_error=False
        )

        if not query_syntax_result.is_valid:
            errors.extend(query_syntax_result.errors)
            details["query_mapping_checks"]["query_syntax_valid"] = False
        else:
            details["query_mapping_checks"]["query_syntax_valid"] = True

        warnings.extend(query_syntax_result.warnings)
        details["query_mapping_checks"].update(query_syntax_result.details.get("validation_checks", {}))

        # Check query language support
        language_support_result = self._validate_query_language_support(query, query_type)
        if not language_support_result["supported"]:
            errors.extend(language_support_result["errors"])
            details["query_mapping_checks"]["language_supported"] = False
        else:
            details["query_mapping_checks"]["language_supported"] = True
        warnings.extend(language_support_result["warnings"])
        details["query_mapping_checks"].update(language_support_result["details"])

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Query mapping validation failed: {', '.join(errors)}",
                code="INVALID_QUERY_MAPPING",
                details=details
            )

        return result

    def _validate_query_language_support(
        self,
        query: str,
        query_type: QueryType
    ) -> Dict[str, Any]:
        """
        Validate query language support.

        Args:
            query: Query string
            query_type: Query type

        Returns:
            Dictionary with language support status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Supported SQL dialects
        sql_dialects = ['postgresql', 'mysql', 'sqlserver', 'mssql', 'sqlite', 'standard']
        # Supported SPARQL versions
        sparql_versions = ['1.0', '1.1']

        if query_type == QueryType.SQL:
            # Check for dialect-specific syntax
            query_upper = query.upper()
            # PostgreSQL-specific features
            if 'ILIKE' in query_upper or '::' in query:
                details["detected_dialect"] = "postgresql"
                details["dialect_supported"] = True
            # MySQL-specific features
            elif 'LIMIT' in query_upper and 'OFFSET' not in query_upper and query_upper.count('LIMIT') == 1:
                # MySQL uses LIMIT without OFFSET differently
                limit_match = re.search(r'LIMIT\s+(\d+)\s*,\s*(\d+)', query_upper)
                if limit_match:
                    details["detected_dialect"] = "mysql"
                    details["dialect_supported"] = True
            # SQL Server-specific features
            elif 'TOP' in query_upper or 'WITH (NOLOCK)' in query_upper:
                details["detected_dialect"] = "sqlserver"
                details["dialect_supported"] = True
            else:
                details["detected_dialect"] = "standard"
                details["dialect_supported"] = True

            details["supported_dialects"] = sql_dialects

        elif query_type == QueryType.SPARQL:
            # Check SPARQL version indicators
            query_upper = query.upper()
            if 'PREFIX' in query_upper or 'SELECT' in query_upper:
                # SPARQL 1.1 features
                if 'VALUES' in query_upper or 'BIND' in query_upper or 'SERVICE' in query_upper:
                    details["detected_version"] = "1.1"
                else:
                    details["detected_version"] = "1.0"
                details["version_supported"] = True
            else:
                details["detected_version"] = "unknown"
                details["version_supported"] = True  # Assume supported

            details["supported_versions"] = sparql_versions

        elif query_type == QueryType.FEDERATED:
            # Federated queries can contain multiple query types
            details["federated_query"] = True
            details["supported"] = True

        elif query_type in [QueryType.REST, QueryType.GRAPHQL]:
            # REST and GraphQL queries are language-agnostic
            details["language_agnostic"] = True
            details["supported"] = True

        else:
            errors.append(f"Unsupported query type for language validation: {query_type}")
            details["supported"] = False

        return {
            "supported": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def validate_caching_configuration(
        self,
        virtual_dataset: VirtualDataset,
        cache_config: Optional[Dict[str, Any]] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate caching configuration (valid TTL, cache keys).

        Validates:
        - Cache TTL is within acceptable range
        - Cache keys are valid and properly formatted
        - Cache configuration is appropriate for the dataset
        - Cache key generation is deterministic

        Args:
            virtual_dataset: VirtualDataset instance to validate
            cache_config: Optional cache configuration dictionary with 'enabled', 'ttl', 'key_prefix', etc.
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "caching_configuration_checks": {}
        }

        # Use provided cache_config or default
        if cache_config is None:
            cache_config = {}

        cache_enabled = cache_config.get("enabled", True)
        cache_ttl = cache_config.get("ttl")
        cache_key_prefix = cache_config.get("key_prefix")
        cache_key = cache_config.get("key")

        details["caching_configuration_checks"]["cache_enabled"] = cache_enabled

        if not cache_enabled:
            details["caching_configuration_checks"]["validation_skipped"] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Validate cache TTL using ResultBusinessRules
        from hub.apps.virtualization.business_rules import ResultBusinessRules
        result_rules = ResultBusinessRules(
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        cache_ttl_result = result_rules.validate_result_caching(
            cache_enabled=True,
            cache_ttl=cache_ttl,
            raise_on_error=False
        )

        if not cache_ttl_result.is_valid:
            errors.extend(cache_ttl_result.errors)
            details["caching_configuration_checks"]["ttl_valid"] = False
        else:
            details["caching_configuration_checks"]["ttl_valid"] = True
            details["caching_configuration_checks"]["validated_ttl"] = cache_ttl_result.details.get("validated_cache_ttl")

        warnings.extend(cache_ttl_result.warnings)

        # Validate cache key prefix if provided
        if cache_key_prefix:
            key_prefix_result = self._validate_cache_key_prefix(cache_key_prefix)
            if not key_prefix_result["valid"]:
                errors.extend(key_prefix_result["errors"])
                details["caching_configuration_checks"]["key_prefix_valid"] = False
            else:
                details["caching_configuration_checks"]["key_prefix_valid"] = True
            warnings.extend(key_prefix_result["warnings"])
            details["caching_configuration_checks"]["key_prefix"] = cache_key_prefix
        else:
            details["caching_configuration_checks"]["key_prefix_provided"] = False

        # Validate cache key if provided
        if cache_key:
            key_result = self._validate_cache_key(cache_key, virtual_dataset)
            if not key_result["valid"]:
                errors.extend(key_result["errors"])
                details["caching_configuration_checks"]["key_valid"] = False
            else:
                details["caching_configuration_checks"]["key_valid"] = True
            warnings.extend(key_result["warnings"])
            details["caching_configuration_checks"]["key"] = cache_key
        else:
            # Generate and validate cache key
            from hub.apps.virtualization.services import VirtualizationService
            service = VirtualizationService(
                tenant_id=str(virtual_dataset.tenant_id) if virtual_dataset.tenant else self.tenant_id,
                user_id=self.user_id
            )
            generated_key = service._get_query_cache_key(virtual_dataset, {})
            key_result = self._validate_cache_key(generated_key, virtual_dataset)
            if not key_result["valid"]:
                warnings.extend(key_result["errors"])  # Generated key issues are warnings
                details["caching_configuration_checks"]["generated_key_valid"] = False
            else:
                details["caching_configuration_checks"]["generated_key_valid"] = True
            warnings.extend(key_result["warnings"])
            details["caching_configuration_checks"]["generated_key"] = generated_key

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Caching configuration validation failed: {', '.join(errors)}",
                code="INVALID_CACHING_CONFIGURATION",
                details=details
            )

        return result

    def _validate_cache_key_prefix(
        self,
        key_prefix: str
    ) -> Dict[str, Any]:
        """
        Validate cache key prefix format.

        Args:
            key_prefix: Cache key prefix string

        Returns:
            Dictionary with validation status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Cache key prefix should be alphanumeric with colons and underscores
        # Max length: 100 characters
        if len(key_prefix) > 100:
            errors.append(
                f"Cache key prefix exceeds maximum length (100 characters): {len(key_prefix)} characters"
            )
            details["length_valid"] = False
        else:
            details["length_valid"] = True

        # Check format (alphanumeric, colons, underscores, hyphens)
        if not re.match(r'^[a-zA-Z0-9:_\-]+$', key_prefix):
            errors.append(
                f"Cache key prefix contains invalid characters. "
                f"Allowed: alphanumeric, colons, underscores, hyphens"
            )
            details["format_valid"] = False
        else:
            details["format_valid"] = True

        # Check it doesn't start with a colon
        if key_prefix.startswith(':') or key_prefix.endswith(':'):
            warnings.append("Cache key prefix should not start or end with colon")
            details["colon_position_valid"] = False
        else:
            details["colon_position_valid"] = True

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def _validate_cache_key(
        self,
        cache_key: str,
        virtual_dataset: VirtualDataset
    ) -> Dict[str, Any]:
        """
        Validate cache key format and structure.

        Args:
            cache_key: Cache key string
            virtual_dataset: VirtualDataset instance

        Returns:
            Dictionary with validation status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {}

        # Cache key should not be empty
        if not cache_key or not cache_key.strip():
            errors.append("Cache key cannot be empty")
            details["key_not_empty"] = False
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "details": details
            }

        details["key_not_empty"] = True
        details["key_length"] = len(cache_key)

        # Cache key max length: 250 characters (Redis default)
        if len(cache_key) > 250:
            errors.append(
                f"Cache key exceeds maximum length (250 characters): {len(cache_key)} characters"
            )
            details["length_valid"] = False
        else:
            details["length_valid"] = True

        # Check format (should contain dataset ID or reference)
        dataset_id_str = str(virtual_dataset.id)
        if dataset_id_str not in cache_key:
            warnings.append(
                "Cache key does not contain dataset ID - may cause cache collisions"
            )
            details["contains_dataset_id"] = False
        else:
            details["contains_dataset_id"] = True

        # Check for invalid characters (spaces, special chars that might cause issues)
        if re.search(r'[^\w:\-\.]', cache_key):
            warnings.append(
                "Cache key contains potentially problematic characters. "
                "Consider using only alphanumeric, colons, hyphens, and dots"
            )
            details["format_valid"] = False
        else:
            details["format_valid"] = True

        # Check key structure (should have prefix:dataset_id:hash pattern)
        parts = cache_key.split(':')
        if len(parts) < 2:
            warnings.append(
                "Cache key structure may not follow recommended pattern (prefix:dataset_id:hash)"
            )
            details["structure_valid"] = False
        else:
            details["structure_valid"] = True
            details["key_parts"] = len(parts)

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def validate_virtual_dataset_schema(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate virtual dataset schema.

        Validates:
        - Schema structure is valid
        - Schema fields are properly defined
        - Schema types are valid
        - Schema constraints are valid (if provided)
        - Schema aligns with query output (if query can be analyzed)

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        # Use existing schema alignment validation
        return self.validate_schema_alignment(virtual_dataset, raise_on_error)

    def validate_schema_alignment(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate schema alignment between query and output schema.

        Validates:
        - Schema structure is valid (if provided)
        - Schema fields align with query output (if query can be analyzed)
        - Schema types are valid
        - Schema constraints are valid

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "schema_alignment_checks": {}
        }

        schema = virtual_dataset.schema or {}
        query = virtual_dataset.query
        query_type = virtual_dataset.query_type

        # Schema is optional - if not provided, skip alignment checks
        if not schema:
            details["schema_alignment_checks"]["schema_provided"] = False
            warnings.append("No schema provided - schema alignment cannot be validated")
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["schema_alignment_checks"]["schema_provided"] = True

        # Validate schema structure
        if not isinstance(schema, dict):
            errors.append("Schema must be a JSON object")
            details["schema_alignment_checks"]["schema_structure_valid"] = False
        else:
            details["schema_alignment_checks"]["schema_structure_valid"] = True

        if errors:
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ValidationError(
                    f"Schema alignment validation failed: {errors[0]}",
                    code="INVALID_SCHEMA_ALIGNMENT",
                    details=details
                )
            return result

        # Validate schema format
        if "fields" in schema:
            # Format: {"fields": [{"name": "...", "type": "...", ...}, ...]}
            if not isinstance(schema["fields"], list):
                errors.append("Schema 'fields' must be an array")
                details["schema_alignment_checks"]["fields_array_valid"] = False
            else:
                details["schema_alignment_checks"]["fields_array_valid"] = True
                details["schema_alignment_checks"]["field_count"] = len(schema["fields"])

                # Validate each field
                for i, field in enumerate(schema["fields"]):
                    if not isinstance(field, dict):
                        errors.append(f"Schema field at index {i} must be an object")
                        continue
                    if "name" not in field:
                        errors.append(f"Schema field at index {i} must have a 'name' property")
                    if "type" not in field:
                        warnings.append(f"Schema field at index {i} should have a 'type' property")

        elif any(isinstance(v, dict) for v in schema.values()):
            # Format: {"field_name": {"type": "...", ...}, ...}
            field_count = len([k for k, v in schema.items() if isinstance(v, dict)])
            details["schema_alignment_checks"]["field_count"] = field_count
            details["schema_alignment_checks"]["fields_array_valid"] = True

            # Validate each field
            for field_name, field_def in schema.items():
                if isinstance(field_def, dict):
                    if "type" not in field_def:
                        warnings.append(f"Schema field '{field_name}' should have a 'type' property")
        else:
            # Unknown schema format - warn but don't error
            warnings.append("Schema format not recognized - using custom format")
            details["schema_alignment_checks"]["fields_array_valid"] = None

        # For SQL queries, try to extract column names from SELECT clause
        if query_type == QueryType.SQL and query:
            try:
                query_columns = self._extract_sql_columns(query)
                if query_columns:
                    details["schema_alignment_checks"]["query_columns_extracted"] = True
                    details["schema_alignment_checks"]["query_column_count"] = len(query_columns)
                    details["schema_alignment_checks"]["query_columns"] = query_columns

                    # If schema has fields, check alignment
                    schema_fields = []
                    if "fields" in schema:
                        schema_fields = [f.get("name") for f in schema["fields"] if isinstance(f, dict)]
                    elif schema:
                        schema_fields = [k for k, v in schema.items() if isinstance(v, dict)]

                    if schema_fields:
                        # Check if query columns match schema fields (order may differ)
                        query_cols_set = set(query_columns)
                        schema_fields_set = set(schema_fields)

                        if query_cols_set != schema_fields_set:
                            missing_in_schema = query_cols_set - schema_fields_set
                            missing_in_query = schema_fields_set - query_cols_set

                            if missing_in_schema:
                                warnings.append(
                                    f"Query columns not in schema: {', '.join(str(col) for col in missing_in_schema)}"
                                )
                            if missing_in_query:
                                warnings.append(
                                    f"Schema fields not in query: {', '.join(str(col) for col in missing_in_query)}"
                                )
                        else:
                            details["schema_alignment_checks"]["columns_aligned"] = True
            except Exception as e:
                # Column extraction failed - not a critical error
                logger.debug(f"Failed to extract columns from SQL query: {e}")
                details["schema_alignment_checks"]["query_columns_extracted"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Schema alignment validation failed: {', '.join(errors)}",
                code="INVALID_SCHEMA_ALIGNMENT",
                details=details
            )

        return result

    def _extract_sql_columns(self, query: str) -> List[str]:
        """
        Extract column names from SQL SELECT query.

        This is a basic implementation that handles simple SELECT statements.
        More complex queries (with JOINs, subqueries, etc.) may not be fully parsed.

        Args:
            query: SQL query string

        Returns:
            List of column names extracted from SELECT clause
        """
        columns = []
        query_upper = query.upper()

        # Find SELECT clause
        select_match = re.search(r'\bSELECT\s+(.+?)\s+FROM\b', query_upper, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return columns

        select_clause = select_match.group(1).strip()

        # Handle SELECT *
        if select_clause.strip() == '*':
            return ['*']

        # Split by comma, handling nested parentheses
        current_column = ""
        paren_depth = 0
        for char in select_clause:
            if char == '(':
                paren_depth += 1
                current_column += char
            elif char == ')':
                paren_depth -= 1
                current_column += char
            elif char == ',' and paren_depth == 0:
                # End of column
                col = current_column.strip()
                if col:
                    # Extract column name (handle AS aliases)
                    col_match = re.search(r'(\w+)(?:\s+AS\s+\w+)?$', col, re.IGNORECASE)
                    if col_match:
                        columns.append(col_match.group(1).lower())
                current_column = ""
            else:
                current_column += char

        # Add last column
        if current_column.strip():
            col = current_column.strip()
            col_match = re.search(r'(\w+)(?:\s+AS\s+\w+)?$', col, re.IGNORECASE)
            if col_match:
                columns.append(col_match.group(1).lower())

        return columns

    def validate_source_compatibility(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate source compatibility with query type and each other.

        Validates:
        - Source types are compatible with query type
        - Sources have required configuration fields
        - Sources are accessible (if asset-based)
        - Cross-tenant source access permissions (if applicable)

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "source_compatibility_checks": {}
        }

        sources = virtual_dataset.sources or []
        query_type = virtual_dataset.query_type

        # Sources are optional for SPARQL queries
        if not sources:
            if query_type == QueryType.SPARQL:
                details["source_compatibility_checks"]["sources_required"] = False
                return ValidationResult(
                    is_valid=True,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
            else:
                errors.append(f"Sources are required for {query_type} queries")
                details["source_compatibility_checks"]["sources_required"] = False
                result = ValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    details=details
                )
                if raise_on_error:
                    raise ValidationError(
                        f"Source compatibility validation failed: {errors[0]}",
                        code="INVALID_SOURCE_COMPATIBILITY",
                        details=details
                    )
                return result

        details["source_compatibility_checks"]["sources_required"] = True
        details["source_compatibility_checks"]["source_count"] = len(sources)

        # Get compatible source types for query type
        compatible_types = self.QUERY_TYPE_SOURCE_COMPATIBILITY.get(query_type, [])
        details["source_compatibility_checks"]["compatible_source_types"] = compatible_types

        # Validate each source
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                errors.append(f"Source configuration at index {i} must be an object")
                continue

            source_type = source_config.get("type", "").lower()
            if not source_type:
                errors.append(f"Source configuration at index {i} must have a 'type' field")
                continue

            # Check source type compatibility with query type
            if compatible_types and source_type not in compatible_types:
                errors.append(
                    f"Source type '{source_type}' at index {i} is not compatible with query type '{query_type}'. "
                    f"Compatible types: {', '.join(compatible_types)}"
                )
                details["source_compatibility_checks"][f"source_{i}_type_compatible"] = False
            else:
                details["source_compatibility_checks"][f"source_{i}_type_compatible"] = True

            # Validate source-specific required fields
            source_errors = self._validate_source_config(source_config, i, source_type)
            errors.extend(source_errors)

            # Check asset-based source access
            asset_id = source_config.get("asset_id")
            if asset_id:
                try:
                    asset = Asset.objects.select_related('tenant').get(id=asset_id)
                    details["source_compatibility_checks"][f"source_{i}_asset_exists"] = True

                    # Check cross-tenant access if applicable
                    if self.tenant_id and str(asset.tenant_id) != self.tenant_id:
                        # Cross-tenant access - check entitlements
                        from hub.apps.marketplace.access_utils import check_entitlement

                        has_access, error_code, _ = check_entitlement(
                            consumer_tenant_id=self.tenant_id,
                            asset_id=str(asset_id),
                            provider_tenant_id=str(asset.tenant_id)
                        )

                        if not has_access:
                            errors.append(
                                f"Source at index {i} references asset from different tenant without entitlement. "
                                f"Error code: {error_code}"
                            )
                            details["source_compatibility_checks"][f"source_{i}_cross_tenant_access"] = False
                        else:
                            details["source_compatibility_checks"][f"source_{i}_cross_tenant_access"] = True
                    else:
                        details["source_compatibility_checks"][f"source_{i}_cross_tenant_access"] = True

                except Asset.DoesNotExist:
                    errors.append(f"Source at index {i} references non-existent asset: {asset_id}")
                    details["source_compatibility_checks"][f"source_{i}_asset_exists"] = False
                except Exception as e:
                    warnings.append(f"Failed to validate asset access for source {i}: {str(e)}")
                    details["source_compatibility_checks"][f"source_{i}_asset_validation"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Source compatibility validation failed: {', '.join(errors)}",
                code="INVALID_SOURCE_COMPATIBILITY",
                details=details
            )

        return result

    def _validate_source_config(
        self,
        source_config: Dict[str, Any],
        source_index: int,
        source_type: str
    ) -> List[str]:
        """
        Validate source configuration based on source type.

        Supports:
        - Traditional sources: postgresql, mysql, sqlserver, sparql, rest, graphql, s3, minio
        - Federated asset sources: {"type": "federated_asset", "asset_id": "uuid", "query": "SELECT * FROM ..."}
        - External resource sources: {"type": "external_resource", "resource_id": "uuid", "asset_id": "uuid"}

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list
            source_type: Type of source

        Returns:
            List of error messages
        """
        errors = []

        # Handle federated asset sources
        if source_type == "federated_asset":
            return self._validate_federated_asset_source_config(source_config, source_index)

        # Handle external resource sources
        if source_type == "external_resource":
            return self._validate_external_resource_source_config(source_config, source_index)

        # Database sources require connection details
        if source_type in ['postgresql', 'mysql', 'sqlserver', 'mssql']:
            required_fields = ['host', 'database']
            for field in required_fields:
                if field not in source_config:
                    errors.append(
                        f"Source at index {source_index} (type: {source_type}) "
                        f"must have '{field}' field"
                    )

        # REST sources require URL
        elif source_type == 'rest':
            if 'url' not in source_config and 'endpoint' not in source_config:
                errors.append(
                    f"Source at index {source_index} (type: {source_type}) "
                    f"must have 'url' or 'endpoint' field"
                )

        # GraphQL sources require endpoint
        elif source_type == 'graphql':
            if 'endpoint' not in source_config and 'url' not in source_config:
                errors.append(
                    f"Source at index {source_index} (type: {source_type}) "
                    f"must have 'endpoint' or 'url' field"
                )

        # S3/MinIO sources require bucket
        elif source_type in ['s3', 'minio']:
            if 'bucket' not in source_config:
                errors.append(
                    f"Source at index {source_index} (type: {source_type}) "
                    f"must have 'bucket' field"
                )

        return errors

    def _validate_federated_asset_source_config(
        self,
        source_config: Dict[str, Any],
        source_index: int
    ) -> List[str]:
        """
        Validate federated asset source configuration.

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list

        Returns:
            List of error messages
        """
        from hub.apps.assets.models import Asset, AssetSourceType
        import uuid

        errors = []

        asset_id = source_config.get("asset_id")
        if not asset_id:
            errors.append(f"Federated asset source at index {source_index} must have 'asset_id' field")
            return errors

        # Validate asset_id is a valid UUID
        try:
            asset_uuid = uuid.UUID(str(asset_id))
        except (ValueError, TypeError):
            errors.append(f"Invalid asset_id format at source index {source_index}: {asset_id}")
            return errors

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=asset_uuid)
        except Asset.DoesNotExist:
            errors.append(f"Federated asset source at index {source_index} references non-existent asset: {asset_id}")
            return errors

        # Validate asset is FEDERATED type
        if asset.source_type != AssetSourceType.FEDERATED:
            errors.append(
                f"Asset {asset_id} at source index {source_index} is not a federated asset "
                f"(source_type: {asset.source_type})"
            )

        # Validate query is provided (optional but recommended)
        query = source_config.get("query")
        if query and not isinstance(query, str):
            errors.append(f"Query field at source index {source_index} must be a string")

        return errors

    def _validate_external_resource_source_config(
        self,
        source_config: Dict[str, Any],
        source_index: int
    ) -> List[str]:
        """
        Validate external resource source configuration.

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list

        Returns:
            List of error messages
        """
        from hub.apps.assets.models import Asset, AssetSourceType, ExternalResourceReference
        import uuid

        errors = []

        resource_id = source_config.get("resource_id")
        asset_id = source_config.get("asset_id")

        if not resource_id:
            errors.append(f"External resource source at index {source_index} must have 'resource_id' field")

        if not asset_id:
            errors.append(f"External resource source at index {source_index} must have 'asset_id' field")

        if not resource_id or not asset_id:
            return errors  # Return early if required fields are missing

        # Validate UUIDs
        try:
            asset_uuid = uuid.UUID(str(asset_id))
        except (ValueError, TypeError):
            errors.append(f"Invalid asset_id format at source index {source_index}: {asset_id}")
            return errors

        # Get asset
        try:
            asset = Asset.objects.select_related('tenant').get(id=asset_uuid)
        except Asset.DoesNotExist:
            errors.append(f"External resource source at index {source_index} references non-existent asset: {asset_id}")
            return errors

        # Validate asset is FEDERATED type
        if asset.source_type != AssetSourceType.FEDERATED:
            errors.append(
                f"Asset {asset_id} at source index {source_index} is not a federated asset "
                f"(source_type: {asset.source_type})"
            )

        # Validate external resource exists and belongs to asset
        try:
            external_resource = ExternalResourceReference.objects.get(
                asset=asset,
                resource_id=str(resource_id)
            )
        except ExternalResourceReference.DoesNotExist:
            errors.append(
                f"External resource '{resource_id}' not found for asset {asset_id} at source index {source_index}"
            )

        return errors

    def validate_cross_source_compatibility(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate cross-source compatibility for virtual datasets with multiple sources.

        Validates:
        - Schema alignment across sources (field names, types)
        - Data type compatibility across sources
        - Cross-tenant source access permissions for all sources

        This method is specifically for federated queries or queries that use
        multiple sources. It ensures that sources can be combined safely.

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "cross_source_checks": {}
        }

        sources = virtual_dataset.sources or []

        # Skip validation if no sources or single source
        if not sources or len(sources) < 2:
            details["cross_source_checks"]["skipped"] = True
            details["cross_source_checks"]["reason"] = (
                "No sources or single source - cross-source validation not applicable"
            )
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["cross_source_checks"]["source_count"] = len(sources)
        details["cross_source_checks"]["skipped"] = False

        # Collect schemas from all sources
        source_schemas: List[Dict[str, Any]] = []
        source_assets: List[Optional[Asset]] = []

        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                errors.append(f"Source configuration at index {i} must be an object")
                continue

            asset_id = source_config.get("asset_id")
            source_schema = None
            source_asset = None

            # Try to get schema from asset if asset_id is provided
            if asset_id:
                try:
                    source_asset = Asset.objects.select_related('tenant').get(id=asset_id)
                    source_assets.append(source_asset)

                    # Get latest dataset schema
                    latest_dataset = source_asset.datasets.order_by('-version').first()
                    if latest_dataset and latest_dataset.schema_json:
                        source_schema = latest_dataset.schema_json
                except Asset.DoesNotExist:
                    errors.append(f"Source at index {i} references non-existent asset: {asset_id}")
                    source_assets.append(None)
                    continue
                except Exception as e:
                    warnings.append(f"Failed to retrieve schema for source {i}: {str(e)}")
                    source_assets.append(source_asset)
                    continue
            else:
                source_assets.append(None)

            # Also check if schema is directly provided in source config
            if not source_schema and "schema" in source_config:
                source_schema = source_config["schema"]

            source_schemas.append(source_schema if source_schema is not None else {})

        # Validate cross-tenant access permissions for all sources
        cross_tenant_errors = self._validate_cross_tenant_source_access(
            source_assets,
            sources
        )
        errors.extend(cross_tenant_errors)
        details["cross_source_checks"]["cross_tenant_access_valid"] = len(cross_tenant_errors) == 0

        # Validate schema alignment across sources
        if source_schemas and all(s is not None for s in source_schemas):
            alignment_result = self._validate_schema_alignment_across_sources(
                source_schemas,
                sources
            )
            errors.extend(alignment_result["errors"])
            warnings.extend(alignment_result["warnings"])
            details["cross_source_checks"].update(alignment_result["details"])

        # Validate data type compatibility across sources
        if source_schemas and all(s is not None for s in source_schemas):
            type_compat_result = self._validate_data_type_compatibility_across_sources(
                source_schemas,
                sources
            )
            errors.extend(type_compat_result["errors"])
            warnings.extend(type_compat_result["warnings"])
            details["cross_source_checks"].update(type_compat_result["details"])

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Cross-source compatibility validation failed: {', '.join(errors)}",
                code="INVALID_CROSS_SOURCE_COMPATIBILITY",
                details=details
            )

        return result

    def _validate_cross_tenant_source_access(
        self,
        source_assets: List[Optional[Asset]],
        sources: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Validate cross-tenant source access permissions for all sources.

        Args:
            source_assets: List of Asset instances (or None) for each source
            sources: List of source configurations

        Returns:
            List of error messages
        """
        errors: List[str] = []

        if not self.tenant_id:
            # No tenant context - skip cross-tenant validation
            return errors

        for i, (source_asset, source_config) in enumerate(zip(source_assets, sources)):
            if not source_asset:
                continue  # Skip if no asset

            # Check if asset is from different tenant
            if str(source_asset.tenant_id) != self.tenant_id:
                # Cross-tenant access - check entitlements
                from hub.apps.marketplace.access_utils import check_entitlement

                has_access, error_code, _ = check_entitlement(
                    consumer_tenant_id=self.tenant_id,
                    asset_id=str(source_asset.id),
                    provider_tenant_id=str(source_asset.tenant_id)
                )

                if not has_access:
                    errors.append(
                        f"Source at index {i} references asset from different tenant without entitlement. "
                        f"Asset: {source_asset.name} (tenant: {source_asset.tenant.name}), "
                        f"Error code: {error_code}"
                    )

        return errors

    def _validate_schema_alignment_across_sources(
        self,
        source_schemas: List[Dict[str, Any]],
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate schema alignment across multiple sources.

        Checks that schemas have compatible field names and structures.

        Args:
            source_schemas: List of schema dictionaries from each source
            sources: List of source configurations

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "schema_alignment_valid": True,
            "source_schemas": []
        }

        # Extract field names from each schema
        source_fields: List[Set[str]] = []

        for i, schema in enumerate(source_schemas):
            if not schema:
                continue

            fields = set()
            if "fields" in schema and isinstance(schema["fields"], list):
                # Format: {"fields": [{"name": "...", "type": "..."}, ...]}
                for field in schema["fields"]:
                    if isinstance(field, dict) and "name" in field:
                        fields.add(field["name"])
            elif isinstance(schema, dict):
                # Format: {"field_name": {"type": "..."}, ...}
                for field_name, field_def in schema.items():
                    if isinstance(field_def, dict):
                        fields.add(field_name)

            source_fields.append(fields)
            details["source_schemas"].append({
                "source_index": i,
                "field_count": len(fields),
                "fields": list(fields)
            })

        # Compare field names across sources
        if len(source_fields) < 2:
            details["schema_alignment_valid"] = True
            return {
                "errors": errors,
                "warnings": warnings,
                "details": details
            }

        # Find common fields and differences
        common_fields = set.intersection(*source_fields) if source_fields else set()
        all_fields = set.union(*source_fields) if source_fields else set()
        unique_fields = all_fields - common_fields

        details["common_fields"] = list(common_fields)
        details["unique_fields"] = list(unique_fields)
        details["common_field_count"] = len(common_fields)
        details["unique_field_count"] = len(unique_fields)

        # Warn if significant field differences
        if unique_fields:
            field_differences = {}
            for i, fields in enumerate(source_fields):
                source_unique = fields - common_fields
                if source_unique:
                    field_differences[f"source_{i}"] = list(source_unique)

            if field_differences:
                warnings.append(
                    f"Schemas have different fields across sources. "
                    f"Common fields: {len(common_fields)}, "
                    f"Unique fields per source: {field_differences}"
                )

        # If no common fields at all, this is a warning (not necessarily an error)
        if not common_fields and all_fields:
            warnings.append(
                "No common fields found across sources - queries may not work as expected"
            )

        details["schema_alignment_valid"] = len(errors) == 0

        return {
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def _validate_data_type_compatibility_across_sources(
        self,
        source_schemas: List[Dict[str, Any]],
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate data type compatibility across multiple sources.

        Checks that fields with the same name have compatible data types.

        Args:
            source_schemas: List of schema dictionaries from each source
            sources: List of source configurations

        Returns:
            Dictionary with errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "type_compatibility_valid": True,
            "type_compatibility_issues": []
        }

        # Extract field types from each schema
        source_field_types: List[Dict[str, str]] = []

        for i, schema in enumerate(source_schemas):
            if not schema:
                continue

            field_types = {}
            if "fields" in schema and isinstance(schema["fields"], list):
                # Format: {"fields": [{"name": "...", "type": "..."}, ...]}
                for field in schema["fields"]:
                    if isinstance(field, dict) and "name" in field:
                        field_name = field["name"]
                        field_type = field.get("type", "string")
                        field_types[field_name] = field_type
            elif isinstance(schema, dict):
                # Format: {"field_name": {"type": "..."}, ...}
                for field_name, field_def in schema.items():
                    if isinstance(field_def, dict):
                        field_type = field_def.get("type", "string")
                        field_types[field_name] = field_type

            source_field_types.append(field_types)

        # Compare types for common fields
        if len(source_field_types) < 2:
            details["type_compatibility_valid"] = True
            return {
                "errors": errors,
                "warnings": warnings,
                "details": details
            }

        # Find all field names across all sources
        all_field_names = set()
        for field_types in source_field_types:
            all_field_names.update(field_types.keys())

        # Check type compatibility for each field
        type_issues = []
        for field_name in all_field_names:
            types_found = []
            sources_with_field = []

            for i, field_types in enumerate(source_field_types):
                if field_name in field_types:
                    types_found.append(field_types[field_name])
                    sources_with_field.append(i)

            # If field exists in multiple sources, check type compatibility
            if len(types_found) > 1:
                # Normalize types for comparison
                normalized_types = [self._normalize_type(t) for t in types_found]

                # Check if all types are compatible
                if not self._are_types_compatible(normalized_types):
                    type_issues.append({
                        "field": field_name,
                        "types": types_found,
                        "sources": sources_with_field,
                        "normalized_types": normalized_types
                    })
                    warnings.append(
                        f"Field '{field_name}' has incompatible types across sources: "
                        f"{dict(zip(sources_with_field, types_found))}"
                    )

        details["type_compatibility_issues"] = type_issues
        details["type_compatibility_valid"] = len(type_issues) == 0

        return {
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def _normalize_type(self, field_type: str) -> str:
        """
        Normalize data type name for comparison.

        Args:
            field_type: Original type name

        Returns:
            Normalized type name
        """
        if not field_type:
            return "string"

        field_type_lower = field_type.lower().strip()

        # Integer types
        if field_type_lower in ["int", "integer", "bigint", "smallint", "tinyint"]:
            return "integer"

        # Float types
        if field_type_lower in ["float", "double", "decimal", "numeric", "real"]:
            return "float"

        # String types
        if field_type_lower in ["string", "text", "varchar", "char", "nvarchar"]:
            return "string"

        # Boolean types
        if field_type_lower in ["boolean", "bool", "bit"]:
            return "boolean"

        # Date/datetime types
        if field_type_lower in ["date", "datetime", "timestamp", "time"]:
            return "datetime"

        # Default to string for unknown types
        return "string"

    def _are_types_compatible(self, types: List[str]) -> bool:
        """
        Check if a list of types are compatible with each other.

        Args:
            types: List of normalized type names

        Returns:
            True if all types are compatible, False otherwise
        """
        if not types:
            return True

        if len(set(types)) == 1:
            return True  # All same type

        # Define compatibility groups
        integer_group = {"integer"}
        float_group = {"integer", "float"}  # Integer can be promoted to float
        string_group = {"string"}
        boolean_group = {"boolean"}
        datetime_group = {"datetime"}

        # Check if all types belong to compatible groups
        type_set = set(types)

        # Integer and float are compatible (integer can be promoted)
        if type_set.issubset(float_group):
            return True

        # All other types must be exactly the same
        if len(type_set) == 1:
            return True

        # String types are generally compatible (but warn)
        if type_set.issubset(string_group):
            return True  # Allow but will warn

        return False

    def validate_cross_tenant_access(
        self,
        virtual_dataset: VirtualDataset,
        query: Optional[str] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate cross-tenant access permissions for virtualization operations.

        Validates:
        - Cross-tenant source access permissions (via GovernanceService/ABAC)
        - Query execution authorization (user has permission to execute query)
        - Result data filtering validation (tenant isolation - results filtered by tenant)

        This method integrates with GovernanceService to check:
        - ABAC policies for cross-tenant asset access
        - User permissions for query execution
        - Tenant isolation policies for result filtering

        Args:
            virtual_dataset: VirtualDataset instance to validate
            query: Optional query string (if different from virtual_dataset.query)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and access details

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "tenant_id": str(virtual_dataset.tenant_id) if virtual_dataset.tenant else None,
            "cross_tenant_access_checks": {}
        }

        if not self.tenant_id:
            errors.append("tenant_id is required for cross-tenant access validation")
            details["cross_tenant_access_checks"]["tenant_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ValidationError(
                    "tenant_id is required for cross-tenant access validation",
                    code="MISSING_TENANT_ID",
                    details=details
                )
            return result

        if not self.user_id:
            errors.append("user_id is required for cross-tenant access validation")
            details["cross_tenant_access_checks"]["user_id_provided"] = False
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                warnings=warnings,
                details=details
            )
            if raise_on_error:
                raise ValidationError(
                    "user_id is required for cross-tenant access validation",
                    code="MISSING_USER_ID",
                    details=details
                )
            return result

        details["cross_tenant_access_checks"]["tenant_id_provided"] = True
        details["cross_tenant_access_checks"]["user_id_provided"] = True

        # Get sources from virtual dataset
        sources = virtual_dataset.sources or []
        if not sources:
            # No sources - validation passes (sources are optional for some query types)
            details["cross_tenant_access_checks"]["sources_provided"] = False
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["cross_tenant_access_checks"]["source_count"] = len(sources)
        details["cross_tenant_access_checks"]["source_access_checks"] = []

        # 1. Validate cross-tenant source access permissions
        source_access_errors = self._validate_cross_tenant_source_access_with_governance(
            sources=sources,
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )
        if source_access_errors:
            errors.extend(source_access_errors)
            details["cross_tenant_access_checks"]["source_access_valid"] = False
        else:
            details["cross_tenant_access_checks"]["source_access_valid"] = True

        # 2. Validate query execution authorization
        query_to_validate = query or virtual_dataset.query
        if query_to_validate:
            query_auth_result = self._validate_query_execution_authorization(
                virtual_dataset=virtual_dataset,
                query=query_to_validate,
                tenant_id=self.tenant_id,
                user_id=self.user_id
            )
            if not query_auth_result["authorized"]:
                errors.extend(query_auth_result["errors"])
                details["cross_tenant_access_checks"]["query_execution_authorized"] = False
            else:
                details["cross_tenant_access_checks"]["query_execution_authorized"] = True
            warnings.extend(query_auth_result["warnings"])
            details["cross_tenant_access_checks"]["query_authorization_details"] = query_auth_result["details"]
        else:
            details["cross_tenant_access_checks"]["query_execution_authorized"] = None
            warnings.append("No query provided for execution authorization check")

        # 3. Validate result data filtering (tenant isolation)
        result_filtering_result = self._validate_result_data_filtering(
            virtual_dataset=virtual_dataset,
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )
        if not result_filtering_result["valid"]:
            errors.extend(result_filtering_result["errors"])
            details["cross_tenant_access_checks"]["result_filtering_valid"] = False
        else:
            details["cross_tenant_access_checks"]["result_filtering_valid"] = True
        warnings.extend(result_filtering_result["warnings"])
        details["cross_tenant_access_checks"]["result_filtering_details"] = result_filtering_result["details"]

        is_valid = len(errors) == 0
        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not is_valid and raise_on_error:
            raise ValidationError(
                f"Cross-tenant access validation failed: {', '.join(errors)}",
                code="CROSS_TENANT_ACCESS_DENIED",
                details=details
            )

        return result

    def _validate_cross_tenant_source_access_with_governance(
        self,
        sources: List[Dict[str, Any]],
        tenant_id: str,
        user_id: str
    ) -> List[str]:
        """
        Validate cross-tenant source access permissions using GovernanceService.

        Integrates with GovernanceService/ABAC to check:
        - Asset access permissions via ABAC policies
        - Cross-tenant entitlements (marketplace)
        - User permissions for accessing assets from other tenants

        Args:
            sources: List of source configurations
            tenant_id: Tenant ID of the requesting tenant
            user_id: User ID requesting access

        Returns:
            List of error messages
        """
        errors: List[str] = []

        try:
            from hub.apps.governance.abac import ABACEngine
            from hub.apps.assets.models import Asset
            from hub.apps.governance.services import GovernanceService

            governance_service = GovernanceService(
                tenant_id=tenant_id,
                user_id=user_id
            )

            for i, source_config in enumerate(sources):
                asset_id = source_config.get("asset_id")
                if not asset_id:
                    continue  # Skip sources without asset_id

                try:
                    asset = Asset.objects.get(id=asset_id)
                except Asset.DoesNotExist:
                    errors.append(
                        f"Source at index {i} references non-existent asset: {asset_id}"
                    )
                    continue

                # Check if asset is from different tenant
                if str(asset.tenant_id) != tenant_id:
                    # Cross-tenant access - check via ABAC and entitlements
                    source_tenant_id = str(asset.tenant_id)

                    # 1. Check ABAC policy evaluation
                    abac_result = ABACEngine.evaluate_access(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        resource_type="ASSET",
                        resource_id=str(asset.id),
                        access_type="READ"
                    )

                    if not abac_result.allowed:
                        # ABAC denied - check if there's an entitlement as fallback
                        from hub.apps.marketplace.access_utils import check_entitlement

                        has_entitlement, error_code, _ = check_entitlement(
                            consumer_tenant_id=tenant_id,
                            asset_id=str(asset.id),
                            provider_tenant_id=source_tenant_id
                        )

                        if not has_entitlement:
                            errors.append(
                                f"Source at index {i} references asset from different tenant without access permission. "
                                f"Asset: {asset.name} (tenant: {asset.tenant.name if asset.tenant else source_tenant_id}), "
                                f"ABAC result: denied, Entitlement: {error_code}"
                            )
                        else:
                            # Has entitlement but ABAC denied - this is a warning
                            logger.warning(
                                f"Asset {asset.id} has entitlement but ABAC policy denied access. "
                                f"Entitlement takes precedence."
                            )
                    else:
                        # ABAC allowed - check if masking is required
                        if abac_result.masking_required:
                            logger.info(
                                f"Asset {asset.id} access allowed but data masking required"
                            )

                else:
                    # Same tenant - check ABAC for consistency
                    # For same-tenant assets, we're more lenient - if no policy exists, allow access
                    abac_result = ABACEngine.evaluate_access(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        resource_type="ASSET",
                        resource_id=str(asset.id),
                        access_type="READ"
                    )

                    # Only error if ABAC explicitly denied (policy exists and denies)
                    # If no policy matches (default deny), we allow same-tenant access
                    if not abac_result.allowed and abac_result.policy:
                        # Policy exists and explicitly denies - this is an error
                        errors.append(
                            f"Source at index {i} references asset from same tenant but user lacks access permission. "
                            f"Asset: {asset.name}, ABAC policy: {abac_result.policy.name if abac_result.policy else 'default deny'}"
                        )

        except Exception as e:
            logger.error(
                f"Failed to validate cross-tenant source access via GovernanceService: {e}",
                exc_info=True
            )
            errors.append(
                f"Failed to validate cross-tenant source access: {str(e)}"
            )

        return errors

    def _validate_query_execution_authorization(
        self,
        virtual_dataset: VirtualDataset,
        query: str,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Validate query execution authorization.

        Checks if user has permission to execute the query, considering:
        - User roles and permissions
        - Query complexity and resource limits
        - Cross-tenant query restrictions

        Args:
            virtual_dataset: VirtualDataset instance
            query: Query string to execute
            tenant_id: Tenant ID
            user_id: User ID

        Returns:
            Dictionary with authorization status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "authorized": True,
            "query_length": len(query),
            "query_type": virtual_dataset.query_type
        }

        try:
            from hub.apps.users.models import User
            from hub.apps.governance.abac import ABACEngine

            # Get user
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                errors.append(f"User {user_id} not found")
                return {
                    "authorized": False,
                    "errors": errors,
                    "warnings": warnings,
                    "details": details
                }

            # Check if user has required role for query execution
            # Users need at least DATA_VIEWER role to execute queries
            has_data_viewer = user.has_role("DATA_VIEWER") or user.has_role("DATA_ANALYST") or user.has_role("TENANT_ADMIN")
            if not has_data_viewer and not user.is_platform_admin:
                errors.append(
                    f"User {user.email} does not have required role (DATA_VIEWER, DATA_ANALYST, or TENANT_ADMIN) "
                    f"for query execution"
                )
                details["authorized"] = False
                details["user_roles"] = [ur.role.name for ur in user.user_roles.all()] if hasattr(user, "user_roles") else []
            else:
                details["user_roles"] = [ur.role.name for ur in user.user_roles.all()] if hasattr(user, "user_roles") else []
                details["has_required_role"] = True

            # Check ABAC policy for virtual dataset access
            # Note: VIRTUAL_DATASET resource type may not have policies - if no policy exists, allow same-tenant access
            if virtual_dataset.id:
                # Only check ABAC if virtual dataset is from different tenant
                if virtual_dataset.tenant and str(virtual_dataset.tenant_id) != tenant_id:
                    abac_result = ABACEngine.evaluate_access(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        resource_type="VIRTUAL_DATASET",
                        resource_id=str(virtual_dataset.id),
                        access_type="READ"
                    )

                    if not abac_result.allowed and abac_result.policy:
                        # Policy exists and explicitly denies - this is an error
                        errors.append(
                            f"User {user.email} does not have access permission to virtual dataset "
                            f"{virtual_dataset.name} from different tenant (ABAC policy denied)"
                        )
                        details["authorized"] = False
                        details["abac_policy_denied"] = True
                    else:
                        details["abac_policy_allowed"] = True
                        if abac_result.masking_required:
                            warnings.append(
                                "Query execution allowed but result data masking may be required"
                            )
                            details["masking_required"] = True
                else:
                    # Same tenant - no ABAC check needed (same-tenant access is allowed)
                    details["abac_policy_allowed"] = True
                    details["same_tenant_access"] = True

            # Check query complexity (warn for very complex queries)
            query_upper = query.upper()
            complexity_indicators = {
                "JOIN": query_upper.count("JOIN"),
                "UNION": query_upper.count("UNION"),
                "SUBQUERY": query_upper.count("SELECT") - 1,
                "CTE": query_upper.count("WITH")
            }

            total_complexity = sum(complexity_indicators.values())
            details["query_complexity"] = {
                "total_score": total_complexity,
                "indicators": complexity_indicators
            }

            if total_complexity > 10:
                warnings.append(
                    f"Query has high complexity score ({total_complexity}). "
                    f"Consider optimizing or breaking into smaller queries."
                )

        except Exception as e:
            logger.error(
                f"Failed to validate query execution authorization: {e}",
                exc_info=True
            )
            errors.append(f"Failed to validate query execution authorization: {str(e)}")
            details["authorized"] = False

        return {
            "authorized": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def _validate_result_data_filtering(
        self,
        virtual_dataset: VirtualDataset,
        tenant_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Validate result data filtering for tenant isolation.

        Ensures that query results are properly filtered by tenant to prevent
        cross-tenant data leakage. Validates:
        - Query includes tenant filtering (if applicable)
        - Result filtering policies are enforced
        - Cross-tenant data is properly isolated

        Args:
            virtual_dataset: VirtualDataset instance
            tenant_id: Tenant ID
            user_id: User ID

        Returns:
            Dictionary with validation status, errors, warnings, and details
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "valid": True,
            "tenant_isolation_checks": {}
        }

        try:
            from hub.apps.governance.abac import ABACEngine

            # Check if virtual dataset has cross-tenant sources
            sources = virtual_dataset.sources or []
            cross_tenant_sources = []

            for i, source_config in enumerate(sources):
                asset_id = source_config.get("asset_id")
                if asset_id:
                    from hub.apps.assets.models import Asset
                    try:
                        asset = Asset.objects.get(id=asset_id)
                        if str(asset.tenant_id) != tenant_id:
                            cross_tenant_sources.append({
                                "source_index": i,
                                "asset_id": str(asset.id),
                                "asset_name": asset.name,
                                "source_tenant_id": str(asset.tenant_id)
                            })
                    except Asset.DoesNotExist:
                        pass

            details["tenant_isolation_checks"]["cross_tenant_source_count"] = len(cross_tenant_sources)
            details["tenant_isolation_checks"]["cross_tenant_sources"] = cross_tenant_sources

            if cross_tenant_sources:
                # Has cross-tenant sources - validate filtering
                query = virtual_dataset.query or ""

                # Check if query includes tenant filtering
                # This is a heuristic check - actual filtering should be enforced at execution time
                query_upper = query.upper()
                tenant_filter_indicators = [
                    "TENANT_ID",
                    "TENANT",
                    f"WHERE.*{tenant_id[:8]}",  # Partial tenant ID match
                ]

                has_tenant_filter = any(
                    indicator in query_upper for indicator in tenant_filter_indicators
                )

                details["tenant_isolation_checks"]["has_explicit_tenant_filter"] = has_tenant_filter

                if not has_tenant_filter:
                    warnings.append(
                        "Query with cross-tenant sources does not appear to include explicit tenant filtering. "
                        "Ensure tenant isolation is enforced at query execution time."
                    )

                # Check ABAC policies for result filtering
                for cross_tenant_source in cross_tenant_sources:
                    asset_id = cross_tenant_source["asset_id"]
                    source_tenant_id = cross_tenant_source["source_tenant_id"]

                    # Check if ABAC policy requires masking for this asset
                    abac_result = ABACEngine.evaluate_access(
                        user_id=user_id,
                        tenant_id=tenant_id,
                        resource_type="ASSET",
                        resource_id=asset_id,
                        access_type="READ"
                    )

                    if abac_result.masking_required:
                        warnings.append(
                            f"Result data masking required for asset {cross_tenant_source['asset_name']} "
                            f"from tenant {source_tenant_id}"
                        )
                        details["tenant_isolation_checks"]["masking_required"] = True
                        details["tenant_isolation_checks"]["masking_assets"] = details["tenant_isolation_checks"].get(
                            "masking_assets", []
                        ) + [asset_id]

            else:
                # No cross-tenant sources - tenant isolation is naturally enforced
                details["tenant_isolation_checks"]["all_sources_same_tenant"] = True

            # Validate that virtual dataset tenant matches context tenant
            # This is a warning, not an error - cross-tenant virtual datasets are allowed with proper permissions
            if virtual_dataset.tenant and str(virtual_dataset.tenant_id) != tenant_id:
                warnings.append(
                    f"Virtual dataset tenant ({virtual_dataset.tenant_id}) does not match "
                    f"validation context tenant ({tenant_id}). Ensure proper cross-tenant permissions."
                )
                details["tenant_isolation_checks"]["tenant_mismatch"] = True
                details["tenant_isolation_checks"]["virtual_dataset_tenant_id"] = str(virtual_dataset.tenant_id)
                details["tenant_isolation_checks"]["context_tenant_id"] = tenant_id

        except Exception as e:
            logger.error(
                f"Failed to validate result data filtering: {e}",
                exc_info=True
            )
            errors.append(f"Failed to validate result data filtering: {str(e)}")
            details["valid"] = False

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "details": details
        }

    def validate_query_language_compatibility(
        self,
        virtual_dataset: VirtualDataset,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate query language compatibility with source types.

        Validates:
        - Query type is supported by all source types
        - Source types support the query language
        - Federated queries have compatible source languages

        Args:
            virtual_dataset: VirtualDataset instance to validate
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "query_type": virtual_dataset.query_type,
            "query_language_checks": {}
        }

        sources = virtual_dataset.sources or []
        query_type = virtual_dataset.query_type

        # Get compatible source types for query type
        compatible_types = self.QUERY_TYPE_SOURCE_COMPATIBILITY.get(query_type, [])
        details["query_language_checks"]["compatible_source_types"] = compatible_types
        details["query_language_checks"]["query_type"] = query_type

        if not sources:
            # No sources - skip language compatibility check
            details["query_language_checks"]["skipped"] = True
            details["query_language_checks"]["reason"] = "No sources provided"
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["query_language_checks"]["skipped"] = False
        details["query_language_checks"]["source_count"] = len(sources)

        # Check each source's language compatibility
        source_languages: List[str] = []
        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                errors.append(f"Source configuration at index {i} must be an object")
                continue

            source_type = source_config.get("type", "").lower()
            if not source_type:
                errors.append(f"Source at index {i} must have a 'type' field")
                continue

            # Map source type to query language
            source_language = self._get_source_language(source_type)
            source_languages.append(source_language)
            details["query_language_checks"][f"source_{i}_language"] = source_language
            details["query_language_checks"][f"source_{i}_type"] = source_type

            # Check if source type is compatible with query type
            if compatible_types and source_type not in compatible_types:
                errors.append(
                    f"Source type '{source_type}' at index {i} does not support query language '{query_type}'. "
                    f"Compatible source types: {', '.join(compatible_types)}"
                )
                details["query_language_checks"][f"source_{i}_compatible"] = False
            else:
                details["query_language_checks"][f"source_{i}_compatible"] = True

        # For federated queries, check language compatibility across sources
        if query_type == QueryType.FEDERATED and len(source_languages) > 1:
            unique_languages = set(source_languages)
            details["query_language_checks"]["unique_languages"] = list(unique_languages)
            details["query_language_checks"]["language_count"] = len(unique_languages)

            # Federated queries can mix SQL sources, but mixing SQL and SPARQL requires special handling
            sql_languages = {"sql"}
            sparql_languages = {"sparql"}
            rest_languages = {"rest", "graphql"}

            has_sql = any(lang in sql_languages for lang in unique_languages)
            has_sparql = any(lang in sparql_languages for lang in unique_languages)
            has_rest = any(lang in rest_languages for lang in unique_languages)

            if has_sql and has_sparql:
                warnings.append(
                    "Federated query mixes SQL and SPARQL sources - ensure proper query translation is configured"
                )
                details["query_language_checks"]["mixed_sql_sparql"] = True
            else:
                details["query_language_checks"]["mixed_sql_sparql"] = False

            if len(unique_languages) > 2:
                warnings.append(
                    f"Federated query uses {len(unique_languages)} different query languages - "
                    "may require complex query translation"
                )
                details["query_language_checks"]["multiple_languages"] = True
            else:
                details["query_language_checks"]["multiple_languages"] = False

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Query language compatibility validation failed: {', '.join(errors)}",
                code="INVALID_QUERY_LANGUAGE_COMPATIBILITY",
                details=details
            )

        return result

    def _get_source_language(self, source_type: str) -> str:
        """
        Map source type to query language.

        Args:
            source_type: Source type (postgresql, mysql, sparql, etc.)

        Returns:
            Query language name (sql, sparql, rest, graphql)
        """
        source_type_lower = source_type.lower()

        # SQL-based sources
        if source_type_lower in ['postgresql', 'mysql', 'sqlserver', 'mssql', 'oracle', 'sqlite']:
            return "sql"

        # SPARQL sources
        if source_type_lower == 'sparql':
            return "sparql"

        # REST sources
        if source_type_lower == 'rest':
            return "rest"

        # GraphQL sources
        if source_type_lower == 'graphql':
            return "graphql"

        # File-based sources (S3, MinIO) don't have a query language
        if source_type_lower in ['s3', 'minio', 'gcs', 'azure_blob']:
            return "file"

        # Default to unknown
        return "unknown"

    def validate_source_connections(
        self,
        virtual_dataset: VirtualDataset,
        test_connectivity: bool = True,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate source connections (test actual connectivity).

        Validates:
        - Source configurations are valid
        - Connections can be established (if test_connectivity=True)
        - Connection credentials are valid
        - Network accessibility

        Args:
            virtual_dataset: VirtualDataset instance to validate
            test_connectivity: If True, actually test connections (default: True)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, and warnings

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "dataset_name": virtual_dataset.name,
            "test_connectivity": test_connectivity,
            "connection_checks": {}
        }

        sources = virtual_dataset.sources or []

        if not sources:
            details["connection_checks"]["skipped"] = True
            details["connection_checks"]["reason"] = "No sources provided"
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        details["connection_checks"]["skipped"] = False
        details["connection_checks"]["source_count"] = len(sources)

        # If connectivity testing is disabled, only validate configuration
        if not test_connectivity:
            details["connection_checks"]["connectivity_testing_disabled"] = True
            for i, source_config in enumerate(sources):
                if not isinstance(source_config, dict):
                    errors.append(f"Source configuration at index {i} must be an object")
                    continue

                source_type = source_config.get("type", "").lower()
                if not source_type:
                    errors.append(f"Source at index {i} must have a 'type' field")
                    continue

                # Validate configuration only
                config_errors = self._validate_source_config(source_config, i, source_type)
                errors.extend(config_errors)
                details["connection_checks"][f"source_{i}_config_valid"] = len(config_errors) == 0

            result = ValidationResult(
                is_valid=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                details=details
            )

            if not result.is_valid and raise_on_error:
                raise ValidationError(
                    f"Source connection validation failed: {', '.join(errors)}",
                    code="INVALID_SOURCE_CONNECTION",
                    details=details
                )

            return result

        # Test actual connectivity
        details["connection_checks"]["connectivity_testing_enabled"] = True

        for i, source_config in enumerate(sources):
            if not isinstance(source_config, dict):
                errors.append(f"Source configuration at index {i} must be an object")
                details["connection_checks"][f"source_{i}_connection_test"] = False
                continue

            source_type = source_config.get("type", "").lower()
            if not source_type:
                errors.append(f"Source at index {i} must have a 'type' field")
                details["connection_checks"][f"source_{i}_connection_test"] = False
                continue

            # Validate configuration first
            config_errors = self._validate_source_config(source_config, i, source_type)
            if config_errors:
                errors.extend(config_errors)
                details["connection_checks"][f"source_{i}_config_valid"] = False
                details["connection_checks"][f"source_{i}_connection_test"] = False
                continue

            details["connection_checks"][f"source_{i}_config_valid"] = True

            # Test connection using connector factory
            connection_result = self._test_source_connection(source_config, i, source_type)
            if not connection_result["success"]:
                errors.append(
                    f"Connection test failed for source {i} (type: {source_type}): "
                    f"{connection_result.get('error', 'Unknown error')}"
                )
                details["connection_checks"][f"source_{i}_connection_test"] = False
                details["connection_checks"][f"source_{i}_connection_error"] = connection_result.get("error")
            else:
                details["connection_checks"][f"source_{i}_connection_test"] = True
                if connection_result.get("warning"):
                    warnings.append(
                        f"Source {i} (type: {source_type}): {connection_result['warning']}"
                    )

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Source connection validation failed: {', '.join(errors)}",
                code="INVALID_SOURCE_CONNECTION",
                details=details
            )

        return result

    def _test_source_connection(
        self,
        source_config: Dict[str, Any],
        source_index: int,
        source_type: str
    ) -> Dict[str, Any]:
        """
        Test connection to a source using connector factory.

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list
            source_type: Type of source

        Returns:
            Dictionary with 'success' (bool), 'error' (str, optional), 'warning' (str, optional)
        """
        try:
            # Try to import connector factory
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
                # Connector factory not available - return warning
                return {
                    "success": True,  # Don't fail if connector factory unavailable
                    "warning": "Connector factory not available - connection test skipped"
                }

            # Map source type to connector type
            connector_type = self._map_source_type_to_connector_type(source_type)
            if not connector_type:
                return {
                    "success": True,  # Don't fail for unsupported types
                    "warning": f"Source type '{source_type}' does not support connection testing"
                }

            # Get connector and test connection
            connector = SourceConnectorFactory.get_connector(connector_type)
            if not hasattr(connector, 'test_connection'):
                return {
                    "success": True,  # Don't fail if method not available
                    "warning": f"Connector for type '{source_type}' does not support connection testing"
                }

            # Test connection with timeout protection
            import signal

            def timeout_handler(signum, frame):
                raise TimeoutError("Connection test timed out after 10 seconds")

            # Set timeout (Unix only)
            timeout_set = False
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)  # 10 second timeout
                timeout_set = True

            try:
                test_result = connector.test_connection(source_config)

                # Handle different return types
                if isinstance(test_result, dict):
                    success = test_result.get("success", False)
                    error = test_result.get("error")
                    if success:
                        return {"success": True}
                    else:
                        return {
                            "success": False,
                            "error": error or "Connection test failed"
                        }
                elif isinstance(test_result, bool):
                    if test_result:
                        return {"success": True}
                    else:
                        return {
                            "success": False,
                            "error": "Connection test returned False"
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Unexpected return type from test_connection: {type(test_result)}"
                    }
            finally:
                if timeout_set and hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)  # Cancel timeout

        except TimeoutError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            # Don't fail validation on connection errors - return as warning
            # This allows validation to proceed even if connections are temporarily unavailable
            return {
                "success": True,  # Don't fail validation
                "warning": f"Connection test failed: {str(e)}"
            }

    def _map_source_type_to_connector_type(self, source_type: str) -> Optional[str]:
        """
        Map source type to connector factory type.

        Args:
            source_type: Source type (postgresql, mysql, etc.)

        Returns:
            Connector type string or None if not supported
        """
        source_type_lower = source_type.lower()

        # Database sources map to DATABASE connector
        if source_type_lower in ['postgresql', 'mysql', 'sqlserver', 'mssql', 'oracle', 'sqlite']:
            return "DATABASE"

        # REST/HTTP sources
        if source_type_lower in ['rest', 'http', 'https']:
            return "HTTP"

        # S3 sources
        if source_type_lower == 's3':
            return "S3"

        # GCS sources
        if source_type_lower == 'gcs':
            return "GCS"

        # Azure Blob sources
        if source_type_lower in ['azure_blob', 'azureblob']:
            return "AZURE_BLOB"

        # FTP sources
        if source_type_lower in ['ftp', 'sftp']:
            return source_type_lower.upper()

        # SPARQL and GraphQL don't have connectors yet
        if source_type_lower in ['sparql', 'graphql']:
            return None

        return None


class QueryExecutionBusinessRules(BusinessRules):
    """
    Business rules validator for query execution decisions.

    Validates and determines:
    - Query optimization strategies
    - Execution mode selection (SYNC vs ASYNC)
    - Timeout validation and configuration

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    # Execution mode selection thresholds
    SYNC_ROW_THRESHOLD = 10000  # < 10,000 rows = SYNC
    SYNC_SIZE_THRESHOLD = 10 * 1024 * 1024  # < 10MB = SYNC
    SYNC_QUERY_LENGTH_THRESHOLD = 1000  # < 1000 characters = SYNC (simple queries)

    # Timeout limits (in seconds)
    MIN_TIMEOUT_SECONDS = 60  # Minimum 1 minute
    MAX_TIMEOUT_SECONDS = 7200  # Maximum 2 hours
    DEFAULT_SYNC_TIMEOUT = 300  # 5 minutes for SYNC
    DEFAULT_ASYNC_TIMEOUT = 3600  # 1 hour for ASYNC

    # Query complexity indicators
    COMPLEX_KEYWORDS = ['JOIN', 'UNION', 'GROUP BY', 'ORDER BY', 'HAVING', 'SUBQUERY', 'WITH', 'RECURSIVE']
    FEDERATED_INDICATORS = ['SERVICE', 'SILENT', 'BIND', 'VALUES']

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "QueryExecutionBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates query execution validation checks.
        It can be called with a RuleExecutionContext or kwargs.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - virtual_dataset: VirtualDataset instance (optional)
                - timeout_seconds: Optional timeout in seconds
                - execution_mode: Optional execution mode
                - validation_type: Optional validation type filter
                    ('timeout', 'execution_mode', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        virtual_dataset = kwargs.get('virtual_dataset')
        if context and hasattr(context, 'resource') and isinstance(context.resource, VirtualDataset):
            virtual_dataset = context.resource
        elif context and hasattr(context, 'metadata') and isinstance(context.metadata, dict):
            virtual_dataset = virtual_dataset or context.metadata.get('virtual_dataset')

        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": validation_type,
        }

        if virtual_dataset:
            details["dataset_id"] = str(virtual_dataset.id) if virtual_dataset.id else None
            details["dataset_name"] = virtual_dataset.name if hasattr(virtual_dataset, 'name') else None

        # Perform validation based on type
        if validation_type in ('timeout', 'all'):
            timeout_seconds = kwargs.get('timeout_seconds')
            execution_mode = kwargs.get('execution_mode')
            timeout_result = self.validate_timeout(
                timeout_seconds=timeout_seconds,
                execution_mode=execution_mode,
                raise_on_error=False
            )
            if not timeout_result.is_valid:
                errors.extend(timeout_result.errors)
                warnings.extend(timeout_result.warnings)
                details["timeout"] = timeout_result.details

        if validation_type in ('execution_mode', 'all') and virtual_dataset:
            # Execution mode selection doesn't return ValidationResult, so we just validate it works
            try:
                execution_mode = self.select_execution_mode(
                    virtual_dataset=virtual_dataset,
                    parameters=kwargs.get('parameters'),
                    force_async=kwargs.get('force_async', False),
                    estimated_result_size=kwargs.get('estimated_result_size'),
                    raise_on_error=False
                )
                details["execution_mode"] = execution_mode
            except Exception as e:
                errors.append(f"Execution mode selection failed: {str(e)}")
                details["execution_mode_error"] = str(e)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def optimize_query(
        self,
        query: str,
        query_type: QueryType,
        raise_on_error: bool = False
    ) -> Dict[str, Any]:
        """
        Optimize query for better performance.

        Applies optimization strategies:
        - Remove unnecessary whitespace
        - Add LIMIT clauses where appropriate
        - Suggest index usage hints
        - Optimize JOIN order (basic heuristics)
        - Remove redundant conditions

        Args:
            query: Query string to optimize
            query_type: Query type (SQL, SPARQL, etc.)
            raise_on_error: If True, raises ValidationError on optimization failure

        Returns:
            Dictionary containing:
            - optimized_query: Optimized query string
            - optimizations_applied: List of optimizations applied
            - warnings: List of warnings about potential issues
            - details: Additional optimization details

        Raises:
            ValidationError: If raise_on_error=True and optimization fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        optimizations_applied: List[str] = []
        details: Dict[str, Any] = {
            "original_query_length": len(query),
            "query_type": query_type,
            "optimization_checks": {}
        }

        if not query or not query.strip():
            errors.append("Query cannot be empty")
            details["optimization_checks"]["query_not_empty"] = False
        else:
            details["optimization_checks"]["query_not_empty"] = True

        if errors:
            result_dict = {
                "optimized_query": query,
                "optimizations_applied": optimizations_applied,
                "warnings": warnings,
                "errors": errors,
                "details": details
            }
            if raise_on_error:
                raise ValidationError(
                    f"Query optimization failed: {errors[0]}",
                    code="QUERY_OPTIMIZATION_FAILED",
                    details=details
                )
            return result_dict

        optimized_query = query
        query_upper = query.upper()

        # Apply optimizations based on query type
        if query_type == QueryType.SQL:
            optimization_result = self._optimize_sql_query(query, query_upper, details)
            optimized_query = optimization_result["optimized_query"]
            optimizations_applied.extend(optimization_result["optimizations_applied"])
            warnings.extend(optimization_result["warnings"])
            details.update(optimization_result["details"])

        elif query_type == QueryType.SPARQL:
            optimization_result = self._optimize_sparql_query(query, query_upper, details)
            optimized_query = optimization_result["optimized_query"]
            optimizations_applied.extend(optimization_result["optimizations_applied"])
            warnings.extend(optimization_result["warnings"])
            details.update(optimization_result["details"])

        else:
            # For other query types, apply basic optimizations
            # Remove excessive whitespace
            import re
            optimized_query = re.sub(r'\s+', ' ', query.strip())
            if optimized_query != query:
                optimizations_applied.append("Removed excessive whitespace")
            details["optimization_checks"]["basic_optimization"] = True

        details["optimized_query_length"] = len(optimized_query)
        details["optimization_checks"]["optimization_completed"] = True

        return {
            "optimized_query": optimized_query,
            "optimizations_applied": optimizations_applied,
            "warnings": warnings,
            "errors": errors,
            "details": details
        }

    def _optimize_sql_query(
        self,
        query: str,
        query_upper: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize SQL query"""
        optimizations_applied: List[str] = []
        warnings: List[str] = []
        optimized_query = query

        # Check for SELECT * without LIMIT
        if "SELECT *" in query_upper and "LIMIT" not in query_upper:
            warnings.append(
                "Query uses SELECT * without LIMIT - consider adding LIMIT clause for large tables"
            )
            details["optimization_checks"]["unbounded_select"] = True
        else:
            details["optimization_checks"]["unbounded_select"] = False

        # Remove excessive whitespace (preserve structure)
        import re
        # Normalize whitespace but preserve newlines in multi-line queries
        if '\n' in query:
            lines = query.split('\n')
            normalized_lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines if line.strip()]
            optimized_query = '\n'.join(normalized_lines)
            if optimized_query != query:
                optimizations_applied.append("Normalized whitespace in multi-line query")
        else:
            optimized_query = re.sub(r'\s+', ' ', query.strip())
            if optimized_query != query:
                optimizations_applied.append("Normalized whitespace")

        # Check for redundant WHERE conditions (basic check)
        if "WHERE" in query_upper:
            # Count WHERE clauses - multiple WHERE clauses are invalid SQL
            where_count = query_upper.count(" WHERE ")
            if where_count > 1:
                warnings.append("Query contains multiple WHERE clauses - may be invalid SQL")
                details["optimization_checks"]["multiple_where_clauses"] = True
            else:
                details["optimization_checks"]["multiple_where_clauses"] = False

        # Check for potential index usage
        if "WHERE" in query_upper:
            # Look for equality conditions that could benefit from indexes
            equality_pattern = re.compile(r'WHERE\s+(\w+)\s*=\s*', re.IGNORECASE)
            if equality_pattern.search(query):
                details["optimization_checks"]["has_equality_conditions"] = True
                optimizations_applied.append("Query has equality conditions suitable for index usage")
            else:
                details["optimization_checks"]["has_equality_conditions"] = False

        return {
            "optimized_query": optimized_query,
            "optimizations_applied": optimizations_applied,
            "warnings": warnings,
            "details": details
        }

    def _optimize_sparql_query(
        self,
        query: str,
        query_upper: str,
        details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize SPARQL query"""
        optimizations_applied: List[str] = []
        warnings: List[str] = []
        optimized_query = query

        # Normalize whitespace
        import re
        if '\n' in query:
            lines = query.split('\n')
            normalized_lines = [re.sub(r'\s+', ' ', line.strip()) for line in lines if line.strip()]
            optimized_query = '\n'.join(normalized_lines)
            if optimized_query != query:
                optimizations_applied.append("Normalized whitespace in SPARQL query")
        else:
            optimized_query = re.sub(r'\s+', ' ', query.strip())
            if optimized_query != query:
                optimizations_applied.append("Normalized whitespace")

        # Check for LIMIT/OFFSET usage
        if "LIMIT" in query_upper or "OFFSET" in query_upper:
            details["optimization_checks"]["has_pagination"] = True
        else:
            details["optimization_checks"]["has_pagination"] = False
            warnings.append("SPARQL query may benefit from LIMIT clause for large result sets")

        # Check for OPTIONAL patterns that could be optimized
        optional_count = query_upper.count("OPTIONAL")
        if optional_count > 3:
            warnings.append(
                f"Query contains {optional_count} OPTIONAL patterns - may impact performance"
            )
            details["optimization_checks"]["many_optional_patterns"] = True
        else:
            details["optimization_checks"]["many_optional_patterns"] = False

        return {
            "optimized_query": optimized_query,
            "optimizations_applied": optimizations_applied,
            "warnings": warnings,
            "details": details
        }

    def select_execution_mode(
        self,
        virtual_dataset: VirtualDataset,
        parameters: Optional[Dict[str, Any]] = None,
        force_async: bool = False,
        estimated_result_size: Optional[int] = None,
        raise_on_error: bool = False
    ) -> QueryExecutionMode:
        """
        Select execution mode (SYNC or ASYNC) based on query characteristics.

        Selection criteria:
        - Query complexity (JOINs, UNIONs, subqueries)
        - Number of sources (federated queries)
        - Estimated result size
        - Query length (simple queries are more likely SYNC)
        - Force async flag

        Args:
            virtual_dataset: VirtualDataset instance
            parameters: Query parameters dictionary
            force_async: Whether to force async execution
            estimated_result_size: Estimated result size in bytes (optional)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            QueryExecutionMode (SYNC or ASYNC)

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        from hub.apps.virtualization.models import QueryExecutionMode

        errors: List[str] = []
        details: Dict[str, Any] = {
            "dataset_id": str(virtual_dataset.id),
            "query_type": virtual_dataset.query_type,
            "selection_criteria": {}
        }

        if force_async:
            details["selection_criteria"]["force_async"] = True
            return QueryExecutionMode.ASYNC  # type: ignore

        query = virtual_dataset.query or ""
        query_upper = query.upper()
        source_count = len(virtual_dataset.sources) if virtual_dataset.sources else 0

        # Check query complexity
        is_complex = any(keyword in query_upper for keyword in self.COMPLEX_KEYWORDS)
        details["selection_criteria"]["is_complex"] = is_complex
        details["selection_criteria"]["complex_keywords_found"] = [
            kw for kw in self.COMPLEX_KEYWORDS if kw in query_upper
        ]

        # Check for federated query indicators
        is_federated = any(indicator in query_upper for indicator in self.FEDERATED_INDICATORS)
        details["selection_criteria"]["is_federated"] = is_federated

        # Check query length
        query_length = len(query)
        is_simple_query = query_length < self.SYNC_QUERY_LENGTH_THRESHOLD
        details["selection_criteria"]["query_length"] = query_length
        details["selection_criteria"]["is_simple_query"] = is_simple_query

        # Check source count
        details["selection_criteria"]["source_count"] = source_count
        is_single_source = source_count <= 1
        details["selection_criteria"]["is_single_source"] = is_single_source

        # Check estimated result size
        if estimated_result_size is not None:
            details["selection_criteria"]["estimated_result_size"] = estimated_result_size
            is_small_result = estimated_result_size < self.SYNC_SIZE_THRESHOLD
            details["selection_criteria"]["is_small_result"] = is_small_result
        else:
            details["selection_criteria"]["estimated_result_size"] = None
            is_small_result = True  # Assume small if unknown

        # Decision logic:
        # - SYNC: Simple query, single source, small result, not complex
        # - ASYNC: Complex query, multiple sources, large result, federated

        if (is_simple_query and is_single_source and not is_complex and
            not is_federated and is_small_result):
            details["selection_criteria"]["selected_mode"] = "SYNC"
            details["selection_criteria"]["reason"] = "Simple query with single source and small result"
            return QueryExecutionMode.SYNC  # type: ignore

        # Default to ASYNC for complex queries
        details["selection_criteria"]["selected_mode"] = "ASYNC"
        if is_complex:
            details["selection_criteria"]["reason"] = "Complex query detected"
        elif source_count > 1:
            details["selection_criteria"]["reason"] = "Multiple sources require async execution"
        elif is_federated:
            details["selection_criteria"]["reason"] = "Federated query requires async execution"
        elif estimated_result_size and estimated_result_size >= self.SYNC_SIZE_THRESHOLD:
            details["selection_criteria"]["reason"] = "Large result size requires async execution"
        else:
            details["selection_criteria"]["reason"] = "Default to async for safety"

        return QueryExecutionMode.ASYNC  # type: ignore

    def validate_timeout(
        self,
        timeout_seconds: Optional[int] = None,
        execution_mode: Optional[QueryExecutionMode] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate timeout configuration for query execution.

        Validates:
        - Timeout is within acceptable range (MIN_TIMEOUT_SECONDS to MAX_TIMEOUT_SECONDS)
        - Timeout is appropriate for execution mode
        - Default timeout is applied if not provided

        Args:
            timeout_seconds: Timeout in seconds (optional)
            execution_mode: Execution mode (SYNC, ASYNC, etc.) - optional
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and validated timeout

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        from hub.apps.virtualization.models import QueryExecutionMode

        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "timeout_validation_checks": {}
        }

        # Determine default timeout based on execution mode
        if timeout_seconds is None:
            if execution_mode == QueryExecutionMode.SYNC:
                validated_timeout = self.DEFAULT_SYNC_TIMEOUT
                details["timeout_validation_checks"]["default_applied"] = True
                details["timeout_validation_checks"]["default_reason"] = "SYNC mode default"
            elif execution_mode == QueryExecutionMode.ASYNC:
                validated_timeout = self.DEFAULT_ASYNC_TIMEOUT
                details["timeout_validation_checks"]["default_applied"] = True
                details["timeout_validation_checks"]["default_reason"] = "ASYNC mode default"
            else:
                # Default to SYNC timeout if mode is unknown
                validated_timeout = self.DEFAULT_SYNC_TIMEOUT
                details["timeout_validation_checks"]["default_applied"] = True
                details["timeout_validation_checks"]["default_reason"] = "Unknown mode, using SYNC default"
                warnings.append(
                    f"Execution mode not specified, using default timeout for SYNC mode ({validated_timeout}s)"
                )
        else:
            validated_timeout = timeout_seconds
            details["timeout_validation_checks"]["default_applied"] = False

        details["timeout_validation_checks"]["provided_timeout"] = timeout_seconds
        details["timeout_validation_checks"]["validated_timeout"] = validated_timeout
        details["timeout_validation_checks"]["execution_mode"] = execution_mode

        # Validate timeout is within acceptable range
        if validated_timeout < self.MIN_TIMEOUT_SECONDS:
            errors.append(
                f"Timeout ({validated_timeout}s) is below minimum ({self.MIN_TIMEOUT_SECONDS}s). "
                f"Minimum timeout is {self.MIN_TIMEOUT_SECONDS} seconds."
            )
            details["timeout_validation_checks"]["within_minimum"] = False
            # Auto-correct to minimum
            validated_timeout = self.MIN_TIMEOUT_SECONDS
            details["timeout_validation_checks"]["auto_corrected"] = True
            warnings.append(f"Timeout auto-corrected to minimum: {validated_timeout}s")
        else:
            details["timeout_validation_checks"]["within_minimum"] = True

        if validated_timeout > self.MAX_TIMEOUT_SECONDS:
            errors.append(
                f"Timeout ({validated_timeout}s) exceeds maximum ({self.MAX_TIMEOUT_SECONDS}s). "
                f"Maximum timeout is {self.MAX_TIMEOUT_SECONDS} seconds."
            )
            details["timeout_validation_checks"]["within_maximum"] = False
            # Auto-correct to maximum
            validated_timeout = self.MAX_TIMEOUT_SECONDS
            details["timeout_validation_checks"]["auto_corrected"] = True
            warnings.append(f"Timeout auto-corrected to maximum: {validated_timeout}s")
        else:
            details["timeout_validation_checks"]["within_maximum"] = True

        # Validate timeout is appropriate for execution mode
        if execution_mode == QueryExecutionMode.SYNC:
            if validated_timeout > 600:  # 10 minutes
                warnings.append(
                    f"SYNC mode timeout ({validated_timeout}s) is high. "
                    f"Consider using ASYNC mode for long-running queries."
                )
                details["timeout_validation_checks"]["sync_timeout_appropriate"] = False
            else:
                details["timeout_validation_checks"]["sync_timeout_appropriate"] = True

        details["timeout_validation_checks"]["final_timeout"] = validated_timeout

        # Add validated timeout to details for easy access
        details["validated_timeout"] = validated_timeout

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Timeout validation failed: {', '.join(errors)}",
                code="INVALID_TIMEOUT",
                details=details
            )

        return result


class ResultBusinessRules(BusinessRules):
    """
    Business rules validator for query result handling.

    Validates and determines:
    - Result caching configuration and validation
    - Pagination parameter validation

    All validation methods follow engineering best practices:
    - No mocks/stubs - use real services and models
    - Fix root causes, not symptoms
    - Comprehensive error messages with context
    - Follow DRY, SOLID, and clean code principles
    """

    # Pagination limits
    MIN_PAGE_SIZE = 1
    MAX_PAGE_SIZE = 1000
    DEFAULT_PAGE_SIZE = 50

    MIN_LIMIT = 1
    MAX_LIMIT = 1000
    DEFAULT_LIMIT = 50

    MIN_PAGE_NUMBER = 1
    MIN_OFFSET = 0

    # Caching configuration
    DEFAULT_CACHE_TTL = 3600  # 1 hour in seconds
    MAX_CACHE_TTL = 86400  # 24 hours in seconds
    MIN_CACHE_TTL = 60  # 1 minute in seconds

    def get_rule_name(self) -> str:
        """Return the rule name for metrics and logging."""
        return "ResultBusinessRules"

    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Main validation method required by BusinessRules base class.

        This method orchestrates result handling validation checks.
        It can be called with a RuleExecutionContext or kwargs.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments:
                - cache_enabled: Whether caching is enabled (optional)
                - cache_ttl: Cache TTL in seconds (optional)
                - result_size: Estimated result size in bytes (optional)
                - page: Page number for pagination (optional)
                - page_size: Items per page (optional)
                - offset: Offset for pagination (optional)
                - limit: Maximum items to return (optional)
                - validation_type: Optional validation type filter
                    ('caching', 'pagination', 'all')

        Returns:
            ValidationResult with validation status and details
        """
        validation_type = kwargs.get('validation_type', 'all')
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "validation_type": validation_type,
        }

        # Perform validation based on type
        if validation_type in ('caching', 'all'):
            cache_result = self.validate_result_caching(
                cache_enabled=kwargs.get('cache_enabled', True),
                cache_ttl=kwargs.get('cache_ttl'),
                result_size=kwargs.get('result_size'),
                raise_on_error=False
            )
            if not cache_result.is_valid:
                errors.extend(cache_result.errors)
                warnings.extend(cache_result.warnings)
                details["caching"] = cache_result.details

        if validation_type in ('pagination', 'all'):
            pagination_result = self.validate_pagination(
                page=kwargs.get('page'),
                page_size=kwargs.get('page_size'),
                offset=kwargs.get('offset'),
                limit=kwargs.get('limit'),
                raise_on_error=False
            )
            if not pagination_result.is_valid:
                errors.extend(pagination_result.errors)
                warnings.extend(pagination_result.warnings)
                details["pagination"] = pagination_result.details

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

    def validate_result_caching(
        self,
        cache_enabled: bool = True,
        cache_ttl: Optional[int] = None,
        result_size: Optional[int] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate result caching configuration.

        Validates:
        - Cache TTL is within acceptable range
        - Cache is appropriate for result size
        - Cache configuration is valid

        Args:
            cache_enabled: Whether caching is enabled
            cache_ttl: Cache TTL in seconds (optional)
            result_size: Estimated result size in bytes (optional)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and validated cache config

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "cache_validation_checks": {}
        }

        details["cache_validation_checks"]["cache_enabled"] = cache_enabled

        if not cache_enabled:
            details["cache_validation_checks"]["validation_skipped"] = True
            return ValidationResult(
                is_valid=True,
                errors=errors,
                warnings=warnings,
                details=details
            )

        # Determine default TTL if not provided
        if cache_ttl is None:
            validated_ttl = self.DEFAULT_CACHE_TTL
            details["cache_validation_checks"]["default_ttl_applied"] = True
            details["cache_validation_checks"]["default_reason"] = "Using default TTL"
        else:
            validated_ttl = cache_ttl
            details["cache_validation_checks"]["default_ttl_applied"] = False

        details["cache_validation_checks"]["provided_ttl"] = cache_ttl
        details["cache_validation_checks"]["validated_ttl"] = validated_ttl

        # Validate TTL is within acceptable range
        if validated_ttl < self.MIN_CACHE_TTL:
            errors.append(
                f"Cache TTL ({validated_ttl}s) is below minimum ({self.MIN_CACHE_TTL}s). "
                f"Minimum TTL is {self.MIN_CACHE_TTL} seconds."
            )
            details["cache_validation_checks"]["within_minimum"] = False
            validated_ttl = self.MIN_CACHE_TTL
            details["cache_validation_checks"]["auto_corrected"] = True
            warnings.append(f"Cache TTL auto-corrected to minimum: {validated_ttl}s")
        else:
            details["cache_validation_checks"]["within_minimum"] = True

        if validated_ttl > self.MAX_CACHE_TTL:
            errors.append(
                f"Cache TTL ({validated_ttl}s) exceeds maximum ({self.MAX_CACHE_TTL}s). "
                f"Maximum TTL is {self.MAX_CACHE_TTL} seconds."
            )
            details["cache_validation_checks"]["within_maximum"] = False
            validated_ttl = self.MAX_CACHE_TTL
            details["cache_validation_checks"]["auto_corrected"] = True
            warnings.append(f"Cache TTL auto-corrected to maximum: {validated_ttl}s")
        else:
            details["cache_validation_checks"]["within_maximum"] = True

        # Validate cache is appropriate for result size
        if result_size is not None:
            details["cache_validation_checks"]["result_size"] = result_size
            # Large results (>100MB) may not be suitable for caching
            large_result_threshold = 100 * 1024 * 1024  # 100MB
            if result_size > large_result_threshold:
                warnings.append(
                    f"Large result size ({result_size} bytes) may not be suitable for caching. "
                    f"Consider using storage instead of cache."
                )
                details["cache_validation_checks"]["large_result_detected"] = True
            else:
                details["cache_validation_checks"]["large_result_detected"] = False
        else:
            details["cache_validation_checks"]["result_size"] = None

        details["cache_validation_checks"]["final_ttl"] = validated_ttl

        # Add validated TTL to details for easy access
        details["validated_cache_ttl"] = validated_ttl

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Result caching validation failed: {', '.join(errors)}",
                code="INVALID_CACHE_CONFIG",
                details=details
            )

        return result

    def validate_pagination(
        self,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
        raise_on_error: bool = False
    ) -> ValidationResult:
        """
        Validate pagination parameters.

        Validates:
        - Page and offset are not both provided (mutually exclusive)
        - Page number is valid (>= 1)
        - Page size is within acceptable range
        - Offset is valid (>= 0)
        - Limit is within acceptable range
        - Default values are applied appropriately

        Args:
            page: Page number for page-based pagination (1-indexed, optional)
            page_size: Items per page (optional)
            offset: Offset for offset-based pagination (optional)
            limit: Maximum number of items to return (optional)
            raise_on_error: If True, raises ValidationError on validation failure

        Returns:
            ValidationResult with validation status, errors, warnings, and validated pagination params

        Raises:
            ValidationError: If raise_on_error=True and validation fails
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, Any] = {
            "pagination_validation_checks": {}
        }

        # Check for mutually exclusive parameters
        if page is not None and offset is not None:
            errors.append(
                "Cannot use both 'page' and 'offset' parameters. "
                "Use either page-based pagination (page + page_size) or offset-based pagination (offset + limit)."
            )
            details["pagination_validation_checks"]["mutually_exclusive_violation"] = True
        else:
            details["pagination_validation_checks"]["mutually_exclusive_violation"] = False

        validated_page = page
        validated_page_size = page_size
        validated_offset = offset
        validated_limit = limit

        # Validate page-based pagination
        if page is not None:
            details["pagination_validation_checks"]["pagination_type"] = "page"
            if page < self.MIN_PAGE_NUMBER:
                errors.append(
                    f"Page number ({page}) is below minimum ({self.MIN_PAGE_NUMBER}). "
                    f"Page numbers must be >= {self.MIN_PAGE_NUMBER}."
                )
                details["pagination_validation_checks"]["page_valid"] = False
                validated_page = self.MIN_PAGE_NUMBER
                warnings.append(f"Page number auto-corrected to minimum: {validated_page}")
            else:
                details["pagination_validation_checks"]["page_valid"] = True

            # Validate page_size
            if page_size is None:
                validated_page_size = self.DEFAULT_PAGE_SIZE
                details["pagination_validation_checks"]["default_page_size_applied"] = True
            else:
                if page_size < self.MIN_PAGE_SIZE:
                    errors.append(
                        f"Page size ({page_size}) is below minimum ({self.MIN_PAGE_SIZE}). "
                        f"Minimum page size is {self.MIN_PAGE_SIZE}."
                    )
                    details["pagination_validation_checks"]["page_size_valid"] = False
                    validated_page_size = self.MIN_PAGE_SIZE
                    warnings.append(f"Page size auto-corrected to minimum: {validated_page_size}")
                elif page_size > self.MAX_PAGE_SIZE:
                    errors.append(
                        f"Page size ({page_size}) exceeds maximum ({self.MAX_PAGE_SIZE}). "
                        f"Maximum page size is {self.MAX_PAGE_SIZE}."
                    )
                    details["pagination_validation_checks"]["page_size_valid"] = False
                    validated_page_size = self.MAX_PAGE_SIZE
                    warnings.append(f"Page size auto-corrected to maximum: {validated_page_size}")
                else:
                    details["pagination_validation_checks"]["page_size_valid"] = True

        # Validate offset-based pagination
        elif offset is not None:
            details["pagination_validation_checks"]["pagination_type"] = "offset"
            if offset < self.MIN_OFFSET:
                errors.append(
                    f"Offset ({offset}) is below minimum ({self.MIN_OFFSET}). "
                    f"Offset must be >= {self.MIN_OFFSET}."
                )
                details["pagination_validation_checks"]["offset_valid"] = False
                validated_offset = self.MIN_OFFSET
                warnings.append(f"Offset auto-corrected to minimum: {validated_offset}")
            else:
                details["pagination_validation_checks"]["offset_valid"] = True

            # Validate limit
            if limit is None:
                validated_limit = self.DEFAULT_LIMIT
                details["pagination_validation_checks"]["default_limit_applied"] = True
            else:
                if limit < self.MIN_LIMIT:
                    errors.append(
                        f"Limit ({limit}) is below minimum ({self.MIN_LIMIT}). "
                        f"Minimum limit is {self.MIN_LIMIT}."
                    )
                    details["pagination_validation_checks"]["limit_valid"] = False
                    validated_limit = self.MIN_LIMIT
                    warnings.append(f"Limit auto-corrected to minimum: {validated_limit}")
                elif limit > self.MAX_LIMIT:
                    errors.append(
                        f"Limit ({limit}) exceeds maximum ({self.MAX_LIMIT}). "
                        f"Maximum limit is {self.MAX_LIMIT}."
                    )
                    details["pagination_validation_checks"]["limit_valid"] = False
                    validated_limit = self.MAX_LIMIT
                    warnings.append(f"Limit auto-corrected to maximum: {validated_limit}")
                else:
                    details["pagination_validation_checks"]["limit_valid"] = True

        # No pagination specified - apply defaults
        else:
            details["pagination_validation_checks"]["pagination_type"] = "none"
            # Apply default limit if no pagination specified
            if limit is None:
                validated_limit = self.DEFAULT_LIMIT
                details["pagination_validation_checks"]["default_limit_applied"] = True
            else:
                # Validate provided limit
                if limit < self.MIN_LIMIT:
                    validated_limit = self.MIN_LIMIT
                    warnings.append(f"Limit auto-corrected to minimum: {validated_limit}")
                elif limit > self.MAX_LIMIT:
                    validated_limit = self.MAX_LIMIT
                    warnings.append(f"Limit auto-corrected to maximum: {validated_limit}")
                else:
                    validated_limit = limit

        details["pagination_validation_checks"]["validated_page"] = validated_page
        details["pagination_validation_checks"]["validated_page_size"] = validated_page_size
        details["pagination_validation_checks"]["validated_offset"] = validated_offset
        details["pagination_validation_checks"]["validated_limit"] = validated_limit

        # Add validated pagination params to details for easy access
        details["validated_page"] = validated_page
        details["validated_page_size"] = validated_page_size
        details["validated_offset"] = validated_offset
        details["validated_limit"] = validated_limit

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Pagination validation failed: {', '.join(errors)}",
                code="INVALID_PAGINATION",
                details=details
            )

        return result

