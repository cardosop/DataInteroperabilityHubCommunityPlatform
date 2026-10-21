# Generated manually for Phase 3: Email Service Integration

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailDelivery',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email_type', models.CharField(choices=[('USER_INVITATION', 'User Invitation'), ('PASSWORD_RESET', 'Password Reset'), ('JOB_COMPLETION', 'Job Completion'), ('JOB_FAILURE', 'Job Failure'), ('API_DEPRECATION', 'API Deprecation')], help_text='Type of email sent', max_length=50)),
                ('to_email', models.EmailField(help_text='Recipient email address', max_length=254)),
                ('subject', models.CharField(help_text='Email subject', max_length=255)),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('SENT', 'Sent'), ('DELIVERED', 'Delivered'), ('BOUNCED', 'Bounced'), ('FAILED', 'Failed'), ('DEFERRED', 'Deferred')], default='PENDING', help_text='Delivery status', max_length=20)),
                ('message_id', models.CharField(blank=True, help_text='Message ID from email service (SendGrid, SES, etc.)', max_length=255, null=True)),
                ('error_message', models.TextField(blank=True, help_text='Error message if delivery failed', null=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retry attempts')),
                ('max_retries', models.IntegerField(default=3, help_text='Maximum number of retry attempts')),
                ('sent_at', models.DateTimeField(blank=True, help_text='When email was sent', null=True)),
                ('delivered_at', models.DateTimeField(blank=True, help_text='When email was delivered (from webhook)', null=True)),
                ('failed_at', models.DateTimeField(blank=True, help_text='When email delivery failed', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='When email delivery record was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='When email delivery record was last updated')),
                ('metadata_json', models.JSONField(blank=True, default=dict, help_text='Additional metadata (template context, etc.)', null=True)),
                ('tenant', models.ForeignKey(blank=True, help_text='Tenant this email is related to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_deliveries', to='tenants.tenant')),
                ('user', models.ForeignKey(blank=True, help_text='User this email is related to', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='email_deliveries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'email_deliveries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['to_email', 'status'], name='email_deli_to_emai_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['email_type', 'status'], name='email_deli_email_t_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['created_at'], name='email_deli_created_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['tenant', 'status'], name='email_deli_tenant__idx'),
        ),
    ]

