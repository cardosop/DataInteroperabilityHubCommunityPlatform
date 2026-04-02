"""
Search Business Rules

Comprehensive business rules validation for search operations, including:
- Search query validation
- Search index validation
- Tenant and user context validation
- Search result validation

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import logging
import re
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass

from django.conf import settings
from django.contrib.postgres.search import SearchQuery

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import register_rule
from hub.apps.search.models import SearchIndex
from hub.apps.users.models import User

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant

logger = logging.getLogger(__name__)


@dataclass
class SearchRuleExecutionContext(RuleExecutionContext):
    """
    Extended execution context for search business rules.

    Adds search-specific context:
    - query: The search query string being validated
    - index: Optional search index instance
    - filters: Optional search filters dictionary
    - tenant: Optional tenant instance for validation
    - user: Optional user instance for permission validation
    """
    query: Optional[str] = None
    index: Optional[SearchIndex] = None
    filters: Optional[Dict[str, Any]] = None
    tenant: Optional[Any] = None  # Using Any to avoid circular import
    user: Optional[User] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        base_dict = super().to_dict()
        base_dict.update({
            'query_length': len(self.query) if self.query else None,
            'query_preview': self.query[:100] if self.query else None,
            'index_id': str(self.index.id) if self.index else None,
            'index_resource_type': self.index.resource_type if self.index else None,
            'index_resource_id': str(self.index.resource_id) if self.index else None,
            'filters': self.filters,
            'filter_count': len(self.filters) if self.filters else 0,
        })
        # Add tenant and user IDs from objects if provided
        if self.tenant:
            base_dict['tenant_id_from_object'] = str(self.tenant.id)
        if self.user:
            base_dict['user_id_from_object'] = str(self.user.id)
        return base_dict


@register_rule(
    rule_name="search_validation",
    description="Validates search queries, indexes, and search operations",
    tags=["search", "validation", "query", "index"],
    priority=10,
    enabled=True
)
class SearchBusinessRules(BusinessRules):
    """
    Business rules for search operations.

    Provides validation for:
    - Search query syntax and security
    - Search index integrity
    - Tenant and user access control
    - Search result validation
    """

    def validate(
        self,
        context: Optional[SearchRuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Validate search business rules.

        Args:
            context: Optional search rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            ValidationResult instance
        """
        result = ValidationResult(is_valid=True)

        # Create context if not provided
        if context is None:
            context = self.create_search_context(**kwargs)

        # Validate query if provided
        if context.query is not None:
            query_result = self._validate_query(context.query, context)
            result = result.combine(query_result)

        # Validate index if provided
        if context.index is not None:
            index_result = self._validate_index(context.index, context)
            result = result.combine(index_result)

        # Validate filters if provided
        if context.filters is not None:
            filters_result = self._validate_filters(context.filters, context)
            result = result.combine(filters_result)

        return result

    def create_search_context(
        self,
        query: Optional[str] = None,
        index: Optional[SearchIndex] = None,
        filters: Optional[Dict[str, Any]] = None,
        tenant: Optional[Any] = None,
        user: Optional[User] = None,
        resource: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SearchRuleExecutionContext:
        """
        Create search rule execution context.

        Args:
            query: Optional search query string
            index: Optional search index instance
            filters: Optional search filters dictionary
            tenant: Optional tenant instance
            user: Optional user instance
            resource: Optional resource being validated
            metadata: Optional additional metadata

        Returns:
            SearchRuleExecutionContext instance
        """
        return SearchRuleExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            resource=resource,
            metadata=metadata or {},
            query=query,
            index=index,
            filters=filters,
            tenant=tenant,
            user=user
        )

    def _validate_query(
        self,
        query: str,
        context: Optional[SearchRuleExecutionContext] = None
    ) -> ValidationResult:
        """
        Validate search query comprehensively.

        Performs validation for:
        - Query syntax (valid PostgreSQL tsquery syntax)
        - Query length (query length limits)
        - Query security (query doesn't access unauthorized data)
        - Query complexity (query complexity limits)

        Args:
            query: Search query string
            context: Optional search rule execution context

        Returns:
            ValidationResult with query validation status
        """
        result = ValidationResult(is_valid=True)

        # Empty/blank query is valid — it represents a filter-only search
        if not query or not query.strip():
            return result

        query_stripped = query.strip()

        # Perform all validation checks
        syntax_result = self._validate_query_syntax(query_stripped)
        result = result.combine(syntax_result)

        length_result = self._validate_query_length(query_stripped)
        result = result.combine(length_result)

        # Security check runs independently - we want to catch security issues even if syntax has errors
        security_result = self._validate_query_security(query_stripped, context)
        result = result.combine(security_result)

        complexity_result = self._validate_query_complexity(query_stripped)
        result = result.combine(complexity_result)

        return result

    def _validate_query_syntax(self, query: str) -> ValidationResult:
        """
        Validate search query syntax (valid PostgreSQL tsquery syntax).

        Checks:
        - Query can be parsed as PostgreSQL tsquery
        - Balanced parentheses
        - Valid operator usage

        Args:
            query: Search query string

        Returns:
            ValidationResult with syntax validation status
        """
        result = ValidationResult(is_valid=True)

        # Check for balanced parentheses
        open_parens = query.count('(')
        close_parens = query.count(')')
        if open_parens != close_parens:
            result.is_valid = False
            result.errors.append(
                f"Search query has unbalanced parentheses. "
                f"Open: {open_parens}, Close: {close_parens}"
            )
            result.details['open_parens'] = open_parens
            result.details['close_parens'] = close_parens

        # Check for invalid operator sequences
        # PostgreSQL tsquery operators: & (AND), | (OR), ! (NOT), <-> (FOLLOWED BY)
        # Operators cannot be at start/end or consecutive
        query_clean = query.strip()
        if query_clean.startswith(('&', '|', '!', '<->')):
            result.is_valid = False
            result.errors.append("Search query cannot start with an operator")
            result.details['invalid_start'] = True

        if query_clean.endswith(('&', '|', '!', '<->')):
            result.is_valid = False
            result.errors.append("Search query cannot end with an operator")
            result.details['invalid_end'] = True

        # Check for consecutive operators (except <-> which is valid)
        operator_pattern = r'[&|!]\s*[&|!]'
        if re.search(operator_pattern, query_clean):
            result.is_valid = False
            result.errors.append("Search query contains consecutive operators")
            result.details['consecutive_operators'] = True

        # Try to parse as PostgreSQL SearchQuery to validate syntax
        try:
            # PostgreSQL SearchQuery will raise an exception for invalid syntax
            SearchQuery(query, config='english')
        except Exception as e:
            # If syntax validation fails, add error but don't fail completely
            # (some queries might be valid but not parseable by SearchQuery)
            error_msg = str(e)
            if 'syntax error' in error_msg.lower() or 'invalid' in error_msg.lower():
                result.is_valid = False
                result.errors.append(f"Invalid search query syntax: {error_msg}")
                result.details['syntax_error'] = error_msg
            else:
                # Log but don't fail for other errors (might be configuration issues)
                logger.debug(f"SearchQuery parsing warning for query '{query[:50]}...': {e}")

        return result

    def _validate_query_length(self, query: str) -> ValidationResult:
        """
        Validate search query length (query length limits).

        Checks:
        - Query meets minimum length requirement
        - Query doesn't exceed maximum length limit

        Args:
            query: Search query string

        Returns:
            ValidationResult with length validation status
        """
        result = ValidationResult(is_valid=True)

        query_length = len(query)
        min_length = getattr(settings, 'SEARCH_QUERY_MIN_LENGTH', 1)
        max_length = getattr(settings, 'SEARCH_QUERY_MAX_LENGTH', 1000)

        if query_length < min_length:
            result.is_valid = False
            result.errors.append(
                f"Search query must be at least {min_length} character(s). "
                f"Current length: {query_length}"
            )
            result.details['query_length'] = query_length
            result.details['min_length'] = min_length

        if query_length > max_length:
            result.is_valid = False
            result.errors.append(
                f"Search query exceeds maximum length of {max_length} characters. "
                f"Current length: {query_length}"
            )
            result.details['query_length'] = query_length
            result.details['max_length'] = max_length

        return result

    def _validate_query_security(
        self,
        query: str,
        context: Optional[SearchRuleExecutionContext] = None
    ) -> ValidationResult:
        """
        Validate query security (query doesn't access unauthorized data).

        Checks:
        - Query doesn't contain SQL injection patterns
        - Query doesn't attempt to bypass tenant isolation
        - Query doesn't contain dangerous patterns

        Args:
            query: Search query string
            context: Optional search rule execution context

        Returns:
            ValidationResult with security validation status
        """
        result = ValidationResult(is_valid=True)

        # Check for potentially dangerous patterns (SQL injection, etc.)
        # Note: PostgreSQL full-text search is generally safe, but we check for obvious issues
        # Patterns that need literal matching (special characters)
        literal_patterns = [
            (';', 'Semicolons are not allowed in search queries'),
            ('--', 'SQL comments are not allowed in search queries'),
            ('/*', 'SQL block comments are not allowed in search queries'),
            ('*/', 'SQL block comment endings are not allowed in search queries'),
        ]

        # Patterns that need word boundary matching (SQL keywords)
        keyword_patterns = [
            ('DROP', 'DROP statements are not allowed in search queries'),
            ('DELETE', 'DELETE statements are not allowed in search queries'),
            ('UPDATE', 'UPDATE statements are not allowed in search queries'),
            ('INSERT', 'INSERT statements are not allowed in search queries'),
            ('ALTER', 'ALTER statements are not allowed in search queries'),
            ('CREATE', 'CREATE statements are not allowed in search queries'),
        ]

        # Check literal patterns (special characters)
        for pattern, message in literal_patterns:
            if pattern in query:
                result.is_valid = False
                result.errors.append(message)
                result.details['dangerous_pattern'] = pattern
                return result  # Return immediately on first dangerous pattern

        # Check keyword patterns (with word boundaries)
        query_upper = query.upper()
        for pattern, message in keyword_patterns:
            if re.search(rf'\b{pattern}\b', query_upper):
                result.is_valid = False
                result.errors.append(message)
                result.details['dangerous_pattern'] = pattern
                return result  # Return immediately on first dangerous pattern

        # Check for attempts to access tenant-specific data through query manipulation
        # This is more of a defensive check since tenant isolation is enforced at the service layer
        if context and context.tenant_id:
            # Check for UUID patterns that might be tenant IDs
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            uuids_in_query = re.findall(uuid_pattern, query, re.IGNORECASE)
            if uuids_in_query:
                # Log warning but don't fail - UUIDs might be legitimate search terms
                result.warnings.append(
                    f"Search query contains UUID-like patterns. "
                    f"Ensure tenant isolation is properly enforced."
                )
                result.details['uuids_found'] = len(uuids_in_query)

        return result

    def _validate_query_complexity(self, query: str) -> ValidationResult:
        """
        Validate query complexity (query complexity limits).

        Calculates complexity score based on:
        - Number of operators (&, |, !, <->)
        - Nesting depth (parentheses)
        - Number of terms

        Args:
            query: Search query string

        Returns:
            ValidationResult with complexity validation status
        """
        result = ValidationResult(is_valid=True)

        complexity_limit = getattr(settings, 'SEARCH_QUERY_COMPLEXITY_LIMIT', 50)

        # Calculate complexity score
        complexity_score = 0

        # Count operators (each operator adds to complexity)
        and_count = query.count('&')
        or_count = query.count('|')
        not_count = query.count('!')
        followed_by_count = query.count('<->')

        complexity_score += and_count * 1
        complexity_score += or_count * 1
        complexity_score += not_count * 2  # NOT is more complex
        complexity_score += followed_by_count * 3  # FOLLOWED BY is most complex

        # Calculate nesting depth (parentheses depth)
        max_depth = 0
        current_depth = 0
        for char in query:
            if char == '(':
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ')':
                current_depth -= 1
                if current_depth < 0:
                    # Unbalanced parentheses (should be caught by syntax validation)
                    break

        # Add depth penalty (exponential)
        complexity_score += max_depth * 5

        # Count terms (approximate - words separated by operators/whitespace)
        # Remove operators and parentheses, then count words
        terms_text = re.sub(r'[&|!()<>-]', ' ', query)
        terms = [t.strip() for t in terms_text.split() if t.strip()]
        term_count = len(terms)

        # Add term count (logarithmic scale)
        if term_count > 10:
            complexity_score += (term_count - 10) * 0.5

        result.details['complexity_score'] = complexity_score
        result.details['operator_count'] = and_count + or_count + not_count + followed_by_count
        result.details['max_depth'] = max_depth
        result.details['term_count'] = term_count

        # Check if complexity exceeds limit
        if complexity_score > complexity_limit:
            result.is_valid = False
            result.errors.append(
                f"Search query complexity ({complexity_score}) exceeds limit ({complexity_limit}). "
                f"Simplify your query by reducing operators, nesting depth, or terms."
            )
        elif complexity_score > complexity_limit * 0.8:
            # Warn if approaching limit
            result.warnings.append(
                f"Search query complexity ({complexity_score}) is approaching limit ({complexity_limit}). "
                f"Consider simplifying your query."
            )

        return result

    def _validate_index(
        self,
        index: SearchIndex,
        context: SearchRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate search index comprehensively.

        Performs validation for:
        - Index structure (valid index structure)
        - Index update (index updates correctly)
        - Index consistency (index consistent with data)

        Args:
            index: SearchIndex instance
            context: Search rule execution context

        Returns:
            ValidationResult with index validation status
        """
        result = ValidationResult(is_valid=True)

        # Perform all validation checks
        structure_result = self._validate_index_structure(index, context)
        result = result.combine(structure_result)

        update_result = self._validate_index_update(index)
        result = result.combine(update_result)

        # Consistency check runs independently - we want to catch consistency issues even if structure has errors
        consistency_result = self._validate_index_consistency(index, context)
        result = result.combine(consistency_result)

        return result

    def _validate_index_structure(
        self,
        index: SearchIndex,
        context: SearchRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate index structure (valid index structure).

        Checks:
        - Required fields are present
        - Field types are correct
        - Field values are valid
        - Tenant ownership is correct

        Args:
            index: SearchIndex instance
            context: Search rule execution context

        Returns:
            ValidationResult with structure validation status
        """
        result = ValidationResult(is_valid=True)

        # Check tenant access if tenant context is available
        if context.tenant_id:
            index_tenant_id = str(index.tenant_id) if index.tenant_id else None
            context_tenant_id = str(context.tenant_id) if context.tenant_id else None

            if index_tenant_id and context_tenant_id and index_tenant_id != context_tenant_id:
                result.is_valid = False
                result.errors.append(
                    f"Search index belongs to a different tenant. "
                    f"Index tenant: {index_tenant_id}, Context tenant: {context_tenant_id}"
                )
                result.details['index_tenant_id'] = index_tenant_id
                result.details['context_tenant_id'] = context_tenant_id

        # Check required fields
        if not index.tenant_id:
            result.is_valid = False
            result.errors.append("Search index must have a tenant")

        if not index.resource_type:
            result.is_valid = False
            result.errors.append("Search index must have a resource_type")
        else:
            # Validate resource_type is one of the allowed values
            valid_resource_types = ['CONTRACT', 'ASSET', 'DATASET', 'VIRTUAL_DATASET']
            if index.resource_type not in valid_resource_types:
                result.is_valid = False
                result.errors.append(
                    f"Search index has invalid resource_type '{index.resource_type}'. "
                    f"Valid types: {', '.join(valid_resource_types)}"
                )
                result.details['invalid_resource_type'] = index.resource_type

        if not index.resource_id:
            result.is_valid = False
            result.errors.append("Search index must have a resource_id")

        # Validate JSON fields structure
        if index.schema_fields is not None:
            if not isinstance(index.schema_fields, list):
                result.is_valid = False
                result.errors.append("Search index schema_fields must be a list")
            else:
                # Validate schema_fields items
                for i, field in enumerate(index.schema_fields):
                    if not isinstance(field, dict):
                        result.warnings.append(
                            f"Schema field at index {i} is not a dictionary"
                        )

        if index.lineage_metadata is not None:
            if not isinstance(index.lineage_metadata, dict):
                result.is_valid = False
                result.errors.append("Search index lineage_metadata must be a dictionary")

        if index.tags is not None:
            if not isinstance(index.tags, list):
                result.is_valid = False
                result.errors.append("Search index tags must be a list")
            else:
                # Validate tags are strings
                for i, tag in enumerate(index.tags):
                    if not isinstance(tag, str):
                        result.warnings.append(
                            f"Tag at index {i} is not a string"
                        )

        # Validate email format if owner_email is provided
        if index.owner_email:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_email(index.owner_email)
            except DjangoValidationError:
                result.is_valid = False
                result.errors.append(f"Search index has invalid owner_email format: {index.owner_email}")

        return result

    def _validate_index_update(self, index: SearchIndex) -> ValidationResult:
        """
        Validate index update (index updates correctly).

        Checks:
        - Timestamps are valid
        - Search vector is present (if expected)
        - Index metadata is up to date

        Args:
            index: SearchIndex instance

        Returns:
            ValidationResult with update validation status
        """
        result = ValidationResult(is_valid=True)

        # Check timestamps
        if index.created_at and index.indexed_at:
            # Allow for small timing differences (up to 5 seconds) due to auto_now/auto_now_add timing
            from datetime import timedelta
            time_diff = index.created_at - index.indexed_at
            if time_diff > timedelta(seconds=5):
                # Only fail if indexed_at is significantly before created_at (more than 5 seconds)
                result.is_valid = False
                result.errors.append(
                    f"Search index indexed_at ({index.indexed_at}) is significantly before created_at ({index.created_at}). "
                    f"Difference: {time_diff.total_seconds()} seconds"
                )
                result.details['timestamp_inconsistency'] = True

        # Check if search_vector is present (it's nullable but should be present for indexed items)
        # Note: We don't fail if it's None, but warn as it might indicate incomplete indexing
        if index.search_vector is None:
            result.warnings.append(
                "Search index search_vector is None. This may indicate incomplete indexing."
            )
            result.details['missing_search_vector'] = True

        # Check if index appears stale (indexed_at is very old compared to created_at)
        if index.created_at and index.indexed_at:
            from django.utils import timezone
            from datetime import timedelta

            # If indexed_at is more than 1 year older than created_at, it might be stale
            time_diff = index.indexed_at - index.created_at
            if time_diff > timedelta(days=365):
                result.warnings.append(
                    f"Search index appears stale. Indexed {time_diff.days} days after creation. "
                    f"Consider re-indexing."
                )
                result.details['potentially_stale'] = True

        return result

    def _validate_index_consistency(
        self,
        index: SearchIndex,
        context: SearchRuleExecutionContext
    ) -> ValidationResult:
        """
        Validate index consistency (index consistent with data).

        Checks:
        - Referenced resource exists
        - Resource belongs to correct tenant
        - Index data matches resource data (title, description, etc.)

        Args:
            index: SearchIndex instance
            context: Search rule execution context

        Returns:
            ValidationResult with consistency validation status
        """
        result = ValidationResult(is_valid=True)

        if not index.resource_type or not index.resource_id:
            # Skip consistency check if structure is invalid
            return result

        try:
            # Try to retrieve the actual resource
            resource = None
            resource_model = None

            if index.resource_type == 'CONTRACT':
                from hub.apps.contracts.models import Contract
                resource_model = Contract
                try:
                    resource = Contract.objects.get(id=index.resource_id)
                except Contract.DoesNotExist:
                    result.is_valid = False
                    result.errors.append(
                        f"Search index references non-existent Contract: {index.resource_id}"
                    )
                    result.details['resource_not_found'] = True
                    return result

            elif index.resource_type == 'ASSET':
                from hub.apps.assets.models import Asset
                resource_model = Asset
                try:
                    resource = Asset.objects.get(id=index.resource_id)
                except Asset.DoesNotExist:
                    result.is_valid = False
                    result.errors.append(
                        f"Search index references non-existent Asset: {index.resource_id}"
                    )
                    result.details['resource_not_found'] = True
                    return result

            elif index.resource_type == 'DATASET':
                from hub.apps.datasets.models import Dataset
                resource_model = Dataset
                try:
                    resource = Dataset.objects.get(id=index.resource_id)
                except Dataset.DoesNotExist:
                    result.is_valid = False
                    result.errors.append(
                        f"Search index references non-existent Dataset: {index.resource_id}"
                    )
                    result.details['resource_not_found'] = True
                    return result

            elif index.resource_type == 'VIRTUAL_DATASET':
                from hub.apps.virtualization.models import VirtualDataset
                resource_model = VirtualDataset
                try:
                    resource = VirtualDataset.objects.get(id=index.resource_id)
                except VirtualDataset.DoesNotExist:
                    result.is_valid = False
                    result.errors.append(
                        f"Search index references non-existent VirtualDataset: {index.resource_id}"
                    )
                    result.details['resource_not_found'] = True
                    return result

            if resource:
                # Check tenant consistency
                resource_tenant_id = str(resource.tenant_id) if hasattr(resource, 'tenant_id') and resource.tenant_id else None
                index_tenant_id = str(index.tenant_id) if index.tenant_id else None

                if resource_tenant_id and index_tenant_id and resource_tenant_id != index_tenant_id:
                    result.is_valid = False
                    result.errors.append(
                        f"Search index tenant ({index_tenant_id}) does not match resource tenant ({resource_tenant_id})"
                    )
                    result.details['tenant_mismatch'] = True
                    result.details['resource_tenant_id'] = resource_tenant_id
                    result.details['index_tenant_id'] = index_tenant_id

                # Check if resource was updated after index was last updated
                if hasattr(resource, 'updated_at') and resource.updated_at:
                    if index.indexed_at and resource.updated_at > index.indexed_at:
                        result.warnings.append(
                            f"Resource was updated ({resource.updated_at}) after index was last updated ({index.indexed_at}). "
                            f"Index may be stale and should be re-indexed."
                        )
                        result.details['stale_index'] = True
                        result.details['resource_updated_at'] = resource.updated_at.isoformat()
                        result.details['index_updated_at'] = index.indexed_at.isoformat()

        except Exception as e:
            # Log error but don't fail validation - might be a transient issue
            logger.warning(
                f"Error checking index consistency for {index.resource_type} {index.resource_id}: {e}",
                exc_info=True
            )
            result.warnings.append(
                f"Could not verify index consistency due to error: {str(e)}"
            )
            result.details['consistency_check_error'] = str(e)

        return result

    def _validate_filters(
        self,
        filters: Dict[str, Any],
        context: Optional[SearchRuleExecutionContext] = None
    ) -> ValidationResult:
        """
        Validate search filters comprehensively.

        This method orchestrates all filter validation checks:
        - Filter expression validation (valid filter expressions)
        - Filter security validation (filters don't bypass access control)
        - Filter performance validation (filters don't cause performance issues)

        Args:
            filters: Search filters dictionary
            context: Optional search rule execution context

        Returns:
            ValidationResult with filter validation status
        """
        result = ValidationResult(is_valid=True)

        # Check filters is a dictionary
        if not isinstance(filters, dict):
            result.is_valid = False
            result.errors.append("Search filters must be a dictionary")
            return result

        # Perform all filter validations
        expression_result = self._validate_filter_expressions(filters)
        result = result.combine(expression_result)

        security_result = self._validate_filter_security(filters, context)
        result = result.combine(security_result)

        performance_result = self._validate_filter_performance(filters)
        result = result.combine(performance_result)

        return result

    def _validate_filter_expressions(self, filters: Dict[str, Any]) -> ValidationResult:
        """
        Validate filter expressions (valid filter expressions).

        Checks:
        - Filter keys are valid
        - Filter values match expected types and formats
        - Filter values are within allowed values (for enums)

        Args:
            filters: Search filters dictionary

        Returns:
            ValidationResult with expression validation status
        """
        result = ValidationResult(is_valid=True)

        # Valid filter keys
        valid_filter_keys = {
            'resource_type',
            'classification',
            'owner_id',
            'tags',
            'domain',
            'quality_status',
            'compliance_status',
        }

        # Valid resource types (from SearchIndex model)
        valid_resource_types = {'CONTRACT', 'ASSET', 'DATASET', 'VIRTUAL_DATASET'}

        # Valid quality statuses (from SearchIndex model)
        valid_quality_statuses = {'PASS', 'WARN', 'FAIL', 'UNKNOWN'}

        # Valid compliance statuses (from SearchIndex model)
        valid_compliance_statuses = {'PASS', 'WARN', 'FAIL', 'UNKNOWN'}

        # Check filter keys
        for key in filters.keys():
            if key not in valid_filter_keys:
                result.warnings.append(
                    f"Unknown filter key '{key}'. Valid keys: {', '.join(sorted(valid_filter_keys))}"
                )

        # Validate resource_type
        if 'resource_type' in filters:
            resource_type = filters['resource_type']
            if not isinstance(resource_type, str):
                result.is_valid = False
                result.errors.append("Filter 'resource_type' must be a string")
            elif resource_type not in valid_resource_types:
                result.is_valid = False
                result.errors.append(
                    f"Invalid resource_type '{resource_type}'. "
                    f"Valid values: {', '.join(sorted(valid_resource_types))}"
                )

        # Validate classification (should be a string, no specific enum values)
        if 'classification' in filters:
            classification = filters['classification']
            if not isinstance(classification, str):
                result.is_valid = False
                result.errors.append("Filter 'classification' must be a string")
            elif not classification.strip():
                result.is_valid = False
                result.errors.append("Filter 'classification' cannot be empty")

        # Validate tags
        if 'tags' in filters:
            tags = filters['tags']
            if not isinstance(tags, list):
                result.is_valid = False
                result.errors.append("Filter 'tags' must be a list")
            else:
                # Validate each tag
                for i, tag in enumerate(tags):
                    if not isinstance(tag, str):
                        result.is_valid = False
                        result.errors.append(f"Filter 'tags[{i}]' must be a string")
                    elif not tag.strip():
                        result.is_valid = False
                        result.errors.append(f"Filter 'tags[{i}]' cannot be empty")

        # Validate owner_id
        if 'owner_id' in filters:
            owner_id = filters['owner_id']
            if not isinstance(owner_id, str):
                result.is_valid = False
                result.errors.append("Filter 'owner_id' must be a string (UUID)")
            else:
                # Validate UUID format
                uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                if not re.match(uuid_pattern, owner_id, re.IGNORECASE):
                    result.is_valid = False
                    result.errors.append(
                        f"Filter 'owner_id' must be a valid UUID format. Got: {owner_id[:20]}..."
                    )

        # Validate domain (should be a string)
        if 'domain' in filters:
            domain = filters['domain']
            if not isinstance(domain, str):
                result.is_valid = False
                result.errors.append("Filter 'domain' must be a string")
            elif not domain.strip():
                result.is_valid = False
                result.errors.append("Filter 'domain' cannot be empty")

        # Validate quality_status
        if 'quality_status' in filters:
            quality_status = filters['quality_status']
            if not isinstance(quality_status, str):
                result.is_valid = False
                result.errors.append("Filter 'quality_status' must be a string")
            elif quality_status not in valid_quality_statuses:
                result.is_valid = False
                result.errors.append(
                    f"Invalid quality_status '{quality_status}'. "
                    f"Valid values: {', '.join(sorted(valid_quality_statuses))}"
                )

        # Validate compliance_status
        if 'compliance_status' in filters:
            compliance_status = filters['compliance_status']
            if not isinstance(compliance_status, str):
                result.is_valid = False
                result.errors.append("Filter 'compliance_status' must be a string")
            elif compliance_status not in valid_compliance_statuses:
                result.is_valid = False
                result.errors.append(
                    f"Invalid compliance_status '{compliance_status}'. "
                    f"Valid values: {', '.join(sorted(valid_compliance_statuses))}"
                )

        return result

    def _validate_filter_security(
        self,
        filters: Dict[str, Any],
        context: Optional[SearchRuleExecutionContext] = None
    ) -> ValidationResult:
        """
        Validate filter security (filters don't bypass access control).

        Checks:
        - Filters don't contain tenant_id (tenant isolation is enforced at service layer)
        - owner_id belongs to the tenant (if context provides tenant)
        - Filters don't attempt to access unauthorized resources

        Args:
            filters: Search filters dictionary
            context: Optional search rule execution context

        Returns:
            ValidationResult with security validation status
        """
        result = ValidationResult(is_valid=True)

        # Check for tenant_id in filters (should not be allowed - tenant isolation is enforced at service layer)
        if 'tenant_id' in filters:
            result.is_valid = False
            result.errors.append(
                "Filter 'tenant_id' is not allowed. Tenant isolation is enforced automatically. "
                "Do not include tenant_id in filters."
            )
            result.details['security_violation'] = 'tenant_id_in_filter'

        # Validate owner_id belongs to tenant if context provides tenant
        if 'owner_id' in filters and context and context.tenant_id:
            owner_id = filters['owner_id']
            if isinstance(owner_id, str):
                try:
                    # Check if owner exists and belongs to tenant
                    owner = User.objects.get(id=owner_id, tenant_id=context.tenant_id)
                    # Owner exists and belongs to tenant - OK
                    result.details['owner_validated'] = True
                except User.DoesNotExist:
                    # Owner doesn't exist or doesn't belong to tenant
                    result.is_valid = False
                    result.errors.append(
                        f"Filter 'owner_id' ({owner_id}) does not exist or does not belong to tenant. "
                        f"Users can only filter by owners within their own tenant."
                    )
                    result.details['security_violation'] = 'invalid_owner_id'
                    result.details['owner_id'] = owner_id
                    result.details['tenant_id'] = context.tenant_id
                except Exception as e:
                    # Log unexpected errors but don't fail validation
                    logger.warning(
                        f"Error validating owner_id filter: {e}",
                        owner_id=owner_id,
                        tenant_id=context.tenant_id
                    )
                    result.warnings.append(
                        f"Could not validate owner_id filter: {str(e)}"
                    )

        # Check for attempts to filter by other tenant's resources
        # This is a defensive check - tenant isolation should be enforced at service layer
        if context and context.tenant_id:
            # Check if any filter values contain UUIDs that might be tenant IDs
            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
            for key, value in filters.items():
                if isinstance(value, str):
                    uuids_in_value = re.findall(uuid_pattern, value, re.IGNORECASE)
                    if uuids_in_value and key != 'owner_id':  # owner_id is validated separately
                        # Log warning but don't fail - these might be legitimate resource IDs
                        result.warnings.append(
                            f"Filter '{key}' contains UUID-like patterns. "
                            f"Ensure tenant isolation is properly enforced."
                        )
                        result.details['uuid_patterns_found'] = len(uuids_in_value)

        return result

    def _validate_filter_performance(self, filters: Dict[str, Any]) -> ValidationResult:
        """
        Validate filter performance (filters don't cause performance issues).

        Checks:
        - Filter count doesn't exceed limits
        - Tag count doesn't exceed limits
        - Filter combinations don't cause performance degradation

        Args:
            filters: Search filters dictionary

        Returns:
            ValidationResult with performance validation status
        """
        result = ValidationResult(is_valid=True)

        # Get performance limits from settings
        max_filter_count = getattr(settings, 'SEARCH_MAX_FILTER_COUNT', 10)
        max_tag_count = getattr(settings, 'SEARCH_MAX_TAG_COUNT', 20)

        # Check filter count
        filter_count = len(filters)
        result.details['filter_count'] = filter_count

        if filter_count > max_filter_count:
            result.is_valid = False
            result.errors.append(
                f"Too many filters ({filter_count}). Maximum allowed: {max_filter_count}. "
                f"Reduce the number of filters to improve performance."
            )
        elif filter_count > max_filter_count * 0.8:
            # Warn if approaching limit
            result.warnings.append(
                f"Filter count ({filter_count}) is approaching limit ({max_filter_count}). "
                f"Consider reducing the number of filters."
            )

        # Check tag count
        if 'tags' in filters:
            tags = filters['tags']
            if isinstance(tags, list):
                tag_count = len(tags)
                result.details['tag_count'] = tag_count

                if tag_count > max_tag_count:
                    result.is_valid = False
                    result.errors.append(
                        f"Too many tags in filter ({tag_count}). Maximum allowed: {max_tag_count}. "
                        f"Reduce the number of tags to improve performance."
                    )
                elif tag_count > max_tag_count * 0.8:
                    # Warn if approaching limit
                    result.warnings.append(
                        f"Tag count ({tag_count}) is approaching limit ({max_tag_count}). "
                        f"Consider reducing the number of tags."
                    )

        # Check for performance-impacting filter combinations
        # Multiple filters on non-indexed fields can cause performance issues
        # Note: Most filters are indexed, but we warn about combinations that might be slow
        performance_impacting_filters = {'domain', 'classification'}
        impacting_count = sum(1 for key in filters.keys() if key in performance_impacting_filters)

        if impacting_count > 2:
            result.warnings.append(
                f"Multiple filters on potentially non-indexed fields ({impacting_count}). "
                f"This may impact search performance. Consider using fewer filters."
            )
            result.details['performance_impacting_filters'] = impacting_count

        return result


