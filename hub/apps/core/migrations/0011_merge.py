"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("core", "0002_create_event_outbox"),
        ("core", "0009_fix_form_draft_constraint"),
        ("core", "0010_rename_form_drafts_user_resource_idx_form_drafts_user_id_7147b5_idx_and_more"),
    ]

    operations = [
    ]
