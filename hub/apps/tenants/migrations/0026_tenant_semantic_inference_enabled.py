# Phase 230.7 (REQ-SEM-INFERENCE-001) — additive: per-tenant OWL/RDFS
# reasoning toggle.  Default False — when flipped True, the SPARQL
# query path routes to Fuseki's ``dataset/inferred`` endpoint that
# overlays a reasoner on the same TDB2 store.  No DB-level index —
# the column is read by-PK during query dispatch, not scanned.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0025_tenant_semantic_memento_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="semantic_inference_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 230.7 (REQ-SEM-INFERENCE-001) — when True, "
                    "SPARQL queries see superclass / subproperty / "
                    "inverseOf inferences materialised by the Fuseki "
                    "reasoner. Expect 2-5x query latency vs. the plain "
                    "dataset endpoint."
                ),
            ),
        ),
    ]
