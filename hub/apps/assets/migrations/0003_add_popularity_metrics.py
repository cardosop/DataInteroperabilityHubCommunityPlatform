# Generated migration for Asset popularity metrics

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0002_rename_assets_tenant_key_idx_assets_tenant__76965e_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='health_score',
            field=models.FloatField(blank=True, help_text='Overall health score (0-100) combining DQ, compliance, freshness, usage', null=True),
        ),
        migrations.AddField(
            model_name='asset',
            name='popularity_score',
            field=models.FloatField(blank=True, help_text='Popularity score (0-100) based on views, downloads, usage frequency', null=True),
        ),
        migrations.AddField(
            model_name='asset',
            name='view_count',
            field=models.IntegerField(default=0, help_text='Number of times asset has been viewed'),
        ),
        migrations.AddField(
            model_name='asset',
            name='download_count',
            field=models.IntegerField(default=0, help_text='Number of times asset has been downloaded'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'health_score'], name='assets_tenant_health_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'popularity_score'], name='assets_tenant_popularity_idx'),
        ),
    ]

