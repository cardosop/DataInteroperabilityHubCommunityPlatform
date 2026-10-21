"""Phase 270.D.1 — Tenant tax billing identity fields.

Adds four columns to ``tenants``:

* ``tax_id`` (CharField max=255) — tenant tax registration number
  (e.g. ``GB123456789``). Empty when unset.
* ``tax_id_type`` (CharField max=32) — Stripe-vocabulary tax type
  (``eu_vat``, ``gb_vat``, ``us_ein``, ``br_cnpj``).
* ``tax_id_verified`` (Boolean, default False) — flips to True
  via the ``customer.tax_id.verified`` webhook.
* ``tax_address`` (JSONField, nullable) — registered address.
  Encrypted at rest via the existing AWS KMS pattern (Phase 211)
  — read via ``Tenant.get_tax_address()`` which decrypts.

All defaults are empty / False so the migration is a no-op for
existing rows.

KMS encryption note
===================
The ``tax_address`` JSONField is encrypted on save via the same
mechanism as ``sso_config`` — ``Tenant.save()`` wraps plaintext
dicts as ``{"_encrypted": <cipher>}``. The migration column type
is JSONField (no DB-level encryption); the application layer
handles the crypto. This matches the existing precedent + means
ops can roll back to a previous code release without losing
data (the ``_encrypted`` sentinel is decode-able by any version
of the encryption helpers).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0064_phase_270_c_5_license_validation"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="tax_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Phase 270.D — tenant tax registration "
                    "number (e.g. ``GB123456789`` for UK VAT, "
                    "``BR12345678000199`` for BR CNPJ). Empty "
                    "when unset. Verification status in "
                    "``tax_id_verified``."
                ),
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="tax_id_type",
            field=models.CharField(
                blank=True,
                default="",
                help_text=(
                    "Phase 270.D — Stripe-vocabulary tax type "
                    "(``eu_vat``, ``gb_vat``, ``us_ein``, "
                    "``br_cnpj``, etc.). Empty when ``tax_id`` "
                    "is unset."
                ),
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="tax_id_verified",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 270.D — True when Stripe's "
                    "``customer.tax_id.verified`` webhook "
                    "confirmed the ID. Flips to False on a new "
                    "submission OR a "
                    "``customer.tax_id.deleted`` event."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="tax_address",
            field=models.JSONField(
                blank=True,
                help_text=(
                    "Phase 270.D — KMS-encrypted (Phase 211 "
                    "pattern) registered tax address: "
                    "``{country, postal_code, line1, line2, "
                    "city, state}``. Read via "
                    "``Tenant.get_tax_address()``; write the "
                    "plaintext dict and ``save()`` encrypts. "
                    "NULL when unset."
                ),
                null=True,
            ),
        ),
    ]
