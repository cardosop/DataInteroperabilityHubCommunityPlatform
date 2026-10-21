# Phase 240.4.B.1 — additive-only:
# AddField data_quality_enabled (BooleanField, default=True) and
# data_quality_advanced_enabled (BooleanField, default=False) on
# Tenant.
#
# - data_quality_enabled is the BASE kill-switch.  Default True so
#   existing tenants keep current behaviour per D240.18 (no surprise
#   disable on rollout).
# - data_quality_advanced_enabled gates the Phase 240.3.B advanced
#   endpoints (anomalies / trends / scorecards / root-cause).  Default
#   False per D240.18 — flip per-tenant after 14d production stability
#   of the basic DQ surface.
#
# Both columns add a default value so the migration is non-blocking on
# large tenants tables (PostgreSQL 11+ rewrites no rows when default
# is a constant).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0032_tenant_dq_thresholds"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="data_quality_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 240.4.B.1 — kill-switch for the entire DQ "
                    "feature. Default True (existing tenants keep "
                    "current behaviour); flip to False to instantly "
                    "disable all DQ API access for incident response "
                    "/ cost containment."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="data_quality_advanced_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 240.4.B.1 — gate for advanced DQ endpoints "
                    "(anomalies / trends / scorecards / "
                    "root-cause-analysis). Default False; flip to True "
                    "per-tenant after the basic DQ feature is stable. "
                    "Conjunctive with data_quality_enabled — the base "
                    "flag must ALSO be True."
                ),
            ),
        ),
    ]
