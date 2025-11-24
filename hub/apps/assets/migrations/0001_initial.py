# Generated migration for assets app

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Asset',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('key', models.CharField(help_text='Human-friendly identifier, unique per tenant', max_length=255)),
                ('name', models.CharField(help_text='Asset name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Asset description', null=True)),
                ('domain', models.CharField(blank=True, help_text='Domain (e.g., marketing, finance)', max_length=100, null=True)),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('ACTIVE', 'Active'), ('PUBLIC', 'Public'), ('RETIRED', 'Retired')], default='DRAFT', help_text='Asset lifecycle status: DRAFT, ACTIVE, PUBLIC, RETIRED', max_length=20)),
                ('visibility', models.CharField(choices=[('INTERNAL', 'Internal'), ('PUBLIC', 'Public')], default='INTERNAL', help_text='Asset visibility: INTERNAL, PUBLIC', max_length=20)),
                ('dq_status', models.CharField(choices=[('UNKNOWN', 'Unknown'), ('PASS', 'Pass'), ('WARN', 'Warning'), ('FAIL', 'Fail')], default='UNKNOWN', help_text='Data Quality status: UNKNOWN, PASS, WARN, FAIL', max_length=20)),
                ('compliance_status', models.CharField(choices=[('UNKNOWN', 'Unknown'), ('PASS', 'Pass'), ('WARN', 'Warning'), ('FAIL', 'Fail')], default='UNKNOWN', help_text='Compliance status: UNKNOWN, PASS, WARN, FAIL', max_length=20)),
                ('version', models.IntegerField(default=1, help_text='Optimistic locking version counter')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, help_text='User who created the asset', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_assets', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(help_text='Tenant this asset belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='assets', to='tenants.tenant')),
            ],
            options={
                'db_table': 'assets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'key'], name='assets_tenant_key_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'visibility'], name='assets_tenant_visibility_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'dq_status'], name='assets_tenant_dq_status_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'compliance_status'], name='assets_tenant_compliance_idx'),
        ),
        migrations.AddIndex(
            model_name='asset',
            index=models.Index(fields=['tenant', 'status'], name='assets_tenant_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='asset',
            constraint=models.UniqueConstraint(fields=['tenant', 'key'], name='unique_asset_key_per_tenant'),
        ),
    ]
