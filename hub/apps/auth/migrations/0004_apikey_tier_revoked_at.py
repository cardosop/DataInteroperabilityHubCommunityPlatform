# feat1 D2: Single API key model — add BaaS tier and revoked_at to auth APIKey

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hub_auth', '0003_apikey_rate_limit_per_hour'),
        ('baas', '0001_initial'),
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
    ]
