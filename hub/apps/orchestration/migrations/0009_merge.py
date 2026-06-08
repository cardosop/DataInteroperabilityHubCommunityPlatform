"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("orchestration", "0001_remove_transformation_workflow_references"),
        ("orchestration", "0002_add_workflow_instance_to_pipeline_execution"),
        ("orchestration", "0006_unique_constraint_and_check_constraints"),
        ("orchestration", "0008_enable_rls_pipeline_dependencies"),
    ]

    operations = [
    ]
