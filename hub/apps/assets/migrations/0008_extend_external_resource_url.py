# Extend ExternalResourceReference.url to support long URLs (e.g. data.gov resources).
# Django URLField defaults to max_length=200; many CKAN resource URLs exceed this.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0007_add_data_strategy_to_asset"),
    ]

    operations = [
        migrations.AlterField(
            model_name="externalresourcereference",
            name="url",
            field=models.URLField(help_text="External resource URL", max_length=2048),
        ),
    ]
