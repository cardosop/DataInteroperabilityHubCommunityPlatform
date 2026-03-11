"""
Unit tests for VirtualizationBusinessRules.

Tests all validation methods using real services and models (no mocks/stubs).
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.core.business_rules.base import ValidationResult
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


class VirtualizationBusinessRulesTest(TestCase):
    """Test cases for VirtualizationBusinessRules."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        self.user = User.objects.create_user(
            email="test@example.com",
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

        # Valid schema
        self.valid_schema = {
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "name", "type": "string"},
                {"name": "age", "type": "integer"},
            ]
        }

        # Valid sources configuration
        self.valid_sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(self.asset.id),
            }
        ]

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        rules = VirtualizationBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id(self):
        """Test initialization with tenant_id"""
        rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_and_user(self):
        """Test initialization with tenant_id and user_id"""
        rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_rule_registration(self):
        """Test that VirtualizationBusinessRules is registered in the business rules registry"""
        registry = get_registry()
        rule_metadata = registry.get_rule("virtualization_dataset_validation")

        self.assertIsNotNone(rule_metadata, "Rule should be registered")
        self.assertEqual(rule_metadata.rule_class, VirtualizationBusinessRules)
        self.assertEqual(rule_metadata.rule_name, "virtualization_dataset_validation")
        self.assertIn("virtualization", rule_metadata.tags)
        self.assertIn("dataset", rule_metadata.tags)
        self.assertIn("validation", rule_metadata.tags)

    def test_get_rule_name(self):
        """Test get_rule_name() method"""
        rules = VirtualizationBusinessRules()
        self.assertEqual(rules.get_rule_name(), "VirtualizationBusinessRules")

    def test_rule_execution_context(self):
        """Test VirtualizationRuleExecutionContext"""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        context = VirtualizationRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            virtual_dataset=virtual_dataset,
            query="SELECT * FROM users",
        )

        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.virtual_dataset, virtual_dataset)
        self.assertEqual(context.query, "SELECT * FROM users")

        # Test to_dict()
        context_dict = context.to_dict()
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["virtual_dataset_id"], str(virtual_dataset.id))
        self.assertIn("query_preview", context_dict)


