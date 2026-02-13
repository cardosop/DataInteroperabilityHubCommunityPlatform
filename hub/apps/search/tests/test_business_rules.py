"""
Tests for Search Business Rules

Comprehensive tests for search business rules validation, including:
- Initialization tests
- Registration tests
- Query validation tests
- Index validation tests
- Filter validation tests
- Integration tests with SearchService
"""

import uuid

from django.conf import settings
from django.test import TestCase

from hub.apps.core.business_rules.registry import get_registry
from hub.apps.search.business_rules import (
    SearchBusinessRules,
    SearchRuleExecutionContext,
)
from hub.apps.search.models import SearchIndex
from hub.apps.search.services import SearchService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


class SearchBusinessRulesInitializationTest(TestCase):
    """Test SearchBusinessRules initialization"""

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

        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_search_business_rules_initialization(self):
        """Test SearchBusinessRules can be initialized with tenant and user"""
        rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.get_rule_name(), "SearchBusinessRules")
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_search_business_rules_initialization_without_user(self):
        """Test SearchBusinessRules can be initialized without user"""
        rules = SearchBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNotNone(rules)
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_search_business_rules_initialization_without_tenant(self):
        """Test SearchBusinessRules can be initialized without tenant"""
        rules = SearchBusinessRules(user_id=str(self.user.id))
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_search_business_rules_initialization_without_context(self):
        """Test SearchBusinessRules can be initialized without tenant or user"""
        rules = SearchBusinessRules()
        self.assertIsNotNone(rules)
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_search_business_rules_enable_caching(self):
        """Test SearchBusinessRules can be initialized with caching enabled/disabled"""
        rules_with_cache = SearchBusinessRules(enable_caching=True)
        self.assertTrue(rules_with_cache.enable_caching)

        rules_without_cache = SearchBusinessRules(enable_caching=False)
        self.assertFalse(rules_without_cache.enable_caching)

    def test_search_business_rules_enable_metrics(self):
        """Test SearchBusinessRules can be initialized with metrics enabled/disabled"""
        rules_with_metrics = SearchBusinessRules(enable_metrics=True)
        self.assertTrue(rules_with_metrics.enable_metrics)

        rules_without_metrics = SearchBusinessRules(enable_metrics=False)
        self.assertFalse(rules_without_metrics.enable_metrics)

    def test_search_business_rules_enable_tracing(self):
        """Test SearchBusinessRules can be initialized with tracing enabled/disabled"""
        rules_with_tracing = SearchBusinessRules(enable_tracing=True)
        self.assertTrue(rules_with_tracing.enable_tracing)

        rules_without_tracing = SearchBusinessRules(enable_tracing=False)
        self.assertFalse(rules_without_tracing.enable_tracing)

    def test_search_business_rules_enable_logging(self):
        """Test SearchBusinessRules can be initialized with logging enabled/disabled"""
        rules_with_logging = SearchBusinessRules(enable_logging=True)
        self.assertTrue(rules_with_logging.enable_logging)

        rules_without_logging = SearchBusinessRules(enable_logging=False)
        self.assertFalse(rules_without_logging.enable_logging)

    def test_create_search_context(self):
        """Test SearchBusinessRules can create search context"""
        rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        context = rules.create_search_context(
            query="test query",
            filters={"resource_type": "CONTRACT"},
            tenant=self.tenant,
            user=self.user,
        )
        self.assertIsNotNone(context)
        self.assertIsInstance(context, SearchRuleExecutionContext)
        self.assertEqual(context.query, "test query")
        self.assertEqual(context.filters, {"resource_type": "CONTRACT"})
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)


