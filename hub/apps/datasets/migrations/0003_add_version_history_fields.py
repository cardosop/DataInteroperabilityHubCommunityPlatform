# Generated migration for dataset version history

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0002_rename_datasets_tenant_asset_idx_datasets_tenant__5d12ce_idx_and_more'),
    ]

    operations = [
        # Add parent_version foreign key
        migrations.AddField(
            model_name='dataset',
            name='parent_version',
            field=models.ForeignKey(
                blank=True,
                help_text='Parent version in version tree',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='child_versions',
                to='datasets.dataset'
            ),
        ),
        # Add version_hash
        migrations.AddField(
            model_name='dataset',
            name='version_hash',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='SHA-256 hash of schema and file content for version identification',
                max_length=64,
                null=True
            ),
        ),
        # Add snapshot_metadata
        migrations.AddField(
            model_name='dataset',
            name='snapshot_metadata',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Additional metadata for version snapshot',
                null=True
            ),
        ),
        # Add is_current
        migrations.AddField(
            model_name='dataset',
            name='is_current',
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text='Whether this is the current version for the asset'
            ),
        ),
        # Add archived_at
        migrations.AddField(
            model_name='dataset',
            name='archived_at',
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text='Timestamp when version was archived',
                null=True
            ),
        ),
        # Add semantic_version
        migrations.AddField(
            model_name='dataset',
            name='semantic_version',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Semantic version string (e.g., '1.0.0')",
                max_length=20,
                null=True
            ),
        ),
        # Add version_tags
        migrations.AddField(
            model_name='dataset',
            name='version_tags',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Version tags (e.g., ['production', 'staging'])",
                null=True
            ),
        ),
        # Add indexes for version queries
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'asset', 'is_current'], name='datasets_tenant_asset_current_idx'),
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'asset', 'semantic_version'], name='datasets_tenant_asset_semver_idx'),
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'asset', 'parent_version'], name='datasets_tenant_asset_parent_idx'),
        ),
        migrations.AddIndex(
            model_name='dataset',
            index=models.Index(fields=['tenant', 'asset', 'archived_at'], name='datasets_tenant_asset_archived_idx'),
        ),
    ]

