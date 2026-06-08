"""Merge conflicting migration leaves."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("audit", "0011_audit_event_tsvector_index_concurrent"),
        ("audit", "0012_enable_rls_audit_merkle_snapshots"),
        ("audit", "0014_auditevent_trace_id"),
        ("audit", "0015_rename_audit_merkle_tenant_pend_idx_audit_merkl_tenant__480222_idx_and_more"),
    ]

    operations = [
    ]