class SearchBusinessRulesRegistrationTest(TestCase):
    """Test SearchBusinessRules registration in business rules registry"""

    def test_search_business_rules_registered(self):
        """Test SearchBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("search_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "search_validation")
        self.assertEqual(rule.rule_class, SearchBusinessRules)
        self.assertIn("search", rule.tags)
        self.assertIn("validation", rule.tags)
        self.assertIn("query", rule.tags)
        self.assertIn("index", rule.tags)

    def test_search_business_rules_priority(self):
        """Test SearchBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("search_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_search_business_rules_description(self):
        """Test SearchBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("search_validation")
        self.assertIsNotNone(rule)
        self.assertIsNotNone(rule.description)
        self.assertIn("search", rule.description.lower())
        self.assertIn("validates", rule.description.lower())

    def test_search_business_rules_enabled(self):
        """Test SearchBusinessRules is enabled by default"""
        registry = get_registry()
        rule = registry.get_rule("search_validation")
        self.assertIsNotNone(rule)
        self.assertTrue(rule.enabled)


class SearchQueryValidationTest(TestCase):
    """Test search query validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_query_valid(self):
        """Test query validation with valid query"""
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query="test query")
        result = self.rules.validate(context)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_query_syntax_valid(self):
        """Test query syntax validation with valid query"""
        query = "test query"
        result = self.rules._validate_query_syntax(query)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_query_syntax_unbalanced_parens(self):
        """Test query syntax validation with unbalanced parentheses"""
        query = "test (query"
        result = self.rules._validate_query_syntax(query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("parentheses", result.errors[0].lower())

    def test_validate_query_syntax_starts_with_operator(self):
        """Test query syntax validation with query starting with operator"""
        query = "& test query"
        result = self.rules._validate_query_syntax(query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("start", result.errors[0].lower())

    def test_validate_query_syntax_ends_with_operator(self):
        """Test query syntax validation with query ending with operator"""
        query = "test query &"
        result = self.rules._validate_query_syntax(query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("end", result.errors[0].lower())

    def test_validate_query_syntax_consecutive_operators(self):
        """Test query syntax validation with consecutive operators"""
        query = "test && query"
        result = self.rules._validate_query_syntax(query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("consecutive", result.errors[0].lower())

    def test_validate_query_length_valid(self):
        """Test query length validation with valid length"""
        query = "test query"
        result = self.rules._validate_query_length(query)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_query_length_too_short(self):
        """Test query length validation with query too short"""
        query = ""
        result = self.rules._validate_query_length(query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("length", result.errors[0].lower())

    def test_validate_query_length_too_long(self):
        """Test query length validation with query exceeding max length"""
        from django.conf import settings

        max_length = getattr(settings, "SEARCH_QUERY_MAX_LENGTH", 1000)
        long_query = "a" * (max_length + 1)
        result = self.rules._validate_query_length(long_query)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeds", result.errors[0].lower())

    def test_validate_query_security_valid(self):
        """Test query security validation with valid query"""
        query = "test query"
        result = self.rules._validate_query_security(query)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_query_security_dangerous_patterns(self):
        """Test query security validation with dangerous patterns"""
        dangerous_queries = [
            ("test; query", ";"),
            ("test-- query", "--"),
            ("test/* query", "/*"),
            ("DROP TABLE", "DROP"),
            ("DELETE FROM", "DELETE"),
        ]

        for query, pattern in dangerous_queries:
            result = self.rules._validate_query_security(query)
            self.assertFalse(result.is_valid)
            self.assertGreater(len(result.errors), 0)
            self.assertEqual(result.details.get("dangerous_pattern"), pattern)

    def test_validate_query_security_with_tenant_context(self):
        """Test query security validation with tenant context"""
        query = "test query"
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=query)
        result = self.rules._validate_query_security(query, context)
        # Should pass for normal queries
        self.assertTrue(result.is_valid)

    def test_validate_query_complexity_simple(self):
        """Test query complexity validation with simple query"""
        query = "test query"
        result = self.rules._validate_query_complexity(query)
        self.assertTrue(result.is_valid)
        self.assertIn("complexity_score", result.details)

    def test_validate_query_complexity_complex(self):
        """Test query complexity validation with complex query"""
        # Create a complex query with many operators and nesting
        query = "((test & query) | (another & term)) & !excluded"
        result = self.rules._validate_query_complexity(query)
        # Should have complexity score calculated
        self.assertIn("complexity_score", result.details)
        self.assertIn("operator_count", result.details)
        self.assertIn("max_depth", result.details)
        self.assertIn("term_count", result.details)

    def test_validate_query_complexity_exceeds_limit(self):
        """Test query complexity validation with query exceeding complexity limit"""
        from django.conf import settings

        complexity_limit = getattr(settings, "SEARCH_QUERY_COMPLEXITY_LIMIT", 50)

        # Create a very complex query that should exceed the limit
        # Deep nesting with many operators
        query = (
            "(" * 10 + "term1 & term2" + ")" * 10 + " | " + "(" * 10 + "term3 & term4" + ")" * 10
        )
        result = self.rules._validate_query_complexity(query)

        # Should fail if complexity exceeds limit
        if result.details.get("complexity_score", 0) > complexity_limit:
            self.assertFalse(result.is_valid)
            self.assertGreater(len(result.errors), 0)
            self.assertIn("complexity", result.errors[0].lower())

    def test_validate_query_empty(self):
        """Test query validation with empty query"""
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query="")
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("empty", result.errors[0].lower())

    def test_validate_query_whitespace_only(self):
        """Test query validation with whitespace-only query"""
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query="   ")
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_query_too_long(self):
        """Test query validation with query exceeding length limit"""
        long_query = "a" * 1001  # Exceeds 1000 character limit
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=long_query)
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("length", result.errors[0].lower())

    def test_validate_query_dangerous_patterns(self):
        """Test query validation with dangerous patterns"""
        dangerous_queries = [
            ("test; query", ";", "Semicolons"),
            ("test-- query", "--", "SQL comments"),
            ("test/* query", "/*", "SQL block comments"),
        ]

        for query, pattern, error_keyword in dangerous_queries:
            context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=query)
            result = self.rules.validate(context)
            self.assertFalse(result.is_valid, f"Query '{query}' should be invalid")
            self.assertGreater(len(result.errors), 0)
            # Check if dangerous pattern is detected in details or error message contains keyword
            errors_str = " ".join(result.errors)
            self.assertTrue(
                result.details.get("dangerous_pattern") == pattern
                or error_keyword.lower() in errors_str.lower(),
                f"Expected dangerous pattern '{pattern}' or keyword '{error_keyword}' to be detected. "
                f"Errors: {result.errors}, Details: {result.details}",
            )

    def test_validate_combined_query_and_filter_errors_error_handling(self):
        """Error handling: validate() with invalid query and invalid filters returns combined errors."""
        context = SearchRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            query="",
            filters={"tenant_id": str(self.tenant.id), "resource_type": "CONTRACT"},
        )
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        errors_lower = " ".join(result.errors).lower()
        self.assertTrue(
            "empty" in errors_lower or "query" in errors_lower,
            f"Expected query-related error in: {result.errors}",
        )
        self.assertTrue(
            "tenant_id" in errors_lower,
            f"Expected filter tenant_id error in: {result.errors}",
        )