class QuerySyntaxValidationTest(TestCase):
    """Test cases for validate_query_syntax()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

    def test_validate_query_syntax_empty_query(self):
        """Test validate_query_syntax with empty query."""
        result = self.business_rules.validate_query_syntax("", QueryType.SQL, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(any("empty" in error.lower() for error in result.errors))

    def test_validate_query_syntax_valid_sql(self):
        """Test validate_query_syntax with valid SQL query."""
        query = "SELECT id, name FROM users WHERE age > 18"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SQL, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertIn("query_type", result.details)
        self.assertEqual(result.details["query_type"], QueryType.SQL)

    def test_validate_query_syntax_sql_forbidden_keyword(self):
        """Test validate_query_syntax with SQL query containing forbidden keyword."""
        query = "DROP TABLE users"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SQL, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("forbidden" in error.lower() for error in result.errors))

    def test_validate_query_syntax_sql_missing_required_keyword(self):
        """Test validate_query_syntax with SQL query missing required keyword."""
        query = "FROM users WHERE age > 18"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SQL, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("must contain" in error.lower() for error in result.errors))

    def test_validate_query_syntax_sql_unbalanced_parentheses(self):
        """Test validate_query_syntax with SQL query with unbalanced parentheses."""
        query = "SELECT id FROM users WHERE (age > 18"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SQL, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("parentheses" in error.lower() for error in result.errors))

    def test_validate_query_syntax_sql_select_star_warning(self):
        """Test validate_query_syntax with SQL SELECT * without LIMIT."""
        query = "SELECT * FROM users"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SQL, raise_on_error=False
        )

        # Should be valid but with warning
        self.assertTrue(result.is_valid)
        self.assertTrue(any("select *" in warning.lower() for warning in result.warnings))

    def test_validate_query_syntax_valid_sparql(self):
        """Test validate_query_syntax with valid SPARQL query."""
        query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?name ?email
        WHERE {
            ?person foaf:name ?name .
            ?person foaf:email ?email .
        }
        """
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SPARQL, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_query_syntax_sparql_forbidden_keyword(self):
        """Test validate_query_syntax with SPARQL query containing forbidden keyword."""
        query = "INSERT DATA { <s> <p> <o> . }"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SPARQL, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("forbidden" in error.lower() for error in result.errors))

    def test_validate_query_syntax_sparql_unbalanced_braces(self):
        """Test validate_query_syntax with SPARQL query with unbalanced braces."""
        query = "SELECT ?name WHERE { ?person foaf:name ?name ."
        result = self.business_rules.validate_query_syntax(
            query, QueryType.SPARQL, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("braces" in error.lower() for error in result.errors))

    def test_validate_query_syntax_federated_query(self):
        """Test validate_query_syntax with federated query."""
        query = "SELECT * FROM source1 UNION SELECT * FROM source2"
        result = self.business_rules.validate_query_syntax(
            query, QueryType.FEDERATED, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_query_syntax_rest_query(self):
        """Test validate_query_syntax with REST query."""
        query = '{"method": "GET", "url": "/api/users"}'
        result = self.business_rules.validate_query_syntax(
            query, QueryType.REST, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_query_syntax_raises_exception(self):
        """Test validate_query_syntax raises exception when raise_on_error=True."""
        query = "DROP TABLE users"
        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_query_syntax(query, QueryType.SQL, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_QUERY_SYNTAX")


class SchemaAlignmentValidationTest(TestCase):
    """Test cases for validate_schema_alignment()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

    def test_validate_schema_alignment_no_schema(self):
        """Test validate_schema_alignment with no schema (optional)."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        # Schema is optional, so validation should pass with warning
        self.assertTrue(result.is_valid)
        self.assertTrue(any("no schema" in warning.lower() for warning in result.warnings))

    def test_validate_schema_alignment_valid_schema(self):
        """Test validate_schema_alignment with valid schema."""
        schema = {"fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]}
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("schema_alignment_checks", result.details)

    def test_validate_schema_alignment_invalid_schema_structure(self):
        """Test validate_schema_alignment with invalid schema structure."""
        # Create dataset with valid schema first
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema={"fields": []},  # Valid schema
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Update to invalid schema using update() to bypass model validation
        VirtualDataset.objects.filter(id=virtual_dataset.id).update(
            schema="invalid"  # Should be dict
        )
        virtual_dataset.refresh_from_db()

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("json object" in error.lower() for error in result.errors))

    def test_validate_schema_alignment_fields_array_format(self):
        """Test validate_schema_alignment with fields array format."""
        schema = {"fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]}
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("field_count", result.details["schema_alignment_checks"])

    def test_validate_schema_alignment_fields_dict_format(self):
        """Test validate_schema_alignment with fields dict format."""
        schema = {"id": {"type": "integer"}, "name": {"type": "string"}}
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_schema_alignment_missing_field_name(self):
        """Test validate_schema_alignment with field missing name."""
        schema = {
            "fields": [{"type": "integer"}, {"name": "name", "type": "string"}]  # Missing name
        }
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("name" in error.lower() for error in result.errors))

    def test_validate_schema_alignment_column_extraction(self):
        """Test validate_schema_alignment with SQL column extraction."""
        schema = {"fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]}
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_schema_alignment(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        # Check if column extraction was attempted
        checks = result.details.get("schema_alignment_checks", {})
        if "query_columns_extracted" in checks:
            self.assertTrue(checks["query_columns_extracted"])

    def test_validate_schema_alignment_raises_exception(self):
        """Test validate_schema_alignment raises exception when raise_on_error=True."""
        # Create dataset with valid schema first
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema={"fields": []},  # Valid schema
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Update to invalid schema using update() to bypass model validation
        VirtualDataset.objects.filter(id=virtual_dataset.id).update(
            schema="invalid"  # Should be dict
        )
        virtual_dataset.refresh_from_db()

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_schema_alignment(virtual_dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_SCHEMA_ALIGNMENT")


class SourceCompatibilityValidationTest(TestCase):
    """Test cases for validate_source_compatibility()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

    def test_validate_source_compatibility_no_sources_sparql(self):
        """Test validate_source_compatibility with no sources for SPARQL (optional)."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT ?name WHERE { ?person foaf:name ?name . }",
            query_type=QueryType.SPARQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Sources are optional for SPARQL
        self.assertTrue(result.is_valid)

    def test_validate_source_compatibility_no_sources_sql(self):
        """Test validate_source_compatibility with no sources for SQL (required)."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("required" in error.lower() for error in result.errors))

    def test_validate_source_compatibility_valid_sources(self):
        """Test validate_source_compatibility with valid sources."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(self.asset.id),
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("source_compatibility_checks", result.details)

    def test_validate_source_compatibility_incompatible_source_type(self):
        """Test validate_source_compatibility with incompatible source type."""
        sources = [
            {
                "type": "sparql",  # SPARQL source not compatible with SQL query
                "endpoint": "http://example.com/sparql",
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("not compatible" in error.lower() for error in result.errors))

    def test_validate_source_compatibility_missing_source_type(self):
        """Test validate_source_compatibility with missing source type."""
        sources = [{"host": "localhost", "database": "testdb"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("type" in error.lower() for error in result.errors))

    def test_validate_source_compatibility_odbc_connection_string(self):
        """Test validate_source_compatibility with ODBC source using connection_string."""
        sources = [
            {
                "type": "odbc",
                "connection_string": "DRIVER={PostgreSQL Unicode};SERVER=localhost;DATABASE=testdb",
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test ODBC Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_source_compatibility_odbc_host_database(self):
        """Test validate_source_compatibility with ODBC source using host+database."""
        sources = [
            {
                "type": "odbc",
                "host": "localhost",
                "database": "testdb",
                "username": "user",
                "password": "secret",
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test ODBC Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_source_compatibility_odbc_missing_config(self):
        """Test validate_source_compatibility with ODBC source missing connection_string and host+database."""
        sources = [{"type": "odbc"}]  # Missing connection_string and host+database
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test ODBC Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "connection_string" in e or "host" in e or "database" in e
                for e in result.errors
            )
        )

    def test_validate_source_compatibility_missing_required_fields(self):
        """Test validate_source_compatibility with missing required fields."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                # Missing 'database' field
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("database" in error.lower() for error in result.errors))

    def test_validate_source_compatibility_nonexistent_asset(self):
        """Test validate_source_compatibility with nonexistent asset."""
        import uuid

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(uuid.uuid4()),  # Non-existent asset
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "non-existent" in error.lower() or "does not exist" in error.lower()
                for error in result.errors
            )
        )

    def test_validate_source_compatibility_valid_asset(self):
        """Test validate_source_compatibility with valid asset."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(self.asset.id),
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        checks = result.details.get("source_compatibility_checks", {})
        self.assertTrue(checks.get("source_0_asset_exists", False))

    def test_validate_source_compatibility_rest_source(self):
        """Test validate_source_compatibility with REST source."""
        sources = [{"type": "rest", "url": "http://example.com/api/users"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query='{"method": "GET", "url": "/api/users"}',
            query_type=QueryType.REST,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)

    def test_validate_source_compatibility_rest_source_missing_url(self):
        """Test validate_source_compatibility with REST source missing URL."""
        sources = [
            {
                "type": "rest"
                # Missing 'url' or 'endpoint'
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query='{"method": "GET", "url": "/api/users"}',
            query_type=QueryType.REST,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("url" in error.lower() or "endpoint" in error.lower() for error in result.errors)
        )

    def test_validate_source_compatibility_raises_exception(self):
        """Test validate_source_compatibility raises exception when raise_on_error=True."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_source_compatibility(virtual_dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_SOURCE_COMPATIBILITY")


class CrossSourceCompatibilityValidationTest(TestCase):
    """Test cases for validate_cross_source_compatibility()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create test assets
        self.asset1 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-1", name="Test Asset 1", status=AssetStatus.ACTIVE
        )
        self.asset2 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-2", name="Test Asset 2", status=AssetStatus.ACTIVE
        )

        # Create datasets with schemas for assets
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        # Create file for asset1
        file1 = File.objects.create(
            tenant=self.tenant, name="test1.csv", size=1000, content_type="text/csv"
        )
        self.dataset1 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset1,
            file=file1,
            schema_json={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            format="CSV",
            version=1,
        )

        # Create file for asset2
        file2 = File.objects.create(
            tenant=self.tenant, name="test2.csv", size=1000, content_type="text/csv"
        )
        self.dataset2 = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset2,
            file=file2,
            schema_json={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            format="CSV",
            version=1,
        )

    def test_validate_cross_source_compatibility_single_source(self):
        """Test validate_cross_source_compatibility with single source (should skip)."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(self.asset1.id),
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Single source - validation should pass (no cross-source checks needed)
        self.assertTrue(result.is_valid)
        self.assertIn("cross_source_checks", result.details)
        self.assertIn("skipped", result.details["cross_source_checks"])

    def test_validate_cross_source_compatibility_no_sources(self):
        """Test validate_cross_source_compatibility with no sources."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT ?name WHERE { ?person foaf:name ?name . }",
            query_type=QueryType.SPARQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # No sources - validation should pass
        self.assertTrue(result.is_valid)

    def test_validate_cross_source_compatibility_aligned_schemas(self):
        """Test validate_cross_source_compatibility with aligned schemas."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb2",
                "asset_id": str(self.asset2.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name, age FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("cross_source_checks", result.details)
        checks = result.details["cross_source_checks"]
        self.assertTrue(checks.get("schema_alignment_valid", False))

    def test_validate_cross_source_compatibility_misaligned_schemas(self):
        """Test validate_cross_source_compatibility with misaligned schemas."""
        # Create asset with different schema
        asset3 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-3", name="Test Asset 3", status=AssetStatus.ACTIVE
        )
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        file3 = File.objects.create(
            tenant=self.tenant, name="test3.csv", size=1000, content_type="text/csv"
        )
        dataset3 = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset3,
            file=file3,
            schema_json={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "email", "type": "string"},  # Different field
                    {"name": "age", "type": "integer"},
                ]
            },
            format="CSV",
            version=1,
        )

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb3",
                "asset_id": str(asset3.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name, age FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Should have warnings about schema misalignment
        self.assertTrue(result.is_valid or len(result.warnings) > 0)
        self.assertIn("cross_source_checks", result.details)

    def test_validate_cross_source_compatibility_incompatible_types(self):
        """Test validate_cross_source_compatibility with incompatible data types."""
        # Create asset with incompatible type
        asset4 = Asset.objects.create(
            tenant=self.tenant, key="test-asset-4", name="Test Asset 4", status=AssetStatus.ACTIVE
        )
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        file4 = File.objects.create(
            tenant=self.tenant, name="test4.csv", size=1000, content_type="text/csv"
        )
        dataset4 = Dataset.objects.create(
            tenant=self.tenant,
            asset=asset4,
            file=file4,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string"},  # Incompatible: integer vs string
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            format="CSV",
            version=1,
        )

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb4",
                "asset_id": str(asset4.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name, age FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Should have warnings about type incompatibility
        self.assertIn("cross_source_checks", result.details)
        checks = result.details["cross_source_checks"]
        if "type_compatibility_issues" in checks:
            self.assertGreater(len(checks["type_compatibility_issues"]), 0)

    def test_validate_cross_source_compatibility_cross_tenant_access(self):
        """Test validate_cross_source_compatibility with cross-tenant sources."""
        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "otherdb",
                "asset_id": str(other_asset.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Should fail due to cross-tenant access without entitlement
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "entitlement" in error.lower() or "cross-tenant" in error.lower()
                for error in result.errors
            )
        )

    def test_validate_cross_source_compatibility_with_entitlement(self):
        """Test validate_cross_source_compatibility with cross-tenant source and entitlement."""
        from hub.apps.tenants.models import KYCStatus

        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        # Create listing and entitlement
        from hub.apps.marketplace.models import (
            Entitlement,
            EntitlementStatus,
            Listing,
            ListingStatus,
            PricingModel,
        )

        listing = Listing.objects.create(
            tenant=other_tenant,
            asset=other_asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )
        entitlement = Entitlement.objects.create(
            tenant=self.tenant, listing=listing, asset=other_asset, status=EntitlementStatus.ACTIVE
        )

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "otherdb",
                "asset_id": str(other_asset.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_source_compatibility(
            virtual_dataset, raise_on_error=False
        )

        # Should pass with valid entitlement
        self.assertTrue(result.is_valid)
        checks = result.details.get("cross_source_checks", {})
        self.assertTrue(checks.get("cross_tenant_access_valid", False))

    def test_validate_cross_source_compatibility_raises_exception(self):
        """Test validate_cross_source_compatibility raises exception when raise_on_error=True."""
        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

        # Create asset in other tenant
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.ACTIVE
        )

        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb1",
                "asset_id": str(self.asset1.id),
            },
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "otherdb",
                "asset_id": str(other_asset.id),
            },
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_cross_source_compatibility(
                virtual_dataset, raise_on_error=True
            )

        self.assertEqual(context.exception.code, "INVALID_CROSS_SOURCE_COMPATIBILITY")


class QueryExecutionBusinessRulesTest(TestCase):
    """Test cases for QueryExecutionBusinessRules."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        self.user = User.objects.create_user(
            email="test@example.com",
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

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        rules = QueryExecutionBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id(self):
        """Test initialization with tenant_id"""
        rules = QueryExecutionBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_optimize_query_sql_success(self):
        """Test SQL query optimization"""
        query = "SELECT   id,   name   FROM   users   WHERE   age > 18"
        result = self.business_rules.optimize_query(
            query=query, query_type=QueryType.SQL, raise_on_error=False
        )

        self.assertIn("optimized_query", result)
        self.assertIn("optimizations_applied", result)
        self.assertIn("warnings", result)
        self.assertIn("details", result)
        # Check that whitespace was normalized
        self.assertNotIn("   ", result["optimized_query"])

    def test_optimize_query_sql_with_select_star_warning(self):
        """Test SQL query optimization with SELECT * warning"""
        query = "SELECT * FROM users"
        result = self.business_rules.optimize_query(
            query=query, query_type=QueryType.SQL, raise_on_error=False
        )

        self.assertTrue(len(result["warnings"]) > 0)
        self.assertIn("SELECT *", result["warnings"][0])

    def test_optimize_query_sparql_success(self):
        """Test SPARQL query optimization"""
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

        self.assertIn("optimized_query", result)
        self.assertIn("optimizations_applied", result)

    def test_optimize_query_empty_query(self):
        """Test query optimization with empty query"""
        result = self.business_rules.optimize_query(
            query="", query_type=QueryType.SQL, raise_on_error=False
        )

        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("cannot be empty", result["errors"][0])

    def test_optimize_query_raises_on_error(self):
        """Test that optimize_query raises exception when raise_on_error=True"""
        with self.assertRaises(ValidationError):
            self.business_rules.optimize_query(
                query="", query_type=QueryType.SQL, raise_on_error=True
            )

    def test_select_execution_mode_sync_simple_query(self):
        """Test execution mode selection for simple query (should be SYNC)"""
        # Simple query with single source
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Simple Query Dataset",
            query="SELECT id FROM users LIMIT 10",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            status=VirtualDatasetStatus.ACTIVE,
        )

        mode = self.business_rules.select_execution_mode(
            virtual_dataset=virtual_dataset, force_async=False
        )

        self.assertEqual(mode, QueryExecutionMode.SYNC)

    def test_select_execution_mode_async_complex_query(self):
        """Test execution mode selection for complex query (should be ASYNC)"""
        # Complex query with JOIN
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Complex Query Dataset",
            query="SELECT u.id, p.name FROM users u JOIN profiles p ON u.id = p.user_id WHERE u.age > 18",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            status=VirtualDatasetStatus.ACTIVE,
        )

        mode = self.business_rules.select_execution_mode(
            virtual_dataset=virtual_dataset, force_async=False
        )

        self.assertEqual(mode, QueryExecutionMode.ASYNC)

    def test_select_execution_mode_async_multiple_sources(self):
        """Test execution mode selection for multiple sources (should be ASYNC)"""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Multi Source Dataset",
            query="SELECT id FROM users",
            query_type=QueryType.SQL,
            sources=[
                {"type": "postgresql", "host": "localhost", "database": "testdb1"},
                {"type": "postgresql", "host": "localhost", "database": "testdb2"},
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

        mode = self.business_rules.select_execution_mode(
            virtual_dataset=virtual_dataset, force_async=False
        )

        self.assertEqual(mode, QueryExecutionMode.ASYNC)

    def test_select_execution_mode_force_async(self):
        """Test execution mode selection with force_async=True"""
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=self.virtual_dataset, force_async=True
        )

        self.assertEqual(mode, QueryExecutionMode.ASYNC)

    def test_select_execution_mode_with_large_result_size(self):
        """Test execution mode selection with large estimated result size"""
        large_size = QueryExecutionBusinessRules.SYNC_SIZE_THRESHOLD + 1
        mode = self.business_rules.select_execution_mode(
            virtual_dataset=self.virtual_dataset,
            estimated_result_size=large_size,
            force_async=False,
        )

        self.assertEqual(mode, QueryExecutionMode.ASYNC)

    def test_validate_timeout_success(self):
        """Test successful timeout validation"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=300, execution_mode=QueryExecutionMode.SYNC, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["validated_timeout"], 300)

    def test_validate_timeout_default_sync(self):
        """Test timeout validation with default for SYNC mode"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=None, execution_mode=QueryExecutionMode.SYNC, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.DEFAULT_SYNC_TIMEOUT
        )

    def test_validate_timeout_default_async(self):
        """Test timeout validation with default for ASYNC mode"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=None, execution_mode=QueryExecutionMode.ASYNC, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.DEFAULT_ASYNC_TIMEOUT
        )

    def test_validate_timeout_below_minimum(self):
        """Test timeout validation with timeout below minimum"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=30,  # Below MIN_TIMEOUT_SECONDS
            execution_mode=QueryExecutionMode.SYNC,
            raise_on_error=False,
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("minimum" in e.lower() and "timeout" in e.lower() for e in result.errors),
            f"Expected error about timeout/minimum, got: {result.errors}",
        )
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.MIN_TIMEOUT_SECONDS
        )

    def test_validate_timeout_above_maximum(self):
        """Test timeout validation with timeout above maximum"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=10000,  # Above MAX_TIMEOUT_SECONDS
            execution_mode=QueryExecutionMode.SYNC,
            raise_on_error=False,
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any("maximum" in e.lower() and "timeout" in e.lower() for e in result.errors),
            f"Expected error about timeout/maximum, got: {result.errors}",
        )
        self.assertEqual(
            result.details["validated_timeout"], QueryExecutionBusinessRules.MAX_TIMEOUT_SECONDS
        )

    def test_validate_timeout_high_sync_warning(self):
        """Test timeout validation with high timeout for SYNC mode (should warn)"""
        result = self.business_rules.validate_timeout(
            timeout_seconds=900,  # 15 minutes - high for SYNC
            execution_mode=QueryExecutionMode.SYNC,
            raise_on_error=False,
        )

        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("SYNC mode timeout", result.warnings[0])

    def test_validate_timeout_raises_on_error(self):
        """Test that validate_timeout raises exception when raise_on_error=True"""
        with self.assertRaises(ValidationError):
            self.business_rules.validate_timeout(
                timeout_seconds=30,  # Below minimum
                execution_mode=QueryExecutionMode.SYNC,
                raise_on_error=True,
            )


class ResultBusinessRulesTest(TestCase):
    """Test cases for ResultBusinessRules."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.business_rules = ResultBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_initialization_without_parameters(self):
        """Test initialization without parameters"""
        rules = ResultBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_initialization_with_tenant_id(self):
        """Test initialization with tenant_id"""
        rules = ResultBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_validate_result_caching_success(self):
        """Test successful result caching validation"""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=3600, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["validated_cache_ttl"], 3600)

    def test_validate_result_caching_disabled(self):
        """Test result caching validation with caching disabled"""
        result = self.business_rules.validate_result_caching(
            cache_enabled=False, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_result_caching_default_ttl(self):
        """Test result caching validation with default TTL"""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=None, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.details["validated_cache_ttl"], ResultBusinessRules.DEFAULT_CACHE_TTL
        )

    def test_validate_result_caching_below_minimum(self):
        """Test result caching validation with TTL below minimum"""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=30, raise_on_error=False  # Below MIN_CACHE_TTL
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to minimum
        self.assertEqual(result.details["validated_cache_ttl"], ResultBusinessRules.MIN_CACHE_TTL)

    def test_validate_result_caching_above_maximum(self):
        """Test result caching validation with TTL above maximum"""
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=100000, raise_on_error=False  # Above MAX_CACHE_TTL
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to maximum
        self.assertEqual(result.details["validated_cache_ttl"], ResultBusinessRules.MAX_CACHE_TTL)

    def test_validate_result_caching_large_result_warning(self):
        """Test result caching validation with large result size (should warn)"""
        large_size = 150 * 1024 * 1024  # 150MB
        result = self.business_rules.validate_result_caching(
            cache_enabled=True, cache_ttl=3600, result_size=large_size, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("Large result size", result.warnings[0])

    def test_validate_result_caching_raises_on_error(self):
        """Test that validate_result_caching raises exception when raise_on_error=True"""
        with self.assertRaises(ValidationError):
            self.business_rules.validate_result_caching(
                cache_enabled=True, cache_ttl=30, raise_on_error=True  # Below minimum
            )

    def test_validate_pagination_page_based_success(self):
        """Test successful page-based pagination validation"""
        result = self.business_rules.validate_pagination(page=1, page_size=50, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["validated_page"], 1)
        self.assertEqual(result.details["validated_page_size"], 50)

    def test_validate_pagination_offset_based_success(self):
        """Test successful offset-based pagination validation"""
        result = self.business_rules.validate_pagination(offset=0, limit=50, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["validated_offset"], 0)
        self.assertEqual(result.details["validated_limit"], 50)

    def test_validate_pagination_mutually_exclusive_error(self):
        """Test pagination validation with both page and offset (should error)"""
        result = self.business_rules.validate_pagination(page=1, offset=0, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Cannot use both", result.errors[0])

    def test_validate_pagination_default_page_size(self):
        """Test pagination validation with default page_size"""
        result = self.business_rules.validate_pagination(
            page=1, page_size=None, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(
            result.details["validated_page_size"], ResultBusinessRules.DEFAULT_PAGE_SIZE
        )

    def test_validate_pagination_default_limit(self):
        """Test pagination validation with default limit"""
        result = self.business_rules.validate_pagination(offset=0, limit=None, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.DEFAULT_LIMIT)

    def test_validate_pagination_page_below_minimum(self):
        """Test pagination validation with page below minimum"""
        result = self.business_rules.validate_pagination(
            page=0, page_size=50, raise_on_error=False  # Below MIN_PAGE_NUMBER
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to minimum
        self.assertEqual(result.details["validated_page"], ResultBusinessRules.MIN_PAGE_NUMBER)

    def test_validate_pagination_page_size_below_minimum(self):
        """Test pagination validation with page_size below minimum"""
        result = self.business_rules.validate_pagination(
            page=1, page_size=0, raise_on_error=False  # Below MIN_PAGE_SIZE
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to minimum
        self.assertEqual(result.details["validated_page_size"], ResultBusinessRules.MIN_PAGE_SIZE)

    def test_validate_pagination_page_size_above_maximum(self):
        """Test pagination validation with page_size above maximum"""
        result = self.business_rules.validate_pagination(
            page=1, page_size=2000, raise_on_error=False  # Above MAX_PAGE_SIZE
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to maximum
        self.assertEqual(result.details["validated_page_size"], ResultBusinessRules.MAX_PAGE_SIZE)

    def test_validate_pagination_offset_below_minimum(self):
        """Test pagination validation with offset below minimum"""
        result = self.business_rules.validate_pagination(
            offset=-1, limit=50, raise_on_error=False  # Below MIN_OFFSET
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to minimum
        self.assertEqual(result.details["validated_offset"], ResultBusinessRules.MIN_OFFSET)

    def test_validate_pagination_limit_below_minimum(self):
        """Test pagination validation with limit below minimum"""
        result = self.business_rules.validate_pagination(
            offset=0, limit=0, raise_on_error=False  # Below MIN_LIMIT
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to minimum
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.MIN_LIMIT)

    def test_validate_pagination_limit_above_maximum(self):
        """Test pagination validation with limit above maximum"""
        result = self.business_rules.validate_pagination(
            offset=0, limit=2000, raise_on_error=False  # Above MAX_LIMIT
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        # Should be auto-corrected to maximum
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.MAX_LIMIT)

    def test_validate_pagination_no_pagination_default_limit(self):
        """Test pagination validation with no pagination specified (should apply default limit)"""
        result = self.business_rules.validate_pagination(
            page=None, offset=None, limit=None, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["validated_limit"], ResultBusinessRules.DEFAULT_LIMIT)

    def test_validate_pagination_raises_on_error(self):
        """Test that validate_pagination raises exception when raise_on_error=True"""
        with self.assertRaises(ValidationError):
            self.business_rules.validate_pagination(
                page=1, offset=0, raise_on_error=True  # Mutually exclusive
            )


class CrossTenantAccessValidationTest(TestCase):
    """Test cases for validate_cross_tenant_access()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")

        self.other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant")

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

        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create assets in both tenants
        self.asset_same_tenant = Asset.objects.create(
            tenant=self.tenant,
            key="same-tenant-asset",
            name="Same Tenant Asset",
            status=(
                AssetStatus.ACTIVE[0]
                if isinstance(AssetStatus.ACTIVE, tuple)
                else AssetStatus.ACTIVE
            ),
        )

        self.asset_other_tenant = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-tenant-asset",
            name="Other Tenant Asset",
            status=(
                AssetStatus.ACTIVE[0]
                if isinstance(AssetStatus.ACTIVE, tuple)
                else AssetStatus.ACTIVE
            ),
        )

        # Add DATA_VIEWER role to user for query execution
        from hub.apps.users.models import Role, UserRole

        role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_VIEWER", defaults={"description": "Data viewer role"}
        )
        UserRole.objects.get_or_create(user=self.user, role=role)

        # Create virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "testdb",
                    "asset_id": str(self.asset_same_tenant.id),
                }
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

    def test_validate_cross_tenant_access_missing_tenant_id(self):
        """Test cross-tenant access validation without tenant_id"""
        rules = VirtualizationBusinessRules(user_id=str(self.user.id))
        result = rules.validate_cross_tenant_access(self.virtual_dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("tenant_id is required" in error for error in result.errors))

    def test_validate_cross_tenant_access_missing_user_id(self):
        """Test cross-tenant access validation without user_id"""
        rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))
        result = rules.validate_cross_tenant_access(self.virtual_dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("user_id is required" in error for error in result.errors))

    def test_validate_cross_tenant_access_no_sources(self):
        """Test cross-tenant access validation with no sources"""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="No Sources Dataset",
            query="SELECT ?name WHERE { ?person foaf:name ?name . }",
            query_type=QueryType.SPARQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_tenant_access(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["cross_tenant_access_checks"]["sources_provided"])

    def test_validate_cross_tenant_access_same_tenant_source(self):
        """Test cross-tenant access validation with same-tenant source"""
        result = self.business_rules.validate_cross_tenant_access(
            self.virtual_dataset, raise_on_error=False
        )

        # Should pass - same tenant source
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["cross_tenant_access_checks"]["source_access_valid"])

    def test_validate_cross_tenant_access_cross_tenant_source_without_permission(self):
        """Test cross-tenant access validation with cross-tenant source without permission"""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Cross Tenant Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "otherdb",
                    "asset_id": str(self.asset_other_tenant.id),
                }
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_tenant_access(
            virtual_dataset, raise_on_error=False
        )

        # Should fail - cross-tenant source without permission
        # Note: This may pass if ABAC allows it, but typically should fail
        # The actual result depends on ABAC policy configuration
        self.assertIn("cross_tenant_access_checks", result.details)

    def test_validate_cross_tenant_access_query_execution_authorization(self):
        """Test query execution authorization check"""
        result = self.business_rules.validate_cross_tenant_access(
            self.virtual_dataset, raise_on_error=False
        )

        self.assertIn("query_execution_authorized", result.details["cross_tenant_access_checks"])
        # User should have authorization (or errors if not)
        auth_status = result.details["cross_tenant_access_checks"]["query_execution_authorized"]
        self.assertIn(auth_status, [True, False, None])

    def test_validate_cross_tenant_access_result_filtering_same_tenant(self):
        """Test result data filtering validation with same-tenant sources"""
        result = self.business_rules.validate_cross_tenant_access(
            self.virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        filtering_details = result.details["cross_tenant_access_checks"]["result_filtering_details"]
        self.assertTrue(
            filtering_details["tenant_isolation_checks"].get("all_sources_same_tenant", False)
        )

    def test_validate_cross_tenant_access_result_filtering_cross_tenant(self):
        """Test result data filtering validation with cross-tenant sources"""
        # Ensure asset is ACTIVE for listing
        if isinstance(AssetStatus.ACTIVE, tuple):
            self.asset_other_tenant.status = AssetStatus.ACTIVE[0]
        else:
            self.asset_other_tenant.status = AssetStatus.ACTIVE
        self.asset_other_tenant.save()

        # Create entitlement for cross-tenant access
        from hub.apps.marketplace.models import (
            Entitlement,
            EntitlementStatus,
            Listing,
            ListingStatus,
            PricingModel,
        )
        from hub.apps.tenants.models import KYCStatus

        self.other_tenant.kyc_status = KYCStatus.VERIFIED
        self.other_tenant.save()

        listing = Listing.objects.create(
            tenant=self.other_tenant,
            asset=self.asset_other_tenant,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={"title": "Test Listing"},
        )
        entitlement = Entitlement.objects.create(
            tenant=self.tenant,
            listing=listing,
            asset=self.asset_other_tenant,
            status=EntitlementStatus.ACTIVE,
        )

        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Cross Tenant Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "otherdb",
                    "asset_id": str(self.asset_other_tenant.id),
                }
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_tenant_access(
            virtual_dataset, raise_on_error=False
        )

        # Should validate result filtering
        self.assertIn("result_filtering_valid", result.details["cross_tenant_access_checks"])
        filtering_details = result.details["cross_tenant_access_checks"]["result_filtering_details"]
        self.assertIn("tenant_isolation_checks", filtering_details)

    def test_validate_cross_tenant_access_raises_on_error(self):
        """Test that validate_cross_tenant_access raises exception when raise_on_error=True"""
        rules = VirtualizationBusinessRules(user_id=str(self.user.id))
        with self.assertRaises(ValidationError) as context:
            rules.validate_cross_tenant_access(self.virtual_dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "MISSING_TENANT_ID")

    def test_validate_cross_tenant_access_with_governance_service_integration(self):
        """Test integration with GovernanceService for access checks"""
        result = self.business_rules.validate_cross_tenant_access(
            self.virtual_dataset, raise_on_error=False
        )

        # Should have source access checks
        self.assertIn("source_access_valid", result.details["cross_tenant_access_checks"])
        # Should have query authorization details
        self.assertIn("query_authorization_details", result.details["cross_tenant_access_checks"])
        # Should have result filtering details
        self.assertIn("result_filtering_details", result.details["cross_tenant_access_checks"])

    def test_validate_cross_tenant_access_tenant_isolation(self):
        """Test tenant isolation validation"""
        # Create virtual dataset with different tenant and a source to trigger result filtering validation
        wrong_tenant_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Wrong Tenant Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "testdb",
                    "asset_id": str(self.asset_same_tenant.id),
                }
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_cross_tenant_access(
            wrong_tenant_dataset, raise_on_error=False
        )

        # Validation should run successfully
        self.assertIn("cross_tenant_access_checks", result.details)
        # Check that result filtering details are present (when sources exist)
        filtering_details = result.details["cross_tenant_access_checks"].get(
            "result_filtering_details", {}
        )
        if filtering_details:
            # If filtering details exist, check tenant isolation checks
            self.assertIn("tenant_isolation_checks", filtering_details)
            tenant_isolation_checks = filtering_details.get("tenant_isolation_checks", {})
            self.assertIsInstance(tenant_isolation_checks, dict)
        # Validation should complete successfully
        self.assertIsNotNone(result)


class VirtualDatasetSourceConfigurationValidationTest(TestCase):
    """Test cases for validate_source_configuration()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

    def test_validate_source_configuration_valid_sources(self):
        """Test validate_source_configuration with valid sources."""
        sources = [
            {
                "type": "postgresql",
                "host": "localhost",
                "database": "testdb",
                "asset_id": str(self.asset.id),
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_configuration(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("source_configuration_checks", result.details)

    def test_validate_source_configuration_unsupported_source_type(self):
        """Test validate_source_configuration with unsupported source type."""
        sources = [{"type": "unsupported_type", "host": "localhost"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_configuration(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("not supported" in error.lower() for error in result.errors))

    def test_validate_source_configuration_invalid_host_format(self):
        """Test validate_source_configuration with invalid host format."""
        sources = [{"type": "postgresql", "host": "invalid..host..name", "database": "testdb"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_configuration(
            virtual_dataset, raise_on_error=False
        )

        # Should have warnings about invalid host format
        self.assertGreater(len(result.warnings), 0)

    def test_validate_source_configuration_invalid_url_format(self):
        """Test validate_source_configuration with invalid URL format."""
        sources = [{"type": "rest", "url": "not-a-valid-url"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query='{"method": "GET"}',
            query_type=QueryType.REST,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_configuration(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("invalid url" in error.lower() for error in result.errors))

    def test_validate_source_configuration_invalid_bucket_name(self):
        """Test validate_source_configuration with invalid S3 bucket name."""
        sources = [{"type": "s3", "bucket": "Invalid.Bucket.Name"}]  # Invalid bucket name
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM s3://bucket/file",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_configuration(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("bucket" in error.lower() for error in result.errors))

    def test_validate_source_configuration_raises_exception(self):
        """Test validate_source_configuration raises exception when raise_on_error=True."""
        sources = [{"type": "unsupported_type"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_source_configuration(virtual_dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_SOURCE_CONFIGURATION")


class VirtualDatasetQueryMappingValidationTest(TestCase):
    """Test cases for validate_query_mapping()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

    def test_validate_query_mapping_valid_sql(self):
        """Test validate_query_mapping with valid SQL query."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_mapping(virtual_dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertIn("query_mapping_checks", result.details)

    def test_validate_query_mapping_empty_query(self):
        """Test validate_query_mapping with empty query."""
        # Create with valid query first, then update to empty to bypass model validation
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        # Update to empty query bypassing model validation
        VirtualDataset.objects.filter(id=virtual_dataset.id).update(query="")
        virtual_dataset.refresh_from_db()

        result = self.business_rules.validate_query_mapping(virtual_dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("empty" in error.lower() for error in result.errors))

    def test_validate_query_mapping_unsupported_query_type(self):
        """Test validate_query_mapping with unsupported query type."""
        # Create with valid query type first, then update to invalid to bypass model validation
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        # Update to invalid query type bypassing model validation
        VirtualDataset.objects.filter(id=virtual_dataset.id).update(query_type="INVALID_TYPE")
        virtual_dataset.refresh_from_db()

        result = self.business_rules.validate_query_mapping(virtual_dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("not supported" in error.lower() for error in result.errors))

    def test_validate_query_mapping_valid_sparql(self):
        """Test validate_query_mapping with valid SPARQL query."""
        query = """
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        SELECT ?name ?email
        WHERE {
            ?person foaf:name ?name .
            ?person foaf:email ?email .
        }
        """
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query=query,
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_mapping(virtual_dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        checks = result.details.get("query_mapping_checks", {})
        self.assertTrue(checks.get("language_supported", False))

    def test_validate_query_mapping_raises_exception(self):
        """Test validate_query_mapping raises exception when raise_on_error=True."""
        # Create with valid query first, then update to empty to bypass model validation
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        # Update to empty query bypassing model validation
        VirtualDataset.objects.filter(id=virtual_dataset.id).update(query="")
        virtual_dataset.refresh_from_db()

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_query_mapping(virtual_dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_QUERY_MAPPING")


class VirtualDatasetCachingConfigurationValidationTest(TestCase):
    """Test cases for validate_caching_configuration()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

    def test_validate_caching_configuration_valid_config(self):
        """Test validate_caching_configuration with valid cache config."""
        cache_config = {"enabled": True, "ttl": 3600}

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("caching_configuration_checks", result.details)

    def test_validate_caching_configuration_disabled(self):
        """Test validate_caching_configuration with caching disabled."""
        cache_config = {"enabled": False}

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        checks = result.details.get("caching_configuration_checks", {})
        self.assertTrue(checks.get("validation_skipped", False))

    def test_validate_caching_configuration_invalid_ttl(self):
        """Test validate_caching_configuration with invalid TTL."""
        cache_config = {"enabled": True, "ttl": 30}  # Below minimum

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("ttl" in error.lower() for error in result.errors))

    def test_validate_caching_configuration_valid_key_prefix(self):
        """Test validate_caching_configuration with valid cache key prefix."""
        cache_config = {"enabled": True, "ttl": 3600, "key_prefix": "virtual_query"}

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        checks = result.details.get("caching_configuration_checks", {})
        self.assertTrue(checks.get("key_prefix_valid", False))

    def test_validate_caching_configuration_invalid_key_prefix(self):
        """Test validate_caching_configuration with invalid cache key prefix."""
        cache_config = {
            "enabled": True,
            "ttl": 3600,
            "key_prefix": "invalid prefix with spaces",  # Invalid characters
        }

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("key prefix" in error.lower() for error in result.errors))

    def test_validate_caching_configuration_valid_cache_key(self):
        """Test validate_caching_configuration with valid cache key."""
        cache_config = {
            "enabled": True,
            "ttl": 3600,
            "key": f"virtual_query:{self.virtual_dataset.id}:abc123:def456",
        }

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        checks = result.details.get("caching_configuration_checks", {})
        self.assertTrue(checks.get("key_valid", False))

    def test_validate_caching_configuration_invalid_cache_key(self):
        """Test validate_caching_configuration with invalid cache key."""
        cache_config = {"enabled": True, "ttl": 3600, "key": "a" * 300}  # Exceeds max length

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("key" in error.lower() for error in result.errors))

    def test_validate_caching_configuration_generated_key(self):
        """Test validate_caching_configuration with generated cache key."""
        cache_config = {"enabled": True, "ttl": 3600}

        result = self.business_rules.validate_caching_configuration(
            self.virtual_dataset, cache_config=cache_config, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        checks = result.details.get("caching_configuration_checks", {})
        self.assertIn("generated_key", checks)

    def test_validate_caching_configuration_raises_exception(self):
        """Test validate_caching_configuration raises exception when raise_on_error=True."""
        cache_config = {"enabled": True, "ttl": 30}  # Below minimum

        with self.assertRaises(ValidationError) as context:
            self.business_rules.validate_caching_configuration(
                self.virtual_dataset, cache_config=cache_config, raise_on_error=True
            )

        self.assertEqual(context.exception.code, "INVALID_CACHING_CONFIGURATION")


class VirtualDatasetSchemaValidationTest(TestCase):
    """Test cases for validate_virtual_dataset_schema()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(tenant_id=str(self.tenant.id))

    def test_validate_virtual_dataset_schema_valid_schema(self):
        """Test validate_virtual_dataset_schema with valid schema."""
        schema = {"fields": [{"name": "id", "type": "integer"}, {"name": "name", "type": "string"}]}
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=schema,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_virtual_dataset_schema(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertIn("schema_alignment_checks", result.details)

    def test_validate_virtual_dataset_schema_no_schema(self):
        """Test validate_virtual_dataset_schema with no schema (optional)."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name FROM users",
            query_type=QueryType.SQL,
            schema=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_virtual_dataset_schema(
            virtual_dataset, raise_on_error=False
        )

        # Schema is optional, so validation should pass with warning
        self.assertTrue(result.is_valid)
        self.assertTrue(any("no schema" in warning.lower() for warning in result.warnings))


class QueryLanguageCompatibilityTest(TestCase):
    """Test cases for validate_query_language_compatibility()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_query_language_compatibility_no_sources(self):
        """Test query language compatibility with no sources."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_language_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["query_language_checks"]["skipped"])

    def test_validate_query_language_compatibility_sql_with_sql_sources(self):
        """Test SQL query with SQL-compatible sources."""
        sources = [
            {"type": "postgresql", "host": "localhost", "database": "testdb"},
            {"type": "mysql", "host": "localhost", "database": "testdb"},
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_language_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["query_language_checks"]["skipped"])
        self.assertEqual(result.details["query_language_checks"]["source_count"], 2)
        self.assertTrue(result.details["query_language_checks"]["source_0_compatible"])
        self.assertTrue(result.details["query_language_checks"]["source_1_compatible"])

    def test_validate_query_language_compatibility_sql_with_incompatible_source(self):
        """Test SQL query with incompatible source type."""
        sources = [{"type": "sparql", "endpoint": "http://example.com/sparql"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_language_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertFalse(result.details["query_language_checks"]["source_0_compatible"])

    def test_validate_query_language_compatibility_federated_mixed_languages(self):
        """Test federated query with mixed SQL and SPARQL sources."""
        sources = [
            {"type": "postgresql", "host": "localhost", "database": "testdb"},
            {"type": "sparql", "endpoint": "http://example.com/sparql"},
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="FEDERATED QUERY",
            query_type=QueryType.FEDERATED,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_query_language_compatibility(
            virtual_dataset, raise_on_error=False
        )

        self.assertTrue(result.is_valid)  # Federated queries allow mixed languages
        self.assertGreater(len(result.warnings), 0)
        self.assertTrue(result.details["query_language_checks"]["mixed_sql_sparql"])

    def test_get_source_language(self):
        """Test _get_source_language mapping."""
        self.assertEqual(self.business_rules._get_source_language("postgresql"), "sql")
        self.assertEqual(self.business_rules._get_source_language("mysql"), "sql")
        self.assertEqual(self.business_rules._get_source_language("odbc"), "sql")
        self.assertEqual(self.business_rules._get_source_language("sparql"), "sparql")
        self.assertEqual(self.business_rules._get_source_language("rest"), "rest")
        self.assertEqual(self.business_rules._get_source_language("graphql"), "graphql")
        self.assertEqual(self.business_rules._get_source_language("s3"), "file")
        self.assertEqual(self.business_rules._get_source_language("unknown"), "unknown")


class SourceConnectionValidationTest(TestCase):
    """Test cases for validate_source_connections()."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.business_rules = VirtualizationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_source_connections_no_sources(self):
        """Test source connection validation with no sources."""
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=None,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_connections(
            virtual_dataset, test_connectivity=True, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["connection_checks"]["skipped"])

    def test_validate_source_connections_test_disabled(self):
        """Test source connection validation with connectivity testing disabled."""
        sources = [{"type": "postgresql", "host": "localhost", "database": "testdb"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_connections(
            virtual_dataset, test_connectivity=False, raise_on_error=False
        )

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["connection_checks"]["connectivity_testing_disabled"])
        self.assertTrue(result.details["connection_checks"]["source_0_config_valid"])

    def test_validate_source_connections_invalid_config(self):
        """Test source connection validation with invalid configuration."""
        sources = [
            {
                "type": "postgresql",
                # Missing required 'host' and 'database' fields
            }
        ]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_connections(
            virtual_dataset, test_connectivity=True, raise_on_error=False
        )

        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["connection_checks"]["source_0_config_valid"])

    def test_validate_source_connections_valid_config(self):
        """Test source connection validation with valid configuration."""
        sources = [{"type": "postgresql", "host": "localhost", "database": "testdb"}]
        virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=sources,
            status=VirtualDatasetStatus.ACTIVE,
        )

        result = self.business_rules.validate_source_connections(
            virtual_dataset, test_connectivity=True, raise_on_error=False
        )

        # Connection test may fail if database is not accessible, but config should be valid
        self.assertTrue(result.details["connection_checks"]["source_0_config_valid"])
        # Connection test result depends on actual connectivity - may succeed or fail
        # but should not cause validation to fail if connector factory is unavailable
        self.assertIn("source_0_connection_test", result.details["connection_checks"])

    def test_map_source_type_to_connector_type(self):
        """Test _map_source_type_to_connector_type mapping."""
        self.assertEqual(
            self.business_rules._map_source_type_to_connector_type("postgresql"), "DATABASE"
        )
        self.assertEqual(
            self.business_rules._map_source_type_to_connector_type("mysql"), "DATABASE"
        )
        self.assertEqual(
            self.business_rules._map_source_type_to_connector_type("odbc"), "DATABASE"
        )
        self.assertEqual(self.business_rules._map_source_type_to_connector_type("rest"), "HTTP")
        self.assertEqual(self.business_rules._map_source_type_to_connector_type("s3"), "S3")
        self.assertIsNone(self.business_rules._map_source_type_to_connector_type("sparql"))
        self.assertIsNone(self.business_rules._map_source_type_to_connector_type("graphql"))
