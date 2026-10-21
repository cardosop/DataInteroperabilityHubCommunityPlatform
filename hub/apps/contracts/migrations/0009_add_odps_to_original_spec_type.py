# Generated manually for ODPS integration (Phase 0.0.1.2)
# Date: 2025-01-15
# Adds ODPS support to OriginalSpecType enum, creates JSONB index for x_odps_link,
# and adds optional original_raw_resolved field for $ref resolution caching

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0008_merge_20251210_0237'),
    ]

    operations = [
        # Step 1: Add ODPS to OriginalSpecType enum choices
        migrations.AlterField(
            model_name='contract',
            name='original_spec_type',
            field=models.CharField(
                choices=[
                    ('ODCS', 'ODCS'),
                    ('ODPS', 'ODPS'),
                ],
                help_text='Original spec type: ODCS (Open Data Contract Standard) or ODPS (Open Data Product Standard)',
                max_length=50
            ),
        ),

        # Step 2: Add optional original_raw_resolved field for $ref resolution caching
        # This field stores the resolved contract content after $ref resolution
        # It's optional and nullable, used for caching resolved $ref documents
        migrations.AddField(
            model_name='contract',
            name='original_raw_resolved',
            field=models.TextField(
                blank=True,
                help_text='Original contract content with all $ref references resolved (cached for performance)',
                null=True,
            ),
        ),

        # Step 3: Create JSONB GIN index for extensions.x_odps_link
        # This index enables efficient queries for ODPS-ODCS bidirectional linking
        migrations.RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS idx_contracts_extensions_odps_link
            ON contracts
            USING GIN ((hub_contract_json -> 'extensions' -> 'x_odps_link'));
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS idx_contracts_extensions_odps_link;
            """,
        ),
    ]

