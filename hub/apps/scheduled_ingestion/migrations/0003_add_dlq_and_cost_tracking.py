# Generated migration for Dead Letter Queue and Cost Tracking

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid
import decimal


class Migration(migrations.Migration):

    dependencies = [
        ('scheduled_ingestion', '0002_add_ingestion_templates'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeadLetterQueueItem',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('file_path', models.CharField(help_text='File path/key that failed', max_length=500)),
                ('error_message', models.TextField(help_text='Error message from last failure')),
                ('error_code', models.CharField(blank=True, help_text='Error code for categorization', max_length=50, null=True)),
                ('retry_count', models.IntegerField(default=0, help_text='Number of retry attempts')),
                ('first_failed_at', models.DateTimeField(help_text='When file first failed')),
                ('last_failed_at', models.DateTimeField(help_text='When file last failed')),
                ('permanently_failed_at', models.DateTimeField(help_text='When file was marked as permanently failed')),
                ('resolution_status', models.CharField(choices=[('PENDING', 'Pending'), ('RETRYING', 'Retrying'), ('RESOLVED', 'Resolved'), ('IGNORED', 'Ignored')], default='PENDING', help_text='Resolution status', max_length=20)),
                ('resolution_notes', models.TextField(blank=True, help_text='Notes about resolution', null=True)),
                ('resolved_at', models.DateTimeField(blank=True, help_text='When item was resolved', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('resolved_by', models.ForeignKey(blank=True, help_text='User who resolved this item', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='resolved_dlq_items', to=settings.AUTH_USER_MODEL)),
                ('scheduled_ingestion', models.ForeignKey(help_text='Scheduled ingestion this DLQ item belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='dlq_items', to='scheduled_ingestion.scheduledingestion')),
            ],
            options={
                'db_table': 'scheduled_ingestion_dlq',
                'ordering': ['-permanently_failed_at'],
            },
        ),
        migrations.CreateModel(
            name='IngestionCost',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('storage_cost_usd', models.DecimalField(decimal_places=4, default=decimal.Decimal('0.0'), help_text='Storage cost in USD', max_digits=10)),
                ('compute_cost_usd', models.DecimalField(decimal_places=4, default=decimal.Decimal('0.0'), help_text='Compute cost in USD', max_digits=10)),
                ('network_cost_usd', models.DecimalField(decimal_places=4, default=decimal.Decimal('0.0'), help_text='Network/transfer cost in USD', max_digits=10)),
                ('total_cost_usd', models.DecimalField(decimal_places=4, default=decimal.Decimal('0.0'), help_text='Total cost in USD', max_digits=10)),
                ('cost_breakdown_json', models.JSONField(blank=True, default=dict, help_text='Detailed cost breakdown', null=True)),
                ('period_start', models.DateTimeField(help_text='Start of cost period')),
                ('period_end', models.DateTimeField(help_text='End of cost period')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('run', models.ForeignKey(blank=True, help_text='Associated ingestion run (if applicable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='costs', to='scheduled_ingestion.scheduledingestionrun')),
                ('scheduled_ingestion', models.ForeignKey(help_text='Scheduled ingestion this cost belongs to', on_delete=django.db.models.deletion.CASCADE, related_name='costs', to='scheduled_ingestion.scheduledingestion')),
            ],
            options={
                'db_table': 'scheduled_ingestion_costs',
                'ordering': ['-period_start'],
            },
        ),
        migrations.AddIndex(
            model_name='deadletterqueueitem',
            index=models.Index(fields=['scheduled_ingestion', 'resolution_status'], name='scheduled_i_schedul_idx'),
        ),
        migrations.AddIndex(
            model_name='deadletterqueueitem',
            index=models.Index(fields=['scheduled_ingestion', 'permanently_failed_at'], name='scheduled_i_schedul_idx2'),
        ),
        migrations.AddIndex(
            model_name='deadletterqueueitem',
            index=models.Index(fields=['resolution_status', 'permanently_failed_at'], name='scheduled_i_resolut_idx'),
        ),
        migrations.AddIndex(
            model_name='ingestioncost',
            index=models.Index(fields=['scheduled_ingestion', 'period_start'], name='scheduled_i_schedul_idx3'),
        ),
        migrations.AddIndex(
            model_name='ingestioncost',
            index=models.Index(fields=['scheduled_ingestion', 'period_end'], name='scheduled_i_schedul_idx4'),
        ),
        migrations.AddIndex(
            model_name='ingestioncost',
            index=models.Index(fields=['run'], name='scheduled_i_run_id_idx'),
        ),
        migrations.AddConstraint(
            model_name='deadletterqueueitem',
            constraint=models.UniqueConstraint(fields=['scheduled_ingestion', 'file_path'], name='unique_dlq_item_per_file'),
        ),
    ]

