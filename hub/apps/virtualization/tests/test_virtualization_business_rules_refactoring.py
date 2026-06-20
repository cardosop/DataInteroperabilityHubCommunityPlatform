"""
Comprehensive test suite for VirtualizationBusinessRules refactoring.

This test suite ensures that all business rules classes work correctly after refactoring
to extend the BusinessRules base class. It tests:

1. All VirtualizationBusinessRules methods
2. All QueryExecutionBusinessRules methods
3. All ResultBusinessRules methods
4. Framework features (caching, metrics, tracing, logging, registry)
5. Backward compatibility

All tests use real services and models (no mocks/stubs) and follow TDD principles.
"""

import uuid

from django.core.cache import cache
from django.test import TestCase, override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.virtualization.business_rules import (
    QueryExecutionBusinessRules,
    ResultBusinessRules,
    VirtualizationBusinessRules,
    VirtualizationRuleExecutionContext,
)
from hub.apps.virtualization.models import (
    QueryExecutionMode,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)


class VirtualizationBusinessRulesRefactoringTest(TestCase):
    """
    Comprehensive test suite for VirtualizationBusinessRules refactoring.

    Tests all methods to ensure they work correctly after refactoring.
    """

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Create test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT id, name, age FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            schema={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "testdb",
                    "asset_id": str(self.asset.id),
                }
            ],
        )

        # Valid SQL query
        self.valid_sql_query = "SELECT id, name, age FROM users WHERE age > 18"

        # Valid SPARQL query
        self.valid_sparql_query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?name ?email
        WHERE {
            ?person foaf:name ?name .
            ?person foaf:email ?email .
        }
        """

    def test_inherits_from_business_rules(self):
        """Test that VirtualizationBusinessRules inherits from BusinessRules."""
        self.assertTrue(issubclass(VirtualizationBusinessRules, BusinessRules))
        self.assertIsInstance(self.business_rules, BusinessRules)

    def test_initialization_with_framework_features(self):
        """Test initialization with framework features enabled/disabled."""
        # Test with all features enabled (default)
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

        # Test with features disabled
        rules_disabled = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            enable_caching=False,
            enable_metrics=False,
            enable_tracing=False,
            enable_logging=False,
        )
        self.assertFalse(rules_disabled.enable_caching)
        self.assertFalse(rules_disabled.enable_metrics)
        self.assertFalse(rules_disabled.enable_tracing)
        self.assertFalse(rules_disabled.enable_logging)

    def test_get_rule_name(self):
        """Test get_rule_name() method."""
        self.assertEqual(self.business_rules.get_rule_name(), "VirtualizationBusinessRules")

    def test_get_cache_ttl(self):
        """Test get_cache_ttl() method."""
        ttl = self.business_rules.get_cache_ttl()
        self.assertIsInstance(ttl, int)
        self.assertGreater(ttl, 0)

    def test_create_context(self):
        """Test create_context() method from base class."""
        context = self.business_rules.create_context(
            resource=self.virtual_dataset, metadata={"test": "value"}
        )
        self.assertIsInstance(context, RuleExecutionContext)
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.resource, self.virtual_dataset)
        self.assertEqual(context.metadata["test"], "value")

    def test_validate_method_exists(self):
        """Test that validate() method exists and is callable."""
        self.assertTrue(hasattr(self.business_rules, "validate"))
        self.assertTrue(callable(self.business_rules.validate))

    def test_validate_with_virtualization_context(self):
        """Test validate() with VirtualizationRuleExecutionContext."""
        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query=self.valid_sql_query,
        )
        result = self.business_rules.validate(context=context, validation_type="all")
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid, f"Expected valid result, errors: {result.errors}")

    def test_validate_with_standard_context(self):
        """Test validate() with standard RuleExecutionContext."""
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resource=self.virtual_dataset,
            metadata={"query": self.valid_sql_query},
        )
        result = self.business_rules.validate(context=context, validation_type="all")
        self.assertIsInstance(result, ValidationResult)

    def test_validate_with_kwargs(self):
        """Test validate() with kwargs instead of context."""
        result = self.business_rules.validate(
            virtual_dataset=self.virtual_dataset, query=self.valid_sql_query, validation_type="all"
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_without_virtual_dataset(self):
        """Test validate() without virtual_dataset (should return error)."""
        result = self.business_rules.validate(validation_type="all")
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_query_syntax_all_types(self):
        """Test validate_query_syntax() for all query types."""
        # SQL
        result = self.business_rules.validate_query_syntax(
            self.valid_sql_query, QueryType.SQL, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

        # SPARQL
        result = self.business_rules.validate_query_syntax(
            self.valid_sparql_query, QueryType.SPARQL, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

        # FEDERATED
        result = self.business_rules.validate_query_syntax(
            "SELECT * FROM users", QueryType.FEDERATED, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

        # REST
        result = self.business_rules.validate_query_syntax(
            "GET /api/users", QueryType.REST, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

        # GRAPHQL
        result = self.business_rules.validate_query_syntax(
            "{ users { id name } }", QueryType.GRAPHQL, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_query_syntax_raises_on_error(self):
        """Test validate_query_syntax() raises exception when raise_on_error=True."""
        with self.assertRaises(ValidationError):
            self.business_rules.validate_query_syntax("", QueryType.SQL, raise_on_error=True)

    def test_validate_source_configuration(self):
        """Test validate_source_configuration() method."""
        result = self.business_rules.validate_source_configuration(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid, f"Source config validation should pass; errors: {result.errors}")

    def test_validate_query_mapping(self):
        """Test validate_query_mapping() method."""
        result = self.business_rules.validate_query_mapping(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_caching_configuration(self):
        """Test validate_caching_configuration() method."""
        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_virtual_dataset_schema(self):
        """Test validate_virtual_dataset_schema() method."""
        result = self.business_rules.validate_virtual_dataset_schema(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_schema_alignment(self):
        """Test validate_schema_alignment() method."""
        result = self.business_rules.validate_schema_alignment(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_source_compatibility(self):
        """Test validate_source_compatibility() method."""
        result = self.business_rules.validate_source_compatibility(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_cross_source_compatibility(self):
        """Test validate_cross_source_compatibility() method."""
        result = self.business_rules.validate_cross_source_compatibility(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_cross_tenant_access(self):
        """Test validate_cross_tenant_access() method."""
        result = self.business_rules.validate_cross_tenant_access(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_query_language_compatibility(self):
        """Test validate_query_language_compatibility() method."""
        result = self.business_rules.validate_query_language_compatibility(
            self.virtual_dataset, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validate_source_connections(self):
        """Test validate_source_connections() method."""
        result = self.business_rules.validate_source_connections(
            self.virtual_dataset, test_connectivity=False, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)

    def test_rule_registration(self):
        """Test that VirtualizationBusinessRules is registered in registry."""
        registry = get_registry()
        rule_metadata = registry.get_rule("virtualization_dataset_validation")
        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_class, VirtualizationBusinessRules)
        self.assertEqual(rule_metadata.rule_name, "virtualization_dataset_validation")


class QueryExecutionBusinessRulesRefactoringTest(TestCase):
    """
    Comprehensive test suite for QueryExecutionBusinessRules refactoring.

    Tests all methods to ensure they work correctly after refactoring.
    """

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.business_rules = QueryExecutionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT id, name FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

    def test_initialization(self):
        """Test initialization."""
        rules = QueryExecutionBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

        rules_with_ids = QueryExecutionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertEqual(rules_with_ids.tenant_id, str(self.tenant.id))
        self.assertEqual(rules_with_ids.user_id, str(self.user.id))

    def test_optimize_query_sql(self):
        """Test optimize_query() for SQL queries."""
        query = "SELECT   id,   name   FROM   users   WHERE   age > 18"
        result = self.business_rules.optimize_query(
            query=query, query_type=QueryType.SQL, raise_on_error=False
        )
        self.assertIsInstance(result, dict)
        self.assertIn("optimized_query", result)
        self.assertIn("optimizations_applied", result)
        self.assertIn("warnings", result)
        self.assertIn("errors", result)
        self.assertIn("details", result)

    def test_optimize_query_sparql(self):
        """Test optimize_query() for SPARQL queries."""
        query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT   ?name   ?email
        WHERE {
            ?person foaf:name ?name .
            ?person foaf:email ?email .
        }
        """
        result = self.business_rules.optimize_query(
            query=query, query_type=QueryType.SPARQL, raise_on_error=False
        )
        self.assertIsInstance(result, dict)
        self.assertIn("optimized_query", result)

    def test_optimize_query_empty(self):
        """Test optimize_query() with empty query."""
        result = self.business_rules.optimize_query(
            query="", query_type=QueryType.SQL, raise_on_error=False
        )
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result["errors"]), 0)

    def test_optimize_query_raises_on_error(self):
        """Test optimize_query() raises exception when raise_on_error=True."""
        with self.assertRaises(ValidationError):
            self.business_rules.optimize_query(
                query="", query_type=QueryType.SQL, raise_on_error=True
            )

    def test_select_execution_mode_sync(self):
        """Test select_execution_mode() returns SYNC for simple queries."""
        # Simple query, single source
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Simple Query Dataset",
            query="SELECT id FROM users LIMIT 10",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=virtual_dataset, raise_on_error=False
        )
        self.assertEqual(
            mode, QueryExecutionMode.SYNC,
            f"Simple single-source SQL query should select SYNC; got {mode}"
        )
        """Test select_execution_mode() returns ASYNC for complex queries."""
        # Complex query with JOIN
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Complex Query Dataset",
            query="SELECT u.id, u.name, p.title FROM users u JOIN posts p ON u.id = p.user_id WHERE u.age > 18 GROUP BY u.id, u.name, p.title ORDER BY u.name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=virtual_dataset, raise_on_error=False
        )
        self.assertEqual(
            mode, QueryExecutionMode.ASYNC,
            f"Complex multi-JOIN query should select ASYNC; got {mode}"
        )

    def test_select_execution_mode_force_async(self):
        """Test select_execution_mode() with force_async=True."""
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=self.virtual_dataset, force_async=True, raise_on_error=False
        )
        self.assertEqual(mode, QueryExecutionMode.ASYNC)

    def test_select_execution_mode_with_estimated_size(self):
        """Test select_execution_mode() with estimated result size."""
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=self.virtual_dataset,
            estimated_result_size=100 * 1024 * 1024,  # 100MB
            raise_on_error=False,
        )
        self.assertEqual(
            mode, QueryExecutionMode.ASYNC,
            f"100MB estimated result should select ASYNC; got {mode}"
        )

    def test_validate_timeout_success(self):
        """Test validate_timeout() with valid timeout."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=300, execution_mode=QueryExecutionMode.SYNC, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validated_timeout", result.details)

    def test_validate_timeout_default_sync(self):
        """Test validate_timeout() with default SYNC timeout."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=None, execution_mode=QueryExecutionMode.SYNC, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_timeout", result.details)
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.DEFAULT_SYNC_TIMEOUT
        )

    def test_validate_timeout_default_async(self):
        """Test validate_timeout() with default ASYNC timeout."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=None, execution_mode=QueryExecutionMode.ASYNC, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_timeout", result.details)
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.DEFAULT_ASYNC_TIMEOUT
        )

    def test_validate_timeout_below_minimum(self):
        """Test validate_timeout() with timeout below minimum."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=30,  # Below MIN_TIMEOUT_SECONDS
            execution_mode=QueryExecutionMode.SYNC,
            raise_on_error=False,
        )
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_timeout", result.details)
        self.assertGreaterEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.MIN_TIMEOUT_SECONDS
        )

    def test_validate_timeout_above_maximum(self):
        """Test validate_timeout() with timeout above maximum."""
        result = self.business_rules.validate_timeout(
            timeout_seconds=10000,  # Above MAX_TIMEOUT_SECONDS
            execution_mode=QueryExecutionMode.SYNC,
            raise_on_error=False,
        )
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to maximum
        self.assertIn("validated_timeout", result.details)
        self.assertLessEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.MAX_TIMEOUT_SECONDS
        )

    def test_validate_timeout_raises_on_error(self):
        """Test validate_timeout() raises exception when raise_on_error=True."""
        # Even though auto-correction happens, errors are still added and should raise
        with self.assertRaises(ValidationError):
            self.business_rules.validate_timeout(
                timeout_seconds=30, execution_mode=QueryExecutionMode.SYNC, raise_on_error=True
            )


