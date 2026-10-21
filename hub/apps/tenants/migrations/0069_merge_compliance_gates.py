"""
Merge migration — reconciles the two parallel 0068_* leaves that branched
off 0067_phase_272_compliance_gate:

* 0068_ensure_compliance_gate_column (Phase 272.2 safety re-add of the
  access_request_compliance_gate_enabled column)
* 0068_phase_274_marketplace_compliance_gate (Phase 274.1 addition of
  marketplace_publish_compliance_gate_enabled)

Both are independent — the safety re-add idempotently touches the
column added in 0067, the Phase 274 migration adds a new column. They
do not conflict at the SQL level, but Django still requires a single
leaf in the migration graph before further migrations can be planned.

This merge node carries no operations of its own; it exists purely to
collapse the two leaves so subsequent tenants migrations depend on a
single linear predecessor.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0068_ensure_compliance_gate_column"),
        ("tenants", "0068_phase_274_marketplace_compliance_gate"),
    ]

    operations = []
