# feat1 D2: Single API key model — add BaaS tier and revoked_at to auth APIKey
# Phase 313 — made core-only safe: the baas dependency is REMOVED; the tier
# FK + index are created CONDITIONALLY (only when the paid BaaS app is
# installed). State operations keep full-mode model parity; core-only
# makemigrations drift for this column is the documented known gap.

from django.db import migrations, models
import django.db.models.deletion


def _add_tier_fk_conditionally(apps, schema_editor):
    if "baas" not in apps.all_models:
        return  # core-only: no BaaS table to reference
    model = apps.get_model("hub_auth", "APIKey")
    field = models.ForeignKey(
        "baas.APITierModel",
        blank=True,
        null=True,
        on_delete=django.db.models.deletion.RESTRICT,
        related_name="auth_api_keys",
    )
    field.set_attributes_from_name("tier")
    schema_editor.add_field(model, field)
    schema_editor.add_index(
        model, models.Index(fields=["tier_id"], name="api_keys_tier_id_idx")
    )


def _drop_tier_fk_conditionally(apps, schema_editor):
    if "baas" not in apps.all_models:
        return
    model = apps.get_model("hub_auth", "APIKey")
    try:
        field = model._meta.get_field("tier")
    except Exception:
        return
    schema_editor.remove_field(model, field)


class Migration(migrations.Migration):

    dependencies = [
        ('hub_auth', '0003_apikey_rate_limit_per_hour'),
        # Phase 313 — the baas dependency is REMOVED; the tier FK is created
        # conditionally below (core-only has no BaaS).
    ]

    operations = [
        migrations.AddField(
            model_name='apikey',
            name='revoked_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Revocation timestamp (null if active); used for BaaS revoke',
                null=True
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    _add_tier_fk_conditionally,
                    reverse_code=_drop_tier_fk_conditionally,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='apikey',
                    name='tier',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='BaaS API tier for this key (null for non-BaaS keys)',
                        null=True,
                        on_delete=django.db.models.deletion.RESTRICT,
                        related_name='auth_api_keys',
                        to='baas.apitiermodel'
                    ),
                ),
                migrations.AddIndex(
                    model_name='apikey',
                    index=models.Index(fields=['tier_id'], name='api_keys_tier_id_idx'),
                ),
            ],
        ),
    ]
