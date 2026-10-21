"""
Add indexes for search query optimization.

This migration creates indexes to optimize search queries including:
- Full-text search on search_vector (already exists via GinIndex, but ensure it's optimized)
- Filter queries (classification, owner, domain, quality_status, compliance_status)
- Analytics queries (query text, no_results, created_at)
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('search', '0001_initial'),
    ]

    operations = [
        # Composite index for search filtering (tenant + resource_type + classification)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_index_tenant_type_classification_idx
            ON search_index
            (tenant_id, resource_type, classification)
            WHERE classification IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_index_tenant_type_classification_idx;
            """,
        ),
        # Composite index for owner filtering (tenant + owner_id)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_index_tenant_owner_idx
            ON search_index
            (tenant_id, owner_id)
            WHERE owner_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_index_tenant_owner_idx;
            """,
        ),
        # Composite index for domain filtering (tenant + domain)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_index_tenant_domain_idx
            ON search_index
            (tenant_id, domain)
            WHERE domain IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_index_tenant_domain_idx;
            """,
        ),
        # Composite index for quality/compliance status filtering
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_index_tenant_quality_compliance_idx
            ON search_index
            (tenant_id, quality_status, compliance_status)
            WHERE quality_status IS NOT NULL OR compliance_status IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_index_tenant_quality_compliance_idx;
            """,
        ),
        # Index for search analytics query text (for query analysis)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_analytics_query_text_idx
            ON search_analytics
            USING gin(to_tsvector('english', query))
            WHERE query IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_analytics_query_text_idx;
            """,
        ),
        # Composite index for analytics no-results tracking
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_analytics_tenant_no_results_idx
            ON search_analytics
            (tenant_id, no_results, created_at)
            WHERE no_results = true;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_analytics_tenant_no_results_idx;
            """,
        ),
        # Composite index for analytics click tracking
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS search_analytics_tenant_clicked_idx
            ON search_analytics
            (tenant_id, clicked_result_id, clicked_at)
            WHERE clicked_result_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS search_analytics_tenant_clicked_idx;
            """,
        ),
    ]

