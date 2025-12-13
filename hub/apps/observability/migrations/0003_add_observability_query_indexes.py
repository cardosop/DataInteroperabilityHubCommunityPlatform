"""
Add indexes for observability metrics queries.

This migration creates indexes to optimize observability queries including:
- Freshness monitoring queries (is_stale, freshness_sla)
- Volume trend queries (period_type, period_start)
- Schema drift queries (drift_severity, is_within_tolerance)
- Pipeline execution queries (pipeline_type, status, created_at)
- SLA compliance queries (sla_type, is_violated)
- Incident queries (incident_type, status, severity)
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('observability', '0002_add_pipeline_sla_incident_models'),
    ]

    operations = [
        # Composite index for freshness monitoring (tenant + is_stale + recorded_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS observability_metrics_tenant_stale_recorded_idx
            ON data_observability_metrics
            (tenant_id, is_stale, recorded_at)
            WHERE is_stale = true;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS observability_metrics_tenant_stale_recorded_idx;
            """,
        ),
        # Composite index for freshness SLA queries (tenant + freshness_sla + recorded_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS observability_metrics_tenant_sla_recorded_idx
            ON data_observability_metrics
            (tenant_id, freshness_sla, recorded_at)
            WHERE freshness_sla IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS observability_metrics_tenant_sla_recorded_idx;
            """,
        ),
        # Composite index for volume trend queries (tenant + period_type + period_start)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS volume_trends_tenant_period_idx
            ON volume_trends
            (tenant_id, period_type, period_start);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS volume_trends_tenant_period_idx;
            """,
        ),
        # Composite index for volume anomaly queries (tenant + is_anomaly + period_start)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS volume_trends_tenant_anomaly_idx
            ON volume_trends
            (tenant_id, is_anomaly, period_start)
            WHERE is_anomaly = true;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS volume_trends_tenant_anomaly_idx;
            """,
        ),
        # Composite index for schema drift queries (tenant + drift_severity + detected_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS schema_drifts_tenant_severity_detected_idx
            ON schema_drifts
            (tenant_id, drift_severity, detected_at);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS schema_drifts_tenant_severity_detected_idx;
            """,
        ),
        # Composite index for schema drift tolerance queries (tenant + is_within_tolerance + detected_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS schema_drifts_tenant_tolerance_detected_idx
            ON schema_drifts
            (tenant_id, is_within_tolerance, detected_at)
            WHERE is_within_tolerance = false;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS schema_drifts_tenant_tolerance_detected_idx;
            """,
        ),
        # Composite index for pipeline execution queries (tenant + pipeline_type + status + created_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS pipeline_executions_tenant_type_status_created_idx
            ON pipeline_executions
            (tenant_id, pipeline_type, status, created_at);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS pipeline_executions_tenant_type_status_created_idx;
            """,
        ),
        # Composite index for pipeline execution by resource (resource_type + resource_id + created_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS pipeline_executions_resource_created_idx
            ON pipeline_executions
            (resource_type, resource_id, created_at)
            WHERE resource_type IS NOT NULL AND resource_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS pipeline_executions_resource_created_idx;
            """,
        ),
        # Composite index for SLA compliance queries (tenant + sla_type + is_violated + is_active)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS data_slas_tenant_type_violated_active_idx
            ON data_slas
            (tenant_id, sla_type, is_violated, is_active)
            WHERE is_active = true;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS data_slas_tenant_type_violated_active_idx;
            """,
        ),
        # Composite index for incident queries (tenant + incident_type + status + severity)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS data_incidents_tenant_type_status_severity_idx
            ON data_incidents
            (tenant_id, incident_type, status, severity);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS data_incidents_tenant_type_status_severity_idx;
            """,
        ),
        # Composite index for incident assignment queries (tenant + assigned_to + status)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS data_incidents_tenant_assigned_status_idx
            ON data_incidents
            (tenant_id, assigned_to_id, status)
            WHERE assigned_to_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS data_incidents_tenant_assigned_status_idx;
            """,
        ),
        # Composite index for incident resource queries (resource_type + resource_id + detected_at)
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS data_incidents_resource_detected_idx
            ON data_incidents
            (resource_type, resource_id, detected_at)
            WHERE resource_type IS NOT NULL AND resource_id IS NOT NULL;
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS data_incidents_resource_detected_idx;
            """,
        ),
    ]

