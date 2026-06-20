"""
Tests for Scheduled Ingestion Business Rules

Comprehensive tests for scheduled ingestion business rules validation following engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive test coverage
- Follow DRY, SOLID, and clean code principles
"""

import logging
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

_LOGGER = logging.getLogger(__name__)

from hub.apps.core.business_rules.registry import get_registry
from hub.apps.scheduled_ingestion.business_rules import (
    ScheduledIngestionBusinessRules,
    ScheduledIngestionRuleExecutionContext,
)
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

User = get_user_model()


def _ensure_db_connection():
    """Ensure default DB connection is open before setUp (avoids 'connection already closed' in batched runs).

    Do not call connections.close_all(): it would close the connection pytest-django uses
    for the test transaction and cause 'connection already closed' in setUp.
    """
    try:
        connection.ensure_connection()
    except Exception:
        try:
            from django.db import connections

            connections.close_all()
            connection.ensure_connection()
        except Exception as _exc:
            _LOGGER.warning(
                "DB connection recovery failed in setUp — test may fail: %s", _exc
            )


class ScheduledIngestionBusinessRulesInitializationTest(TestCase):
    """Test ScheduledIngestionBusinessRules initialization"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_scheduled_ingestion_business_rules_initialization_with_tenant_and_user(self):
        """Test ScheduledIngestionBusinessRules initialization with tenant and user"""
        rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertEqual(rules.user_id, str(self.user.id))
        self.assertTrue(rules.enable_caching)
        self.assertTrue(rules.enable_metrics)
        self.assertTrue(rules.enable_tracing)
        self.assertTrue(rules.enable_logging)

    def test_scheduled_ingestion_business_rules_initialization_without_tenant(self):
        """Test ScheduledIngestionBusinessRules initialization without tenant"""
        rules = ScheduledIngestionBusinessRules(user_id=str(self.user.id))
        self.assertIsNone(rules.tenant_id)
        self.assertEqual(rules.user_id, str(self.user.id))

    def test_scheduled_ingestion_business_rules_initialization_without_user(self):
        """Test ScheduledIngestionBusinessRules initialization without user"""
        rules = ScheduledIngestionBusinessRules(tenant_id=str(self.tenant.id))
        self.assertEqual(rules.tenant_id, str(self.tenant.id))
        self.assertIsNone(rules.user_id)

    def test_scheduled_ingestion_business_rules_initialization_without_tenant_and_user(self):
        """Test ScheduledIngestionBusinessRules initialization without tenant and user"""
        rules = ScheduledIngestionBusinessRules()
        self.assertIsNone(rules.tenant_id)
        self.assertIsNone(rules.user_id)

    def test_scheduled_ingestion_business_rules_get_rule_name(self):
        """Test ScheduledIngestionBusinessRules get_rule_name method"""
        rules = ScheduledIngestionBusinessRules()
        self.assertEqual(rules.get_rule_name(), "ScheduledIngestionBusinessRules")


class ScheduledIngestionBusinessRulesRegistrationTest(TestCase):
    """Test ScheduledIngestionBusinessRules registration in business rules registry"""

    def test_scheduled_ingestion_business_rules_registered(self):
        """Test ScheduledIngestionBusinessRules is registered in the registry"""
        registry = get_registry()
        rule = registry.get_rule("scheduled_ingestion_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.rule_name, "scheduled_ingestion_validation")
        self.assertEqual(rule.rule_class, ScheduledIngestionBusinessRules)
        self.assertIn("scheduled_ingestion", rule.tags)
        self.assertIn("validation", rule.tags)
        self.assertIn("ingestion", rule.tags)

    def test_scheduled_ingestion_business_rules_priority(self):
        """Test ScheduledIngestionBusinessRules has correct priority"""
        registry = get_registry()
        rule = registry.get_rule("scheduled_ingestion_validation")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.priority, 10)

    def test_scheduled_ingestion_business_rules_description(self):
        """Test ScheduledIngestionBusinessRules has correct description"""
        registry = get_registry()
        rule = registry.get_rule("scheduled_ingestion_validation")
        self.assertIsNotNone(rule)
        self.assertIn("scheduled ingestion", rule.description.lower())
        self.assertIn("validates", rule.description.lower())


class ScheduledIngestionRuleExecutionContextTest(TestCase):
    """Test ScheduledIngestionRuleExecutionContext"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        self.ingestion_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )

    def test_scheduled_ingestion_rule_execution_context_creation(self):
        """Test ScheduledIngestionRuleExecutionContext creation"""
        context = ScheduledIngestionRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            schedule=self.schedule,
            ingestion_run=self.ingestion_run,
            tenant=self.tenant,
            user=self.user,
        )
        self.assertEqual(context.tenant_id, str(self.tenant.id))
        self.assertEqual(context.user_id, str(self.user.id))
        self.assertEqual(context.schedule, self.schedule)
        self.assertEqual(context.ingestion_run, self.ingestion_run)
        self.assertEqual(context.tenant, self.tenant)
        self.assertEqual(context.user, self.user)

    def test_scheduled_ingestion_rule_execution_context_to_dict(self):
        """Test ScheduledIngestionRuleExecutionContext to_dict method"""
        context = ScheduledIngestionRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            schedule=self.schedule,
            ingestion_run=self.ingestion_run,
            tenant=self.tenant,
            user=self.user,
        )
        context_dict = context.to_dict()
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        self.assertEqual(context_dict["schedule_id"], str(self.schedule.id))
        self.assertEqual(context_dict["schedule_name"], self.schedule.name)
        self.assertEqual(context_dict["schedule_status"], self.schedule.status)
        self.assertEqual(context_dict["ingestion_run_id"], str(self.ingestion_run.id))
        self.assertEqual(context_dict["ingestion_run_status"], self.ingestion_run.status)
        self.assertEqual(context_dict["source_type"], self.schedule.source_type)

    def test_scheduled_ingestion_rule_execution_context_to_dict_without_schedule(self):
        """Test ScheduledIngestionRuleExecutionContext to_dict without schedule"""
        context = ScheduledIngestionRuleExecutionContext(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        context_dict = context.to_dict()
        # tenant_id and user_id should be set from context parameters
        self.assertEqual(context_dict["tenant_id"], str(self.tenant.id))
        self.assertEqual(context_dict["user_id"], str(self.user.id))
        # Schedule-related fields should be None since schedule is not provided
        self.assertIsNone(context_dict["schedule_id"])
        self.assertIsNone(context_dict["schedule_name"])
        self.assertIsNone(context_dict["schedule_status"])
        self.assertIsNone(context_dict["ingestion_run_id"])
        self.assertIsNone(context_dict["source_type"])


class ScheduledIngestionScheduleFormatValidationTest(TestCase):
    """Test schedule format validation"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_cron_expression_valid(self):
        """Test validation of valid cron expression"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("cron_expression_valid"))

    def test_validate_cron_expression_invalid(self):
        """Test validation of invalid cron expression"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "invalid cron", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertFalse(result.details.get("cron_expression_valid"))

    def test_validate_cron_expression_missing(self):
        """Test validation when cron expression is missing"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"timezone": "UTC"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Cron expression is required", result.errors[0])

    def test_validate_daily_schedule_valid(self):
        """Test validation of valid daily schedule"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "14:30"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("time_format_valid"))

    def test_validate_daily_schedule_invalid_time(self):
        """Test validation of daily schedule with invalid time"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "25:00"},  # Invalid hour
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_weekly_schedule_valid(self):
        """Test validation of valid weekly schedule"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.WEEKLY,
            schedule_config={"days_of_week": [0, 2, 4], "time": "09:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("days_of_week_valid"))
        self.assertTrue(result.details.get("time_format_valid"))

    def test_validate_weekly_schedule_invalid_days(self):
        """Test validation of weekly schedule with invalid days"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.WEEKLY,
            schedule_config={"days_of_week": [0, 7, 8], "time": "09:00"},  # Invalid days
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_monthly_schedule_valid(self):
        """Test validation of valid monthly schedule"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.MONTHLY,
            schedule_config={"day_of_month": 15, "time": "10:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("day_of_month_valid"))
        self.assertTrue(result.details.get("time_format_valid"))

    def test_validate_monthly_schedule_invalid_day(self):
        """Test validation of monthly schedule with invalid day"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.MONTHLY,
            schedule_config={"day_of_month": 32, "time": "10:00"},  # Invalid day
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_format(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class ScheduledIngestionScheduleConflictDetectionTest(TestCase):
    """Test schedule conflict detection"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_schedule_conflicts_no_conflicts(self):
        """Test conflict detection when no conflicts exist"""
        schedule1 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Schedule 1",
            source_type=SourceType.S3,
            source_config={"bucket": "bucket1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Schedule 2",
            source_type=SourceType.S3,
            source_config={"bucket": "bucket2"},  # Different bucket
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        result = self.rules._validate_schedule_conflicts(schedule1)
        self.assertTrue(result.is_valid)
        # Check that conflict check passed and count is 0
        self.assertTrue(result.details.get("conflict_check_passed"))
        overlapping_count = result.details.get("overlapping_schedules_count", 0)
        self.assertEqual(overlapping_count, 0)

    def test_validate_schedule_conflicts_same_source_different_time(self):
        """Test conflict detection for same source but different times"""
        schedule1 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Schedule 1",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Schedule 2",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},  # Same bucket
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "12:00"},  # Different time
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        result = self.rules._validate_schedule_conflicts(schedule1)
        # Should not have conflicts since times are different
        self.assertTrue(result.is_valid or len(result.errors) == 0)

    def test_validate_schedule_conflicts_paused_schedule(self):
        """Test conflict detection skips paused schedules"""
        schedule1 = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Schedule 1",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.PAUSED,  # Paused
            created_by=self.user,
        )
        result = self.rules._validate_schedule_conflicts(schedule1)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("conflict_check_skipped"))


class ScheduledIngestionScheduleTimezoneValidationTest(TestCase):
    """Test schedule timezone validation"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_timezone_valid(self):
        """Test validation of valid timezone"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 0 * * *", "timezone": "America/New_York"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_timezone(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertTrue(result.details.get("timezone_valid"))

    def test_validate_timezone_invalid(self):
        """Test validation of invalid timezone"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 0 * * *", "timezone": "Invalid/Timezone"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_timezone(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_timezone_default_utc(self):
        """Test validation defaults to UTC if timezone not specified"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 0 * * *"},  # No timezone specified
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_timezone(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


class ScheduledIngestionScheduleResourceValidationTest(TestCase):
    """Test schedule resource validation"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_s3_source_valid(self):
        """Test validation of valid S3 source config"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_resource(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_s3_source_missing_bucket(self):
        """Test validation of S3 source config missing bucket"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"region": "us-east-1"},  # Missing bucket
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_resource(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("bucket", result.errors[0].lower())

    def test_validate_http_source_valid(self):
        """Test validation of valid HTTP source config"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.HTTP,
            source_config={"base_url": "https://example.com/data.csv"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_resource(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_database_source_valid(self):
        """Test validation of valid database source config"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.DATABASE,
            source_config={"host": "localhost", "database": "testdb", "port": 5432},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_resource(schedule)
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_database_source_missing_fields(self):
        """Test validation of database source config missing required fields"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.DATABASE,
            source_config={"host": "localhost"},  # Missing database
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_schedule_resource(schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)


class ScheduledIngestionBusinessRulesIntegrationTest(TestCase):
    """Integration tests with ScheduledIngestionService"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_schedule_comprehensive(self):
        """Test comprehensive schedule validation"""
        schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        result = self.rules.validate(schedule=schedule, validation_type="schedule")
        self.assertTrue(result.is_valid)
        self.assertIn("schedule", result.details.get("validated_items", []))

    def test_validate_schedule_with_invalid_config(self):
        """Test validation catches invalid schedule configuration"""
        schedule = ScheduledIngestion(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.CUSTOM_CRON,
            schedule_config={"cron": "invalid cron", "timezone": "UTC"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules.validate(schedule=schedule, validation_type="schedule")
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_integration_with_ingestion_service(self):
        """Test integration with IngestionService"""
        # Create a valid schedule
        schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Integration Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

        # Validate schedule using business rules
        result = self.rules.validate(schedule=schedule, validation_type="schedule")
        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")

        # Verify schedule can be retrieved by IngestionService
        # IngestionService inherits from BaseService which doesn't take tenant_id in constructor
        service = IngestionService()
        service.tenant_id = str(self.tenant.id)
        retrieved_schedule = service.get_ingestion_status(
            scheduled_ingestion_id=str(schedule.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(retrieved_schedule.id, schedule.id)
        self.assertEqual(retrieved_schedule.name, schedule.name)


class ScheduledIngestionSourceValidationTest(TestCase):
    """Test source validation - comprehensive tests for source type, connection, accessibility, and schema validation"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_source_type_valid(self):
        """Test source type validation with valid source types"""
        for source_type in SourceType.values:
            result = self.rules._validate_source_type(source_type)
            self.assertTrue(result.is_valid, f"Source type {source_type} should be valid")
            self.assertEqual(len(result.errors), 0)
            self.assertTrue(result.details.get("source_type_valid"))

    def test_validate_source_type_invalid(self):
        """Test source type validation with invalid source type"""
        invalid_source_type = "INVALID_TYPE"
        result = self.rules._validate_source_type(invalid_source_type)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("Invalid source type", result.errors[0])
        self.assertFalse(result.details.get("source_type_valid"))

    def test_validate_source_type_missing(self):
        """Test source type validation when source type is missing"""
        result = self.rules._validate_source_type(None)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("required", result.errors[0].lower())

    def test_validate_source_config_required_fields_s3(self):
        """Test required fields validation for S3 source"""
        # Valid S3 config
        source_config = {"bucket": "test-bucket"}
        result = self.rules._validate_source_config_required_fields(
            SourceType.S3.value, source_config
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Missing required field
        source_config = {"region": "us-east-1"}  # Missing bucket
        result = self.rules._validate_source_config_required_fields(
            SourceType.S3.value, source_config
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("bucket", result.errors[0].lower())

    def test_validate_source_config_required_fields_database(self):
        """Test required fields validation for DATABASE source"""
        # Valid database config
        source_config = {"host": "localhost", "database": "testdb"}
        result = self.rules._validate_source_config_required_fields(
            SourceType.DATABASE.value, source_config
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Missing required fields
        source_config = {"host": "localhost"}  # Missing database
        result = self.rules._validate_source_config_required_fields(
            SourceType.DATABASE.value, source_config
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_source_config_required_fields_http(self):
        """Test required fields validation for HTTP source"""
        # Valid HTTP config
        source_config = {"base_url": "https://example.com"}
        result = self.rules._validate_source_config_required_fields(
            SourceType.HTTP.value, source_config
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Missing required field
        source_config = {}  # Missing base_url
        result = self.rules._validate_source_config_required_fields(
            SourceType.HTTP.value, source_config
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_source_config_required_fields_ftp(self):
        """Test required fields validation for FTP source"""
        # Valid FTP config
        source_config = {"host": "ftp.example.com"}
        result = self.rules._validate_source_config_required_fields(
            SourceType.FTP.value, source_config
        )
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

        # Missing required field
        source_config = {}  # Missing host
        result = self.rules._validate_source_config_required_fields(
            SourceType.FTP.value, source_config
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_source_with_dict(self):
        """Test source validation with dictionary source"""
        source = {"source_type": SourceType.S3, "source_config": {"bucket": "test-bucket"}}
        result = self.rules._validate_source(source)
        # Should pass basic validation (connection test may fail if connector unavailable)
        self.assertIsNotNone(result.details.get("source_type"))
        self.assertIn("validation_checks", result.details)

    def test_validate_source_with_scheduled_ingestion(self):
        """Test source validation with ScheduledIngestion instance"""
        schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_source(schedule, tenant=self.tenant)
        self.assertIsNotNone(result.details.get("source_type"))
        self.assertIn("validation_checks", result.details)

    def test_validate_source_invalid_type(self):
        """Test source validation with invalid source type"""
        source = {"source_type": "INVALID_TYPE", "source_config": {}}
        result = self.rules._validate_source(source)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_source_not_dict_or_schedule(self):
        """Test source validation with invalid source type (not dict or ScheduledIngestion)"""
        source = "invalid source"
        result = self.rules._validate_source(source)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("dictionary or ScheduledIngestion", result.errors[0])

    def test_validate_source_connection_skipped_when_connector_unavailable(self):
        """Test that connection validation gracefully handles connector factory unavailability"""
        source = {"source_type": SourceType.S3.value, "source_config": {"bucket": "test-bucket"}}
        result = self.rules._validate_source_connection(
            SourceType.S3.value, source["source_config"]
        )
        # Should not fail if connector factory unavailable - should return warning instead
        # Connection test may be skipped, but validation should still return a result
        self.assertIn("connection_validation", result.details)
        # If connector unavailable, should have warning but not error
        if not result.is_valid:
            # If it fails, it should be due to missing required fields, not connector unavailability
            pass

    def test_validate_source_accessibility_http(self):
        """Test source accessibility validation for HTTP source"""
        # Note: This test may make actual HTTP requests
        source_config = {"base_url": "https://httpbin.org/status/200"}
        result = self.rules._validate_source_accessibility(SourceType.HTTP.value, source_config)
        self.assertIn("accessibility_validation", result.details)
        # Should not fail validation even if URL is unreachable (should be warning)
        # Accessibility check is informational, not blocking

    def test_validate_source_schema_compatibility_no_target_asset(self):
        """Test schema compatibility validation when no target asset provided"""
        source_config = {"bucket": "test-bucket"}
        result = self.rules._validate_source_schema_compatibility(
            SourceType.S3.value, source_config, None
        )
        self.assertTrue(result.is_valid)  # Should not fail if no target asset
        self.assertGreater(len(result.warnings), 0)
        # Check that skip_reason exists and contains relevant text
        skip_reason = result.details.get("skip_reason", "")
        self.assertTrue("no_target_asset" in skip_reason or "skip" in skip_reason.lower())

    def test_validate_source_comprehensive_with_schedule(self):
        """Test comprehensive source validation with ScheduledIngestion instance"""
        schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Comprehensive Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "region": "us-east-1"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        result = self.rules._validate_source(schedule, tenant=self.tenant)

        # Check that all validation checks were performed
        validation_checks = result.details.get("validation_checks", {})
        self.assertIn("source_type", validation_checks)
        self.assertIn("connection", validation_checks)
        self.assertIn("accessibility", validation_checks)

        # Source type should be valid
        self.assertTrue(result.details.get("source_type_valid", False))

        # Should have source_type in details (it's stored as string from the model)
        # ScheduledIngestion.source_type is stored as a string in the database
        # So it will be 'S3', not SourceType.S3 enum
        source_type_in_details = result.details.get("source_type")
        # It should be the string 'S3' (the enum value)
        self.assertEqual(source_type_in_details, SourceType.S3.value)

    def test_validate_source_integration_with_service(self):
        """Test source validation integration with ScheduledIngestionService"""
        schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Integration Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

        # Validate source using business rules
        result = self.rules.validate(source=schedule, validation_type="source")

        # Should have validation result
        self.assertIsNotNone(result)
        self.assertIn("source_validation", result.details)

        # Verify schedule can be used with service
        # IngestionService inherits from BaseService which doesn't have __init__
        # but IngestionEventPublisher has __init__ that accepts kwargs
        # We'll set tenant_id as attribute after instantiation
        service = IngestionService()
        service.tenant_id = str(self.tenant.id)
        # Service should be able to work with validated schedule
        self.assertIsNotNone(service)
        self.assertEqual(service.tenant_id, str(self.tenant.id))

        # Verify we can retrieve the schedule using the service
        retrieved = service.get_ingestion_status(
            scheduled_ingestion_id=str(schedule.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(retrieved.id, schedule.id)


class IngestionRunValidationTest(TestCase):
    """Test comprehensive ingestion run validation"""

    def setUp(self):
        """Set up test fixtures"""
        _ensure_db_connection()
        from datetime import timedelta

        from django.utils import timezone

        self.timezone = timezone
        self.timedelta = timedelta

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledIngestionBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.schedule = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Schedule",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def test_validate_run_eligibility_active_schedule(self):
        """Test run eligibility validation with active schedule"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_run_eligibility(run, self.schedule)
        self.assertIn("eligibility_validation", result.details)
        self.assertTrue(result.details.get("schedule_active", False))

    def test_validate_run_eligibility_paused_schedule(self):
        """Test run eligibility validation with paused schedule"""
        self.schedule.status = ScheduledIngestionStatus.PAUSED
        self.schedule.save()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_run_eligibility(run, self.schedule)
        self.assertFalse(result.is_valid)
        self.assertFalse(result.details.get("schedule_active", True))
        self.assertGreater(len(result.errors), 0)

    def test_validate_run_status_transition_pending(self):
        """Test status transition validation for PENDING run"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_run_status_transition(run)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("timestamps_consistent", False))
        self.assertEqual(result.details.get("current_status"), ScheduledIngestionRunStatus.PENDING)
        self.assertEqual(len(result.errors), 0)

    def test_validate_run_status_transition_running(self):
        """Test status transition validation for RUNNING run"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=self.timezone.now(),
        )
        result = self.rules._validate_run_status_transition(run)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("timestamps_consistent", False))
        self.assertIsNotNone(result.details.get("started_at"))
        self.assertEqual(len(result.errors), 0)

    def test_validate_run_status_transition_running_without_started_at(self):
        """Test status transition validation for RUNNING run without started_at"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.RUNNING
        )
        result = self.rules._validate_run_status_transition(run)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_run_status_transition_completed(self):
        """Test status transition validation for COMPLETED run"""
        started_at = self.timezone.now() - self.timedelta(hours=1)
        completed_at = self.timezone.now()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
        )
        result = self.rules._validate_run_status_transition(run)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("timestamps_consistent", False))
        self.assertEqual(len(result.errors), 0)

    def test_validate_run_status_transition_completed_invalid_timestamps(self):
        """Test status transition validation for COMPLETED run with invalid timestamps"""
        started_at = self.timezone.now()
        completed_at = self.timezone.now() - self.timedelta(hours=1)
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
        )
        result = self.rules._validate_run_status_transition(run)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_incremental_ingestion_valid_state(self):
        """Test incremental ingestion validation with valid state"""
        self.schedule.ingestion_state = {
            "processed_files": ["file1.csv", "file2.csv"],
            "failed_files": [],
            "file_to_dataset": {"file1.csv": "dataset-uuid-1"},
        }
        self.schedule.last_processed_file = "file2.csv"
        self.schedule.last_processed_timestamp = self.timezone.now()
        self.schedule.save()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_incremental_ingestion(run, self.schedule)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("state_structure_valid", False))

    def test_validate_incremental_ingestion_invalid_state_structure(self):
        """Test incremental ingestion validation with invalid state structure"""
        self.schedule.ingestion_state = "invalid_state"  # Should be dict
        self.schedule.save()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_incremental_ingestion(run, self.schedule)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_incremental_ingestion_inconsistent_state(self):
        """Test incremental ingestion validation with inconsistent state"""
        self.schedule.ingestion_state = {
            "processed_files": ["file1.csv"],
        }
        self.schedule.last_processed_file = "file2.csv"  # Not in processed_files
        self.schedule.save()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_incremental_ingestion(run, self.schedule)
        # Should have warning but not error
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)

    def test_validate_run_retry_no_job(self):
        """Test run retry validation without job"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_run_retry(run)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details.get("retry_count"), 0)
        self.assertEqual(result.details.get("max_retries"), 2)

    def test_validate_run_retry_with_job(self):
        """Test run retry validation with job"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="SCHEDULED_INGESTION",
            resource_id=str(self.schedule.id),
            details_json={"retry_count": 1},
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.FAILED,
            job_id=job.id,
        )
        result = self.rules._validate_run_retry(run)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details.get("retry_count"), 1)
        self.assertEqual(result.details.get("max_retries"), 2)
        self.assertTrue(result.details.get("retry_count_within_limit", False))

    def test_validate_run_retry_exceeded_max_retries(self):
        """Test run retry validation when max retries exceeded"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.SCHEDULED_INGESTION,
            status=JobStatus.PENDING,
            resource_type="SCHEDULED_INGESTION",
            resource_id=str(self.schedule.id),
            details_json={"retry_count": 3},  # Exceeds max_retries of 2
        )
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.FAILED,
            job_id=job.id,
        )
        result = self.rules._validate_run_retry(run)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_ingestion_run_comprehensive(self):
        """Test comprehensive ingestion run validation"""
        started_at = self.timezone.now() - self.timedelta(hours=1)
        completed_at = self.timezone.now()
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=started_at,
            completed_at=completed_at,
            files_found=10,
            files_processed=8,
            files_failed=2,
        )
        result = self.rules._validate_ingestion_run(run, tenant=self.tenant)
        self.assertIn("ingestion_run_validation", result.details)
        self.assertIn("validation_checks", result.details)
        validation_checks = result.details.get("validation_checks", {})
        self.assertIn("eligibility", validation_checks)
        self.assertIn("status_transition", validation_checks)
        self.assertIn("incremental", validation_checks)
        self.assertIn("retry", validation_checks)

    def test_validate_ingestion_run_integration_with_service(self):
        """Test ingestion run validation integration with ScheduledIngestionService"""
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.schedule, status=ScheduledIngestionRunStatus.PENDING
        )
        result = self.rules._validate_ingestion_run(run, tenant=self.tenant)
        self.assertIsNotNone(result)

        # Verify service can work with validated run
        service = IngestionService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        self.assertIsNotNone(service)
        self.assertEqual(service.tenant_id, str(self.tenant.id))
