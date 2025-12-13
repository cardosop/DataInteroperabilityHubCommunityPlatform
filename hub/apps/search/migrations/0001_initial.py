# Generated migration for search index and analytics

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.search
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create SearchIndex table
        migrations.CreateModel(
            name='SearchIndex',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('resource_type', models.CharField(choices=[('CONTRACT', 'Contract'), ('ASSET', 'Asset'), ('DATASET', 'Dataset')], help_text='Type of resource being indexed', max_length=50)),
                ('resource_id', models.UUIDField(help_text='UUID of the resource being indexed')),
                ('title', models.CharField(blank=True, help_text='Title or name of the resource', max_length=255, null=True)),
                ('description', models.TextField(blank=True, help_text='Description of the resource', null=True)),
                ('schema_fields', models.JSONField(blank=True, default=list, help_text='Schema field names and types (for datasets/contracts)', null=True)),
                ('schema_text', models.TextField(blank=True, help_text='Flattened schema text for search', null=True)),
                ('lineage_metadata', models.JSONField(blank=True, default=dict, help_text='Lineage metadata (source contracts, models, fields)', null=True)),
                ('lineage_text', models.TextField(blank=True, help_text='Flattened lineage text for search', null=True)),
                ('tags', models.JSONField(blank=True, default=list, help_text='Tags associated with the resource', null=True)),
                ('tags_text', models.TextField(blank=True, help_text='Flattened tags text for search', null=True)),
                ('domain', models.CharField(blank=True, help_text='Domain of the resource (e.g., sales, finance)', max_length=255, null=True)),
                ('owner_id', models.UUIDField(blank=True, help_text='Owner user ID', null=True)),
                ('owner_email', models.EmailField(blank=True, help_text='Owner email for search', max_length=254, null=True)),
                ('classification', models.CharField(blank=True, help_text='Data classification (PUBLIC, INTERNAL, CONFIDENTIAL, etc.)', max_length=50, null=True)),
                ('quality_status', models.CharField(blank=True, help_text='Quality status (PASS, WARN, FAIL, UNKNOWN)', max_length=20, null=True)),
                ('compliance_status', models.CharField(blank=True, help_text='Compliance status (PASS, WARN, FAIL, UNKNOWN)', max_length=20, null=True)),
                ('search_vector', django.contrib.postgres.search.SearchVectorField(help_text='PostgreSQL tsvector for full-text search', null=True)),
                ('indexed_at', models.DateTimeField(auto_now=True, help_text='When this index was last updated')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this index was created')),
                ('tenant', models.ForeignKey(help_text='Tenant this search index belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='search_indices', to='tenants.tenant')),
            ],
            options={
                'db_table': 'search_index',
                'ordering': ['-indexed_at'],
            },
        ),
        # Create SearchAnalytics table
        migrations.CreateModel(
            name='SearchAnalytics',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('query', models.TextField(help_text='Search query text')),
                ('query_type', models.CharField(choices=[('SEARCH', 'Search Query'), ('SUGGESTION', 'Suggestion Query')], default='SEARCH', help_text='Type of query', max_length=20)),
                ('filters', models.JSONField(blank=True, default=dict, help_text='Filters applied to the search (type, classification, etc.)', null=True)),
                ('result_count', models.IntegerField(default=0, help_text='Number of results returned')),
                ('no_results', models.BooleanField(default=False, help_text='Whether the query returned no results')),
                ('clicked_result_id', models.UUIDField(blank=True, help_text='ID of the result that was clicked (if any)', null=True)),
                ('clicked_result_type', models.CharField(blank=True, help_text='Type of the result that was clicked', max_length=50, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, help_text='When the result was clicked', null=True)),
                ('session_id', models.CharField(blank=True, help_text='Session ID for tracking user sessions', max_length=255, null=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the user', null=True)),
                ('user_agent', models.TextField(blank=True, help_text='User agent string', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When this search was performed')),
                ('tenant', models.ForeignKey(help_text='Tenant this search analytics belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='search_analytics', to='tenants.tenant')),
                ('user', models.ForeignKey(blank=True, help_text='User who performed the search', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='search_queries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'search_analytics',
                'ordering': ['-created_at'],
            },
        ),
        # Add indexes for SearchIndex
        migrations.AddIndex(
            model_name='searchindex',
            index=models.Index(fields=['tenant', 'resource_type', 'resource_id'], name='search_inde_tenant__resource_idx'),
        ),
        migrations.AddIndex(
            model_name='searchindex',
            index=models.Index(fields=['tenant', 'resource_type'], name='search_inde_tenant__resource_type_idx'),
        ),
        migrations.AddIndex(
            model_name='searchindex',
            index=models.Index(fields=['tenant', 'classification'], name='search_inde_tenant__classification_idx'),
        ),
        migrations.AddIndex(
            model_name='searchindex',
            index=models.Index(fields=['tenant', 'owner_id'], name='search_inde_tenant__owner_id_idx'),
        ),
        migrations.AddIndex(
            model_name='searchindex',
            index=models.Index(fields=['tenant', 'domain'], name='search_inde_tenant__domain_idx'),
        ),
        migrations.AddIndex(
            model_name='searchindex',
            index=django.contrib.postgres.indexes.GinIndex(fields=['search_vector'], name='search_inde_search_vector_gin_idx'),
        ),
        # Add unique constraint for SearchIndex
        migrations.AddConstraint(
            model_name='searchindex',
            constraint=models.UniqueConstraint(fields=['tenant', 'resource_type', 'resource_id'], name='unique_search_index'),
        ),
        # Add indexes for SearchAnalytics
        migrations.AddIndex(
            model_name='searchanalytics',
            index=models.Index(fields=['tenant', 'created_at'], name='search_anal_tenant__created_at_idx'),
        ),
        migrations.AddIndex(
            model_name='searchanalytics',
            index=models.Index(fields=['tenant', 'query'], name='search_anal_tenant__query_idx'),
        ),
        migrations.AddIndex(
            model_name='searchanalytics',
            index=models.Index(fields=['tenant', 'no_results'], name='search_anal_tenant__no_results_idx'),
        ),
        migrations.AddIndex(
            model_name='searchanalytics',
            index=models.Index(fields=['tenant', 'user'], name='search_anal_tenant__user_idx'),
        ),
        migrations.AddIndex(
            model_name='searchanalytics',
            index=models.Index(fields=['created_at'], name='search_anal_created_at_idx'),
        ),
    ]

