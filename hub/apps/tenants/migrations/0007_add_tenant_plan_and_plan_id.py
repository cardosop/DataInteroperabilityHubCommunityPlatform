# Generated manually for Phase 25.1.1 - TenantPlan and Tenant.plan_id

import hub.apps.tenants.models
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_add_odps_refs_config"),
    ]

    operations = [
        migrations.CreateModel(
            name="TenantPlan",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Plan name (e.g., 'Free Plan', 'Pro Plan')",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL-safe plan identifier (e.g., 'free', 'pro', 'enterprise')",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "tier",
                    models.CharField(
                        choices=[("FREE", "Free"), ("PRO", "Pro"), ("ENTERPRISE", "Enterprise")],
                        help_text="Plan tier: FREE, PRO, or ENTERPRISE",
                        max_length=20,
                    ),
                ),
                (
                    "limits_json",
                    models.JSONField(
                        default=hub.apps.tenants.models.default_empty_dict,
                        help_text="Plan limits as JSON (e.g., {'max_assets': 10, 'max_api_calls_per_month': 10000, 'max_scheduled_runs_per_month': 100})",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this plan is currently active and available for subscription",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "tenant_plans",
                "ordering": ["name"],
            },
        ),
        migrations.AddIndex(
            model_name="tenantplan",
            index=models.Index(fields=["slug"], name="tenant_plan_slug_idx"),
        ),
        migrations.AddIndex(
            model_name="tenantplan",
            index=models.Index(fields=["tier"], name="tenant_plan_tier_idx"),
        ),
        migrations.AddIndex(
            model_name="tenantplan",
            index=models.Index(fields=["is_active"], name="tenant_plan_is_active_idx"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="plan",
            field=models.ForeignKey(
                blank=True,
                help_text="Subscription plan for this tenant",
                null=True,
                on_delete=models.SET_NULL,
                related_name="tenants",
                to="tenants.tenantplan",
            ),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(fields=["plan"], name="tenant_plan_idx"),
        ),
    ]
