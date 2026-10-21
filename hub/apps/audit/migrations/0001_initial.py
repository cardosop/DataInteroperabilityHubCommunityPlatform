# Generated migration for audit app

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
            name='AuditEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('resource_type', models.CharField(help_text='Type of resource (e.g., TENANT, USER, CONTRACT, ASSET, AUTH)', max_length=50)),
                ('resource_id', models.UUIDField(blank=True, help_text='ID of the resource (null for resource-less events)', null=True)),
                ('action', models.CharField(help_text='Action performed (e.g., CREATED, UPDATED, DELETED, LOGIN, LOGOUT)', max_length=100)),
                ('result', models.CharField(choices=[('SUCCESS', 'Success'), ('FAILURE', 'Failure'), ('WARNING', 'Warning')], default='SUCCESS', help_text='Result of the action', max_length=20)),
                ('details_json', models.JSONField(default=dict, help_text='Additional details as JSON (no PII allowed)')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When the event occurred (UTC)')),
                ('actor_user', models.ForeignKey(blank=True, help_text='User who performed the action (null for system events)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audited_actions', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(blank=True, help_text='Tenant this event belongs to (null for platform-level events)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_events', to='tenants.tenant')),
            ],
            options={
                'db_table': 'audit_events',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['tenant', 'timestamp'], name='audit_events_tenant_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['actor_user', 'timestamp'], name='audit_events_actor_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['resource_type', 'resource_id'], name='audit_events_resource_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['action', 'timestamp'], name='audit_events_action_timestamp_idx'),
        ),
        migrations.AddIndex(
            model_name='auditevent',
            index=models.Index(fields=['timestamp'], name='audit_events_timestamp_idx'),
        ),
    ]

