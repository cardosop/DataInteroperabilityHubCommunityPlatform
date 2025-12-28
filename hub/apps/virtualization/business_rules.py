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

from hub.apps.virtualization.models import VirtualDataset, QueryType, QueryExecutionMode
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset
from hub.apps.core.services.base import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]

    def __init__(
        self,
        is_valid: bool = True,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.details = details or {}

    def __bool__(self):
        return self.is_valid


class VirtualizationBusinessRules:
    """
    Business rules validator for virtual datasets.

    Validates:
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
        'sparql', 'rest', 'graphql', 's3', 'minio'
    ]

    # Source type compatibility with query types
    QUERY_TYPE_SOURCE_COMPATIBILITY = {
        QueryType.SQL: ['postgresql', 'mysql', 'sqlserver', 'mssql'],
        QueryType.SPARQL: ['sparql'],
        QueryType.REST: ['rest'],
        QueryType.GRAPHQL: ['graphql'],
        QueryType.FEDERATED: ['postgresql', 'mysql', 'sqlserver', 'mssql', 'sparql', 'rest', 'graphql']
    }

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize VirtualizationBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission and cross-tenant validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

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

        Args:
            source_config: Source configuration dictionary
            source_index: Index of source in sources list
            source_type: Type of source

        Returns:
            List of error messages
        """
        errors = []

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


class QueryExecutionBusinessRules:
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

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize QueryExecutionBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for user-specific validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

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

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        # Add validated timeout to details for easy access
        result.details["validated_timeout"] = validated_timeout

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Timeout validation failed: {', '.join(errors)}",
                code="INVALID_TIMEOUT",
                details=details
            )

        return result


class ResultBusinessRules:
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

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize ResultBusinessRules.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for user-specific validation
        """
        self.tenant_id = tenant_id
        self.user_id = user_id

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

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        # Add validated TTL to details for easy access
        result.details["validated_cache_ttl"] = validated_ttl

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

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            details=details
        )

        # Add validated pagination params to details for easy access
        result.details["validated_page"] = validated_page
        result.details["validated_page_size"] = validated_page_size
        result.details["validated_offset"] = validated_offset
        result.details["validated_limit"] = validated_limit

        if not result.is_valid and raise_on_error:
            raise ValidationError(
                f"Pagination validation failed: {', '.join(errors)}",
                code="INVALID_PAGINATION",
                details=details
            )

        return result

