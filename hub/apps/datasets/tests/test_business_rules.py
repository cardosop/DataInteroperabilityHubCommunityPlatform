"""
Unit tests for DatasetsBusinessRules.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model

from hub.apps.assets.tests.factories import AssetFactory
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.datasets.business_rules import DatasetsBusinessRules, DatasetsRuleExecutionContext
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.tests.factories import DatasetFactory
from hub.apps.datasets.tests.test_base import DatasetsTestBase
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DatasetsBusinessRulesInitializationTest(DatasetsTestBase):
    """Test DatasetsBusinessRules initialization"""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_datasets_business_rules_initialization_creates_instance(self):
        """Test DatasetsBusinessRules can be initialized"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsNotNone(rules)

    def test_datasets_business_rules_initialization_sets_rule_name(self):
        """Test DatasetsBusinessRules initialization sets rule name correctly"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertEqual(rules.get_rule_name(), "DatasetsBusinessRules")

    def test_datasets_business_rules_initialization_sets_tenant_id(self):
        """Test DatasetsBusinessRules initialization sets tenant_id correctly"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))

    def test_datasets_business_rules_initialization_sets_user_id(self):
        """Test DatasetsBusinessRules initialization sets user_id correctly"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_datasets_business_rules_initialization_without_user_creates_instance(self):
        """Test DatasetsBusinessRules can be initialized without user"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNotNone(rules)

    def test_datasets_business_rules_initialization_without_user_sets_tenant_id(self):
        """Test DatasetsBusinessRules initialization without user sets tenant_id correctly"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))

    def test_datasets_business_rules_initialization_without_user_sets_user_id_to_none(self):
        """Test DatasetsBusinessRules initialization without user sets user_id to None"""
        rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_datasets_business_rules_initialization_without_tenant_creates_instance(self):
        """Test DatasetsBusinessRules can be initialized without tenant"""
        rules = DatasetsBusinessRules(user_id=str(self.user.id))
        self.assertIsNotNone(rules)

    def test_datasets_business_rules_initialization_without_tenant_sets_tenant_id_to_none(self):
        """Test DatasetsBusinessRules initialization without tenant sets tenant_id to None"""
        rules = DatasetsBusinessRules(user_id=str(self.user.id))
        self.assertIsNone(rules.tenant_id)

    def test_datasets_business_rules_initialization_without_tenant_sets_user_id(self):
        """Test DatasetsBusinessRules initialization without tenant sets user_id correctly"""
        rules = DatasetsBusinessRules(user_id=str(self.user.id))
        self.assertEqual(rules.user_id, str(self.user.id))


class DatasetsBusinessRulesRegistrationTest(DatasetsTestBase):
    """Test DatasetsBusinessRules registration in business rules registry"""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_datasets_business_rules_registered_in_registry(self):
        """Test DatasetsBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertIsNotNone(rule)

    def test_datasets_business_rules_registered_with_correct_name(self):
        """Test DatasetsBusinessRules is registered with correct name"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertEqual(rule.rule_name, "datasets_validation")

    def test_datasets_business_rules_registered_with_correct_class(self):
        """Test DatasetsBusinessRules is registered with correct class"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertEqual(rule.rule_class, DatasetsBusinessRules)

    def test_datasets_business_rules_registered_with_datasets_tag(self):
        """Test DatasetsBusinessRules is registered with datasets tag"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertIn("datasets", rule.tags)

    def test_datasets_business_rules_registered_with_validation_tag(self):
        """Test DatasetsBusinessRules is registered with validation tag"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertIn("validation", rule.tags)

    def test_datasets_business_rules_priority(self):
        """Test DatasetsBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("datasets_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)


class DatasetsBusinessRulesValidationTest(DatasetsTestBase):
    """Test DatasetsBusinessRules validation methods"""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_validate_without_dataset(self):
        """Test validate method without dataset"""
        result = self.rules.validate()
        self.assertFalse(result.is_valid)
        self.assertIn("Dataset is required", result.errors[0])

    def test_validate_with_valid_dataset_returns_valid_result(self):
        """Test validate method with valid dataset returns valid result"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, tenant=self.tenant, user=self.user)
        self.assertTrue(result.is_valid)

    def test_validate_with_valid_dataset_includes_all_validation_check_types(self):
        """validate() with validation_type='all' includes every expected
        check type key in result.details['validation_checks']."""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, tenant=self.tenant, user=self.user)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)

        checks = result.details["validation_checks"]
        for check_type in (
            "structure",
            "schema",
            "tenant_context",
            "permissions",
            "version",
            "file_relationship",
        ):
            self.assertIn(
                check_type, checks,
                f"validation_checks must include '{check_type}'",
            )

    def test_validate_with_datasets_rule_execution_context(self):
        """Test validate method with DatasetsRuleExecutionContext"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        context = DatasetsRuleExecutionContext(
            dataset=dataset, tenant=self.tenant, user=self.user, file=self.file
        )

        result = self.rules.validate(context=context)
        self.assertTrue(result.is_valid)

    def test_validate_structure_only(self):
        """Test validate method with structure validation only"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertTrue(result.is_valid)

    def test_validate_structure_only_includes_structure_check(self):
        """Test validate method with structure validation only includes structure check"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertIn("structure", result.details["validation_checks"])

    def test_validate_structure_only_excludes_schema_check(self):
        """Test validate method with structure validation only excludes schema check"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertNotIn("schema", result.details["validation_checks"])

    def test_validate_schema_only(self):
        """Test validate method with schema validation only"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={"fields": [{"name": "id", "type": "string"}]},
        )

        result = self.rules.validate(dataset=dataset, validation_type="schema")
        self.assertTrue(result.is_valid)
        self.assertIn("schema", result.details["validation_checks"])
        self.assertNotIn("structure", result.details["validation_checks"])

    def test_validate_structure_missing_tenant(self):
        """Test structure validation with missing tenant"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )
        # Remove tenant (this shouldn't happen in practice, but test the validation)
        dataset.tenant = None

        result = self.rules._validate_dataset_structure(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("Dataset must have a tenant", result.errors)

    def test_validate_structure_missing_file(self):
        """Test structure validation with missing file"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )
        # Remove file (this shouldn't happen in practice, but test the validation)
        dataset.file = None

        result = self.rules._validate_dataset_structure(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("Dataset must have a file", result.errors)

    def test_validate_structure_invalid_format(self):
        """Test structure validation with invalid format"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="INVALID", version=1
        )

        result = self.rules._validate_dataset_structure(dataset)
        self.assertTrue(result.is_valid)  # Warning only, not error
        self.assertIn("not a standard format", result.warnings[0])

    def test_validate_structure_invalid_version(self):
        """Test structure validation with invalid version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=0,  # Invalid version
        )

        result = self.rules._validate_dataset_structure(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("version must be a positive integer", result.errors[0])

    def test_validate_schema_valid(self):
        """Test schema validation with valid schema"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
        )

        result = self.rules._validate_dataset_schema(dataset)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["schema_valid"])
        self.assertEqual(result.details["fields_count"], 2)

    def test_validate_schema_no_schema(self):
        """Test schema validation with no schema"""
        # Create dataset and explicitly set schema_json to None
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json=None,  # Explicitly set to None
        )
        # Override the default schema_json that factory might set
        dataset.schema_json = None
        dataset.save()

        result = self.rules._validate_dataset_schema(dataset)
        self.assertTrue(result.is_valid)  # Not an error if no schema
        self.assertTrue(len(result.warnings) > 0)
        self.assertIn("no schema_json", result.warnings[0])

    def test_validate_schema_invalid_structure(self):
        """Test schema validation with invalid schema structure"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json="not a dict",  # Invalid structure
        )

        result = self.rules._validate_dataset_schema(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a dictionary", result.errors[0])

    def test_validate_schema_missing_fields(self):
        """Test schema validation with missing fields"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={},  # Missing fields
        )

        result = self.rules._validate_dataset_schema(dataset)
        self.assertTrue(result.is_valid)  # Warning only
        self.assertIn("missing 'fields' key", result.warnings[0])

    def test_validate_schema_invalid_fields(self):
        """Test schema validation with invalid fields"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={"fields": "not a list"},  # Invalid fields
        )

        result = self.rules._validate_dataset_schema(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a list", result.errors[0])

    def test_validate_schema_field_missing_name(self):
        """Test schema validation with field missing name"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=1,
            schema_json={"fields": [{"type": "string"}]},  # Missing name
        )

        result = self.rules._validate_dataset_schema(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("missing required 'name' property", result.errors[0])

    def test_validate_tenant_context_valid(self):
        """Test tenant context validation with matching tenants"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_tenant_context(dataset, tenant=self.tenant)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["tenants_match"])

    def test_validate_tenant_context_mismatch(self):
        """Test tenant context validation with mismatched tenants"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_tenant_context(dataset, tenant=other_tenant)
        self.assertFalse(result.is_valid)
        self.assertIn("does not match", result.errors[0])

    def test_validate_permissions_valid(self):
        """Test permissions validation with matching tenant"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_permissions(dataset, user=self.user)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["access_allowed"])

    def test_validate_permissions_no_user(self):
        """Test permissions validation without user"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_permissions(dataset, user=None)
        self.assertTrue(result.is_valid)  # Not an error if no user
        self.assertIn("User not provided", result.warnings[0])

    def test_validate_permissions_tenant_mismatch(self):
        """Test permissions validation with tenant mismatch"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{_uid}@example.com", password="testpass123", tenant=other_tenant
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_permissions(dataset, user=other_user)
        # Cross-tenant access requires ABAC policy or access request
        # Without either, access should be denied
        self.assertFalse(result.is_valid)
        self.assertIn("does not have", result.errors[0])
        self.assertTrue(result.details["tenant_isolation"]["cross_tenant"])

    def test_validate_version_valid(self):
        """Test version validation with valid version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_dataset_version(dataset)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["version_valid"])

    def test_validate_version_invalid(self):
        """Test version validation with invalid version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            version=0,  # Invalid
        )

        result = self.rules._validate_dataset_version(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a positive integer", result.errors[0])

    def test_validate_file_relationship_valid(self):
        """Test file relationship validation with matching file"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_file_relationship(dataset, file=self.file)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["files_match"])

    def test_validate_file_relationship_mismatch(self):
        """Test file relationship validation with mismatched file"""
        other_file = File.objects.create(
            tenant=self.tenant,
            name="other.csv",
            size=2000,
            content_type="text/csv",
            storage_path="/test/other.csv",
            status=FileStatus.ACTIVE,
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules._validate_file_relationship(dataset, file=other_file)
        self.assertFalse(result.is_valid)
        self.assertIn("does not match", result.errors[0])

    # ========== FILE SCAN STATUS GATING (Phase 260.2.D) ==========

    def test_validate_structure_blocks_infected_file(self):
        """Structure validation rejects a dataset whose source file has
        scan_status=INFECTED."""
        infected_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="infected.csv",
            content_type="text/csv",
            size=10,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.INFECTED,
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=infected_file, format="CSV", version=1
        )
        result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertFalse(
            result.is_valid,
            "Structure validation must reject dataset on INFECTED file",
        )
        self.assertTrue(
            any("infected" in e.lower() for e in result.errors),
            f"Errors must mention infected/malware; got {result.errors}",
        )

    def test_validate_structure_blocks_pending_scan_when_clamav_enabled(self):
        """Structure validation rejects a dataset whose source file has
        scan_status=PENDING_SCAN when CLAMAV is enabled."""
        from django.test import override_settings

        pending_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="pending_scan.csv",
            content_type="text/csv",
            size=10,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.PENDING_SCAN,
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=pending_file, format="CSV", version=1
        )
        with override_settings(CLAMAV_ENABLED=True):
            result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertFalse(
            result.is_valid,
            "Structure validation must reject dataset on PENDING_SCAN file "
            "when CLAMAV_ENABLED is True",
        )
        self.assertTrue(
            any("pending" in e.lower() for e in result.errors),
            f"Errors must mention pending scan; got {result.errors}",
        )

    # ========== FILE_ACTIVE VALIDATION (Phase 260.5.B) ==========

    def test_validate_file_active_rejects_pending_file(self):
        """file_active validation rejects a PENDING file."""
        pending_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="pending_upload.csv",
            content_type="text/csv",
            size=10,
            status=FileStatus.PENDING,
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=pending_file, format="CSV", version=1
        )
        result = self.rules.validate(
            dataset=dataset, file=pending_file, validation_type="file_active"
        )
        self.assertFalse(
            result.is_valid,
            "file_active validation must reject a PENDING file",
        )
        self.assertIn("file_active", result.details["validation_checks"])
        self.assertFalse(
            result.details["validation_checks"]["file_active"].get("admitted", True),
            "PENDING file must not be admitted for dataset creation",
        )

    # ========== FORMAT-MISMATCH WARNING ==========

    def test_validate_structure_warns_format_mismatch(self):
        """Structure validation warns when dataset format disagrees with
        the file extension."""
        mismatch_file = File.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="data.json",
            content_type="application/json",
            size=10,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
        )
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=mismatch_file, format="CSV", version=1
        )
        result = self.rules._validate_dataset_structure(dataset)
        self.assertTrue(
            any("may not match" in w.lower() for w in result.warnings),
            f"Warnings must include format-mismatch hint; got {result.warnings}",
        )
        self.assertFalse(
            result.details.get("format_matches_file", True),
            "format_matches_file must be False when CSV format is set on a .json file",
        )


