"""
285.9.1.3a — Add dbt-native execution fields to TransformationPipeline.

- ``warehouse_credential_ref`` — AWS SM ARN for warehouse credentials
- ``git_credential_ref`` — AWS SM ARN for git PAT (dbt repo clone)
- ``source_config`` — JSONField for {git_repo_url, dbt_project_subpath,
  target_name, dbt_timeout_seconds}

All fields are nullable (not every pipeline needs dbt execution).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("transformation", "0006_enable_rls_wrangling_sessions"),
    ]

    operations = [
        migrations.AddField(
            model_name="transformationpipeline",
            name="warehouse_credential_ref",
            field=models.CharField(
                blank=True,
                help_text="AWS Secrets Manager ARN for warehouse credentials (dbt profiles.yml)",
                max_length=2048,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="transformationpipeline",
            name="git_credential_ref",
            field=models.CharField(
                blank=True,
                help_text="AWS Secrets Manager ARN for git Personal Access Token (dbt repo clone)",
                max_length=2048,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="transformationpipeline",
            name="source_config",
            field=models.JSONField(
                blank=True,
                help_text="dbt source configuration: {git_repo_url, dbt_project_subpath, target_name, dbt_timeout_seconds}",
                null=True,
            ),
        ),
    ]