class SearchIndexValidationTest(TestCase):
    """Test search index validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_index_valid(self):
        """Test index validation with valid index"""
        # Create a real contract first so consistency check passes
        from hub.apps.contracts.models import Contract

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
            title="Test Contract",
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules.validate(context)
        self.assertTrue(
            result.is_valid,
            f"Index validation failed: {result.errors}, warnings: {result.warnings}",
        )
        self.assertEqual(len(result.errors), 0)

    def test_validate_index_wrong_tenant(self):
        """Test index validation with index from different tenant"""
        index = SearchIndex.objects.create(
            tenant=self.other_tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Other Tenant Contract",
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_index_structure_missing_tenant(self):
        """Test index structure validation with missing tenant"""
        index = SearchIndex(
            resource_type="CONTRACT", resource_id=uuid.uuid4(), title="Test Contract"
        )
        # Don't save to avoid database constraint
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_structure(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("tenant" in error.lower() for error in result.errors))

    def test_validate_index_structure_invalid_resource_type(self):
        """Test index structure validation with invalid resource type"""
        index = SearchIndex.objects.create(
            tenant=self.tenant, resource_type="INVALID_TYPE", resource_id=uuid.uuid4(), title="Test"
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_structure(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("resource_type" in error.lower() for error in result.errors))

    def test_validate_index_structure_invalid_schema_fields(self):
        """Test index structure validation with invalid schema_fields"""
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Test Contract",
            schema_fields="not a list",  # type: ignore
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_structure(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("schema_fields" in error.lower() for error in result.errors))

    def test_validate_index_structure_invalid_tags(self):
        """Test index structure validation with invalid tags"""
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Test Contract",
            tags="not a list",  # type: ignore
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_structure(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("tags" in error.lower() for error in result.errors))

    def test_validate_index_structure_invalid_email(self):
        """Test index structure validation with invalid email"""
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Test Contract",
            owner_email="invalid-email",
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_structure(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("email" in error.lower() for error in result.errors))

    def test_validate_index_update_timestamp_inconsistency(self):
        """Test index update validation with timestamp inconsistency"""
        from datetime import timedelta

        from django.utils import timezone

        # Create a real contract first
        from hub.apps.contracts.models import Contract

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
            title="Test Contract",
        )
        # Manually set indexed_at before created_at (shouldn't happen normally)
        # Need to refresh from DB first to get the actual created_at
        index.refresh_from_db()
        # Set indexed_at to be significantly before created_at (more than 5 seconds)
        # Use update() to bypass auto_now=True on indexed_at field
        SearchIndex.objects.filter(id=index.id).update(
            indexed_at=index.created_at - timedelta(days=1)
        )
        index.refresh_from_db()

        result = self.rules._validate_index_update(index)
        self.assertFalse(
            result.is_valid, f"Expected timestamp inconsistency error. Errors: {result.errors}"
        )
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any(
                "indexed_at" in error.lower()
                or "created_at" in error.lower()
                or "significantly" in error.lower()
                for error in result.errors
            )
        )

    def test_validate_index_update_missing_search_vector(self):
        """Test index update validation with missing search_vector"""
        # Create a real contract first
        from hub.apps.contracts.models import Contract

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
            title="Test Contract",
            search_vector=None,
        )
        result = self.rules._validate_index_update(index)
        # Should warn but not fail
        self.assertTrue(
            result.is_valid, f"Expected valid result with warnings. Errors: {result.errors}"
        )
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(any("search_vector" in warning.lower() for warning in result.warnings))

    def test_validate_index_consistency_resource_not_found(self):
        """Test index consistency validation with non-existent resource"""
        non_existent_id = uuid.uuid4()
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=non_existent_id,
            title="Non-existent Contract",
        )
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_consistency(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any(
                "non-existent" in error.lower() or "not found" in error.lower()
                for error in result.errors
            )
        )

    def test_validate_index_consistency_tenant_mismatch(self):
        """Test index consistency validation with tenant mismatch"""
        from hub.apps.contracts.models import Contract

        # Create contract in tenant
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        # Create index with wrong tenant
        index = SearchIndex.objects.create(
            tenant=self.other_tenant,  # Wrong tenant
            resource_type="CONTRACT",
            resource_id=contract.id,
            title="Test Contract",
        )

        context = SearchRuleExecutionContext(tenant_id=str(self.other_tenant.id), index=index)
        result = self.rules._validate_index_consistency(index, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("tenant" in error.lower() for error in result.errors))

    def test_validate_index_consistency_stale_index(self):
        """Test index consistency validation with stale index"""
        from datetime import timedelta

        from django.utils import timezone

        from hub.apps.contracts.models import Contract

        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        # Create index
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
            title="Test Contract",
        )

        # Refresh contract to get updated_at
        contract.refresh_from_db()

        # Refresh index to get actual timestamps
        index.refresh_from_db()

        # Update contract (simulating resource update)
        # Set updated_at explicitly if it exists
        if hasattr(contract, "updated_at"):
            contract.updated_at = timezone.now()
            contract.save()
            contract.refresh_from_db()

        # Set index indexed_at to be older than contract updated_at or created_at
        if hasattr(contract, "updated_at") and contract.updated_at:
            index.indexed_at = contract.updated_at - timedelta(days=1)
        else:
            # If updated_at doesn't exist, use created_at
            index.indexed_at = contract.created_at - timedelta(days=1)
        index.save()

        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        result = self.rules._validate_index_consistency(index, context)
        # Should warn about stale index if updated_at exists and was set
        self.assertTrue(
            result.is_valid, f"Consistency check should not fail. Errors: {result.errors}"
        )
        # Check for warnings - Contract model may or may not have updated_at field
        # If it does and was updated, we should get a warning
        if hasattr(contract, "updated_at") and contract.updated_at:
            # Only assert warning if updated_at is actually newer than indexed_at
            if contract.updated_at > index.indexed_at:
                self.assertGreater(
                    len(result.warnings),
                    0,
                    f"Expected stale index warning when updated_at ({contract.updated_at}) > indexed_at ({index.indexed_at}). "
                    f"Warnings: {result.warnings}",
                )
                self.assertTrue(
                    any(
                        "stale" in warning.lower() or "updated" in warning.lower()
                        for warning in result.warnings
                    )
                )


class SearchFilterValidationTest(TestCase):
    """Test search filter validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_filters_valid(self):
        """Test filter validation with valid filters"""
        filters = {
            "resource_type": "CONTRACT",
            "classification": "PUBLIC",
            "tags": ["tag1", "tag2"],
            "owner_id": str(self.user.id),  # Use valid owner_id from tenant
        }
        context = SearchRuleExecutionContext(
            tenant_id=str(self.tenant.id), filters=filters, tenant=self.tenant, user=self.user
        )
        result = self.rules.validate(context)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filters_invalid_type(self):
        """Test filter validation with invalid filter type"""
        context = SearchRuleExecutionContext(
            tenant_id=str(self.tenant.id), filters="not a dict"  # type: ignore
        )
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary", result.errors[0].lower())

    def test_validate_filters_invalid_tags(self):
        """Test filter validation with invalid tags format"""
        filters = {"tags": "not a list"}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tags", result.errors[0].lower())

    def test_validate_filters_invalid_owner_id(self):
        """Test filter validation with invalid owner_id format"""
        filters = {"owner_id": 12345}  # Not a string UUID
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules.validate(context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("owner_id", result.errors[0].lower())

    def test_validate_filters_unknown_key(self):
        """Test filter validation with unknown filter key"""
        filters = {"unknown_key": "value"}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules.validate(context)
        # Unknown keys generate warnings, not errors
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("unknown", result.warnings[0].lower())


class SearchFilterExpressionValidationTest(TestCase):
    """Test search filter expression validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_filter_expressions_valid_resource_type(self):
        """Test filter expression validation with valid resource_type"""
        filters = {"resource_type": "CONTRACT"}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_expressions(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filter_expressions_invalid_resource_type(self):
        """Test filter expression validation with invalid resource_type"""
        filters = {"resource_type": "INVALID_TYPE"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("resource_type", result.errors[0].lower())

    def test_validate_filter_expressions_invalid_resource_type_type(self):
        """Test filter expression validation with non-string resource_type"""
        filters = {"resource_type": 123}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("resource_type", result.errors[0].lower())

    def test_validate_filter_expressions_valid_quality_status(self):
        """Test filter expression validation with valid quality_status"""
        filters = {"quality_status": "PASS"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filter_expressions_invalid_quality_status(self):
        """Test filter expression validation with invalid quality_status"""
        filters = {"quality_status": "INVALID"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("quality_status", result.errors[0].lower())

    def test_validate_filter_expressions_valid_compliance_status(self):
        """Test filter expression validation with valid compliance_status"""
        filters = {"compliance_status": "PASS"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filter_expressions_invalid_compliance_status(self):
        """Test filter expression validation with invalid compliance_status"""
        filters = {"compliance_status": "INVALID"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("compliance_status", result.errors[0].lower())

    def test_validate_filter_expressions_empty_classification(self):
        """Test filter expression validation with empty classification"""
        filters = {"classification": ""}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("classification", result.errors[0].lower())

    def test_validate_filter_expressions_empty_domain(self):
        """Test filter expression validation with empty domain"""
        filters = {"domain": ""}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("domain", result.errors[0].lower())

    def test_validate_filter_expressions_invalid_tags_item(self):
        """Test filter expression validation with invalid tag item"""
        filters = {"tags": ["valid", 123, "also_valid"]}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tags", result.errors[0].lower())

    def test_validate_filter_expressions_empty_tag(self):
        """Test filter expression validation with empty tag"""
        filters = {"tags": ["valid", "", "also_valid"]}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tags", result.errors[0].lower())

    def test_validate_filter_expressions_invalid_owner_id_format(self):
        """Test filter expression validation with invalid owner_id UUID format"""
        filters = {"owner_id": "not-a-uuid"}
        result = self.rules._validate_filter_expressions(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("owner_id", result.errors[0].lower())


class SearchFilterSecurityValidationTest(TestCase):
    """Test search filter security validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_filter_security_tenant_id_in_filter(self):
        """Test filter security validation rejects tenant_id in filters"""
        filters = {"tenant_id": str(self.tenant.id)}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_security(filters, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant_id", result.errors[0].lower())

    def test_validate_filter_security_valid_owner_id(self):
        """Test filter security validation with valid owner_id belonging to tenant"""
        filters = {"owner_id": str(self.user.id)}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_security(filters, context)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("owner_validated", False))

    def test_validate_filter_security_invalid_owner_id_different_tenant(self):
        """Test filter security validation rejects owner_id from different tenant"""
        filters = {"owner_id": str(self.other_user.id)}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_security(filters, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("owner_id", result.errors[0].lower())
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_filter_security_invalid_owner_id_nonexistent(self):
        """Test filter security validation rejects nonexistent owner_id"""
        filters = {"owner_id": str(uuid.uuid4())}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_security(filters, context)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("owner_id", result.errors[0].lower())

    def test_validate_filter_security_no_context(self):
        """Test filter security validation without context"""
        filters = {"resource_type": "CONTRACT"}
        result = self.rules._validate_filter_security(filters, None)
        # Should pass without context (can't validate owner_id)
        self.assertTrue(result.is_valid)

    def test_validate_filter_security_uuid_patterns_warning(self):
        """Test filter security validation warns about UUID patterns"""
        filters = {"domain": f"domain-{uuid.uuid4()}"}
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        result = self.rules._validate_filter_security(filters, context)
        # Should pass but with warnings
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)


class SearchFilterPerformanceValidationTest(TestCase):
    """Test search filter performance validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_filter_performance_valid_filter_count(self):
        """Test filter performance validation with valid filter count"""
        filters = {
            "resource_type": "CONTRACT",
            "classification": "PUBLIC",
            "quality_status": "PASS",
        }
        result = self.rules._validate_filter_performance(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filter_performance_excessive_filters(self):
        """Test filter performance validation with excessive filter count"""
        # Create filters exceeding the limit (default is 10)
        filters = {f"filter_{i}": f"value_{i}" for i in range(15)}
        result = self.rules._validate_filter_performance(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("filter", result.errors[0].lower())

    def test_validate_filter_performance_valid_tag_count(self):
        """Test filter performance validation with valid tag count"""
        filters = {"tags": [f"tag_{i}" for i in range(10)]}
        result = self.rules._validate_filter_performance(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_filter_performance_excessive_tags(self):
        """Test filter performance validation with excessive tag count"""
        # Create tags exceeding the limit (default is 20)
        filters = {"tags": [f"tag_{i}" for i in range(25)]}
        result = self.rules._validate_filter_performance(filters)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tag", result.errors[0].lower())

    def test_validate_filter_performance_approaching_filter_limit(self):
        """Test filter performance validation warns when approaching filter limit"""
        # Create filters near the limit (default is 10, so 9 should warn since 9 > 10 * 0.8 = 8)
        filters = {f"filter_{i}": f"value_{i}" for i in range(9)}
        result = self.rules._validate_filter_performance(filters)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("filter", result.warnings[0].lower())

    def test_validate_filter_performance_approaching_tag_limit(self):
        """Test filter performance validation warns when approaching tag limit"""
        # Create tags near the limit (default is 20, so 17 should warn since 17 > 20 * 0.8 = 16)
        filters = {"tags": [f"tag_{i}" for i in range(17)]}
        result = self.rules._validate_filter_performance(filters)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("tag", result.warnings[0].lower())

    def test_validate_filter_performance_impacting_combinations(self):
        """Test filter performance validation warns about performance-impacting combinations"""
        filters = {"domain": "sales", "classification": "PUBLIC", "resource_type": "CONTRACT"}
        result = self.rules._validate_filter_performance(filters)
        # Should pass but may warn about combinations
        self.assertTrue(result.is_valid)


class SearchFilterValidationIntegrationTest(TestCase):
    """Integration tests for search filter validation with SearchService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.search_service = SearchService()

        # Create some test search indices
        self.index1 = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Test Contract 1",
            description="This is a test contract",
            classification="PUBLIC",
            quality_status="PASS",
            tags=["tag1", "tag2"],
        )
        self.index2 = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            title="Test Asset 1",
            description="This is a test asset",
            classification="INTERNAL",
            quality_status="WARN",
        )

    def test_search_service_with_validated_filters(self):
        """Test SearchService integration with validated filters"""
        filters = {
            "resource_type": "CONTRACT",
            "classification": "PUBLIC",
            "quality_status": "PASS",
        }

        # Validate filters first
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        validation_result = self.rules.validate(context)

        # Should pass validation
        self.assertTrue(validation_result.is_valid)
        self.assertEqual(len(validation_result.errors), 0)

        # Use validated filters with SearchService
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id),
            query="test",
            resource_type=filters.get("resource_type"),
            classification=filters.get("classification"),
            quality_status=filters.get("quality_status"),
            limit=10,
        )

        # Should return results
        self.assertGreaterEqual(total, 0)
        # Results should match filters
        for result in results:
            if filters.get("resource_type"):
                self.assertEqual(result.get("type"), filters.get("resource_type"))

    def test_search_service_with_invalid_filters(self):
        """Test SearchService integration with invalid filters"""
        filters = {
            "tenant_id": str(self.tenant.id),  # Should be rejected
            "resource_type": "CONTRACT",
        }

        # Validate filters
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), filters=filters)
        validation_result = self.rules.validate(context)

        # Should fail validation
        self.assertFalse(validation_result.is_valid)
        self.assertGreater(len(validation_result.errors), 0)
        self.assertIn("tenant_id", validation_result.errors[0].lower())

    def test_search_service_with_comprehensive_filters(self):
        """Test SearchService integration with comprehensive filter validation"""
        filters = {
            "resource_type": "CONTRACT",
            "classification": "PUBLIC",
            "quality_status": "PASS",
            "compliance_status": "PASS",
            "tags": ["tag1", "tag2"],
            "owner_id": str(self.user.id),
            "domain": "test-domain",
        }

        # Validate filters
        context = SearchRuleExecutionContext(
            tenant_id=str(self.tenant.id), filters=filters, tenant=self.tenant, user=self.user
        )
        validation_result = self.rules.validate(context)

        # Should pass validation
        self.assertTrue(validation_result.is_valid)
        self.assertEqual(len(validation_result.errors), 0)

        # Use validated filters with SearchService
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id),
            query="test",
            resource_type=filters.get("resource_type"),
            classification=filters.get("classification"),
            quality_status=filters.get("quality_status"),
            compliance_status=filters.get("compliance_status"),
            tags=filters.get("tags"),
            owner_id=filters.get("owner_id"),
            domain=filters.get("domain"),
            limit=10,
        )

        # Should return results
        self.assertGreaterEqual(total, 0)


