# feat1 D2: Single API key model — add BaaS tier and revoked_at to auth APIKey
# Phase 313 — paid-ward FK: the baas dependency is REMOVED. `revoked_at`
# remains a plain core field; the tier FK + index are added to the DATABASE
# only when the baas app is installed and the column does not already exist.
# State operations for tier are ABSENT — the link lives on the paid side
# (baas.APIKeyTierAssignment) in every mode.

from django.db import migrations, models
import django.db.models.deletion


def _column_exists(schema_editor, table, column):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = %s",
            [table, column],
        )
        return cursor.fetchone() is not None


def _add_tier_fk_if_needed(apps, schema_editor):
    if "baas" not in apps.all_models:
        return  # core-only: no BaaS table to reference
    if _column_exists(schema_editor, "api_keys", "tier_id"):
        return  # pre-existing full install already has the column
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


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hub_auth', '0003_apikey_rate_limit_per_hour'),
        # Phase 313 — the baas dependency is REMOVED (see docstring).
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
        migrations.RunPython(
            _add_tier_fk_if_needed,
            reverse_code=_noop,
        ),
    ]
