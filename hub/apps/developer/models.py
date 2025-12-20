"""
Developer Experience Models

Models for plugin marketplace and SDK documentation.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class PluginStatus(models.TextChoices):
    """Plugin status enumeration"""
    AVAILABLE = "AVAILABLE", "Available"
    DEPRECATED = "DEPRECATED", "Deprecated"
    BETA = "BETA", "Beta"
    ALPHA = "ALPHA", "Alpha"


class PluginCategory(models.TextChoices):
    """Plugin category enumeration"""
    CONNECTOR = "CONNECTOR", "Connector"
    TRANSFORMER = "TRANSFORMER", "Transformer"
    VALIDATOR = "VALIDATOR", "Validator"
    ANALYZER = "ANALYZER", "Analyzer"
    INTEGRATION = "INTEGRATION", "Integration"
    OTHER = "OTHER", "Other"


class Plugin(models.Model):
    """
    Plugin model representing a plugin in the plugin marketplace.
    
    Plugins extend platform functionality and can be discovered and installed by users.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Plugin name (unique)"
    )
    description = models.TextField(
        help_text="Plugin description"
    )
    version = models.CharField(
        max_length=50,
        help_text="Plugin version (semantic versioning)"
    )
    author = models.CharField(
        max_length=255,
        help_text="Plugin author/organization"
    )
    category = models.CharField(
        max_length=50,
        choices=PluginCategory.choices,
        default=PluginCategory.OTHER,
        help_text="Plugin category"
    )
    status = models.CharField(
        max_length=20,
        choices=PluginStatus.choices,
        default=PluginStatus.AVAILABLE,
        help_text="Plugin status: AVAILABLE, DEPRECATED, BETA, ALPHA"
    )
    download_count = models.IntegerField(
        default=0,
        help_text="Number of times plugin has been downloaded"
    )
    rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Average rating (0-5)"
    )
    metadata_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="Additional plugin metadata (tags, dependencies, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "plugins"
        ordering = ["-download_count", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["category"]),
            models.Index(fields=["name"]),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"


class SDKLanguage(models.TextChoices):
    """SDK language enumeration"""
    PYTHON = "python", "Python"
    JAVASCRIPT = "javascript", "JavaScript"
    TYPESCRIPT = "typescript", "TypeScript"
    R = "r", "R"
    GO = "go", "Go"


class SDKDocumentation(models.Model):
    """
    SDK Documentation model for storing SDK documentation and examples.
    
    Provides SDK documentation, code examples, and API reference for multiple languages.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    language = models.CharField(
        max_length=50,
        choices=SDKLanguage.choices,
        help_text="SDK language"
    )
    version = models.CharField(
        max_length=50,
        help_text="SDK version (semantic versioning)"
    )
    documentation = models.TextField(
        help_text="SDK documentation (markdown format)"
    )
    installation = models.CharField(
        max_length=255,
        help_text="Installation instructions (e.g., 'pip install datahub-sdk')"
    )
    quick_start = models.TextField(
        help_text="Quick start code snippet"
    )
    examples_json = models.JSONField(
        null=True,
        blank=True,
        default=list,
        help_text="Code examples as JSON array"
    )
    api_reference_json = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text="API reference documentation"
    )
    documentation_url = models.URLField(
        null=True,
        blank=True,
        help_text="External documentation URL"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this SDK version is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "sdk_documentation"
        ordering = ["language", "-version"]
        indexes = [
            models.Index(fields=["language", "is_active"]),
            models.Index(fields=["version"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["language", "version"],
                name="unique_sdk_language_version"
            )
        ]
    
    def __str__(self):
        return f"{self.language} SDK v{self.version}"