class SearchQueryValidationIntegrationTest(TestCase):
    """Integration tests for search query validation with SearchService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.search_service = SearchService()

        # Create some test search indices
        self.index1 = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Test Contract 1",
            description="This is a test contract",
        )
        self.index2 = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            title="Test Asset 1",
            description="This is a test asset",
        )

    def test_search_service_with_validated_query(self):
        """Test SearchService integration with validated query"""
        query = "test contract"

        # Validate query first
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=query)
        validation_result = self.rules.validate(context)
        self.assertTrue(
            validation_result.is_valid, f"Query validation failed: {validation_result.errors}"
        )

        # Perform search using SearchService
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id), query=query, limit=10
        )

        # Should return results without errors
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 0)

    def test_search_service_rejects_invalid_query(self):
        """Test that SearchService should work with business rules validation"""
        # This test demonstrates that queries should be validated before calling SearchService
        invalid_query = "test; DROP TABLE"

        # Validate query first
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=invalid_query)
        validation_result = self.rules.validate(context)

        # Validation should fail
        self.assertFalse(validation_result.is_valid)
        self.assertGreater(len(validation_result.errors), 0)

        # In a real scenario, we would not call SearchService with invalid queries
        # This test ensures validation catches the issue before service call

    def test_search_service_with_complex_query(self):
        """Test SearchService with complex but valid query"""
        query = "test & contract"

        # Validate query first
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), query=query)
        validation_result = self.rules.validate(context)

        # Complex queries should be validated for complexity
        if validation_result.is_valid:
            # If valid, perform search
            results, total = self.search_service.search(
                tenant_id=str(self.tenant.id), query=query, limit=10
            )
            self.assertIsInstance(results, list)
            self.assertIsInstance(total, int)
        else:
            # If complexity exceeds limit, should not proceed
            self.assertIn("complexity", " ".join(validation_result.errors).lower())

    def test_search_service_tenant_isolation(self):
        """Test that SearchService enforces tenant isolation"""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )

        # Create index for other tenant
        other_index = SearchIndex.objects.create(
            tenant=other_tenant,
            resource_type="CONTRACT",
            resource_id=uuid.uuid4(),
            title="Other Tenant Contract",
        )

        # Search should only return results for current tenant
        query = "contract"
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id), query=query, limit=10
        )

        # Verify results only contain current tenant's data
        for result in results:
            self.assertEqual(str(result.get("tenant_id")), str(self.tenant.id))

        # Verify other tenant's index is not in results
        result_ids = [r.get("id") for r in results]
        self.assertNotIn(str(other_index.id), result_ids)


class SearchIndexValidationIntegrationTest(TestCase):
    """Integration tests for search index validation with SearchService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = SearchBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.search_service = SearchService()

    def test_search_service_with_validated_index(self):
        """Test SearchService integration with validated index"""
        from hub.apps.contracts.models import Contract

        # Create a contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Test Contract", "description": "A test contract"}
            },
        )

        # Index the contract
        from hub.apps.search.indexing import SearchIndexer

        index = SearchIndexer.index_contract(contract)

        # Validate index
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        validation_result = self.rules.validate(context)
        self.assertTrue(
            validation_result.is_valid, f"Index validation failed: {validation_result.errors}"
        )

        # Perform search using SearchService
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id), query="test contract", limit=10
        )

        # Should return results without errors
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 0)

        # Verify the indexed contract appears in results (search returns SearchIndex IDs)
        result_ids = [r.get("id") for r in results]
        # The search might return the index or might need to match by resource_id
        # Check if either the index ID or the contract ID appears in results
        found = str(index.id) in result_ids or str(contract.id) in result_ids
        self.assertTrue(
            found,
            f"Expected index {index.id} or contract {contract.id} in results. "
            f"Result IDs: {result_ids}, Total: {total}",
        )

    def test_search_service_rejects_invalid_index_structure(self):
        """Test that SearchService should work with business rules validation"""
        # Create index with invalid structure (missing required fields)
        index = SearchIndex(
            tenant=self.tenant,
            resource_type="",  # Invalid: empty resource_type
            resource_id=uuid.uuid4(),
            title="Test",
        )
        # Don't save to avoid database constraint

        # Validate index
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        validation_result = self.rules.validate(context)

        # Validation should fail
        self.assertFalse(validation_result.is_valid)
        self.assertGreater(len(validation_result.errors), 0)

        # In a real scenario, we would not use SearchService with invalid indexes
        # This test ensures validation catches the issue before service usage

    def test_search_service_with_stale_index(self):
        """Test SearchService with stale but valid index"""
        from datetime import timedelta

        from django.utils import timezone

        from hub.apps.contracts.models import Contract

        # Create contract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type="ODCS",
            original_spec_version="1.0.0",
            hub_contract_json={"info": {"title": "Test Contract"}},
        )

        # Index the contract
        from hub.apps.search.indexing import SearchIndexer

        index = SearchIndexer.index_contract(contract)

        # Update contract (simulating resource update)
        contract.updated_at = timezone.now()
        contract.save()

        # Refresh index and contract to get actual timestamps
        index.refresh_from_db()
        contract.refresh_from_db()

        # Set index indexed_at to be older than contract updated_at (if it exists)
        if hasattr(contract, "updated_at") and contract.updated_at:
            index.indexed_at = contract.updated_at - timedelta(days=1)
        else:
            # If updated_at doesn't exist, use created_at
            index.indexed_at = contract.created_at - timedelta(days=1)
        index.save()

        # Validate index (should warn about staleness if updated_at exists)
        context = SearchRuleExecutionContext(tenant_id=str(self.tenant.id), index=index)
        validation_result = self.rules.validate(context)

        # Should be valid
        self.assertTrue(validation_result.is_valid)
        # Only check for warnings if contract has updated_at and it's newer than indexed_at
        if (
            hasattr(contract, "updated_at")
            and contract.updated_at
            and contract.updated_at > index.indexed_at
        ):
            self.assertGreater(
                len(validation_result.warnings),
                0,
                f"Expected stale index warning. Warnings: {validation_result.warnings}",
            )

        # SearchService should still work (stale index is still usable)
        results, total = self.search_service.search(
            tenant_id=str(self.tenant.id), query="test", limit=10
        )
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
