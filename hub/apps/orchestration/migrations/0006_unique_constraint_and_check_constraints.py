"""Phase 92.6/92.7 — Replace unique_together with UniqueConstraint; add CheckConstraint for WorkflowInstance status."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orchestration", "0005_phase68_compensation_incomplete_and_attempt"),
    ]

    operations = [
        # 92.6 — WorkflowDefinition: unique_together → UniqueConstraint
        migrations.AlterUniqueTogether(
            name="workflowdefinition",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="workflowdefinition",
            constraint=models.UniqueConstraint(
                fields=["name", "version"],
                name="unique_workflow_def_name_version",
            ),
        ),
        # 92.6 — WorkflowStep: unique_together → UniqueConstraint
        migrations.AlterUniqueTogether(
            name="workflowstep",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="workflowstep",
            constraint=models.UniqueConstraint(
                fields=["workflow_instance", "step_index"],
                name="unique_workflow_step_instance_index",
            ),
        ),
        # 92.7 — WorkflowInstance: CheckConstraint for status field
        migrations.AddConstraint(
            model_name="workflowinstance",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "DRAFT",
                        "RUNNING",
                        "COMPLETED",
                        "FAILED",
                        "CANCELLED",
                        "PAUSED",
                        "ROLLING_BACK",
                        "ROLLED_BACK",
                        "COMPENSATION_INCOMPLETE",
                    ]
                ),
                name="workflow_instance_status_valid",
            ),
        ),
    ]
