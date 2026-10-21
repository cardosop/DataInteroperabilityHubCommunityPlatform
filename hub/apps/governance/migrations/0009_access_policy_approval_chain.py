"""
Phase 272.4 — AccessPolicy.required_approval_chain.

JSONField storing an ordered list of approval steps. Each step
is a dict with ``step`` (int), ``role`` (str), and ``label`` (str).
Default [] means single-step (current behavior).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0008_multi_step_approval"),
    ]

    operations = [
        migrations.AddField(
            model_name="accesspolicy",
            name="required_approval_chain",
            field=models.JSONField(
                default=list,
                blank=True,
                help_text=(
                    "Ordered list of approval steps for multi-step workflows. "
                    "Each step: {step: int, role: str, label: str}. "
                    "Default [] means single-step approval."
                ),
            ),
        ),
    ]
