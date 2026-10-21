"""
Migration: add search_vector field + GIN index to assets.Asset (Phase 18.2).

search_vector is null=True so existing rows are unaffected until the
background RQ task rebuilds them.  The GIN index is CONCURRENTLY-safe
via Django's AddIndex operation.
"""
from django.db import migrations
import django.contrib.postgres.indexes
import django.contrib.postgres.search


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0008_extend_external_resource_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="search_vector",
            field=django.contrib.postgres.search.SearchVectorField(
                blank=True,
                help_text=(
                    "PostgreSQL tsvector for full-text search "
                    "(auto-maintained)"
                ),
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="asset",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"],
                name="asset_search_vector_gin_idx",
            ),
        ),
    ]