class DatasetsBusinessRulesSchemaValidationTest(DatasetsTestBase):
    """Test comprehensive dataset schema validation"""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_schema_structure_validation_valid(self):
        """Test schema structure validation with valid schema"""
        schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }

        result = self.rules._validate_schema_structure(schema)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details["has_valid_structure"])

    def test_schema_structure_validation_invalid_dict(self):
        """Test schema structure validation with invalid structure"""
        schema = "not a dict"

        result = self.rules._validate_schema_structure(schema)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a dictionary", result.errors[0])

    def test_schema_structure_validation_missing_fields(self):
        """Test schema structure validation with missing fields key"""
        schema = {"other_key": "value"}

        result = self.rules._validate_schema_structure(schema)
        self.assertTrue(result.is_valid)  # Warning only
        self.assertIn("missing 'fields' key", result.warnings[0])

    def test_schema_structure_validation_invalid_fields_type(self):
        """Test schema structure validation with invalid fields type"""
        schema = {"fields": "not a list"}

        result = self.rules._validate_schema_structure(schema)
        self.assertFalse(result.is_valid)
        self.assertIn("must be a list", result.errors[0])

    def test_schema_fields_validation_valid(self):
        """Test schema fields validation with valid fields"""
        schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "data_type": "integer", "nullable": True},
            ]
        }

        result = self.rules._validate_schema_fields(schema)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.details["fields_count"], 2)
        self.assertEqual(result.details["valid_fields"], 2)

    def test_schema_fields_validation_missing_name(self):
        """Test schema fields validation with missing name"""
        schema = {"fields": [{"type": "string"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertFalse(result.is_valid)
        self.assertIn("missing required 'name' property", result.errors[0])

    def test_schema_fields_validation_invalid_name(self):
        """Test schema fields validation with invalid name"""
        schema = {"fields": [{"name": "", "type": "string"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertFalse(result.is_valid)
        self.assertIn("invalid name", result.errors[0])

    def test_schema_fields_validation_duplicate_names(self):
        """Test schema fields validation with duplicate field names"""
        schema = {"fields": [{"name": "id", "type": "string"}, {"name": "id", "type": "integer"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertFalse(result.is_valid)
        self.assertIn("Duplicate field name", result.errors[0])

    def test_schema_fields_validation_missing_type(self):
        """Test schema fields validation with missing type"""
        schema = {"fields": [{"name": "id"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertTrue(result.is_valid)  # Warning only
        self.assertIn("missing 'type' or 'data_type' property", result.warnings[0])

    def test_schema_fields_validation_invalid_type(self):
        """Test schema fields validation with invalid data type"""
        schema = {"fields": [{"name": "id", "type": "invalid_type"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertTrue(result.is_valid)  # Warning only
        self.assertIn("unrecognized data type", result.warnings[0])

    def test_schema_fields_validation_invalid_nullable(self):
        """Test schema fields validation with invalid nullable"""
        schema = {"fields": [{"name": "id", "type": "string", "nullable": "yes"}]}

        result = self.rules._validate_schema_fields(schema)
        self.assertTrue(result.is_valid)  # Warning only
        self.assertIn("non-boolean 'nullable' property", result.warnings[0])

    def test_schema_version_compatibility_fully_compatible(self):
        """Test schema version compatibility with fully compatible schemas"""
        previous_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}
        current_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_version_compatibility(
            previous_dataset, current_dataset
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["compatibility_level"], "FULLY_COMPATIBLE")
        self.assertTrue(result.details["version_compatible"])

    def test_schema_version_compatibility_backward_compatible(self):
        """Test schema version compatibility with backward compatible schemas"""
        previous_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}
        current_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_version_compatibility(
            previous_dataset, current_dataset
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["compatibility_level"], "BACKWARD_COMPATIBLE")
        self.assertTrue(result.details["version_compatible"])

    def test_schema_version_compatibility_incompatible(self):
        """Test schema version compatibility with incompatible schemas"""
        previous_schema = {"fields": [{"name": "id", "data_type": "string", "nullable": False}]}
        current_schema = {"fields": [{"name": "id", "data_type": "integer", "nullable": False}]}

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_version_compatibility(
            previous_dataset, current_dataset
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.details["compatibility_level"], "INCOMPATIBLE")
        self.assertFalse(result.details["version_compatible"])
        self.assertIn("incompatible", result.errors[0])

    def test_schema_version_compatibility_no_previous_schema(self):
        """Test schema version compatibility when previous has no schema"""
        current_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}

        # Create previous dataset without schema (factory sets default, so we need to clear it)
        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )
        previous_dataset.schema_json = None
        previous_dataset.save()

        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_version_compatibility(
            previous_dataset, current_dataset
        )
        self.assertTrue(result.is_valid)
        # Check that warning mentions no schema
        self.assertTrue(any("no schema" in w.lower() for w in result.warnings))

    def test_schema_evolution_backward_compatible(self):
        """Test schema evolution validation with backward compatible changes"""
        previous_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}
        current_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_evolution(previous_dataset, current_dataset)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["backward_compatible"])
        self.assertTrue(result.details["evolution_valid"])

    def test_schema_evolution_breaking_changes(self):
        """Test schema evolution validation with breaking changes"""
        previous_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }
        current_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules._validate_schema_evolution(previous_dataset, current_dataset)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details["backward_compatible"])
        self.assertFalse(result.details["evolution_valid"])
        self.assertIn("breaking changes", result.errors[0])

    def test_validate_dataset_schema_complete(self):
        """Test complete dataset schema validation"""
        schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=schema
        )

        result = self.rules.validate_dataset_schema(dataset)
        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)
        self.assertIn("structure", result.details["validation_checks"])
        self.assertIn("fields", result.details["validation_checks"])

    def test_validate_dataset_schema_with_previous_version(self):
        """Test dataset schema validation with previous version"""
        previous_schema = {"fields": [{"name": "id", "type": "string", "nullable": False}]}
        current_schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }

        previous_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=previous_schema
        )
        current_dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=2, schema_json=current_schema
        )

        result = self.rules.validate_dataset_schema(
            current_dataset, previous_dataset=previous_dataset
        )
        self.assertTrue(result.is_valid)
        self.assertIn("validation_checks", result.details)
        self.assertIn("version_compatibility", result.details["validation_checks"])
        self.assertIn("evolution", result.details["validation_checks"])


class DatasetsBusinessRulesSchemaValidationIntegrationTest(DatasetsTestBase):
    """Integration tests for schema validation via DatasetsBusinessRules.

    Validates schema structure and field validation through the business
    rules layer using factory-created datasets (does NOT go through
    DatasetService — the DatasetService integration is tested elsewhere)."""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_dataset_service_with_schema_validation(self):
        """Test DatasetService.create_dataset with schema validation"""
        schema = {
            "fields": [
                {"name": "id", "type": "string", "nullable": False},
                {"name": "value", "type": "integer", "nullable": True},
            ]
        }

        # Create dataset directly (DatasetService may have different interface)
        # Then validate schema
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=schema
        )

        # Validate schema
        result = self.rules.validate_dataset_schema(dataset)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details["fields_count"], 2)
        self.assertIn("validation_checks", result.details)
        self.assertIn("structure", result.details["validation_checks"])
        self.assertIn("fields", result.details["validation_checks"])

    def test_dataset_service_with_invalid_schema(self):
        """Test DatasetService with invalid schema"""
        invalid_schema = {"fields": [{"type": "string"}]}  # Missing name

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1, schema_json=invalid_schema
        )

        # Validate schema - should fail
        result = self.rules.validate_dataset_schema(dataset)
        self.assertFalse(result.is_valid)
        self.assertIn("missing required 'name' property", result.errors[0])


