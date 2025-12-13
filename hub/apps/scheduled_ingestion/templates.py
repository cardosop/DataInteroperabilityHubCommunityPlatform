"""
Ingestion Templates

Pre-configured templates for common ingestion patterns.
"""
import uuid
from typing import Dict, Any, Optional
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from .models import ScheduledIngestion, SourceType, ScheduleType


class IngestionTemplate(models.Model):
    """
    Template for common ingestion patterns.
    
    Templates provide pre-configured settings for common ingestion scenarios
    like S3 daily files, API polling, database replication, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="ingestion_templates",
        null=True,
        blank=True,
        help_text="Tenant this template belongs to (null for system-wide templates)"
    )
    name = models.CharField(
        max_length=255,
        help_text="Template name"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Template description"
    )
    template_type = models.CharField(
        max_length=50,
        help_text="Template type (e.g., 'S3_DAILY_FILES', 'API_POLLING', 'DATABASE_REPLICATION')"
    )
    is_system_template = models.BooleanField(
        default=False,
        help_text="True if this is a system-wide template (available to all tenants)"
    )
    source_type = models.CharField(
        max_length=50,
        choices=SourceType.choices,
        help_text="Source type for this template"
    )
    source_config_template = models.JSONField(
        help_text="Source configuration template with placeholders (e.g., {bucket_name}, {api_key})"
    )
    schedule_type = models.CharField(
        max_length=20,
        choices=ScheduleType.choices,
        default=ScheduleType.DAILY,
        help_text="Default schedule type"
    )
    schedule_config_template = models.JSONField(
        help_text="Schedule configuration template"
    )
    file_pattern_template = models.CharField(
        max_length=255,
        help_text="File pattern template (e.g., 'data_{date}.csv' where {date} is a placeholder)"
    )
    ingestion_config_template = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Ingestion configuration template (DQ settings, auto-create asset, etc.)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_ingestion_templates",
        null=True,
        blank=True,
        help_text="User who created the template"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "ingestion_templates"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "template_type"]),
            models.Index(fields=["is_system_template", "template_type"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                condition=models.Q(tenant__isnull=False),
                name="unique_template_name_per_tenant"
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(is_system_template=True),
                name="unique_system_template_name"
            ),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"
    
    def clean(self):
        """Validate template"""
        # System templates must not have tenant
        if self.is_system_template and self.tenant:
            raise ValidationError("System templates cannot have a tenant")
        
        # Non-system templates must have tenant
        if not self.is_system_template and not self.tenant:
            raise ValidationError("Non-system templates must have a tenant")


class IngestionTemplateManager:
    """
    Manager for ingestion templates with application logic.
    """
    
    @staticmethod
    def create_from_template(
        template: IngestionTemplate,
        name: str,
        tenant_id: str,
        user_id: str,
        template_variables: Dict[str, Any]
    ) -> ScheduledIngestion:
        """
        Create scheduled ingestion from template.
        
        Args:
            template: IngestionTemplate instance
            name: Name for the scheduled ingestion
            tenant_id: Tenant UUID
            user_id: User UUID
            template_variables: Dictionary of variables to replace in template placeholders
            
        Returns:
            Created ScheduledIngestion instance
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        
        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)
        
        # Resolve template variables in source config
        source_config = IngestionTemplateManager._resolve_template_variables(
            template.source_config_template,
            template_variables
        )
        
        # Resolve template variables in schedule config
        schedule_config = IngestionTemplateManager._resolve_template_variables(
            template.schedule_config_template,
            template_variables
        )
        
        # Resolve template variables in file pattern
        file_pattern = IngestionTemplateManager._resolve_string_template(
            template.file_pattern_template,
            template_variables
        )
        
        # Resolve template variables in ingestion config
        ingestion_config = {}
        if template.ingestion_config_template:
            ingestion_config = IngestionTemplateManager._resolve_template_variables(
                template.ingestion_config_template,
                template_variables
            )
        
        # Create scheduled ingestion
        scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=name,
            description=template.description,
            source_type=template.source_type,
            source_config=source_config,
            schedule_type=template.schedule_type,
            schedule_config=schedule_config,
            file_pattern=file_pattern,
            auto_create_asset=ingestion_config.get("auto_create_asset", False),
            auto_activate=ingestion_config.get("auto_activate", False),
            created_by=user
        )
        
        # Set ingestion state with DQ configuration if provided
        if ingestion_config:
            scheduled_ingestion.ingestion_state = {
                "enable_dq_validation": ingestion_config.get("enable_dq_validation", False),
                "dq_profile_key": ingestion_config.get("dq_profile_key", "intake_basic_gx"),
                "dq_strict_mode": ingestion_config.get("dq_strict_mode", True),
                "min_quality_score": ingestion_config.get("min_quality_score", 0.8)
            }
            scheduled_ingestion.save(update_fields=['ingestion_state'])
        
        return scheduled_ingestion
    
    @staticmethod
    def _resolve_template_variables(
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Resolve template variables in dictionary.
        
        Args:
            template: Template dictionary with placeholders
            variables: Variables to replace placeholders
            
        Returns:
            Resolved dictionary
        """
        import json
        
        # Convert to JSON string, replace variables, then parse back
        template_str = json.dumps(template)
        resolved_str = IngestionTemplateManager._resolve_string_template(
            template_str,
            variables
        )
        return json.loads(resolved_str)
    
    @staticmethod
    def _resolve_string_template(
        template: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Resolve template variables in string.
        
        Args:
            template: Template string with {variable} placeholders
            variables: Variables to replace placeholders
            
        Returns:
            Resolved string
        """
        result = template
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        return result
    
    @staticmethod
    def get_system_templates() -> models.QuerySet:
        """
        Get all system-wide templates.
        
        Returns:
            QuerySet of system templates
        """
        return IngestionTemplate.objects.filter(is_system_template=True)
    
    @staticmethod
    def get_tenant_templates(tenant_id: str) -> models.QuerySet:
        """
        Get templates available to a tenant (system + tenant-specific).
        
        Args:
            tenant_id: Tenant UUID
            
        Returns:
            QuerySet of available templates
        """
        from hub.apps.tenants.models import Tenant
        
        tenant = Tenant.objects.get(id=tenant_id)
        
        # Get system templates and tenant-specific templates
        return IngestionTemplate.objects.filter(
            models.Q(is_system_template=True) | models.Q(tenant=tenant)
        )


def create_system_templates():
    """
    Create default system templates for common ingestion patterns.
    """
    from django.utils import timezone
    
    templates = [
        {
            "name": "S3 Daily Files",
            "description": "Ingest daily files from S3 bucket",
            "template_type": "S3_DAILY_FILES",
            "source_type": SourceType.S3,
            "source_config_template": {
                "bucket_name": "{bucket_name}",
                "prefix": "{prefix}",
                "region": "{region}",
                "access_key_id": "{access_key_id}",
                "secret_access_key": "{secret_access_key}"
            },
            "schedule_type": ScheduleType.DAILY,
            "schedule_config_template": {
                "time": "00:00",
                "timezone": "UTC"
            },
            "file_pattern_template": "{file_pattern}",
            "ingestion_config_template": {
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx",
                "dq_strict_mode": True,
                "min_quality_score": 0.8,
                "auto_create_asset": True,
                "auto_activate": False
            }
        },
        {
            "name": "API Polling",
            "description": "Poll API endpoint for new data",
            "template_type": "API_POLLING",
            "source_type": SourceType.HTTP,
            "source_config_template": {
                "url": "{api_url}",
                "method": "GET",
                "headers": {
                    "Authorization": "Bearer {api_key}"
                },
                "params": {}
            },
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config_template": {
                "cron": "0 */6 * * *",  # Every 6 hours
                "timezone": "UTC"
            },
            "file_pattern_template": "api_response_{timestamp}.json",
            "ingestion_config_template": {
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx",
                "dq_strict_mode": False,
                "min_quality_score": 0.7,
                "auto_create_asset": True,
                "auto_activate": True
            }
        },
        {
            "name": "Database Replication",
            "description": "Replicate data from database",
            "template_type": "DATABASE_REPLICATION",
            "source_type": SourceType.DATABASE,
            "source_config_template": {
                "host": "{db_host}",
                "port": "{db_port}",
                "database": "{db_name}",
                "username": "{db_username}",
                "password": "{db_password}",
                "query": "{sql_query}"
            },
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config_template": {
                "cron": "0 0 * * *",  # Daily at midnight
                "timezone": "UTC"
            },
            "file_pattern_template": "db_export_{date}.csv",
            "ingestion_config_template": {
                "enable_dq_validation": True,
                "dq_profile_key": "intake_basic_gx",
                "dq_strict_mode": True,
                "min_quality_score": 0.9,
                "auto_create_asset": True,
                "auto_activate": False
            }
        }
    ]
    
    for template_data in templates:
        template, created = IngestionTemplate.objects.get_or_create(
            name=template_data["name"],
            is_system_template=True,
            defaults={
                "description": template_data["description"],
                "template_type": template_data["template_type"],
                "source_type": template_data["source_type"],
                "source_config_template": template_data["source_config_template"],
                "schedule_type": template_data["schedule_type"],
                "schedule_config_template": template_data["schedule_config_template"],
                "file_pattern_template": template_data["file_pattern_template"],
                "ingestion_config_template": template_data.get("ingestion_config_template", {})
            }
        )
        
        if created:
            print(f"Created system template: {template.name}")

