"""
Unit tests for Ingestion Templates
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.scheduled_ingestion.templates import (
    IngestionTemplate,
    IngestionTemplateManager,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class IngestionTemplateTest(TestCase):
    """Test IngestionTemplate model"""

    def setUp(self):
        """Set up test fixtures (unique slug per test to avoid collisions with --reuse-db)."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_create_system_template(self):
        """Test creating system template"""
        template = IngestionTemplate.objects.create(
            name="System Template",
            description="System-wide template",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={"bucket_name": "{bucket_name}"},
            schedule_type="DAILY",
            schedule_config_template={"time": "00:00"},
            file_pattern_template="{file_pattern}",
        )

        assert template.is_system_template
        assert template.tenant is None

    def test_create_tenant_template(self):
        """Test creating tenant-specific template"""
        template = IngestionTemplate.objects.create(
            tenant=self.tenant,
            name="Tenant Template",
            description="Tenant-specific template",
            template_type="CUSTOM",
            is_system_template=False,
            source_type="S3",
            source_config_template={"bucket_name": "{bucket_name}"},
            schedule_type="DAILY",
            schedule_config_template={"time": "00:00"},
            file_pattern_template="{file_pattern}",
            created_by=self.user,
        )

        assert not template.is_system_template
        assert template.tenant == self.tenant

    def test_template_clean_system_with_tenant(self):
        """Test template validation - system template cannot have tenant"""
        template = IngestionTemplate(
            tenant=self.tenant,
            name="Invalid Template",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            template.clean()

    def test_template_clean_non_system_without_tenant(self):
        """Test template validation - non-system template must have tenant"""
        template = IngestionTemplate(
            name="Invalid Template",
            template_type="CUSTOM",
            is_system_template=False,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            template.clean()


class IngestionTemplateManagerTest(TestCase):
    """Test IngestionTemplateManager"""

    def setUp(self):
        """Set up test fixtures (unique slug per test to avoid collisions with --reuse-db)."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.template = IngestionTemplate.objects.create(
            name="S3 Daily Files",
            description="Ingest daily files from S3",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={
                "bucket_name": "{bucket_name}",
                "prefix": "{prefix}",
                "region": "{region}",
            },
            schedule_type="DAILY",
            schedule_config_template={"time": "{time}", "timezone": "{timezone}"},
            file_pattern_template="{file_pattern}",
            ingestion_config_template={
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx",
                "auto_create_asset": True,
            },
        )

    def test_create_from_template(self):
        """Test creating scheduled ingestion from template"""
        template_variables = {
            "bucket_name": "my-bucket",
            "prefix": "data/",
            "region": "us-east-1",
            "time": "00:00",
            "timezone": "UTC",
            "file_pattern": ".*\\.csv",
        }

        scheduled_ingestion = IngestionTemplateManager.create_from_template(
            template=self.template,
            name="My Ingestion",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            template_variables=template_variables,
        )

        assert scheduled_ingestion.name == "My Ingestion"
        assert scheduled_ingestion.tenant == self.tenant
        assert scheduled_ingestion.source_type == "S3"

        # Verify source config was resolved
        assert scheduled_ingestion.get_source_config()["bucket_name"] == "my-bucket"
        assert scheduled_ingestion.get_source_config()["prefix"] == "data/"
        assert scheduled_ingestion.get_source_config()["region"] == "us-east-1"

        # Verify file pattern was resolved
        assert scheduled_ingestion.file_pattern == ".*\\.csv"

        # Verify ingestion state with DQ config
        assert scheduled_ingestion.ingestion_state["enable_dq_validation"]
        assert scheduled_ingestion.ingestion_state["dq_profile_key"] == "intake_basic_gx"

    def test_resolve_template_variables(self):
        """Test resolving template variables"""
        template = {
            "bucket_name": "{bucket_name}",
            "prefix": "{prefix}",
            "nested": {"key": "{value}"},
        }

        variables = {"bucket_name": "my-bucket", "prefix": "data/", "value": "resolved"}

        resolved = IngestionTemplateManager._resolve_template_variables(template, variables)

        assert resolved["bucket_name"] == "my-bucket"
        assert resolved["prefix"] == "data/"
        assert resolved["nested"]["key"] == "resolved"

    def test_resolve_string_template(self):
        """Test resolving string template"""
        template = "s3://{bucket_name}/{prefix}{file_pattern}"

        variables = {"bucket_name": "my-bucket", "prefix": "data/", "file_pattern": ".*\\.csv"}

        resolved = IngestionTemplateManager._resolve_string_template(template, variables)

        assert resolved == "s3://my-bucket/data/.*\\.csv"

    def test_get_system_templates(self):
        """Test getting system templates"""
        # Create system template
        system_template = IngestionTemplate.objects.create(
            name="System Template",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        # Create tenant template
        tenant_template = IngestionTemplate.objects.create(
            tenant=self.tenant,
            name="Tenant Template",
            template_type="CUSTOM",
            is_system_template=False,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        system_templates = IngestionTemplateManager.get_system_templates()

        assert system_template in system_templates
        assert tenant_template not in system_templates

    def test_get_tenant_templates(self):
        """Test getting templates available to tenant"""
        # Create system template
        system_template = IngestionTemplate.objects.create(
            name="System Template",
            template_type="S3_DAILY_FILES",
            is_system_template=True,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        # Create tenant template
        tenant_template = IngestionTemplate.objects.create(
            tenant=self.tenant,
            name="Tenant Template",
            template_type="CUSTOM",
            is_system_template=False,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        # Create another tenant's template (unique slug to avoid collision with --reuse-db)
        other_slug = f"other-tenant-{uuid.uuid4().hex[:8]}"
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=other_slug,
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_template = IngestionTemplate.objects.create(
            tenant=other_tenant,
            name="Other Template",
            template_type="CUSTOM",
            is_system_template=False,
            source_type="S3",
            source_config_template={},
            schedule_type="DAILY",
            schedule_config_template={},
            file_pattern_template=".*",
        )

        tenant_templates = IngestionTemplateManager.get_tenant_templates(str(self.tenant.id))

        assert system_template in tenant_templates
        assert tenant_template in tenant_templates
        assert other_template not in tenant_templates
