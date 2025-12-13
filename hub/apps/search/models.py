"""
Search Models

Models for full-text search index and search analytics.
"""
import uuid
from django.db import models
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.conf import settings
from django.utils import timezone


class SearchIndex(models.Model):
    """
    Full-text search index for contracts, assets, datasets, and related metadata.
    
    Uses PostgreSQL tsvector for efficient full-text search with GIN indexes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="search_indices",
        help_text="Tenant this search index belongs to"
    )
    # Polymorphic resource reference
    resource_type = models.CharField(
        max_length=50,
        choices=[
            ("CONTRACT", "Contract"),
            ("ASSET", "Asset"),
            ("DATASET", "Dataset"),
        ],
        help_text="Type of resource being indexed"
    )
    resource_id = models.UUIDField(
        help_text="UUID of the resource being indexed"
    )
    # Searchable content
    title = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Title or name of the resource"
    )
    description = models.TextField(
        null=True,
        blank=True,
        help_text="Description of the resource"
    )
    schema_fields = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Schema field names and types (for datasets/contracts)"
    )
    schema_text = models.TextField(
        null=True,
        blank=True,
        help_text="Flattened schema text for search"
    )
    lineage_metadata = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Lineage metadata (source contracts, models, fields)"
    )
    lineage_text = models.TextField(
        null=True,
        blank=True,
        help_text="Flattened lineage text for search"
    )
    tags = models.JSONField(
        default=list,
        null=True,
        blank=True,
        help_text="Tags associated with the resource"
    )
    tags_text = models.TextField(
        null=True,
        blank=True,
        help_text="Flattened tags text for search"
    )
    domain = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Domain of the resource (e.g., sales, finance)"
    )
    owner_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Owner user ID"
    )
    owner_email = models.EmailField(
        null=True,
        blank=True,
        help_text="Owner email for search"
    )
    classification = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Data classification (PUBLIC, INTERNAL, CONFIDENTIAL, etc.)"
    )
    quality_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Quality status (PASS, WARN, FAIL, UNKNOWN)"
    )
    compliance_status = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Compliance status (PASS, WARN, FAIL, UNKNOWN)"
    )
    # Full-text search vector (PostgreSQL tsvector)
    search_vector = SearchVectorField(
        null=True,
        help_text="PostgreSQL tsvector for full-text search"
    )
    # Metadata
    indexed_at = models.DateTimeField(
        auto_now=True,
        help_text="When this index was last updated"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this index was created"
    )
    
    class Meta:
        db_table = "search_index"
        ordering = ["-indexed_at"]
        indexes = [
            models.Index(fields=["tenant", "resource_type", "resource_id"]),
            models.Index(fields=["tenant", "resource_type"]),
            models.Index(fields=["tenant", "classification"]),
            models.Index(fields=["tenant", "owner_id"]),
            models.Index(fields=["tenant", "domain"]),
            GinIndex(fields=["search_vector"]),  # GIN index for fast full-text search
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "resource_type", "resource_id"],
                name="unique_search_index"
            ),
        ]
    
    def __str__(self):
        return f"{self.resource_type} {self.resource_id} - {self.title}"


class SearchAnalytics(models.Model):
    """
    Search analytics for tracking search queries, clicks, and no-result queries.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="search_analytics",
        help_text="Tenant this search analytics belongs to"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="search_queries",
        null=True,
        blank=True,
        help_text="User who performed the search"
    )
    query = models.TextField(
        help_text="Search query text"
    )
    query_type = models.CharField(
        max_length=20,
        choices=[
            ("SEARCH", "Search Query"),
            ("SUGGESTION", "Suggestion Query"),
        ],
        default="SEARCH",
        help_text="Type of query"
    )
    # Filters applied
    filters = models.JSONField(
        default=dict,
        null=True,
        blank=True,
        help_text="Filters applied to the search (type, classification, etc.)"
    )
    # Results
    result_count = models.IntegerField(
        default=0,
        help_text="Number of results returned"
    )
    no_results = models.BooleanField(
        default=False,
        help_text="Whether the query returned no results"
    )
    # Click tracking
    clicked_result_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="ID of the result that was clicked (if any)"
    )
    clicked_result_type = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="Type of the result that was clicked"
    )
    clicked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the result was clicked"
    )
    # Metadata
    session_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Session ID for tracking user sessions"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user"
    )
    user_agent = models.TextField(
        null=True,
        blank=True,
        help_text="User agent string"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this search was performed"
    )
    
    class Meta:
        db_table = "search_analytics"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["tenant", "query"]),
            models.Index(fields=["tenant", "no_results"]),
            models.Index(fields=["tenant", "user"]),
            models.Index(fields=["created_at"]),
        ]
    
    def __str__(self):
        return f"Search: {self.query[:50]}... ({self.result_count} results)"