class ResultBusinessRulesRefactoringTest(TestCase):
    """
    Comprehensive test suite for ResultBusinessRules refactoring.

    Tests all methods to ensure they work correctly after refactoring.
    """

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.business_rules = ResultBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_initialization(self):
        """Test initialization."""
        rules = ResultBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

        rules_with_ids = ResultBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertEqual(rules_with_ids.tenant_id, str(self.tenant.id))
        self.assertEqual(rules_with_ids.user_id, str(self.user.id))

    def test_validate_result_caching_success(self):
        """Test validate_result_caching() with valid configuration."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=3600, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validated_cache_ttl", result.details)

    def test_validate_result_caching_disabled(self):
        """Test validate_result_caching() with caching disabled."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=False, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)

    def test_validate_result_caching_default_ttl(self):
        """Test validate_result_caching() with default TTL."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=None, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_cache_ttl", result.details)
        self.assertEqual(
            result.details["validated_cache_ttl"], ResultBusinessRules.DEFAULT_CACHE_TTL
        )

    def test_validate_result_caching_below_minimum(self):
        """Test validate_result_caching() with TTL below minimum."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True,
            cache_ttl=30,  # Below MIN_CACHE_TTL
            raise_on_error=False,
        )
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_cache_ttl", result.details)
        self.assertGreaterEqual(
            result.details["validated_cache_ttl"], ResultBusinessRules.MIN_CACHE_TTL
        )

    def test_validate_result_caching_above_maximum(self):
        """Test validate_result_caching() with TTL above maximum."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True,
            cache_ttl=100000,  # Above MAX_CACHE_TTL
            raise_on_error=False,
        )
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to maximum
        self.assertIn("validated_cache_ttl", result.details)
        self.assertLessEqual(
            result.details["validated_cache_ttl"], ResultBusinessRules.MAX_CACHE_TTL
        )

    def test_validate_result_caching_large_result_warning(self):
        """Test validate_result_caching() with large result size."""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True,
            cache_ttl=3600,
            result_size=200 * 1024 * 1024,  # 200MB
            raise_on_error=False,
        )
        self.assertIsInstance(result, ValidationResult)
        # Large result should be valid but generate a warning
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0, "Large result should trigger a warning")

    def test_validate_result_caching_raises_on_error(self):
        """Test validate_result_caching() raises exception when raise_on_error=True."""
        # Even though auto-correction happens, errors are still added and should raise
        with self.assertRaises(ValidationError):
            self.business_rules.validate_result_caching(
                cache_enabled=True, cache_ttl=30, raise_on_error=True
            )

    def test_validate_pagination_page_based(self):
        """Test validate_pagination() with page-based pagination."""
        result = self.business_rules.validate_pagination(page=1, page_size=50, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validated_page", result.details)
        self.assertIn("validated_page_size", result.details)

    def test_validate_pagination_offset_based(self):
        """Test validate_pagination() with offset-based pagination."""
        result = self.business_rules.validate_pagination(offset=0, limit=50, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertIn("validated_offset", result.details)
        self.assertIn("validated_limit", result.details)

    def test_validate_pagination_mutually_exclusive_error(self):
        """Test validate_pagination() with both page and offset (should error)."""
        result = self.business_rules.validate_pagination(page=1, offset=0, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_pagination_default_page_size(self):
        """Test validate_pagination() with default page size."""
        result = self.business_rules.validate_pagination(
            page=1, page_size=None, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_page_size", result.details)
        self.assertEqual(
            result.details["validated_page_size"], ResultBusinessRules.DEFAULT_PAGE_SIZE
        )

    def test_validate_pagination_default_limit(self):
        """Test validate_pagination() with default limit."""
        result = self.business_rules.validate_pagination(offset=0, limit=None, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_limit", result.details)
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.DEFAULT_LIMIT)

    def test_validate_pagination_page_below_minimum(self):
        """Test validate_pagination() with page below minimum."""
        result = self.business_rules.validate_pagination(page=0, page_size=50, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_page", result.details)
        self.assertGreaterEqual(
            result.details["validated_page"], ResultBusinessRules.MIN_PAGE_NUMBER
        )

    def test_validate_pagination_page_size_below_minimum(self):
        """Test validate_pagination() with page_size below minimum."""
        result = self.business_rules.validate_pagination(page=1, page_size=0, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_page_size", result.details)
        self.assertGreaterEqual(
            result.details["validated_page_size"], ResultBusinessRules.MIN_PAGE_SIZE
        )

    def test_validate_pagination_page_size_above_maximum(self):
        """Test validate_pagination() with page_size above maximum."""
        result = self.business_rules.validate_pagination(
            page=1, page_size=2000, raise_on_error=False
        )
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to maximum
        self.assertIn("validated_page_size", result.details)
        self.assertLessEqual(
            result.details["validated_page_size"], ResultBusinessRules.MAX_PAGE_SIZE
        )

    def test_validate_pagination_offset_below_minimum(self):
        """Test validate_pagination() with offset below minimum."""
        result = self.business_rules.validate_pagination(offset=-1, limit=50, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_offset", result.details)
        self.assertGreaterEqual(result.details["validated_offset"], ResultBusinessRules.MIN_OFFSET)

    def test_validate_pagination_limit_below_minimum(self):
        """Test validate_pagination() with limit below minimum."""
        result = self.business_rules.validate_pagination(offset=0, limit=0, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to minimum
        self.assertIn("validated_limit", result.details)
        self.assertGreaterEqual(result.details["validated_limit"], ResultBusinessRules.MIN_LIMIT)

    def test_validate_pagination_limit_above_maximum(self):
        """Test validate_pagination() with limit above maximum."""
        result = self.business_rules.validate_pagination(offset=0, limit=2000, raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        # Should auto-correct to maximum
        self.assertIn("validated_limit", result.details)
        self.assertLessEqual(result.details["validated_limit"], ResultBusinessRules.MAX_LIMIT)

    def test_validate_pagination_no_pagination_default_limit(self):
        """Test validate_pagination() with no pagination (should apply default limit)."""
        result = self.business_rules.validate_pagination(raise_on_error=False)
        self.assertIsInstance(result, ValidationResult)
        self.assertIn("validated_limit", result.details)
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.DEFAULT_LIMIT)

    def test_validate_pagination_raises_on_error(self):
        """Test validate_pagination() raises exception when raise_on_error=True."""
        with self.assertRaises(ValidationError):
            self.business_rules.validate_pagination(page=1, offset=0, raise_on_error=True)


class FrameworkFeaturesTest(TestCase):
    """
    Test framework features integration.

    Tests caching, metrics, tracing, logging, and registry features.
    """

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT id, name FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Clear cache before each test
        cache.clear()

    @override_settings(CACHE_TTL_BUSINESS_RULES=60)
    def test_caching_enabled(self):
        """Test that caching works when enabled."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=True
        )

        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
        )

        # First call - should execute and cache
        result1 = rules.execute(context=context, validation_type="all")
        self.assertIsInstance(result1, ValidationResult)

        # Second call - should use cache
        result2 = rules.execute(context=context, validation_type="all")
        self.assertIsInstance(result2, ValidationResult)

        # Results should be the same
        self.assertEqual(result1.is_valid, result2.is_valid)
        self.assertEqual(len(result1.errors), len(result2.errors))

    def test_caching_disabled(self):
        """Test that caching is skipped when disabled."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), enable_caching=False
        )

        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
        )

        # Should execute without caching
        result = rules.execute(context=context, validation_type="all", use_cache=False)
        self.assertIsInstance(result, ValidationResult)

    def test_execute_method_exists(self):
        """Test that execute() method exists from base class."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertTrue(hasattr(rules, "execute"))
        self.assertTrue(callable(rules.execute))

    def test_execute_with_context(self):
        """Test execute() method with context."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
        )

        result = rules.execute(context=context, validation_type="all")
        self.assertIsInstance(result, ValidationResult)

    def test_execute_without_context(self):
        """Test execute() method without context (creates default)."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        result = rules.execute(
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
            validation_type="all",
        )
        self.assertIsInstance(result, ValidationResult)

    def test_validation_result_combine(self):
        """Test ValidationResult.combine() method."""
        result1 = ValidationResult(
            is_valid=True, errors=["error1"], warnings=["warning1"], details={"key1": "value1"}
        )
        result2 = ValidationResult(
            is_valid=False, errors=["error2"], warnings=["warning2"], details={"key2": "value2"}
        )

        combined = result1.combine(result2)
        self.assertFalse(combined.is_valid)  # False AND True = False
        self.assertEqual(len(combined.errors), 2)
        self.assertEqual(len(combined.warnings), 2)
        self.assertEqual(combined.details["key1"], "value1")
        self.assertEqual(combined.details["key2"], "value2")

    def test_validation_result_bool(self):
        """Test ValidationResult boolean conversion."""
        valid_result = ValidationResult(is_valid=True)
        invalid_result = ValidationResult(is_valid=False)

        self.assertTrue(valid_result)
        self.assertFalse(invalid_result)

    def test_validation_result_str(self):
        """Test ValidationResult string representation."""
        result = ValidationResult(is_valid=True, errors=["error1"], warnings=["warning1"])
        str_repr = str(result)
        self.assertIn("VALID", str_repr)
        self.assertIn("errors=1", str_repr)
        self.assertIn("warnings=1", str_repr)

    def test_rule_execution_context_to_dict(self):
        """Test RuleExecutionContext.to_dict() method."""
        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
        )

        context_dict = context.to_dict()
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["virtual_dataset_id"], str(self.virtual_dataset.id))
        self.assertIn("query_preview", context_dict)

    def test_rule_execution_context_get_cache_key_suffix(self):
        """Test RuleExecutionContext.get_cache_key_suffix() method."""
        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=self.virtual_dataset,
            query="SELECT id, name FROM users WHERE age > 18",
        )

        suffix = context.get_cache_key_suffix()
        self.assertIsInstance(suffix, str)
        self.assertGreater(len(suffix), 0)

    def test_registry_get_rule(self):
        """Test registry.get_rule() method."""
        registry = get_registry()
        rule_metadata = registry.get_rule("virtualization_dataset_validation")
        self.assertIsNotNone(rule_metadata)
        self.assertEqual(rule_metadata.rule_class, VirtualizationBusinessRules)

    def test_registry_get_all_rules(self):
        """Test registry.get_all_rules() method."""
        registry = get_registry()
        rules = registry.get_all_rules()
        self.assertIsInstance(rules, dict)
        self.assertIn("virtualization_dataset_validation", rules)
        self.assertEqual(
            rules["virtualization_dataset_validation"].rule_class, VirtualizationBusinessRules
        )

    def test_compose_method_exists(self):
        """Test that compose() method exists from base class."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertTrue(hasattr(rules, "compose"))
        self.assertTrue(callable(rules.compose))

    def test_compose_rules(self):
        """Test compose() method for combining multiple rules."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        def rule1(context):
            return ValidationResult(is_valid=True, details={"rule1": "executed"})

        def rule2(context):
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = rules.create_context(resource=self.virtual_dataset)
        result = rules.compose(rule1, rule2, context=context)
        self.assertIsInstance(result, ValidationResult)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["rule1"], "executed")
        self.assertEqual(result.details["rule2"], "executed")

    def test_compose_rules_short_circuit(self):
        """Test compose() method with short_circuit=True."""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        def rule1(context):
            return ValidationResult(is_valid=False, errors=["error1"])

        def rule2(context):
            return ValidationResult(is_valid=True, details={"rule2": "executed"})

        context = rules.create_context(resource=self.virtual_dataset)
        result = rules.compose(rule1, rule2, context=context, short_circuit=True)
        self.assertIsInstance(result, ValidationResult)
        self.assertFalse(result.is_valid)
        # rule2 should not have executed due to short-circuit
        self.assertNotIn("rule2", result.details)