class DatasetsBusinessRulesVersioningTest(DatasetsTestBase):
    """Test cases for dataset versioning validation methods."""
    _needs_storage = False

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.rules = DatasetsBusinessRules(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create asset
        self.asset = AssetFactory.create_asset(
            tenant=self.tenant, created_by=self.user, status="DRAFT"
        )

    def test_validate_version_number_valid(self):
        """Test version number validation with valid semantic version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        result = self.rules.validate_version_number(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertIn("version_validation", result.details)
        self.assertTrue(result.details["version_validation"]["format_valid"])

    def test_validate_version_number_invalid_format(self):
        """Test version number validation with invalid format"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="invalid",
        )

        result = self.rules.validate_version_number(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Invalid semantic version format" in error for error in result.errors))

    def test_validate_version_number_missing(self):
        """Test version number validation with missing semantic version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version=None,
        )

        result = self.rules.validate_version_number(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # Missing version is a warning, not error
        self.assertTrue(
            any("Semantic version is not set" in warning for warning in result.warnings)
        )

    def test_validate_version_number_zero_version(self):
        """Test version number validation with 0.0.0"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="0.0.0",
        )

        result = self.rules.validate_version_number(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # Valid but warning
        self.assertTrue(any("0.0.0" in warning for warning in result.warnings))

    def test_validate_version_number_raises_on_error(self):
        """Test that validate_version_number raises exception when raise_on_error=True"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="invalid",
        )

        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.rules.validate_version_number(dataset, raise_on_error=True)

        self.assertEqual(context.exception.code, "INVALID_SEMANTIC_VERSION")

    def test_validate_version_compatibility_no_parent(self):
        """Test version compatibility validation with no parent version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        result = self.rules.validate_version_compatibility(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["compatibility_checks"]["has_parent"])

    def test_validate_version_compatibility_valid_increment(self):
        """Test version compatibility validation with valid version increment"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            parent_version=parent,
        )

        result = self.rules.validate_version_compatibility(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["compatibility_checks"]["compatibility_valid"])

    def test_validate_version_compatibility_version_regression(self):
        """Test version compatibility validation with version regression"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="2.0.0",
        )

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.0.0",  # Regression
            parent_version=parent,
        )

        result = self.rules.validate_version_compatibility(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Version regression" in error for error in result.errors))

    def test_validate_version_compatibility_breaking_change_no_major_bump(self):
        """Test version compatibility validation with breaking change without major version bump"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
        )

        # Breaking change: remove field
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.1.0",  # Minor bump, but breaking change
            parent_version=parent,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                    # name field removed - breaking change
                ]
            },
        )

        result = self.rules.validate_version_compatibility(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("Breaking changes detected" in error for error in result.errors))

    def test_validate_version_compatibility_breaking_change_with_major_bump(self):
        """Test version compatibility validation with breaking change and major version bump"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                ]
            },
        )

        # Breaking change: remove field, but major version bump
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="2.0.0",  # Major bump
            parent_version=parent,
            schema_json={
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                    # name field removed - breaking change
                ]
            },
        )

        result = self.rules.validate_version_compatibility(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["compatibility_checks"]["breaking_change_handled"])

    def test_validate_version_creation_unique(self):
        """Test version creation validation with unique version"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        result = self.rules.validate_version_creation(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.details["creation_checks"]["version_unique"])

    def test_validate_version_creation_duplicate_version(self):
        """Test version creation validation with duplicate version number"""
        DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        # Create a new dataset instance with duplicate version (without saving)
        # This simulates what would happen if we tried to create a duplicate
        dataset = Dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,  # Duplicate version
            semantic_version="1.1.0",
        )
        # Don't save - just validate the creation logic
        result = self.rules.validate_version_creation(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("already exists" in error for error in result.errors))

    def test_validate_version_creation_duplicate_semantic_version(self):
        """Test version creation validation with duplicate semantic version"""
        DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.0.0",  # Duplicate semantic version
        )

        result = self.rules.validate_version_creation(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any(
                "Semantic version" in error and "already exists" in error for error in result.errors
            )
        )

    def test_validate_version_creation_version_increment(self):
        """Test version creation validation with invalid version increment"""
        DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.0.0",
        )

        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,  # Less than existing version
            semantic_version="1.1.0",
        )

        result = self.rules.validate_version_creation(dataset, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("must be greater than latest version" in error for error in result.errors)
        )

    def test_validate_version_creation_no_asset(self):
        """Test version creation validation without asset"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=None,  # No asset
            format="CSV",
            version=1,
            semantic_version="1.0.0",
        )

        result = self.rules.validate_version_creation(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # No asset means no uniqueness check
        self.assertTrue(
            any("not associated with an asset" in warning for warning in result.warnings)
        )

    def test_validate_version_deletion_no_references(self):
        """Test version deletion validation with no references"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=False,
        )

        result = self.rules.validate_version_deletion(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)
        self.assertFalse(result.details["deletion_checks"]["has_child_versions"])
        self.assertFalse(result.details["deletion_checks"]["is_current"])

    def test_validate_version_deletion_with_child_versions(self):
        """Test version deletion validation with child versions"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=False,
        )

        # Create child version
        DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            parent_version=parent,
            is_current=True,
        )

        result = self.rules.validate_version_deletion(parent, raise_on_error=False)

        self.assertFalse(result.is_valid)
        self.assertTrue(any("child version" in error.lower() for error in result.errors))
        self.assertTrue(result.details["deletion_checks"]["has_child_versions"])

    def test_validate_version_deletion_is_current(self):
        """Test version deletion validation when version is current (warning, not blocker)"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=True,
        )

        result = self.rules.validate_version_deletion(dataset, raise_on_error=False)

        # is_current is a warning only; deletion is still valid (can unset before delete)
        self.assertTrue(result.is_valid)
        self.assertTrue(
            any("current" in w.lower() for w in result.warnings),
            f"Expected warning about current version, got: {result.warnings}",
        )
        self.assertTrue(result.details["deletion_checks"]["is_current"])

    def test_validate_version_deletion_with_classifications(self):
        """Test version deletion validation with data classifications"""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=False,
        )

        # Create classification
        from hub.apps.governance.models import (
            ClassificationCategory,
            ClassificationStatus,
            DataClassification,
        )

        DataClassification.objects.create(
            tenant=self.tenant,
            dataset=dataset,
            category=ClassificationCategory.PUBLIC,
            status=ClassificationStatus.AUTO_CLASSIFIED,
            created_by=self.user,
        )

        result = self.rules.validate_version_deletion(dataset, raise_on_error=False)

        self.assertTrue(result.is_valid)  # Classifications are warnings, not errors
        self.assertTrue(any("classification" in warning.lower() for warning in result.warnings))
        self.assertTrue(result.details["deletion_checks"]["has_classifications"])

    def test_validate_version_deletion_raises_on_error(self):
        """Test that validate_version_deletion raises exception when raise_on_error=True"""
        parent = DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=1,
            semantic_version="1.0.0",
            is_current=False,
        )
        DatasetFactory.create_dataset(
            tenant=self.tenant,
            file=self.file,
            asset=self.asset,
            format="CSV",
            version=2,
            semantic_version="1.1.0",
            parent_version=parent,
            is_current=True,
        )

        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as context:
            self.rules.validate_version_deletion(parent, raise_on_error=True)
        self.assertEqual(context.exception.code, "VERSION_DELETION_FAILED")

    # ========== ERROR HANDLING ==========

    def test_validate_persisted_dataset(self):
        """Test that validate handles persisted datasets without raising."""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate(dataset=dataset, validation_type="structure")
        self.assertIsNotNone(
            result, "validate on a persisted dataset must return a ValidationResult"
        )
        self.assertTrue(
            result.is_valid,
            "Persisted dataset with valid structure must validate: "
            f"errors={result.errors}",
        )
        self.assertIn("validation_checks", result.details)
        self.assertIn("structure", result.details["validation_checks"])

    def test_validate_error_handling_invalid_dataset(self):
        """Test error handling with a non-persisted Dataset.

        A Dataset that exists only in-memory (no DB row) lacks a file
        FK and a format value, so structure validation must return
        is_valid=False with material errors about missing fields —
        not crash with an ORM exception."""
        import uuid

        fake_dataset = Dataset(id=uuid.uuid4(), tenant=self.tenant)

        result = self.rules.validate(dataset=fake_dataset, validation_type="structure")
        self.assertIsNotNone(
            result, "Validate on non-persisted dataset must return a ValidationResult"
        )
        self.assertFalse(
            result.is_valid,
            "Non-persisted Dataset must fail structure validation; "
            f"got is_valid=True, errors={result.errors}",
        )
        self.assertGreater(
            len(result.errors), 0,
            "Must return at least one validation error (missing file, missing format, etc.)",
        )

    def test_validate_error_handling_none_dataset(self):
        """Test error handling with None dataset"""
        # Validate(None) must return a result without crashing
        result = self.rules.validate(None, validation_type="structure")
        self.assertIsNotNone(result, "validate(None) must return a ValidationResult (with errors)")
        self.assertFalse(result.is_valid, "validate(None) must return is_valid=False")
        self.assertIn("Dataset is required", result.errors[0])

    def test_validate_schema_with_persisted_dataset(self):
        """Test that schema validation handles persisted datasets without raising."""
        dataset = DatasetFactory.create_dataset(
            tenant=self.tenant, file=self.file, format="CSV", version=1
        )

        result = self.rules.validate_dataset_schema(dataset)
        self.assertIsNotNone(
            result, "validate_dataset_schema on a persisted dataset must return a ValidationResult"
        )
        self.assertTrue(
            result.is_valid,
            "Persisted dataset with schema must produce a valid result; "
            f"errors={result.errors}, warnings={result.warnings}",
        )
        self.assertIn("validation_checks", result.details)
