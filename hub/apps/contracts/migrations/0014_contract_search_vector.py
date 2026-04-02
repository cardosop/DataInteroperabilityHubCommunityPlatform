"""
Migration: add search_vector field + GIN index to contracts.Contract
(Phase 18.2).

search_vector is null=True so existing rows are unaffected until the
background RQ task rebuilds them.
"""
from django.db import migrations
import django.contrib.postgres.indexes
import django.contrib.postgres.search


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0013_remove_hub_contract_json_db_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="search_vector",
            field=django.contrib.postgres.search.SearchVectorField(
                blank=True,
                help_text=(
                    "PostgreSQL tsvector for full-text search "
                    "(auto-maintained via post_save signal)"
                ),
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="contract",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"],
                name="contract_search_vector_gin_idx",
            ),
        ),
    ]
