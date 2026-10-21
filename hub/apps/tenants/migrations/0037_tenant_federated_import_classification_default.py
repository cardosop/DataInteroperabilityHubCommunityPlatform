# Phase 250.5.F.1 (closes G2-3) — federated-import default
# classification field.
#
# Adds ``Tenant.federated_import_classification_default`` CharField
# (max 20, default ``"INTERNAL"``). Applied to every imported
# federated-asset metadata blob at intake so the consumer-side
# row is born with a production-safe sensitivity classification
# even when the source tenant hasn't published a classification.
#
# Migration safety:
# * Single ``AddField`` with a constant default — PostgreSQL 11+
#   rewrites zero rows on the schema change.
# * Default ``"INTERNAL"`` (NOT ``"PUBLIC"``) is the safe-default
#   posture — federated metadata may carry PII the source tenant
#   hasn't classified, and PUBLIC default would risk leaking
#   unclassified PII into the public catalogue.
# * No backfill needed: the ``default="INTERNAL"`` populates both
#   new INSERTs and existing rows.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0036_tenant_federated_import_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="federated_import_classification_default",
            field=models.CharField(
                max_length=20,
                default="INTERNAL",
                help_text=(
                    "Phase 250.5.F.1 — default sensitivity "
                    "classification stamped on every imported "
                    "federated-asset metadata blob at intake. "
                    "Values mirror "
                    "``governance.ClassificationCategory`` "
                    "(PUBLIC / INTERNAL / CONFIDENTIAL / "
                    "RESTRICTED / PII / PHI / PCI / FINANCIAL / "
                    "LEGAL). Default INTERNAL — production-safe "
                    "posture for unknown source-tenant "
                    "classification. Tenants flip to PII / "
                    "RESTRICTED for marketplaces carrying "
                    "sensitive payloads."
                ),
            ),
        ),
    ]
